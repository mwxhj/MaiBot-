#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
林镜(LingJing) - 记忆管理器
"""

import asyncio
import json
import os
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional, Union, Tuple
import heapq

from ..utils.logger import get_logger
from ..models.memory_models import Memory
from ..exceptions import MemoryError, MemoryRetrievalError
from ..constants import MemoryType, MemoryPriority

# 单例实例
_memory_manager_instance = None

class MemoryManager:
    """记忆管理器，负责管理机器人的记忆"""
    
    def __init__(self):
        """初始化记忆管理器"""
        self.logger = get_logger('linjing.memory.manager')
        self.config = None
        self.storage_path = None
        self.vector_store = None
        self.llm_interface = None
        
        # 记忆缓存
        self.memory_cache: Dict[str, Memory] = {}
        self.recent_memories: List[str] = []  # 记忆ID列表
        self.max_cache_size = 1000
        
        # 向量存储配置
        self.use_vector_store = True
        self.embedding_batch_size = 16
        
        # 记忆处理配置
        self.max_importance_score = 10.0
        self.min_importance_threshold = 2.0  # 低于此阈值的记忆可能被丢弃
    
    async def initialize(self) -> None:
        """初始化记忆管理器"""
        self.logger.info("初始化记忆管理器...")
        
        # 导入配置
        from ..config import async_get_config
        self.config = await async_get_config()
        
        if not self.config:
            self.logger.error("无法获取配置信息")
            return
        
        # 设置存储路径
        memory_config = self.config.get('memory', {})
        self.storage_path = memory_config.get('storage_path', 'data/memories')
        
        # 确保存储目录存在
        os.makedirs(self.storage_path, exist_ok=True)
        
        # 设置缓存大小
        self.max_cache_size = memory_config.get('max_cache_size', 1000)
        
        # 导入LLM接口
        from ..llm.llm_interface import get_llm_interface
        self.llm_interface = await get_llm_interface()
        
        # 设置向量存储
        self.use_vector_store = memory_config.get('use_vector_store', True)
        
        if self.use_vector_store:
            await self._initialize_vector_store()
        
        # 加载最近的记忆
        await self._load_recent_memories()
        
        self.logger.info("记忆管理器初始化完成")
    
    async def _initialize_vector_store(self) -> None:
        """初始化向量存储"""
        try:
            # 根据配置选择向量存储实现
            vector_store_type = self.config.get('memory', {}).get('vector_store', 'local')
            
            if vector_store_type == 'local':
                from ..storage.vector_stores.local_vector_store import LocalVectorStore
                self.vector_store = LocalVectorStore()
            elif vector_store_type == 'faiss':
                from ..storage.vector_stores.faiss_vector_store import FaissVectorStore
                self.vector_store = FaissVectorStore()
            elif vector_store_type == 'chromadb':
                from ..storage.vector_stores.chroma_vector_store import ChromaVectorStore
                self.vector_store = ChromaVectorStore()
            elif vector_store_type == 'qdrant':
                from ..storage.vector_stores.qdrant_vector_store import QdrantVectorStore
                self.vector_store = QdrantVectorStore()
            elif vector_store_type == 'milvus':
                from ..storage.vector_stores.milvus_vector_store import MilvusVectorStore
                self.vector_store = MilvusVectorStore()
            elif vector_store_type == 'pinecone':
                from ..storage.vector_stores.pinecone_vector_store import PineconeVectorStore
                self.vector_store = PineconeVectorStore()
            else:
                raise MemoryError(f"不支持的向量存储类型: {vector_store_type}")
            
            # 配置向量存储
            vector_store_config = self.config.get('memory', {}).get('vector_store_config', {})
            await self.vector_store.initialize(vector_store_config)
            
            self.logger.info(f"向量存储 ({vector_store_type}) 初始化成功")
        
        except ImportError as e:
            self.logger.error(f"导入向量存储模块失败: {e}")
            self.use_vector_store = False
        except Exception as e:
            self.logger.error(f"初始化向量存储失败: {e}")
            self.use_vector_store = False
    
    async def _load_recent_memories(self) -> None:
        """加载最近的记忆到缓存"""
        try:
            # 读取记忆索引文件（如果存在）
            index_path = os.path.join(self.storage_path, 'memory_index.json')
            if os.path.exists(index_path):
                with open(index_path, 'r', encoding='utf-8') as f:
                    index_data = json.load(f)
                    
                    # 获取最近添加的记忆ID
                    memory_ids = index_data.get('recent_memories', [])
                    
                    # 加载前N个记忆
                    count = min(self.max_cache_size, len(memory_ids))
                    for memory_id in memory_ids[:count]:
                        memory = await self._load_memory_from_disk(memory_id)
                        if memory:
                            self.memory_cache[memory_id] = memory
                            self.recent_memories.append(memory_id)
            
            self.logger.info(f"已加载 {len(self.memory_cache)} 条记忆到缓存")
        
        except Exception as e:
            self.logger.error(f"加载记忆缓存失败: {e}")
    
    async def _load_memory_from_disk(self, memory_id: str) -> Optional[Memory]:
        """
        从磁盘加载记忆
        
        Args:
            memory_id: 记忆ID
            
        Returns:
            记忆对象，如果不存在则返回None
        """
        try:
            file_path = os.path.join(self.storage_path, f"{memory_id}.json")
            
            if not os.path.exists(file_path):
                return None
            
            with open(file_path, 'r', encoding='utf-8') as f:
                memory_data = json.load(f)
                
            return Memory.from_dict(memory_data)
        
        except Exception as e:
            self.logger.error(f"加载记忆 {memory_id} 失败: {e}")
            return None
    
    async def _save_memory_to_disk(self, memory: Memory) -> bool:
        """
        将记忆保存到磁盘
        
        Args:
            memory: 记忆对象
            
        Returns:
            是否保存成功
        """
        try:
            memory_data = memory.to_dict()
            file_path = os.path.join(self.storage_path, f"{memory.id}.json")
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(memory_data, f, ensure_ascii=False, indent=2)
            
            return True
        
        except Exception as e:
            self.logger.error(f"保存记忆 {memory.id} 失败: {e}")
            return False
    
    async def _save_memory_index(self) -> None:
        """保存记忆索引"""
        try:
            index_data = {
                'last_updated': datetime.now().isoformat(),
                'recent_memories': self.recent_memories
            }
            
            index_path = os.path.join(self.storage_path, 'memory_index.json')
            
            with open(index_path, 'w', encoding='utf-8') as f:
                json.dump(index_data, f, ensure_ascii=False, indent=2)
        
        except Exception as e:
            self.logger.error(f"保存记忆索引失败: {e}")
    
    async def create_memory(self, content: str, memory_type: str = MemoryType.EPISODIC,
                         priority: int = MemoryPriority.MEDIUM, 
                         metadata: Optional[Dict[str, Any]] = None) -> Memory:
        """
        创建新记忆
        
        Args:
            content: 记忆内容
            memory_type: 记忆类型
            priority: 优先级
            metadata: 元数据
            
        Returns:
            创建的记忆对象
        """
        # 生成唯一ID
        memory_id = str(uuid.uuid4())
        
        # 创建记忆对象
        memory = Memory(
            id=memory_id,
            content=content,
            memory_type=memory_type,
            priority=priority,
            metadata=metadata or {},
            importance_score=self._calculate_initial_importance(content, priority)
        )
        
        # 如果使用向量存储，则生成嵌入
        if self.use_vector_store and self.vector_store:
            try:
                embedding = await self.llm_interface.create_embedding(content)
                memory.vector = embedding
                
                # 添加到向量存储
                await self.vector_store.add_memory(memory_id, embedding, memory.to_dict())
            except Exception as e:
                self.logger.error(f"生成记忆嵌入失败: {e}")
        
        # 添加到缓存
        self.memory_cache[memory_id] = memory
        self.recent_memories.insert(0, memory_id)  # 添加到最近记忆的开头
        
        # 如果缓存超过最大大小，移除最老的记忆
        if len(self.memory_cache) > self.max_cache_size:
            self._trim_cache()
        
        # 保存到磁盘
        await self._save_memory_to_disk(memory)
        await self._save_memory_index()
        
        self.logger.debug(f"创建新记忆: {memory_id}, 类型: {memory_type}")
        
        return memory
    
    def _calculate_initial_importance(self, content: str, priority: int) -> float:
        """
        计算初始重要性评分
        
        Args:
            content: 记忆内容
            priority: 优先级
            
        Returns:
            重要性评分
        """
        # 基于优先级的基础分数
        base_score = {
            MemoryPriority.HIGH: 7.0,
            MemoryPriority.MEDIUM: 5.0,
            MemoryPriority.LOW: 3.0,
            MemoryPriority.TRIVIAL: 1.0
        }.get(priority, 5.0)
        
        # 内容长度影响
        length_factor = min(1.0, len(content) / 500)
        
        # 组合评分
        importance = base_score * (0.8 + 0.2 * length_factor)
        
        return min(self.max_importance_score, importance)
    
    async def get_memory(self, memory_id: str) -> Optional[Memory]:
        """
        获取单个记忆
        
        Args:
            memory_id: 记忆ID
            
        Returns:
            记忆对象，如果不存在则返回None
        """
        # 检查缓存
        memory = self.memory_cache.get(memory_id)
        
        if memory:
            # 更新访问信息
            memory.update_access()
            return memory
        
        # 从磁盘加载
        memory = await self._load_memory_from_disk(memory_id)
        
        if memory:
            # 更新访问信息
            memory.update_access()
            
            # 添加到缓存
            self.memory_cache[memory_id] = memory
            
            # 更新最近记忆列表
            if memory_id in self.recent_memories:
                self.recent_memories.remove(memory_id)
            self.recent_memories.insert(0, memory_id)
            
            # 清理缓存
            self._trim_cache()
            
            return memory
        
        return None
    
    async def update_memory(self, memory: Memory) -> bool:
        """
        更新记忆
        
        Args:
            memory: 记忆对象
            
        Returns:
            是否更新成功
        """
        # 更新缓存
        self.memory_cache[memory.id] = memory
        
        # 如果使用向量存储且内容发生变化，则更新向量
        if self.use_vector_store and self.vector_store:
            try:
                # 如果不存在向量或内容变化，重新生成嵌入
                if not memory.vector:
                    embedding = await self.llm_interface.create_embedding(memory.content)
                    memory.vector = embedding
                    
                    # 更新向量存储
                    await self.vector_store.update_memory(memory.id, embedding, memory.to_dict())
            except Exception as e:
                self.logger.error(f"更新记忆向量失败: {e}")
        
        # 保存到磁盘
        success = await self._save_memory_to_disk(memory)
        
        # 调整最近记忆列表
        if memory.id in self.recent_memories:
            self.recent_memories.remove(memory.id)
        self.recent_memories.insert(0, memory.id)
        await self._save_memory_index()
        
        return success
    
    async def delete_memory(self, memory_id: str) -> bool:
        """
        删除记忆
        
        Args:
            memory_id: 记忆ID
            
        Returns:
            是否删除成功
        """
        # 从缓存中删除
        if memory_id in self.memory_cache:
            del self.memory_cache[memory_id]
        
        # 从最近记忆列表中删除
        if memory_id in self.recent_memories:
            self.recent_memories.remove(memory_id)
        
        # 从向量存储中删除
        if self.use_vector_store and self.vector_store:
            try:
                await self.vector_store.delete_memory(memory_id)
            except Exception as e:
                self.logger.error(f"从向量存储中删除记忆失败: {e}")
        
        # 从磁盘中删除
        try:
            file_path = os.path.join(self.storage_path, f"{memory_id}.json")
            if os.path.exists(file_path):
                os.remove(file_path)
            
            # 更新索引
            await self._save_memory_index()
            
            return True
        except Exception as e:
            self.logger.error(f"删除记忆文件失败: {e}")
            return False
    
    def _trim_cache(self) -> None:
        """清理记忆缓存，保持在最大大小以内"""
        # 如果缓存未超过最大大小，无需清理
        if len(self.memory_cache) <= self.max_cache_size:
            return
        
        # 需要移除的记忆数量
        to_remove = len(self.memory_cache) - self.max_cache_size
        
        # 从最老的记忆开始移除
        for memory_id in self.recent_memories[-to_remove:]:
            if memory_id in self.memory_cache:
                del self.memory_cache[memory_id]
        
        # 更新最近记忆列表
        self.recent_memories = self.recent_memories[:-to_remove]
    
    async def retrieve_relevant_memories(self, query: str, limit: int = 5, 
                                       memory_type: Optional[str] = None,
                                       min_relevance: float = 0.6) -> List[Memory]:
        """
        检索与查询相关的记忆
        
        Args:
            query: 查询文本
            limit: 最大返回数量
            memory_type: 记忆类型过滤，可选
            min_relevance: 最小相关性阈值
            
        Returns:
            相关记忆列表
        """
        if not query:
            return []
        
        # 如果使用向量存储，使用语义检索
        if self.use_vector_store and self.vector_store:
            try:
                # 生成查询的嵌入向量
                query_embedding = await self.llm_interface.create_embedding(query)
                
                # 向量检索
                search_results = await self.vector_store.search(
                    query_embedding, 
                    limit=limit*2,  # 获取更多结果，以便后续过滤
                    min_score=min_relevance
                )
                
                # 加载记忆对象
                memories = []
                for result in search_results:
                    memory_id = result['id']
                    relevance = result['score']
                    
                    # 根据ID加载记忆
                    memory = await self.get_memory(memory_id)
                    
                    if memory:
                        # 更新相关性评分
                        memory.update_relevance(relevance)
                        
                        # 应用类型过滤
                        if memory_type is None or memory.memory_type == memory_type:
                            memories.append(memory)
                
                # 按相关性排序并限制数量
                memories.sort(key=lambda m: m.relevance_score, reverse=True)
                return memories[:limit]
            
            except Exception as e:
                self.logger.error(f"检索记忆失败: {e}")
                # 回退到简单关键词匹配
        
        # 如果向量检索失败或未启用，使用简单关键词匹配
        return await self._fallback_keyword_search(query, limit, memory_type)
    
    async def _fallback_keyword_search(self, query: str, limit: int, 
                                     memory_type: Optional[str] = None) -> List[Memory]:
        """
        关键词匹配检索（备用方法）
        
        Args:
            query: 查询文本
            limit: 最大返回数量
            memory_type: 记忆类型过滤，可选
            
        Returns:
            相关记忆列表
        """
        # 将查询转换为小写并拆分为关键词
        keywords = query.lower().split()
        
        # 对缓存中的记忆计算相关性
        scored_memories = []
        for memory in self.memory_cache.values():
            # 应用类型过滤
            if memory_type is not None and memory.memory_type != memory_type:
                continue
            
            # 计算基本匹配分数
            content_lower = memory.content.lower()
            match_count = sum(1 for keyword in keywords if keyword in content_lower)
            
            if match_count > 0:
                # 计算相关性评分
                relevance = match_count / len(keywords)
                
                # 考虑重要性
                final_score = 0.7 * relevance + 0.3 * (memory.importance_score / 10.0)
                
                memory.update_relevance(final_score)
                scored_memories.append((final_score, memory))
        
        # 按分数排序
        scored_memories.sort(reverse=True)
        
        # 返回前N个记忆
        return [memory for _, memory in scored_memories[:limit]]
    
    async def get_memories_by_type(self, memory_type: str, limit: int = 10, 
                                 sort_by: str = 'importance') -> List[Memory]:
        """
        获取指定类型的记忆
        
        Args:
            memory_type: 记忆类型
            limit: 最大返回数量
            sort_by: 排序方式，可选 'importance', 'recency', 'access'
            
        Returns:
            记忆列表
        """
        # 收集所有符合类型的记忆
        memories = [m for m in self.memory_cache.values() if m.memory_type == memory_type]
        
        # 应用排序
        if sort_by == 'importance':
            memories.sort(key=lambda m: m.importance_score, reverse=True)
        elif sort_by == 'recency':
            memories.sort(key=lambda m: m.created_at, reverse=True)
        elif sort_by == 'access':
            memories.sort(key=lambda m: m.last_accessed, reverse=True)
        
        # 返回前N个记忆
        return memories[:limit]
    
    async def get_core_memories(self, limit: int = 5) -> List[Memory]:
        """
        获取核心记忆
        
        Args:
            limit: 最大返回数量
            
        Returns:
            核心记忆列表
        """
        # 收集所有核心记忆
        core_memories = [m for m in self.memory_cache.values() if m.is_core_memory]
        
        # 按重要性排序
        core_memories.sort(key=lambda m: m.importance_score, reverse=True)
        
        # 返回前N个核心记忆
        return core_memories[:limit]
    
    async def get_recent_memories(self, limit: int = 10) -> List[Memory]:
        """
        获取最近的记忆
        
        Args:
            limit: 最大返回数量
            
        Returns:
            最近记忆列表
        """
        memories = []
        count = min(limit, len(self.recent_memories))
        
        for memory_id in self.recent_memories[:count]:
            memory = self.memory_cache.get(memory_id)
            if memory:
                memories.append(memory)
        
        return memories
    
    async def mark_as_core_memory(self, memory_id: str, is_core: bool = True) -> bool:
        """
        将记忆标记为核心记忆
        
        Args:
            memory_id: 记忆ID
            is_core: 是否为核心记忆
            
        Returns:
            是否成功
        """
        memory = await self.get_memory(memory_id)
        
        if not memory:
            return False
        
        memory.set_as_core_memory(is_core)
        
        # 更新记忆
        return await self.update_memory(memory)
    
    async def update_importance(self, memory_id: str, importance: float) -> bool:
        """
        更新记忆重要性
        
        Args:
            memory_id: 记忆ID
            importance: 重要性评分
            
        Returns:
            是否成功
        """
        memory = await self.get_memory(memory_id)
        
        if not memory:
            return False
        
        # 确保评分在有效范围内
        adjusted_importance = min(self.max_importance_score, max(0.0, importance))
        
        memory.update_importance(adjusted_importance)
        
        # 更新记忆
        return await self.update_memory(memory)
    
    async def cleanup_memories(self) -> int:
        """
        清理低重要性记忆
        
        Returns:
            删除的记忆数量
        """
        # 列出可能要删除的记忆ID
        to_delete = []
        
        for memory_id, memory in self.memory_cache.items():
            # 不删除核心记忆
            if memory.is_core_memory:
                continue
                
            # 计算衰减后的评分
            decay_score = memory.calculate_decay_score(current_time=datetime.now())
            
            # 如果衰减分数低于阈值，并且重要性低于阈值，加入删除列表
            if decay_score < 0.2 and memory.importance_score < self.min_importance_threshold:
                to_delete.append(memory_id)
        
        # 删除记忆
        delete_count = 0
        for memory_id in to_delete:
            success = await self.delete_memory(memory_id)
            if success:
                delete_count += 1
        
        self.logger.info(f"记忆清理完成，删除了 {delete_count} 条记忆")
        
        return delete_count


async def get_memory_manager() -> MemoryManager:
    """
    获取记忆管理器实例（单例模式）
    
    Returns:
        MemoryManager: 记忆管理器实例
    """
    global _memory_manager_instance
    
    if _memory_manager_instance is None:
        _memory_manager_instance = MemoryManager()
        await _memory_manager_instance.initialize()
    
    return _memory_manager_instance 