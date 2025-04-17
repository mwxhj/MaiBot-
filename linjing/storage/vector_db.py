#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
向量数据库管理器模块，基于Qdrant提供高性能向量存储和检索服务。
"""

import logging
import os
import uuid
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.http import models as rest
from qdrant_client.http.exceptions import UnexpectedResponse

logger = logging.getLogger(__name__)


class VectorDBManager:
    """
    向量数据库管理器，提供向量存储、检索和管理功能。
    
    基于Qdrant实现，支持高维向量的相似性搜索和过滤。
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        初始化向量数据库管理器。
        
        Args:
            config: 向量数据库配置字典，包含连接和集合参数
        """
        self.config = config or {}
        self.collection_name = self.config.get("collection_name", "memories")
        self.vector_size = self.config.get("vector_size", 1536)  # 默认为OpenAI向量大小
        self.similarity = self.config.get("similarity", "cosine")  # 相似度度量方式
        self.location = self.config.get("location", None)  # 本地文件路径或远程URL
        
        # 确保本地存储目录存在
        if self.location is None:
            self.location = "data/vector_db"
            os.makedirs(self.location, exist_ok=True)
        
        # 初始化客户端
        self._client = None
        self._initialized = False
        
        logger.info(f"向量数据库管理器初始化，集合：{self.collection_name}，向量大小：{self.vector_size}")
    
    async def connect(self) -> bool:
        """
        连接到向量数据库
        
        Returns:
            是否连接成功
        """
        if self._client is not None:
            return True
        
        try:
            # 创建客户端
            self._client = QdrantClient(path=self.location)
            
            # 检查集合是否存在，不存在则创建
            await self._initialize_collection()
            
            self._initialized = True
            logger.info(f"成功连接到Qdrant向量数据库，路径：{self.location}")
            return True
        except Exception as e:
            logger.error(f"连接向量数据库失败: {e}", exc_info=True)
            return False
    
    async def disconnect(self) -> None:
        """
        断开向量数据库连接
        """
        if self._client:
            self._client = None
            self._initialized = False
            logger.info("已断开向量数据库连接")
    
    async def _initialize_collection(self) -> None:
        """
        初始化向量集合
        """
        if not self._client:
            await self.connect()
        
        try:
            # 检查集合是否存在
            collections = self._client.get_collections().collections
            exists = any(collection.name == self.collection_name for collection in collections)
            
            if not exists:
                # 创建集合
                self._client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=rest.VectorParams(
                        size=self.vector_size,
                        distance=self.similarity,
                    )
                )
                logger.info(f"创建向量集合 {self.collection_name}")
        except Exception as e:
            logger.error(f"初始化向量集合失败: {e}", exc_info=True)
            raise
    
    async def add_vector(self, vector: List[float], payload: Dict[str, Any] = None, id: str = None) -> str:
        """
        添加向量到数据库
        
        Args:
            vector: 向量数据
            payload: 与向量关联的元数据
            id: 向量ID，如未提供则自动生成
            
        Returns:
            向量ID
        """
        if not self._initialized:
            await self.connect()
        
        if not id:
            id = str(uuid.uuid4())
        
        try:
            # 验证向量维度
            if len(vector) != self.vector_size:
                logger.error(f"向量维度 {len(vector)} 与设置的维度 {self.vector_size} 不匹配")
                return ""
            
            # 添加向量点
            self._client.upsert(
                collection_name=self.collection_name,
                points=[
                    rest.PointStruct(
                        id=id,
                        vector=vector,
                        payload=payload or {}
                    )
                ]
            )
            logger.debug(f"添加向量成功，ID: {id}")
            return id
        except Exception as e:
            logger.error(f"添加向量失败: {e}", exc_info=True)
            return ""
    
    async def get_vector(self, id: str) -> Optional[Dict[str, Any]]:
        """
        获取指定ID的向量
        
        Args:
            id: 向量ID
            
        Returns:
            向量记录，包含vector和payload，未找到则返回None
        """
        if not self._initialized:
            await self.connect()
        
        try:
            result = self._client.retrieve(
                collection_name=self.collection_name,
                ids=[id],
                with_vectors=True,
                with_payload=True
            )
            
            if not result:
                return None
            
            point = result[0]
            return {
                "id": point.id,
                "vector": point.vector,
                "payload": point.payload
            }
        except Exception as e:
            logger.error(f"获取向量失败: {e}", exc_info=True)
            return None
    
    async def delete_vector(self, id: str) -> bool:
        """
        删除指定ID的向量
        
        Args:
            id: 向量ID
            
        Returns:
            是否删除成功
        """
        if not self._initialized:
            await self.connect()
        
        try:
            self._client.delete(
                collection_name=self.collection_name,
                points_selector=rest.PointIdsList(
                    points=[id]
                )
            )
            logger.debug(f"成功删除向量，ID: {id}")
            return True
        except Exception as e:
            logger.error(f"删除向量失败: {e}", exc_info=True)
            return False
    
    async def update_vector(self, id: str, vector: List[float] = None, payload: Dict[str, Any] = None) -> bool:
        """
        更新向量数据或元数据
        
        Args:
            id: 向量ID
            vector: 新的向量数据，可选
            payload: 新的元数据，可选
            
        Returns:
            是否更新成功
        """
        if not self._initialized:
            await self.connect()
        
        if vector is None and payload is None:
            logger.warning("更新向量时未提供有效数据")
            return False
        
        try:
            # 获取当前向量数据
            existing = await self.get_vector(id)
            if not existing:
                logger.warning(f"待更新的向量 {id} 不存在")
                return False
            
            # 构建更新点
            update_vector = vector if vector is not None else existing["vector"]
            update_payload = {**existing["payload"], **(payload or {})} if payload else existing["payload"]
            
            # 验证向量维度
            if len(update_vector) != self.vector_size:
                logger.error(f"更新的向量维度 {len(update_vector)} 与设置的维度 {self.vector_size} 不匹配")
                return False
            
            # 更新向量
            self._client.upsert(
                collection_name=self.collection_name,
                points=[
                    rest.PointStruct(
                        id=id,
                        vector=update_vector,
                        payload=update_payload
                    )
                ]
            )
            logger.debug(f"成功更新向量，ID: {id}")
            return True
        except Exception as e:
            logger.error(f"更新向量失败: {e}", exc_info=True)
            return False
    
    async def search_similar(
        self, 
        vector: List[float], 
        limit: int = 10, 
        score_threshold: float = 0.0,
        filter_conditions: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """
        搜索相似向量
        
        Args:
            vector: 查询向量
            limit: 返回结果数量限制
            score_threshold: 相似度分数阈值，低于该值的结果将被过滤
            filter_conditions: 过滤条件
            
        Returns:
            相似向量列表，按相似度降序排列
        """
        if not self._initialized:
            await self.connect()
        
        try:
            # 验证向量维度
            if len(vector) != self.vector_size:
                logger.error(f"查询向量维度 {len(vector)} 与设置的维度 {self.vector_size} 不匹配")
                return []
            
            # 构建过滤条件
            filter_obj = None
            if filter_conditions:
                filter_obj = self._build_filter(filter_conditions)
            
            # 执行搜索
            search_result = self._client.search(
                collection_name=self.collection_name,
                query_vector=vector,
                limit=limit,
                query_filter=filter_obj,
                with_vectors=True,
                with_payload=True,
                score_threshold=score_threshold
            )
            
            # 格式化结果
            results = []
            for point in search_result:
                results.append({
                    "id": point.id,
                    "score": point.score,
                    "vector": point.vector,
                    "payload": point.payload
                })
            
            return results
        except Exception as e:
            logger.error(f"搜索相似向量失败: {e}", exc_info=True)
            return []
    
    async def batch_add_vectors(self, vectors_data: List[Dict[str, Any]]) -> List[str]:
        """
        批量添加向量
        
        Args:
            vectors_data: 向量数据列表，每项包含vector、payload和可选的id
            
        Returns:
            成功添加的向量ID列表
        """
        if not self._initialized:
            await self.connect()
        
        try:
            points = []
            ids = []
            
            for data in vectors_data:
                vector = data.get("vector")
                payload = data.get("payload", {})
                id = data.get("id", str(uuid.uuid4()))
                
                # 验证向量维度
                if len(vector) != self.vector_size:
                    logger.warning(f"向量维度 {len(vector)} 与设置的维度 {self.vector_size} 不匹配，跳过")
                    continue
                
                points.append(
                    rest.PointStruct(
                        id=id,
                        vector=vector,
                        payload=payload
                    )
                )
                ids.append(id)
            
            if points:
                self._client.upsert(
                    collection_name=self.collection_name,
                    points=points
                )
                logger.info(f"批量添加 {len(points)} 个向量成功")
            
            return ids
        except Exception as e:
            logger.error(f"批量添加向量失败: {e}", exc_info=True)
            return []
    
    async def count_vectors(self, filter_conditions: Dict[str, Any] = None) -> int:
        """
        计算向量数量
        
        Args:
            filter_conditions: 过滤条件
            
        Returns:
            向量数量
        """
        if not self._initialized:
            await self.connect()
        
        try:
            # 构建过滤条件
            filter_obj = None
            if filter_conditions:
                filter_obj = self._build_filter(filter_conditions)
            
            # 获取集合信息
            count = self._client.count(
                collection_name=self.collection_name,
                count_filter=filter_obj
            )
            
            return count.count
        except Exception as e:
            logger.error(f"计算向量数量失败: {e}", exc_info=True)
            return 0
    
    async def clear_collection(self) -> bool:
        """
        清空集合中的所有向量
        
        Returns:
            是否清空成功
        """
        if not self._initialized:
            await self.connect()
        
        try:
            self._client.delete(
                collection_name=self.collection_name,
                points_selector=rest.FilterSelector(
                    filter=rest.Filter(
                        must=[
                            rest.FieldCondition(
                                key="id",
                                match=rest.MatchValue(value="*")
                            )
                        ]
                    )
                )
            )
            logger.info(f"已清空集合 {self.collection_name}")
            return True
        except Exception as e:
            logger.error(f"清空集合失败: {e}", exc_info=True)
            return False
    
    def _build_filter(self, conditions: Dict[str, Any]) -> rest.Filter:
        """
        构建查询过滤条件
        
        Args:
            conditions: 过滤条件字典
            
        Returns:
            Qdrant过滤条件对象
        """
        must_conditions = []
        should_conditions = []
        must_not_conditions = []
        
        # 处理基本条件
        for key, value in conditions.items():
            # 处理复杂条件（操作符前缀）
            if isinstance(value, dict):
                # 范围条件
                if "gt" in value:
                    must_conditions.append(
                        rest.FieldCondition(
                            key=key,
                            range=rest.Range(
                                gt=value["gt"]
                            )
                        )
                    )
                if "gte" in value:
                    must_conditions.append(
                        rest.FieldCondition(
                            key=key,
                            range=rest.Range(
                                gte=value["gte"]
                            )
                        )
                    )
                if "lt" in value:
                    must_conditions.append(
                        rest.FieldCondition(
                            key=key,
                            range=rest.Range(
                                lt=value["lt"]
                            )
                        )
                    )
                if "lte" in value:
                    must_conditions.append(
                        rest.FieldCondition(
                            key=key,
                            range=rest.Range(
                                lte=value["lte"]
                            )
                        )
                    )
                
                # 不等于条件
                if "ne" in value:
                    must_not_conditions.append(
                        rest.FieldCondition(
                            key=key,
                            match=rest.MatchValue(
                                value=value["ne"]
                            )
                        )
                    )
                
                # 包含条件（数组）
                if "in" in value and isinstance(value["in"], list):
                    should_conditions.extend([
                        rest.FieldCondition(
                            key=key,
                            match=rest.MatchValue(
                                value=item
                            )
                        ) for item in value["in"]
                    ])
            # 简单精确匹配
            else:
                must_conditions.append(
                    rest.FieldCondition(
                        key=key,
                        match=rest.MatchValue(
                            value=value
                        )
                    )
                )
        
        # 构建过滤器
        filter_params = {}
        if must_conditions:
            filter_params["must"] = must_conditions
        if should_conditions:
            filter_params["should"] = should_conditions
        if must_not_conditions:
            filter_params["must_not"] = must_not_conditions
        
        return rest.Filter(**filter_params) 