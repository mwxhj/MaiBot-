#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
林镜(LingJing) - 向量存储基类接口
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Union

class BaseVectorStore(ABC):
    """向量存储基类，定义向量存储的接口"""
    
    @abstractmethod
    async def initialize(self, config: Dict[str, Any]) -> None:
        """
        初始化向量存储
        
        Args:
            config: 配置参数
        """
        pass
    
    @abstractmethod
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
        pass
    
    @abstractmethod
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
        pass
    
    @abstractmethod
    async def delete_memory(self, memory_id: str) -> bool:
        """
        删除记忆向量
        
        Args:
            memory_id: 记忆ID
            
        Returns:
            是否成功
        """
        pass
    
    @abstractmethod
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
        pass
    
    @abstractmethod
    async def get_memory(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """
        获取记忆数据
        
        Args:
            memory_id: 记忆ID
            
        Returns:
            记忆数据，包含 id, embedding 和 metadata
        """
        pass
    
    @abstractmethod
    async def get_stats(self) -> Dict[str, Any]:
        """
        获取向量存储统计信息
        
        Returns:
            统计信息
        """
        pass 