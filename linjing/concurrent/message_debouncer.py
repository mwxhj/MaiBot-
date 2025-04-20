#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
消息去重与合并处理模块，用于处理快速连续发送的相似消息。

提供以下功能：
1. 消息分组
2. 按批次处理
3. 可配置的合并策略
4. 设置延迟窗口
5. 消息优先级处理
"""

import asyncio
import copy
import hashlib
import json
import logging
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

from linjing.types.message_types import Message
from linjing.utils.logger import get_logger

# 获取日志记录器
logger = get_logger(__name__)


@dataclass
class MessageGroup:
    """消息组，用于合并短时间内的多条消息"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    chat_id: str = ""  # 聊天ID（群聊或私聊ID）
    messages: List[Any] = field(default_factory=list)
    contexts: List[Any] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)
    update_time: float = field(default_factory=time.time)
    ready_for_processing: bool = False  # 是否准备好处理
    processors: List[Callable] = field(default_factory=list)  # 处理函数列表
    user_ids: Set[str] = field(default_factory=set)  # 用户ID集合
    session_ids: Set[str] = field(default_factory=set)  # 会话ID集合
    
    def add_message(self, message: Any, context: Any, processor: Callable) -> None:
        """添加消息到组"""
        self.messages.append(message)
        self.contexts.append(context)
        if processor not in self.processors:
            self.processors.append(processor)
        self.update_time = time.time()
        
        # 提取用户ID和会话ID（如果有）
        if hasattr(message, 'user_id'):
            self.user_ids.add(str(message.user_id))
        if hasattr(context, 'user_id'):
            self.user_ids.add(str(context.user_id))
        
        if hasattr(message, 'session_id'):
            self.session_ids.add(str(message.session_id))
        if hasattr(context, 'session_id'):
            self.session_ids.add(str(context.session_id))
    
    def count(self) -> int:
        """获取消息数量"""
        return len(self.messages)
    
    def should_process(self, max_wait: float, min_count: int, max_count: int) -> bool:
        """判断是否应该处理此消息组"""
        # 如果已标记为待处理，直接返回True
        if self.ready_for_processing:
            return True
            
        now = time.time()
        # 等待时间已超过最大等待时间
        if now - self.start_time >= max_wait:
            return True
        
        # 消息数已达到最大数量
        if self.count() >= max_count:
            return True
        
        # 消息数已达到最小数量且较长时间没有新消息
        if self.count() >= min_count and now - self.update_time >= max_wait / 2:
            return True
        
        return False
    
    def mark_ready(self) -> None:
        """标记为准备好处理"""
        self.ready_for_processing = True
        logger.debug(f"消息组 {self.id} 标记为准备处理，包含 {self.count()} 条消息")
    
    def can_merge(self, message: Any, context: Any) -> bool:
        """
        检查消息是否可以合并到当前分组
        
        Args:
            message: 消息对象
            context: 消息上下文
            
        Returns:
            是否可以合并
        """
        if self.ready_for_processing:
            return False
        
        # 检查用户ID是否一致
        user_id = getattr(message, 'user_id', None) or getattr(context, 'user_id', None)
        if user_id and self.user_ids and str(user_id) not in self.user_ids:
            return False
        
        # 检查会话ID是否一致
        session_id = getattr(message, 'session_id', None) or getattr(context, 'session_id', None)
        if session_id and self.session_ids and str(session_id) not in self.session_ids:
            return False
        
        return True


