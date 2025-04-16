#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
林镜(LingJing) - 本地向量存储
"""

import os
import json
import pickle
import numpy as np
from typing import Dict, Any, List, Optional, Union, Tuple
from datetime import datetime

from .base_vector_store import BaseVectorStore
from ...utils.logger import get_logger

class LocalVectorStore(BaseVectorStore):
    """简单的本地向量存储，使用内存存储和余弦相似度计算"""
    
    def __init__(self):
        """初始化本地向量存储"""
        self.logger = get_logger('linjing.storage.local_vector_store')
        self.vectors: Dict[str, List[float]] = {}
        self.metadata: Dict[str, Dict[str, Any]] = {}
        self.config: Dict[str, Any] = {}
        self.storage_path: Optional[str] = None
        self.index_file: Optional[str] = None
        self.persist_enabled: bool = True
        self.last_save_time: Optional[datetime] = None
        self.save_interval: int = 60  # 默认60秒保存一次
    
    async def initialize(self, config: Dict[str, Any]) -> None:
        """
        初始化向量存储
        
        Args:
            config: 配置参数
        """
        self.config = config
        
        # 存储路径设置
        self.storage_path = config.get('storage_path', 'data/vector_store')
        
        # 确保存储目录存在
        if self.persist_enabled:
            os.makedirs(self.storage_path, exist_ok=True)
            
        # 索引文件路径
        self.index_file = os.path.join(self.storage_path, 'vector_index.pkl')
        
        # 持久化配置
        self.persist_enabled = config.get('persist_enabled', True)
        self.save_interval = config.get('save_interval', 60)
        
        # 加载已有数据
        if self.persist_enabled and os.path.exists(self.index_file):
            await self._load_index()
        
        self.logger.info(f"本地向量存储初始化完成，向量数量: {len(self.vectors)}")
    
    async def add_memory(self, memory_id: str, embedding: List[float], metadata: Dict[str, Any]) -> bool:
        """
        添加记忆向量
        
        Args:
            memory_id: 记忆ID
            embedding: 嵌入向量
            metadata: 元数据
            
        Returns:
            是否成功
        """
        # 存储向量和元数据
        self.vectors[memory_id] = embedding
        self.metadata[memory_id] = metadata
        
        # 持久化
        if self.persist_enabled:
            await self._save_index()
        
        return True
    
    async def update_memory(self, memory_id: str, embedding: List[float], metadata: Dict[str, Any]) -> bool:
        """
        更新记忆向量
        
        Args:
            memory_id: 记忆ID
            embedding: 嵌入向量
            metadata: 元数据
            
        Returns:
            是否成功
        """
        # 更新向量和元数据
        self.vectors[memory_id] = embedding
        self.metadata[memory_id] = metadata
        
        # 持久化
        if self.persist_enabled:
            await self._save_index()
        
        return True
    
    async def delete_memory(self, memory_id: str) -> bool:
        """
        删除记忆向量
        
        Args:
            memory_id: 记忆ID
            
        Returns:
            是否成功
        """
        # 检查是否存在
        if memory_id not in self.vectors:
            return False
        
        # 删除向量和元数据
        del self.vectors[memory_id]
        if memory_id in self.metadata:
            del self.metadata[memory_id]
        
        # 持久化
        if self.persist_enabled:
            await self._save_index()
        
        return True
    
    async def search(self, query_embedding: List[float], limit: int = 5, min_score: float = 0.0) -> List[Dict[str, Any]]:
        """
        搜索相似向量
        
        Args:
            query_embedding: 查询向量
            limit: 最大返回数量
            min_score: 最小相似度阈值
            
        Returns:
            搜索结果列表，每个结果包含 id, score 和 metadata
        """
        if not self.vectors:
            return []
        
        # 计算所有向量的相似度
        query_vector = np.array(query_embedding)
        scores = []
        
        for memory_id, vector in self.vectors.items():
            # 计算余弦相似度
            similarity = self._cosine_similarity(query_vector, np.array(vector))
            
            # 如果相似度超过阈值，加入结果
            if similarity >= min_score:
                scores.append((memory_id, similarity))
        
        # 按相似度排序
        scores.sort(key=lambda x: x[1], reverse=True)
        
        # 构建结果
        results = []
        for memory_id, score in scores[:limit]:
            result = {
                'id': memory_id,
                'score': float(score),
                'metadata': self.metadata.get(memory_id, {})
            }
            results.append(result)
        
        return results
    
    async def get_memory(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """
        获取记忆数据
        
        Args:
            memory_id: 记忆ID
            
        Returns:
            记忆数据，包含 id, embedding 和 metadata
        """
        if memory_id not in self.vectors:
            return None
        
        return {
            'id': memory_id,
            'embedding': self.vectors[memory_id],
            'metadata': self.metadata.get(memory_id, {})
        }
    
    async def get_stats(self) -> Dict[str, Any]:
        """
        获取向量存储统计信息
        
        Returns:
            统计信息
        """
        vector_count = len(self.vectors)
        
        # 计算平均向量维度
        avg_dimension = 0
        if vector_count > 0:
            dimensions = [len(v) for v in self.vectors.values()]
            avg_dimension = sum(dimensions) / len(dimensions)
        
        stats = {
            'vector_count': vector_count,
            'storage_type': 'local',
            'avg_dimension': avg_dimension,
            'memory_usage': self._estimate_memory_usage(),
            'last_save_time': self.last_save_time.isoformat() if self.last_save_time else None
        }
        
        return stats
    
    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """
        计算两个向量的余弦相似度
        
        Args:
            vec1: 向量1
            vec2: 向量2
            
        Returns:
            相似度(0-1)
        """
        # 零向量处理
        if np.all(vec1 == 0) or np.all(vec2 == 0):
            return 0.0
        
        # 计算余弦相似度: cosine = dot(A, B) / (|A| * |B|)
        dot_product = np.dot(vec1, vec2)
        norm_a = np.linalg.norm(vec1)
        norm_b = np.linalg.norm(vec2)
        
        # 避免除零
        if norm_a == 0 or norm_b == 0:
            return 0.0
            
        similarity = dot_product / (norm_a * norm_b)
        
        # 确保值在0-1之间（理论上-1到1，但这里我们只关心正相关）
        return max(0.0, float(similarity))
    
    async def _save_index(self) -> None:
        """保存索引到磁盘"""
        if not self.persist_enabled or not self.index_file:
            return
        
        # 检查是否需要保存（基于时间间隔）
        now = datetime.now()
        if self.last_save_time and (now - self.last_save_time).total_seconds() < self.save_interval:
            return
        
        try:
            # 构建索引数据
            index_data = {
                'vectors': self.vectors,
                'metadata': self.metadata,
                'last_updated': now.isoformat()
            }
            
            # 保存到文件
            with open(self.index_file, 'wb') as f:
                pickle.dump(index_data, f)
            
            self.last_save_time = now
            self.logger.debug(f"向量索引保存成功，向量数量: {len(self.vectors)}")
        
        except Exception as e:
            self.logger.error(f"保存向量索引失败: {e}")
    
    async def _load_index(self) -> None:
        """从磁盘加载索引"""
        if not self.index_file or not os.path.exists(self.index_file):
            return
        
        try:
            with open(self.index_file, 'rb') as f:
                index_data = pickle.load(f)
            
            # 加载数据
            self.vectors = index_data.get('vectors', {})
            self.metadata = index_data.get('metadata', {})
            
            # 记录加载时间
            self.last_save_time = datetime.now()
            
            self.logger.debug(f"向量索引加载成功，向量数量: {len(self.vectors)}")
        
        except Exception as e:
            self.logger.error(f"加载向量索引失败: {e}")
            # 初始化为空
            self.vectors = {}
            self.metadata = {}
    
    def _estimate_memory_usage(self) -> str:
        """
        估计内存使用情况
        
        Returns:
            内存使用量字符串
        """
        # 估计向量使用的内存
        vector_bytes = 0
        for vec in self.vectors.values():
            vector_bytes += len(vec) * 8  # 每个浮点数约8字节
        
        # 估计元数据使用的内存（粗略估计）
        metadata_bytes = 0
        for meta in self.metadata.values():
            metadata_bytes += 1024  # 假设每个元数据平均1KB
        
        total_bytes = vector_bytes + metadata_bytes
        
        # 转换为可读格式
        if total_bytes < 1024:
            return f"{total_bytes} B"
        elif total_bytes < 1024 * 1024:
            return f"{total_bytes/1024:.2f} KB"
        elif total_bytes < 1024 * 1024 * 1024:
            return f"{total_bytes/(1024*1024):.2f} MB"
        else:
            return f"{total_bytes/(1024*1024*1024):.2f} GB" 