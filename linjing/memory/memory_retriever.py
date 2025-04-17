#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
记忆检索器模块，负责检索与当前对话相关的记忆。
"""

import logging
from typing import Any, Dict, List, Optional, Union
import time

from linjing.memory.memory_manager import Memory, MemoryType

logger = logging.getLogger(__name__)


class MemoryRetriever:
    """
    记忆检索器，用于检索与查询相关的记忆。
    
    该类提供了针对不同类型记忆和不同查询场景的优化检索方法。
    """
    
    def __init__(self, memory_manager=None, llm_manager=None, config=None):
        """
        初始化记忆检索器
        
        Args:
            memory_manager: 记忆管理器实例
            llm_manager: 语言模型管理器实例
            config: 配置字典
        """
        self.memory_manager = memory_manager
        self.llm_manager = llm_manager
        self.config = config or {}
        
        # 检索参数
        self.default_limit = self.config.get("default_limit", 5)
        self.relevance_threshold = self.config.get("relevance_threshold", 0.65)
        self.recency_weight = self.config.get("recency_weight", 0.3)
        self.importance_weight = self.config.get("importance_weight", 0.2)
        self.relevance_weight = self.config.get("relevance_weight", 0.5)
        self.cache_ttl = self.config.get("cache_ttl", 60)  # 缓存有效期，秒
        
        # 检索缓存
        self.cache = {}
        
        logger.info("记忆检索器初始化完成")
    
    async def retrieve(self, query: str, user_id: str, session_id: Optional[str] = None, 
                     memory_types: Optional[List[Union[MemoryType, str]]] = None,
                     limit: Optional[int] = None, use_cache: bool = True) -> List[Memory]:
        """
        检索与查询相关的记忆
        
        Args:
            query: 查询文本
            user_id: 用户ID
            session_id: 会话ID
            memory_types: 要检索的记忆类型列表
            limit: 返回结果数量上限
            use_cache: 是否使用缓存
            
        Returns:
            相关记忆列表
        """
        if not self.memory_manager:
            logger.warning("未提供记忆管理器，无法检索记忆")
            return []
        
        limit = limit or self.default_limit
        
        # 检查缓存
        cache_key = f"{query}_{user_id}_{session_id}_{str(memory_types)}_{limit}"
        if use_cache and cache_key in self.cache:
            cache_entry = self.cache[cache_key]
            if time.time() - cache_entry["timestamp"] < self.cache_ttl:
                logger.debug(f"使用缓存结果: {query[:20]}")
                return cache_entry["memories"]
        
        # 如果没有指定记忆类型，默认查询所有类型
        if not memory_types:
            memory_types = [
                MemoryType.CONVERSATION,
                MemoryType.FACT,
                MemoryType.EXPERIENCE,
                MemoryType.RELATIONSHIP,
                MemoryType.PREFERENCE,
                MemoryType.USER_PROFILE
            ]
        
        # 首先进行基本检索
        memories = await self.memory_manager.retrieve_relevant(
            query, 
            limit=limit * 2,  # 检索更多结果，后续会进行重排序
            user_id=user_id,
            memory_types=memory_types
        )
        
        # 如果获取的记忆太少，尝试扩大检索范围
        if len(memories) < limit * 0.5 and user_id:
            logger.debug(f"基本检索结果过少({len(memories)}个)，扩大检索范围")
            # 尝试不限制用户ID进行检索
            additional_memories = await self.memory_manager.retrieve_relevant(
                query, 
                limit=limit,
                memory_types=memory_types
            )
            
            # 合并结果，去重
            seen_ids = {memory.id for memory in memories}
            for memory in additional_memories:
                if memory.id not in seen_ids:
                    memories.append(memory)
                    seen_ids.add(memory.id)
        
        # 重新排序记忆
        ranked_memories = await self.rank_memories(memories, query)
        
        # 限制返回数量
        result = ranked_memories[:limit]
        
        # 更新缓存
        if use_cache:
            self.cache[cache_key] = {
                "memories": result,
                "timestamp": time.time()
            }
            
            # 清理过期缓存
            self._clean_cache()
        
        return result
    
    async def rank_memories(self, memories: List[Memory], query: str) -> List[Memory]:
        """
        根据多种因素对记忆进行排序
        
        Args:
            memories: 记忆列表
            query: 查询文本
            
        Returns:
            排序后的记忆列表
        """
        if not memories:
            return []
        
        # 计算每个记忆的综合得分
        scored_memories = []
        current_time = time.time()
        
        for memory in memories:
            # 相关性得分（从元数据中获取，如果有）
            relevance_score = memory.metadata.get("similarity_score", 0.5)
            
            # 重要性得分
            importance_score = memory.importance
            
            # 时间衰减因子（基于创建时间）
            hours_since_creation = (current_time - memory.creation_time) / 3600
            recency_score = 1.0 * (0.95 ** min(hours_since_creation, 720))  # 最多考虑30天
            
            # 计算综合得分
            final_score = (
                self.relevance_weight * relevance_score +
                self.importance_weight * importance_score +
                self.recency_weight * recency_score
            )
            
            scored_memories.append((memory, final_score))
        
        # 根据得分降序排序
        scored_memories.sort(key=lambda x: x[1], reverse=True)
        
        # 使用LLM进一步优化结果排序（可选）
        if self.llm_manager and len(scored_memories) > 1:
            try:
                # 尝试使用LLM重新排序前10个结果
                top_memories = [m for m, _ in scored_memories[:10]]
                reranked_memories = await self._rerank_with_llm(top_memories, query)
                
                # 如果LLM重排序成功，替换原列表开头的元素
                if reranked_memories:
                    reranked_ids = [m.id for m in reranked_memories]
                    remaining = [m for m, _ in scored_memories if m.id not in reranked_ids]
                    
                    # 合并结果
                    return reranked_memories + [m for m, _ in remaining]
            except Exception as e:
                logger.error(f"使用LLM重排序记忆失败: {e}", exc_info=True)
        
        # 返回排序后的记忆列表
        return [memory for memory, _ in scored_memories]
    
    async def _rerank_with_llm(self, memories: List[Memory], query: str) -> List[Memory]:
        """
        使用LLM重新排序记忆
        
        Args:
            memories: 记忆列表
            query: 查询文本
            
        Returns:
            重新排序的记忆列表
        """
        if not self.llm_manager or len(memories) <= 1:
            return memories
        
        try:
            # 准备记忆内容
            memory_texts = []
            for i, memory in enumerate(memories, 1):
                memory_type = memory.memory_type.name if isinstance(memory.memory_type, MemoryType) else str(memory.memory_type)
                memory_texts.append(f"记忆{i}: [{memory_type}] {memory.content}")
            
            memory_content = "\n".join(memory_texts)
            
            # 构建提示词
            prompt = f"""
            请根据以下查询，对给定的记忆按照与查询的相关性从高到低进行排序：
            
            查询: {query}
            
            记忆列表:
            {memory_content}
            
            请返回排序后的记忆编号，格式为逗号分隔的数字列表，例如"3,1,4,2,5"。只需返回数字序列，不要包含其他内容。
            """
            
            # 生成排序结果
            response = await self.llm_manager.generate_text(prompt, max_tokens=50)
            
            # 解析排序结果
            try:
                # 清理响应文本
                response = response.strip().replace(" ", "")
                
                # 提取数字序列
                import re
                match = re.search(r'(\d+(?:,\d+)*)', response)
                if match:
                    response = match.group(1)
                
                # 解析为索引列表
                indices = [int(idx) - 1 for idx in response.split(",") if idx.isdigit()]
                
                # 过滤无效索引
                valid_indices = [idx for idx in indices if 0 <= idx < len(memories)]
                
                # 如果没有得到有效排序，返回原列表
                if not valid_indices:
                    return memories
                
                # 按新顺序排列记忆
                reranked = []
                for idx in valid_indices:
                    reranked.append(memories[idx])
                
                # 添加任何未在排序中出现的记忆
                seen_ids = {memory.id for memory in reranked}
                for memory in memories:
                    if memory.id not in seen_ids:
                        reranked.append(memory)
                
                return reranked
                
            except Exception as e:
                logger.error(f"解析LLM排序结果失败: {e}", exc_info=True)
                return memories
                
        except Exception as e:
            logger.error(f"使用LLM重排序记忆失败: {e}", exc_info=True)
            return memories
    
    async def retrieve_memory_by_type(self, user_id: str, memory_type: Union[MemoryType, str], 
                                    limit: int = 10) -> List[Memory]:
        """
        按类型检索用户记忆
        
        Args:
            user_id: 用户ID
            memory_type: 记忆类型
            limit: 返回结果数量上限
            
        Returns:
            指定类型的记忆列表
        """
        if not self.memory_manager:
            logger.warning("未提供记忆管理器，无法检索记忆")
            return []
        
        try:
            # 将内存类型转换为字符串
            if isinstance(memory_type, MemoryType):
                memory_type_str = memory_type.name
            else:
                memory_type_str = str(memory_type)
            
            # 构建查询条件
            query = f"SELECT * FROM memories WHERE user_id = ? AND memory_type = ? ORDER BY importance DESC LIMIT ?"
            params = (user_id, memory_type_str, limit)
            
            # 执行查询
            if self.memory_manager.db_manager:
                results = await self.memory_manager.db_manager.execute_query(query, params)
                
                # 处理结果
                memories = []
                for row in results:
                    # 处理元数据
                    if "metadata" in row and isinstance(row["metadata"], str):
                        try:
                            import json
                            row["metadata"] = json.loads(row["metadata"])
                        except Exception:
                            row["metadata"] = {}
                    
                    memory = Memory.from_dict(row)
                    memory.access()  # 记录访问
                    memories.append(memory)
                
                return memories
        
        except Exception as e:
            logger.error(f"按类型检索记忆失败: {e}", exc_info=True)
        
        return []
    
    async def retrieve_user_profile(self, user_id: str) -> Optional[Memory]:
        """
        检索用户资料记忆
        
        Args:
            user_id: 用户ID
            
        Returns:
            用户资料记忆，如果没有则返回None
        """
        profiles = await self.retrieve_memory_by_type(user_id, MemoryType.USER_PROFILE, limit=1)
        return profiles[0] if profiles else None
    
    async def retrieve_user_preferences(self, user_id: str, limit: int = 5) -> List[Memory]:
        """
        检索用户偏好记忆
        
        Args:
            user_id: 用户ID
            limit: 返回结果数量上限
            
        Returns:
            用户偏好记忆列表
        """
        return await self.retrieve_memory_by_type(user_id, MemoryType.PREFERENCE, limit=limit)
    
    async def retrieve_recent_conversations(self, user_id: str, limit: int = 10) -> List[Memory]:
        """
        检索最近对话记忆
        
        Args:
            user_id: 用户ID
            limit: 返回结果数量上限
            
        Returns:
            最近对话记忆列表
        """
        if not self.memory_manager:
            logger.warning("未提供记忆管理器，无法检索记忆")
            return []
        
        try:
            # 构建查询条件
            query = """
            SELECT * FROM memories 
            WHERE user_id = ? AND memory_type = ? 
            ORDER BY creation_time DESC 
            LIMIT ?
            """
            params = (user_id, MemoryType.CONVERSATION.name, limit)
            
            # 执行查询
            if self.memory_manager.db_manager:
                results = await self.memory_manager.db_manager.execute_query(query, params)
                
                # 处理结果
                memories = []
                for row in results:
                    # 处理元数据
                    if "metadata" in row and isinstance(row["metadata"], str):
                        try:
                            import json
                            row["metadata"] = json.loads(row["metadata"])
                        except Exception:
                            row["metadata"] = {}
                    
                    memory = Memory.from_dict(row)
                    memory.access()  # 记录访问
                    memories.append(memory)
                
                return memories
        
        except Exception as e:
            logger.error(f"检索最近对话记忆失败: {e}", exc_info=True)
        
        return []
    
    def clear_cache(self) -> None:
        """
        清空检索缓存
        """
        self.cache = {}
        logger.debug("已清空记忆检索缓存")
    
    def _clean_cache(self) -> None:
        """
        清理过期缓存
        """
        current_time = time.time()
        expired_keys = []
        
        for key, entry in self.cache.items():
            if current_time - entry["timestamp"] > self.cache_ttl:
                expired_keys.append(key)
        
        for key in expired_keys:
            del self.cache[key]
        
        if expired_keys:
            logger.debug(f"已清理{len(expired_keys)}个过期缓存项") 