class MessageDebouncer:
    """消息去重/合并器，合并短时间内的连续消息"""
    
    def __init__(
        self,
        debounce_window: float = 0.5,
        min_messages_to_combine: int = 2,
        max_messages_to_combine: int = 5,
        high_alert_only: bool = True,
        check_interval: float = 0.1
    ):
        """
        初始化消息去重/合并器
        
        Args:
            debounce_window: 合并窗口（秒）
            min_messages_to_combine: 最小合并消息数
            max_messages_to_combine: 最大合并消息数
            high_alert_only: 是否仅在高警戒模式下合并
            check_interval: 检查间隔（秒）
        """
        self.debounce_window = debounce_window
        self.min_messages = min_messages_to_combine
        self.max_messages = max_messages_to_combine
        self.high_alert_only = high_alert_only
        self.check_interval = check_interval
        
        # 会话/聊天ID -> 消息分组
        self.active_groups: Dict[str, MessageGroup] = {}
        self.pending_groups: Dict[str, MessageGroup] = {}
        self.group_lock = asyncio.Lock()
        self.running = False
        self.check_task: Optional[asyncio.Task] = None
        
        # 处理函数
        self.processor: Optional[Callable] = None
        
        logger.info(
            f"消息去重/合并器初始化，窗口: {debounce_window}秒，"
            f"最小消息: {min_messages_to_combine}，"
            f"最大消息: {max_messages_to_combine}，"
            f"高警戒模式专属: {high_alert_only}"
        )
    
    def set_processor(self, processor: Callable) -> None:
        """
        设置消息处理函数
        
        Args:
            processor: 处理函数，接收消息列表和上下文列表作为参数
        """
        self.processor = processor
        logger.info("已设置消息处理函数")
    
    async def start(self) -> None:
        """启动消息去重/合并器"""
        if self.running:
            return
        
        self.running = True
        logger.info(
            f"启动消息合并器，窗口: {self.debounce_window}秒，"
            f"最小消息数: {self.min_messages}，"
            f"最大消息数: {self.max_messages}，"
            f"高警戒模式专属: {self.high_alert_only}"
        )
        
        # 启动检查任务
        self.check_task = asyncio.create_task(self._check_groups())
        
        # 启动状态日志任务，每15秒记录一次
        asyncio.create_task(self.log_group_status(interval=15.0))
        
        logger.info("消息合并器已启动")
    
    async def stop(self) -> None:
        """停止消息去重/合并器"""
        if not self.running:
            return
        
        self.running = False
        
        # 取消检查任务
        if self.check_task and not self.check_task.done():
            self.check_task.cancel()
            try:
                await self.check_task
            except asyncio.CancelledError:
                pass
        
        # 处理所有待处理的分组
        await self._process_pending_groups()
        
        logger.info("消息合并器已停止")
    
    async def process_message(
        self,
        message: Any,
        context: Any,
        processor: Callable = None,
        is_high_alert: bool = False
    ) -> Tuple[bool, Optional[str]]:
        """
        处理消息，尝试合并或直接处理
        
        Args:
            message: 消息对象
            context: 消息上下文
            processor: 处理函数，如不提供则使用默认函数
            is_high_alert: 是否为高警戒模式
            
        Returns:
            (是否处理, 分组ID)
        """
        # 如果是高警戒模式且设置了仅在高警戒模式下合并
        if not is_high_alert and self.high_alert_only:
            # 直接处理消息
            if processor:
                await processor(message, context)
            elif self.processor:
                await self.processor([message], [context])
            else:
                logger.warning("没有可用的处理函数，消息未处理")
                return False, None
            
            return True, None
        
        # 获取聊天/会话ID
        chat_id = self._get_chat_id(message, context)
        
        async with self.group_lock:
            # 检查是否有活跃分组可以合并
            if chat_id in self.active_groups:
                group = self.active_groups[chat_id]
                if group.can_merge(message, context):
                    # 合并到现有分组
                    group.add_message(message, context, processor or self.processor)
                    logger.debug(f"消息已合并到分组 {group.id}，当前消息数: {group.count()}")
                    
                    # 检查是否应该处理该分组
                    if group.should_process(self.debounce_window, self.min_messages, self.max_messages):
                        # 移动到待处理队列
                        self._move_to_pending(chat_id)
                    
                    return False, group.id
            
            # 创建新分组
            group = MessageGroup(chat_id=chat_id)
            group.add_message(message, context, processor or self.processor)
            self.active_groups[chat_id] = group
            logger.debug(f"已创建新分组 {group.id} 用于聊天 {chat_id}")
            
            # 如果是单条消息模式，直接处理
            if self.min_messages > 1:
                return False, group.id
            
            # 如果最小消息数为1，直接处理
            # 移动到待处理队列
            self._move_to_pending(chat_id)
            return False, group.id
    
    def _move_to_pending(self, chat_id: str) -> None:
        """将活跃分组移动到待处理队列"""
        if chat_id in self.active_groups:
            group = self.active_groups.pop(chat_id)
            group.mark_ready()
            self.pending_groups[chat_id] = group
            logger.debug(f"分组 {group.id} 已移动到待处理队列")
    
    async def _check_groups(self) -> None:
        """检查所有活跃分组，将满足条件的移动到待处理队列"""
        try:
            while self.running:
                await self._check_active_groups()
                await self._process_pending_groups()
                await asyncio.sleep(self.check_interval)
        except asyncio.CancelledError:
            logger.info("分组检查任务已取消")
        except Exception as e:
            logger.error(f"分组检查任务出错: {e}", exc_info=True)
    
    async def _check_active_groups(self) -> None:
        """检查所有活跃分组"""
        async with self.group_lock:
            for chat_id in list(self.active_groups.keys()):
                group = self.active_groups[chat_id]
                if group.should_process(self.debounce_window, self.min_messages, self.max_messages):
                    self._move_to_pending(chat_id)
    
    async def _process_pending_groups(self) -> None:
        """处理所有待处理分组"""
        groups_to_process = []
        
        async with self.group_lock:
            # 复制待处理分组列表以避免处理过程中的竞态条件
            groups_to_process = list(self.pending_groups.values())
            self.pending_groups.clear()
        
        # 处理每个分组
        for group in groups_to_process:
            try:
                # 选择处理器（优先使用组内处理器）
                processors = group.processors
                if not processors and self.processor:
                    processors = [self.processor]
                
                if not processors:
                    logger.warning(f"分组 {group.id} 没有可用的处理函数")
                    continue
                
                # 处理分组
                for processor in processors:
                    await self._process_group(group, processor)
            except Exception as e:
                logger.error(f"处理分组 {group.id} 时出错: {e}", exc_info=True)
    
    async def _process_group(self, group: MessageGroup, processor: Callable) -> None:
        """
        处理单个分组
        
        Args:
            group: 消息分组
            processor: 处理函数
        """
        logger.info(f"处理分组 {group.id}，包含 {group.count()} 条消息")
        
        try:
            start_time = time.time()
            await processor(group.messages, group.contexts)
            process_time = time.time() - start_time
            logger.info(f"分组 {group.id} 处理完成，耗时: {process_time:.3f}秒")
        except Exception as e:
            logger.error(f"处理分组 {group.id} 时出错: {e}", exc_info=True)
    
    def get_status(self) -> Dict[str, Any]:
        """
        获取当前状态
        
        Returns:
            状态信息字典
        """
        active_count = len(self.active_groups)
        pending_count = len(self.pending_groups)
        
        active_messages = sum(group.count() for group in self.active_groups.values())
        pending_messages = sum(group.count() for group in self.pending_groups.values())
        
        return {
            "running": self.running,
            "active_groups": active_count,
            "pending_groups": pending_count,
            "active_messages": active_messages,
            "pending_messages": pending_messages,
            "total_groups": active_count + pending_count,
            "total_messages": active_messages + pending_messages,
            "config": {
                "debounce_window": self.debounce_window,
                "min_messages": self.min_messages,
                "max_messages": self.max_messages,
                "high_alert_only": self.high_alert_only,
                "check_interval": self.check_interval
            }
        }
    
    async def log_group_status(self, interval: float = 30.0) -> None:
        """
        定期记录分组状态
        
        Args:
            interval: 记录间隔（秒）
        """
        try:
            while self.running:
                await self._log_detailed_status()
                await asyncio.sleep(interval)
        except asyncio.CancelledError:
            logger.info("分组状态日志任务已取消")
        except Exception as e:
            logger.error(f"分组状态日志任务出错: {e}", exc_info=True)
    
    async def _log_detailed_status(self) -> None:
        """记录详细的分组状态"""
        status = self.get_status()
        
        # 记录基本状态
        logger.info(
            f"消息合并器状态: {status['active_groups']} 个活跃分组, "
            f"{status['pending_groups']} 个待处理分组, "
            f"共 {status['total_messages']} 条消息"
        )
        
        # 如果有活跃分组，记录详情
        if status['active_groups'] > 0:
            async with self.group_lock:
                logger.debug("活跃分组详情:")
                for chat_id, group in self.active_groups.items():
                    age = time.time() - group.start_time
                    idle = time.time() - group.update_time
                    logger.debug(
                        f"  - 分组 {group.id} (聊天 {chat_id}): "
                        f"{group.count()} 条消息, "
                        f"存在时间: {age:.1f}秒, "
                        f"闲置时间: {idle:.1f}秒"
                    )
        
        # 如果有待处理分组，记录详情
        if status['pending_groups'] > 0:
            async with self.group_lock:
                logger.debug("待处理分组详情:")
                for chat_id, group in self.pending_groups.items():
                    age = time.time() - group.start_time
                    logger.debug(
                        f"  - 分组 {group.id} (聊天 {chat_id}): "
                        f"{group.count()} 条消息, "
                        f"存在时间: {age:.1f}秒"
                    )
    
    def _get_chat_id(self, message: Any, context: Any) -> str:
        """
        获取消息的聊天ID
        
        Args:
            message: 消息对象
            context: 消息上下文
            
        Returns:
            聊天ID
        """
        # 尝试从消息和上下文中提取会话ID
        session_id = (
            getattr(message, 'session_id', None) or 
            getattr(context, 'session_id', None)
        )
        if session_id:
            return str(session_id)
            
        # 尝试从消息和上下文中提取对话ID或聊天ID
        chat_id = (
            getattr(message, 'chat_id', None) or 
            getattr(context, 'chat_id', None) or
            getattr(message, 'conversation_id', None) or 
            getattr(context, 'conversation_id', None)
        )
        if chat_id:
            return str(chat_id)
        
        # 尝试从消息和上下文中提取群组ID和用户ID
        group_id = (
            getattr(message, 'group_id', None) or 
            getattr(context, 'group_id', None)
        )
        if group_id:
            return f"group_{group_id}"
        
        user_id = (
            getattr(message, 'user_id', None) or 
            getattr(context, 'user_id', None)
        )
        if user_id:
            return f"user_{user_id}"
        
        # 如果都没有，使用对象ID作为聊天ID
        return f"obj_{id(message)}" 