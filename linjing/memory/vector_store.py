#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
向量存储模块，负责记忆的向量化存储和检索。
"""

import logging
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


class VectorStore:
    """
    向量存储，提供对向量化记忆的存储和检索功能。
    
    本类是对向量数据库的抽象封装，支持多种向量数据库后端。
    """
    
    def __init__(self, vector_db=None, config=None):
        """
        初始化向量存储
        
        Args:
            vector_db: 向量数据库管理器实例
            config: 配置字典
        """
        self.vector_db = vector_db
        self.config = config or {}
        self.collection_name = self.config.get("collection_name", "memories")
        self.vector_dimension = self.config.get("vector_dimension", 1536)  # 默认维度（OpenAI Embedding维度）
        self.initialize_done = False
        
        logger.info("向量存储初始化")
    
    async def initialize(self) -> bool:
        """
        初始化向量存储
        
        Returns:
            是否初始化成功
        """
        if not self.vector_db:
            logger.warning("未提供向量数据库，向量存储功能将不可用")
            return False
        
        try:
            # 尝试连接向量数据库
            if not await self.vector_db.connect():
                logger.error("连接向量数据库失败")
                return False
            
            # 确保集合存在
            collection_exists = await self.vector_db.collection_exists(self.collection_name)
            
            if not collection_exists:
                logger.info(f"创建向量集合: {self.collection_name}")
                if not await self.vector_db.create_collection(self.collection_name, self.vector_dimension):
                    logger.error(f"创建向量集合失败: {self.collection_name}")
                    return False
            
            self.initialize_done = True
            logger.info("向量存储初始化完成")
            return True
            
        except Exception as e:
            logger.error(f"初始化向量存储时出错: {e}", exc_info=True)
            return False
    
    async def add_vector(self, vector_id: str, vector: List[float], metadata: Dict[str, Any] = None) -> bool:
        """
        添加向量到存储
        
        Args:
            vector_id: 向量ID
            vector: 向量数据
            metadata: 向量元数据
            
        Returns:
            是否添加成功
        """
        if not self.vector_db or not self.initialize_done:
            logger.warning("向量存储未初始化，无法添加向量")
            return False
        
        try:
            metadata = metadata or {}
            
            # 确保元数据中包含向量ID
            if "id" not in metadata:
                metadata["id"] = vector_id
            
            # 插入向量
            result = await self.vector_db.insert_vectors(
                self.collection_name,
                [vector_id],
                [vector],
                [metadata]
            )
            
            if result:
                logger.debug(f"向量添加成功: {vector_id}")
                return True
            else:
                logger.error(f"向量添加失败: {vector_id}")
                return False
                
        except Exception as e:
            logger.error(f"添加向量时出错: {e}", exc_info=True)
            return False
    
    async def get_vector(self, vector_id: str) -> Optional[Dict[str, Any]]:
        """
        获取指定ID的向量
        
        Args:
            vector_id: 向量ID
            
        Returns:
            向量数据和元数据的字典，如果找不到则返回None
        """
        if not self.vector_db or not self.initialize_done:
            logger.warning("向量存储未初始化，无法获取向量")
            return None
        
        try:
            # 获取向量
            vector_data = await self.vector_db.get_vector(self.collection_name, vector_id)
            
            if vector_data:
                logger.debug(f"获取向量成功: {vector_id}")
                return vector_data
            else:
                logger.debug(f"未找到向量: {vector_id}")
                return None
                
        except Exception as e:
            logger.error(f"获取向量时出错: {e}", exc_info=True)
            return None
    
    async def update_vector(self, vector_id: str, vector: List[float], metadata: Dict[str, Any] = None) -> bool:
        """
        更新向量
        
        Args:
            vector_id: 向量ID
            vector: 新的向量数据
            metadata: 新的元数据
            
        Returns:
            是否更新成功
        """
        if not self.vector_db or not self.initialize_done:
            logger.warning("向量存储未初始化，无法更新向量")
            return False
        
        try:
            # 首先删除旧向量
            delete_result = await self.delete_vector(vector_id)
            
            if not delete_result:
                logger.warning(f"删除旧向量失败，继续尝试添加新向量: {vector_id}")
            
            # 添加新向量
            add_result = await self.add_vector(vector_id, vector, metadata)
            
            if add_result:
                logger.debug(f"向量更新成功: {vector_id}")
                return True
            else:
                logger.error(f"向量更新失败: {vector_id}")
                return False
                
        except Exception as e:
            logger.error(f"更新向量时出错: {e}", exc_info=True)
            return False
    
    async def delete_vector(self, vector_id: str) -> bool:
        """
        删除向量
        
        Args:
            vector_id: 向量ID
            
        Returns:
            是否删除成功
        """
        if not self.vector_db or not self.initialize_done:
            logger.warning("向量存储未初始化，无法删除向量")
            return False
        
        try:
            # 删除向量
            result = await self.vector_db.delete_vector(self.collection_name, vector_id)
            
            if result:
                logger.debug(f"向量删除成功: {vector_id}")
                return True
            else:
                logger.error(f"向量删除失败: {vector_id}")
                return False
                
        except Exception as e:
            logger.error(f"删除向量时出错: {e}", exc_info=True)
            return False
    
    async def search(self, query_vector: List[float], limit: int = 5, 
                   filter_dict: Dict[str, Any] = None, score_threshold: float = 0.0) -> List[Dict[str, Any]]:
        """
        搜索相似向量
        
        Args:
            query_vector: 查询向量
            limit: 返回结果数量上限
            filter_dict: 过滤条件字典
            score_threshold: 相似度分数阈值，只返回高于此分数的结果
            
        Returns:
            相似向量列表，包含ID、向量数据、元数据和相似度分数
        """
        if not self.vector_db or not self.initialize_done:
            logger.warning("向量存储未初始化，无法搜索向量")
            return []
        
        try:
            # 执行向量搜索
            results = await self.vector_db.search(
                self.collection_name,
                query_vector,
                limit=limit,
                filter_dict=filter_dict
            )
            
            # 过滤低于分数阈值的结果
            if score_threshold > 0:
                results = [r for r in results if r.get("score", 0) >= score_threshold]
            
            logger.debug(f"向量搜索完成，找到{len(results)}个结果")
            return results
                
        except Exception as e:
            logger.error(f"搜索向量时出错: {e}", exc_info=True)
            return []
    
    async def batch_add_vectors(self, vector_ids: List[str], vectors: List[List[float]], 
                              metadatas: List[Dict[str, Any]] = None) -> bool:
        """
        批量添加向量
        
        Args:
            vector_ids: 向量ID列表
            vectors: 向量数据列表
            metadatas: 元数据列表
            
        Returns:
            是否添加成功
        """
        if not self.vector_db or not self.initialize_done:
            logger.warning("向量存储未初始化，无法批量添加向量")
            return False
        
        if len(vector_ids) != len(vectors):
            logger.error("向量ID数量与向量数据数量不匹配")
            return False
        
        if metadatas and len(metadatas) != len(vectors):
            logger.error("元数据数量与向量数据数量不匹配")
            return False
        
        try:
            # 如果没有提供元数据，创建空元数据
            if not metadatas:
                metadatas = [{} for _ in vector_ids]
            
            # 确保每个元数据字典中包含向量ID
            for i, metadata in enumerate(metadatas):
                if "id" not in metadata:
                    metadata["id"] = vector_ids[i]
            
            # 批量插入向量
            result = await self.vector_db.insert_vectors(
                self.collection_name,
                vector_ids,
                vectors,
                metadatas
            )
            
            if result:
                logger.debug(f"批量添加向量成功: {len(vector_ids)}个向量")
                return True
            else:
                logger.error("批量添加向量失败")
                return False
                
        except Exception as e:
            logger.error(f"批量添加向量时出错: {e}", exc_info=True)
            return False
    
    async def count_vectors(self) -> int:
        """
        获取向量数量
        
        Returns:
            向量数量
        """
        if not self.vector_db or not self.initialize_done:
            logger.warning("向量存储未初始化，无法获取向量数量")
            return 0
        
        try:
            # 获取向量数量
            count = await self.vector_db.count_vectors(self.collection_name)
            logger.debug(f"向量数量: {count}")
            return count
                
        except Exception as e:
            logger.error(f"获取向量数量时出错: {e}", exc_info=True)
            return 0
    
    async def clear_collection(self) -> bool:
        """
        清空集合中的所有向量
        
        Returns:
            是否清空成功
        """
        if not self.vector_db or not self.initialize_done:
            logger.warning("向量存储未初始化，无法清空集合")
            return False
        
        try:
            # 清空集合
            result = await self.vector_db.clear_collection(self.collection_name)
            
            if result:
                logger.info(f"成功清空向量集合: {self.collection_name}")
                return True
            else:
                logger.error(f"清空向量集合失败: {self.collection_name}")
                return False
                
        except Exception as e:
            logger.error(f"清空向量集合时出错: {e}", exc_info=True)
            return False 