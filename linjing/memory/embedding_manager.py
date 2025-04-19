#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
嵌入管理器模块，负责生成和更新记忆的向量嵌入。
提供批量处理和异步操作功能，支持多种嵌入模型。
"""

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from linjing.memory.memory_manager import MemoryManager
from linjing.llm.llm_manager import LLMManager

logger = logging.getLogger(__name__)


class EmbeddingManager:
    """
    嵌入管理器，负责生成和更新记忆的向量嵌入。
    
    提供以下功能：
    - 为新添加的记忆生成向量嵌入
    - 批量处理未嵌入的记忆
    - 定期更新重要记忆的向量嵌入
    - 支持多种嵌入模型和提供方
    """
    
    def __init__(
        self, 
        memory_manager: MemoryManager,
        llm_manager: LLMManager,
        config: Dict[str, Any] = None
    ):
        """
        初始化嵌入管理器
        
        Args:
            memory_manager: 记忆管理器实例
            llm_manager: 语言模型管理器实例
            config: 配置字典
        """
        self.memory_manager = memory_manager
        self.llm_manager = llm_manager
        self.config = config or {}
        
        self.batch_size = self.config.get("batch_size", 10)
        self.max_retries = self.config.get("max_retries", 3)
        self.retry_delay = self.config.get("retry_delay", 5)
        self.processing_lock = asyncio.Lock()
        self.processing = False
        
        # 记录处理中的记忆ID，避免重复处理
        self.processing_ids: Set[str] = set()
        
        logger.info("嵌入管理器初始化完成")
    
    async def generate_embedding(self, text: str) -> Optional[List[float]]:
        """
        为文本生成向量嵌入
        
        Args:
            text: 输入文本
            
        Returns:
            向量嵌入，如果生成失败则返回None
        """
        try:
            embedding = await self.llm_manager.generate_embedding(text)
            return embedding
        except Exception as e:
            logger.error(f"生成向量嵌入失败: {e}", exc_info=True)
            return None
    
    async def add_conversation_with_embedding(
        self,
        user_id: str,
        session_id: str,
        content: str,
        role: str,
        metadata: Dict[str, Any] = None,
        importance: float = 1.0,
        id: str = None
    ) -> str:
        """
        添加对话记忆并生成向量嵌入
        
        Args:
            user_id: 用户ID
            session_id: 会话ID
            content: 对话内容
            role: 角色（'user'或'assistant'）
            metadata: 附加元数据
            importance: 重要性分数
            id: 记忆ID，默认自动生成
            
        Returns:
            记忆ID
        """
        try:
            # 生成向量嵌入
            embedding = await self.generate_embedding(content)
            
            # 添加对话记忆
            memory_id = await self.memory_manager.add_conversation_memory(
                user_id=user_id,
                session_id=session_id,
                content=content,
                role=role,
                metadata=metadata,
                embedding=embedding,
                importance=importance,
                id=id
            )
            
            return memory_id
        except Exception as e:
            logger.error(f"添加带嵌入的对话记忆失败: {e}", exc_info=True)
            
            # 如果生成嵌入失败，尝试不带嵌入添加记忆
            try:
                memory_id = await self.memory_manager.add_conversation_memory(
                    user_id=user_id,
                    session_id=session_id,
                    content=content,
                    role=role,
                    metadata=metadata,
                    embedding=None,
                    importance=importance,
                    id=id
                )
                
                # 安排稍后生成嵌入
                if memory_id:
                    asyncio.create_task(self._generate_embedding_later(memory_id, "conversation"))
                
                return memory_id
            except Exception as e2:
                logger.error(f"添加对话记忆失败: {e2}", exc_info=True)
                return ""
    
    async def add_knowledge_with_embedding(
        self,
        content: str,
        category: str = None,
        source: str = None,
        metadata: Dict[str, Any] = None,
        importance: float = 1.0,
        id: str = None
    ) -> str:
        """
        添加知识记忆并生成向量嵌入
        
        Args:
            content: 知识内容
            category: 知识类别
            source: 知识来源
            metadata: 附加元数据
            importance: 重要性分数
            id: 记忆ID，默认自动生成
            
        Returns:
            记忆ID
        """
        try:
            # 生成向量嵌入
            embedding = await self.generate_embedding(content)
            
            # 添加知识记忆
            memory_id = await self.memory_manager.add_knowledge_memory(
                content=content,
                category=category,
                source=source,
                metadata=metadata,
                embedding=embedding,
                importance=importance,
                id=id
            )
            
            return memory_id
        except Exception as e:
            logger.error(f"添加带嵌入的知识记忆失败: {e}", exc_info=True)
            
            # 如果生成嵌入失败，尝试不带嵌入添加记忆
            try:
                memory_id = await self.memory_manager.add_knowledge_memory(
                    content=content,
                    category=category,
                    source=source,
                    metadata=metadata,
                    embedding=None,
                    importance=importance,
                    id=id
                )
                
                # 安排稍后生成嵌入
                if memory_id:
                    asyncio.create_task(self._generate_embedding_later(memory_id, "knowledge"))
                
                return memory_id
            except Exception as e2:
                logger.error(f"添加知识记忆失败: {e2}", exc_info=True)
                return ""
    
    async def _generate_embedding_later(
        self,
        memory_id: str,
        memory_type: str,
        retry_count: int = 0
    ) -> bool:
        """
        稍后为记忆生成向量嵌入
        
        Args:
            memory_id: 记忆ID
            memory_type: 记忆类型，'conversation'或'knowledge'
            retry_count: 当前重试次数
            
        Returns:
            是否成功生成嵌入
        """
        # 避免重复处理
        if memory_id in self.processing_ids:
            return False
        
        self.processing_ids.add(memory_id)
        
        try:
            # 延迟一段时间后重试
            delay = self.retry_delay * (2 ** retry_count)  # 指数退避
            await asyncio.sleep(delay)
            
            # 获取记忆内容
            content = None
            if memory_type == "conversation":
                query = "SELECT content FROM conversations WHERE id = ?"
            else:  # knowledge
                query = "SELECT content FROM knowledge WHERE id = ?"
            
            result = await self.memory_manager.db.execute_query(query, (memory_id,))
            
            if not result:
                logger.warning(f"未找到记忆: {memory_id}")
                self.processing_ids.remove(memory_id)
                return False
            
            content = result[0][0]
            
            # 生成向量嵌入
            embedding = await self.generate_embedding(content)
            
            if not embedding:
                if retry_count < self.max_retries:
                    self.processing_ids.remove(memory_id)
                    return await self._generate_embedding_later(memory_id, memory_type, retry_count + 1)
                else:
                    logger.error(f"为记忆 {memory_id} 生成嵌入失败，已达到最大重试次数")
                    self.processing_ids.remove(memory_id)
                    return False
            
            # 更新记忆嵌入
            success = await self.memory_manager.update_memory_embedding(
                memory_id=memory_id,
                memory_type=memory_type,
                embedding=embedding
            )
            
            if success:
                logger.debug(f"已为记忆 {memory_id} 生成嵌入")
            else:
                logger.error(f"更新记忆 {memory_id} 的嵌入失败")
            
            self.processing_ids.remove(memory_id)
            return success
        except Exception as e:
            logger.error(f"为记忆 {memory_id} 生成嵌入失败: {e}", exc_info=True)
            
            if retry_count < self.max_retries:
                self.processing_ids.remove(memory_id)
                return await self._generate_embedding_later(memory_id, memory_type, retry_count + 1)
            else:
                logger.error(f"为记忆 {memory_id} 生成嵌入失败，已达到最大重试次数")
                
                if memory_id in self.processing_ids:
                    self.processing_ids.remove(memory_id)
                    
                return False
    
    async def process_pending_embeddings(self, limit: int = None) -> int:
        """
        处理待生成嵌入的记忆
        
        Args:
            limit: 单次处理的最大记录数，如为None则使用配置中的默认值
            
        Returns:
            成功处理的记录数
        """
        if limit is None:
            limit = self.config.get("pending_processing_limit", 100)
        """
        处理待生成嵌入的记忆
        
        Args:
            limit: 单次处理的最大记录数
            
        Returns:
            成功处理的记录数
        """
        # 避免并发处理
        async with self.processing_lock:
            if self.processing:
                logger.debug("已有进程正在处理嵌入，跳过")
                return 0
            
            self.processing = True
        
        try:
            processed_count = 0
            
            # 查询未生成嵌入的对话记忆
            conv_query = """
                SELECT id FROM conversations 
                WHERE embedding_generated = 0
                LIMIT ?
            """
            conv_results = await self.memory_manager.db.execute_query(conv_query, (limit,))
            
            # 处理对话记忆
            conversation_tasks = []
            for row in conv_results:
                memory_id = row[0]
                
                # 避免重复处理
                if memory_id not in self.processing_ids:
                    task = asyncio.create_task(self._generate_embedding_later(memory_id, "conversation"))
                    conversation_tasks.append(task)
            
            # 等待所有对话记忆的嵌入生成完成
            if conversation_tasks:
                results = await asyncio.gather(*conversation_tasks, return_exceptions=True)
                processed_count += sum(1 for r in results if r is True)
            
            # 如果还有处理配额，继续处理知识记忆
            remaining_limit = limit - len(conversation_tasks)
            
            if remaining_limit > 0:
                # 查询未生成嵌入的知识记忆
                know_query = """
                    SELECT id FROM knowledge 
                    WHERE embedding_generated = 0
                    LIMIT ?
                """
                know_results = await self.memory_manager.db.execute_query(know_query, (remaining_limit,))
                
                # 处理知识记忆
                knowledge_tasks = []
                for row in know_results:
                    memory_id = row[0]
                    
                    # 避免重复处理
                    if memory_id not in self.processing_ids:
                        task = asyncio.create_task(self._generate_embedding_later(memory_id, "knowledge"))
                        knowledge_tasks.append(task)
                
                # 等待所有知识记忆的嵌入生成完成
                if knowledge_tasks:
                    results = await asyncio.gather(*knowledge_tasks, return_exceptions=True)
                    processed_count += sum(1 for r in results if r is True)
            
            logger.info(f"处理完成 {processed_count} 条待生成嵌入的记忆")
            return processed_count
        except Exception as e:
            logger.error(f"处理待生成嵌入的记忆失败: {e}", exc_info=True)
            return 0
        finally:
            self.processing = False
    
    async def search_similar_memories(
        self,
        query: str,
        limit: int = 5,
        memory_type: str = "all",
        user_id: str = None,
        session_id: str = None,
        score_threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        搜索与查询语义相似的记忆
        
        Args:
            query: 查询文本
            limit: 返回数量限制
            memory_type: 记忆类型，可选 'all', 'conversation', 'knowledge'
            user_id: 用户ID，用于过滤对话记忆
            session_id: 会话ID，用于过滤对话记忆
            score_threshold: 相似度分数阈值
            
        Returns:
            相似记忆列表
        """
        try:
            # 为查询生成向量嵌入
            query_embedding = await self.generate_embedding(query)
            
            if not query_embedding:
                logger.error("无法为查询生成向量嵌入")
                return []
            
            # 搜索相似记忆
            results = await self.memory_manager.search_similar_memories(
                query_embedding=query_embedding,
                limit=limit,
                memory_type=memory_type,
                user_id=user_id,
                session_id=session_id,
                score_threshold=score_threshold
            )
            
            return results
        except Exception as e:
            logger.error(f"搜索相似记忆失败: {e}", exc_info=True)
            return []
    
    async def start_background_processing(self, interval: int = 300) -> None:
        """
        启动后台嵌入处理任务
        
        Args:
            interval: 处理间隔(秒)
        """
        logger.info(f"启动后台嵌入处理任务，间隔 {interval} 秒")
        
        while True:
            try:
                # 处理待生成嵌入的记忆
                await self.process_pending_embeddings()
                
                # 等待下一个间隔
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                logger.info("后台嵌入处理任务已取消")
                break
            except Exception as e:
                logger.error(f"后台嵌入处理任务发生错误: {e}", exc_info=True)
                await asyncio.sleep(interval)  # 出错时也等待一个间隔 