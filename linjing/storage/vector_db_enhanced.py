#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
增强版向量数据库管理器，基于Qdrant实现高性能向量存储和检索。

提供以下增强功能：
1. 连接池模式，高效管理Qdrant客户端连接
2. 支持服务器模式和本地模式
3. 重试机制，处理临时连接故障
4. 自动资源清理，防止内存泄漏
5. 健康检查和诊断功能
6. 更优雅的错误处理和日志记录
"""

import asyncio
import functools
import logging
import os
import re  # 添加re模块用于正则表达式匹配
import time
import uuid
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable, TypeVar, cast

# Qdrant相关导入
from qdrant_client import QdrantClient
from qdrant_client.http import models as rest
from qdrant_client.http.exceptions import UnexpectedResponse, ResponseHandlingException
from qdrant_client.http.models import PointStruct, Distance, VectorParams
from qdrant_client.http.models import UpdateStatus

logger = logging.getLogger(__name__)

# 类型变量
T = TypeVar('T')

# 全局连接池
_connection_pool: Dict[str, QdrantClient] = {}
_pool_lock = asyncio.Lock()
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="qdrant_worker")


@dataclass
class ConnectionConfig:
    """向量数据库连接配置"""
    collection_name: str
    vector_size: int
    similarity: str = "cosine"  # 可选: "cosine", "euclid", "dot"
    
    # 连接详情
    local: bool = True         # 是否使用本地模式
    host: Optional[str] = None
    port: Optional[int] = None
    grpc_port: Optional[int] = None
    api_key: Optional[str] = None
    https: bool = False
    prefix: Optional[str] = None
    timeout: float = 10.0
    
    # 本地存储配置
    local_path: Optional[str] = None
    
    # 重试配置
    max_retries: int = 3
    retry_delay: float = 1.0
    
    # 扩展配置
    batch_size: int = 100      # 批量操作大小
    cache_size: int = 1000     # 客户端缓存大小
    
    # 内部字段
    _similarity_map: Dict[str, Distance] = field(default_factory=lambda: {
        "cosine": Distance.COSINE,
        "euclid": Distance.EUCLID,
        "dot": Distance.DOT,
    })
    
    def get_client_key(self) -> str:
        """生成客户端唯一键"""
        if self.local:
            return f"local:{self.local_path or 'default'}"
        else:
            return f"remote:{self.host}:{self.port}"
    
    def get_similarity(self) -> Distance:
        """获取相似度度量方式"""
        return self._similarity_map.get(self.similarity.lower(), Distance.COSINE)


def with_retry(func):
    """带重试机制的装饰器，用于自动重试可能因连接问题失败的函数"""
    @functools.wraps(func)
    async def wrapper(self: 'VectorDBManagerEnhanced', *args, **kwargs):
        config = self.config
        max_retries = config.max_retries
        retry_delay = config.retry_delay
        
        last_error = None
        for attempt in range(max_retries + 1):
            try:
                # 非异步方法的处理
                if not asyncio.iscoroutinefunction(func):
                    loop = asyncio.get_event_loop()
                    return await loop.run_in_executor(
                        _executor, 
                        functools.partial(func, self, *args, **kwargs)
                    )
                # 异步方法直接调用
                return await func(self, *args, **kwargs)
            
            except (ConnectionError, TimeoutError, UnexpectedResponse, ResponseHandlingException) as e:
                last_error = e
                if attempt < max_retries:
                    wait_time = retry_delay * (2 ** attempt)  # 指数退避
                    logger.warning(
                        f"操作失败 ({func.__name__}), 尝试 {attempt+1}/{max_retries}, "
                        f"将在 {wait_time:.2f}s 后重试: {str(e)}"
                    )
                    await asyncio.sleep(wait_time)
                    # 如果客户端可能有问题，尝试重新连接
                    if isinstance(e, (ConnectionError, TimeoutError)):
                        try:
                            await self.reconnect()
                        except Exception as conn_err:
                            logger.error(f"重新连接失败: {conn_err}")
            except Exception as e:
                # 非连接错误直接抛出
                logger.error(f"向量数据库操作错误 ({func.__name__}): {e}", exc_info=True)
                raise
        
        # 所有重试都失败
        logger.error(f"达到最大重试次数 ({max_retries})，操作失败: {last_error}")
        raise last_error
    
    return wrapper


class VectorDBManagerEnhanced:
    """
    增强版向量数据库管理器
    
    基于Qdrant的高性能向量数据库接口，支持连接池、重试机制和服务器/本地模式。
    """
    
    def __init__(self, config_dict: Dict[str, Any]):
        """
        初始化向量数据库管理器
        
        Args:
            config_dict: 配置字典，包含连接和存储参数
        """
        # 复制配置字典，避免修改原始配置
        config_dict = dict(config_dict)
        
        # 移除不支持的参数
        if 'type' in config_dict:
            config_dict.pop('type')
        if 'db_type' in config_dict:
            config_dict.pop('db_type')
        
        # 兼容性处理：path -> local_path
        if 'path' in config_dict:
            config_dict['local_path'] = config_dict.pop('path')
            
        # 兼容性处理：dimension -> vector_size
        if 'dimension' in config_dict:
            config_dict['vector_size'] = config_dict.pop('dimension')
            
        # 设置默认本地路径
        if config_dict.get("local", True) and not config_dict.get("local_path"):
            data_dir = os.environ.get("LINJING_DATA_DIR", os.path.expanduser("~/.linjing/data"))
            config_dict["local_path"] = os.path.join(data_dir, "qdrant_db")
        
        # 创建配置对象
        self.config = ConnectionConfig(**config_dict)
        
        # 初始化状态
        self.client: Optional[QdrantClient] = None
        self.connected = False
        self.collection_exists = False
        
        # 规范化路径
        if self.config.local and self.config.local_path:
            self.config.local_path = os.path.abspath(os.path.expanduser(self.config.local_path))
            # 确保目录存在
            Path(self.config.local_path).mkdir(parents=True, exist_ok=True)
        
        logger.debug(f"初始化向量数据库管理器: {self.config.collection_name}, "
                    f"模式: {'本地' if self.config.local else '服务器'}")
    
    async def connect(self) -> bool:
        """
        连接到向量数据库
        
        Returns:
            是否成功连接
        """
        if self.connected and self.client:
            return True
        
        async with _pool_lock:
            client_key = self.config.get_client_key()
            
            # 检查池中是否已有连接
            if client_key in _connection_pool:
                self.client = _connection_pool[client_key]
                logger.debug(f"从连接池获取客户端: {client_key}")
            else:
                # 创建新连接
                try:
                    params = {}
                    
                    if self.config.local:
                        # 修复Windows路径处理
                        local_path = self.config.local_path
                        
                        # Windows路径特殊处理
                        if os.name == 'nt':
                            # 确保路径格式正确
                            local_path = os.path.normpath(local_path)
                            
                            # 移除可能的file:///前缀
                            if local_path.startswith('file:///'):
                                local_path = local_path[8:]
                                
                            # 直接使用绝对路径，避免URI识别问题
                            if re.match(r'^[a-zA-Z]:', local_path):
                                # 确保使用原始路径格式，不转换为URI
                                local_path = os.path.abspath(local_path)
                            
                            logger.debug(f"Windows路径处理: 原始路径={self.config.local_path} => 处理后={local_path}")
                        
                        # 确保目录存在
                        os.makedirs(local_path, exist_ok=True)
                        
                        # 使用path参数而不是location参数
                        params["path"] = local_path
                        
                        # 关键参数：禁止Qdrant自动将路径转换为URI
                        params["path_to_uri"] = False
                        
                        logger.info(f"连接本地向量数据库: {local_path}")
                    else:
                        # 服务器模式参数
                        params["url"] = f"{'https' if self.config.https else 'http'}://{self.config.host}:{self.config.port}"
                        if self.config.grpc_port:
                            params["grpc_port"] = self.config.grpc_port
                        if self.config.api_key:
                            params["api_key"] = self.config.api_key
                        if self.config.prefix:
                            params["prefix"] = self.config.prefix
                        
                        logger.info(f"连接服务器向量数据库: {params['url']}")
                    
                    # 设置通用参数
                    params["timeout"] = self.config.timeout
                    
                    # 创建客户端前记录详细参数(不含敏感信息)
                    safe_params = dict(params)
                    if "api_key" in safe_params:
                        safe_params["api_key"] = "***"
                    logger.debug(f"创建Qdrant客户端参数: {safe_params}")
                    
                    # 创建客户端
                    loop = asyncio.get_event_loop()
                    client = await loop.run_in_executor(
                        _executor, 
                        lambda: QdrantClient(**params)
                    )
                    
                    # 添加到连接池
                    _connection_pool[client_key] = client
                    self.client = client
                    
                except Exception as e:
                    logger.error(f"连接向量数据库失败: {e}", exc_info=True)
                    self.connected = False
                    return False
        
        # 初始化集合
        try:
            success = await self._initialize_collection()
            self.connected = success
            return success
        except Exception as e:
            logger.error(f"初始化集合失败: {e}", exc_info=True)
            self.connected = False
            return False
    
    async def reconnect(self) -> bool:
        """
        重新连接到向量数据库
        
        Returns:
            是否成功重连
        """
        logger.info(f"尝试重新连接向量数据库: {self.config.collection_name}")
        # 移除旧连接
        if self.client:
            async with _pool_lock:
                client_key = self.config.get_client_key()
                if client_key in _connection_pool:
                    del _connection_pool[client_key]
            self.client = None
        
        self.connected = False
        self.collection_exists = False
        
        # 重新连接
        return await self.connect()
    
    async def disconnect(self) -> bool:
        """
        断开与向量数据库的连接
        
        Returns:
            是否成功断开
        """
        if not self.connected or not self.client:
            return True
        
        try:
            # 注意：不从连接池中移除客户端，只标记本实例为断开
            self.connected = False
            return True
        except Exception as e:
            logger.error(f"断开向量数据库连接失败: {e}")
            return False
    
    async def _initialize_collection(self) -> bool:
        """
        初始化集合，如果不存在则创建
        
        Returns:
            是否成功初始化
        """
        if not self.client:
            return False
        
        try:
            loop = asyncio.get_event_loop()
            # 检查集合是否存在
            collections = await loop.run_in_executor(
                _executor,
                self.client.get_collections
            )
            
            exists = any(c.name == self.config.collection_name for c in collections.collections)
            
            if not exists:
                logger.info(f"创建集合: {self.config.collection_name}")
                # 创建新集合
                await loop.run_in_executor(
                    _executor,
                    lambda: self.client.create_collection(
                        collection_name=self.config.collection_name,
                        vectors_config=VectorParams(
                            size=self.config.vector_size,
                            distance=self.config.get_similarity()
                        )
                    )
                )
            
            self.collection_exists = True
            return True
        except Exception as e:
            logger.error(f"初始化集合失败: {e}", exc_info=True)
            self.collection_exists = False
            return False
    
    @with_retry
    async def add_vector(self, 
                     vector_id: str, 
                     vector: List[float], 
                     metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        添加向量到数据库
        
        Args:
            vector_id: 向量ID
            vector: 向量数据
            metadata: 关联元数据
            
        Returns:
            是否成功添加
        """
        if not self.connected or not self.client:
            if not await self.connect():
                return False
        
        try:
            point = PointStruct(
                id=vector_id,
                vector=vector,
                payload=metadata or {}
            )
            
            result = self.client.upsert(
                collection_name=self.config.collection_name,
                points=[point]
            )
            
            return result.status == UpdateStatus.COMPLETED
        except Exception as e:
            logger.error(f"添加向量失败 (ID: {vector_id}): {e}")
            raise
    
    @with_retry
    async def add_vectors_batch(self, 
                           items: List[Dict[str, Any]]) -> bool:
        """
        批量添加向量到数据库
        
        Args:
            items: 包含向量信息的字典列表，每个字典必须包含 "id", "vector" 键，
                  可选包含 "metadata" 键
                  
        Returns:
            是否成功添加全部向量
        """
        if not self.connected or not self.client:
            if not await self.connect():
                return False
        
        try:
            points = [
                PointStruct(
                    id=item["id"],
                    vector=item["vector"],
                    payload=item.get("metadata", {})
                )
                for item in items
            ]
            
            # 分批处理
            batch_size = self.config.batch_size
            results = []
            
            for i in range(0, len(points), batch_size):
                batch = points[i:i + batch_size]
                result = self.client.upsert(
                    collection_name=self.config.collection_name,
                    points=batch
                )
                results.append(result.status == UpdateStatus.COMPLETED)
            
            return all(results)
        except Exception as e:
            logger.error(f"批量添加向量失败: {e}")
            raise
    
    @with_retry
    async def get_vector(self, 
                     vector_id: str) -> Optional[Dict[str, Any]]:
        """
        获取指定ID的向量
        
        Args:
            vector_id: 向量ID
            
        Returns:
            包含向量和元数据的字典，如未找到则返回None
        """
        if not self.connected or not self.client:
            if not await self.connect():
                return None
        
        try:
            points = self.client.retrieve(
                collection_name=self.config.collection_name,
                ids=[vector_id],
                with_vectors=True,
                with_payload=True
            )
            
            if not points:
                return None
            
            point = points[0]
            return {
                "id": point.id,
                "vector": point.vector,
                "metadata": point.payload
            }
        except Exception as e:
            logger.error(f"获取向量失败 (ID: {vector_id}): {e}")
            raise
    
    @with_retry
    async def update_vector(self, 
                        vector_id: str, 
                        vector: Optional[List[float]] = None, 
                        metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        更新指定ID的向量
        
        Args:
            vector_id: 向量ID
            vector: 新的向量数据(可选)
            metadata: 新的元数据(可选)
            
        Returns:
            是否成功更新
        """
        if not self.connected or not self.client:
            if not await self.connect():
                return False
        
        try:
            # 构建更新对象
            if vector is not None:
                # 更新向量
                vector_result = self.client.update_vectors(
                    collection_name=self.config.collection_name,
                    points=[(vector_id, vector)]
                )
                vector_success = vector_result.status == UpdateStatus.COMPLETED
            else:
                vector_success = True
            
            if metadata is not None:
                # 更新元数据
                payload_result = self.client.set_payload(
                    collection_name=self.config.collection_name,
                    payload=metadata,
                    points=[vector_id]
                )
                payload_success = payload_result.status == UpdateStatus.COMPLETED
            else:
                payload_success = True
            
            return vector_success and payload_success
        except Exception as e:
            logger.error(f"更新向量失败 (ID: {vector_id}): {e}")
            raise
    
    @with_retry
    async def delete_vector(self, vector_id: str) -> bool:
        """
        删除指定ID的向量
        
        Args:
            vector_id: 向量ID
            
        Returns:
            是否成功删除
        """
        if not self.connected or not self.client:
            if not await self.connect():
                return False
        
        try:
            result = self.client.delete(
                collection_name=self.config.collection_name,
                points_selector=[vector_id]
            )
            return result.status == UpdateStatus.COMPLETED
        except Exception as e:
            logger.error(f"删除向量失败 (ID: {vector_id}): {e}")
            raise
    
    @with_retry
    async def search_similar(self, 
                         query_vector: List[float], 
                         limit: int = 10, 
                         score_threshold: Optional[float] = None,
                         filter_condition: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        搜索相似向量
        
        Args:
            query_vector: 查询向量
            limit: 返回结果数量上限
            score_threshold: 相似度分数阈值
            filter_condition: 过滤条件
            
        Returns:
            相似向量列表，按相似度降序排列
        """
        if not self.connected or not self.client:
            if not await self.connect():
                return []
        
        try:
            search_params = {
                "collection_name": self.config.collection_name,
                "query_vector": query_vector,
                "limit": limit,
                "with_vectors": True,
                "with_payload": True
            }
            
            if score_threshold is not None:
                search_params["score_threshold"] = score_threshold
                
            if filter_condition is not None:
                search_params["query_filter"] = rest.Filter(**filter_condition)
            
            results = self.client.search(**search_params)
            
            return [{
                "id": point.id,
                "vector": point.vector,
                "metadata": point.payload,
                "score": point.score
            } for point in results]
        except Exception as e:
            logger.error(f"搜索相似向量失败: {e}")
            raise
    
    async def health_check(self) -> Dict[str, Any]:
        """
        检查向量数据库的健康状态
        
        Returns:
            包含健康状态信息的字典
        """
        start_time = time.time()
        status = {
            "connected": False,
            "collection_exists": False,
            "response_time_ms": 0,
            "errors": []
        }
        
        try:
            # 测试连接
            if not self.client:
                await self.connect()
            
            if not self.client:
                status["errors"].append("连接失败: 客户端为空")
                return status
            
            # 检查集合
            loop = asyncio.get_event_loop()
            collections = await loop.run_in_executor(
                _executor,
                self.client.get_collections
            )
            
            status["connected"] = True
            status["collection_exists"] = any(
                c.name == self.config.collection_name 
                for c in collections.collections
            )
            
            # 测试集合信息获取
            if status["collection_exists"]:
                collection_info = await loop.run_in_executor(
                    _executor,
                    lambda: self.client.get_collection(self.config.collection_name)
                )
                
                status["collection_info"] = {
                    "vectors_count": collection_info.vectors_count,
                    "points_count": collection_info.points_count,
                    "status": str(collection_info.status),
                    "vector_size": collection_info.config.params.vectors.size,
                    "distance": str(collection_info.config.params.vectors.distance)
                }
        except Exception as e:
            status["errors"].append(f"健康检查错误: {str(e)}")
        
        status["response_time_ms"] = round((time.time() - start_time) * 1000, 2)
        return status
    
    def __del__(self):
        """析构函数，资源清理"""
        # 注意：不从连接池中移除客户端，让池管理生命周期 