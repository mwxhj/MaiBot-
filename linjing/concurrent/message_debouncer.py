#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
消息去重/合并器模块，负责合并短时间内的连续消息。

提供以下功能：
1. 短时窗口内的消息合并
2. 消息分组与批处理
3. 高警戒模式（对重要对话不合并）
4. 可配置的合并策略
"""

import asyncio
import time
import uuid
from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from linjing.utils.logger import get_logger

# 获取日志记录器
logger = get_logger(__name__)


class MessageGroup:
    """消息分组，表示一组可以合并的消息"""
    
    def __init__(self, group_id: str = None):
        """
        初始化消息分组
        
        Args:
            group_id: 分组ID，如果为None则自动生成
        """
        self.group_id = group_id or f"group_{uuid.uuid4().hex}"
        self.messages: List[Any] = []
        self.contexts: List[Any] = []
        self.created_at = time.time()
        self.last_update = time.time()
        self.user_ids: Set[str] = set()
        self.session_ids: Set[str] = set()
        self.ready_to_process = False
    
    def add_message(self, message: Any, context: Any) -> None:
        """
        添加消息到分组
        
        Args:
            message: 消息对象
            context: 消息上下文
        """
        self.messages.append(message)
        self.contexts.append(context)
        self.last_update = time.time()
        
        # 提取用户ID和会话ID（如果有）
        if hasattr(message, 'user_id'):
            self.user_ids.add(str(message.user_id))
        if hasattr(context, 'user_id'):
            self.user_ids.add(str(context.user_id))
        
        if hasattr(message, 'session_id'):
            self.session_ids.add(str(message.session_id))
        if hasattr(context, 'session_id'):
            self.session_ids.add(str(context.session_id))
    
    def can_merge(self, message: Any, context: Any) -> bool:
        """
        检查消息是否可以合并到当前分组
        
        Args:
            message: 消息对象
            context: 消息上下文
            
        Returns:
            是否可以合并
        """
        if self.ready_to_process:
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
    
    def should_process(self, window: float, min_messages: int, max_messages: int) -> bool:
        """
        检查分组是否应该被处理
        
        Args:
            window: 时间窗口（秒）
            min_messages: 最小消息数
            max_messages: 最大消息数
            
        Returns:
            是否应该处理
        """
        # 如果已标记为待处理，直接返回True
        if self.ready_to_process:
            return True
        
        # 检查消息数量
        if len(self.messages) >= max_messages:
            return True
        
        # 检查时间窗口
        time_elapsed = time.time() - self.last_update
        if time_elapsed >= window and len(self.messages) >= min_messages:
            return True
        
        return False
    
    def mark_as_ready(self) -> None:
        """标记分组为待处理状态"""
        self.ready_to_process = True
    
    def __len__(self) -> int:
        """获取分组中的消息数量"""
        return len(self.messages)


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
        
        # 会话ID -> 消息分组
        self.active_groups: Dict[str, MessageGroup] = {}
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
        
        # 处理所有剩余的消息分组
        await self._process_all_groups()
        
        logger.info("消息去重/合并器已停止")
    
    async def process_message(
        self,
        message: Any,
        context: Any,
        processor: Callable = None,
        is_high_alert: bool = False
    ) -> Tuple[bool, Optional[str]]:
        """
        处理消息，可能将其合并到现有分组或创建新分组
        
        Args:
            message: 消息对象
            context: 消息上下文
            processor: 处理函数，如果为None则使用设置的处理函数
            is_high_alert: 是否处于高警戒模式
            
        Returns:
            (是否被合并, 分组ID)
        """
        # 获取消息ID或其他标识用于日志
        message_id = getattr(message, 'id', id(message))
        session_id = getattr(context, 'session_id', None) or getattr(message, 'session_id', None)
        user_id = getattr(context, 'user_id', None) or getattr(message, 'user_id', None)
        
        logger.info(f"消息合并器接收到消息 {message_id}，用户: {user_id}，会话: {session_id}，高警戒: {is_high_alert}")
        
        # 如果未启动，直接返回未合并
        if not self.running:
            logger.warning("消息合并器未启动，无法合并消息")
            return False, None
        
        # 如果没有处理函数，直接返回未合并
        if processor is None:
            processor = self.processor
        if processor is None:
            logger.warning("未设置消息处理函数，无法合并消息")
            return False, None
        
        # 如果高警戒模式独占且当前非高警戒，直接返回未合并
        if self.high_alert_only and not is_high_alert:
            logger.info(f"消息 {message_id} 非高警戒模式，跳过合并")
            return False, None
        
        # 获取会话ID
        if not session_id:
            logger.warning(f"消息 {message_id} 未包含会话ID，无法合并")
            return False, None
        
        session_id = str(session_id)
        
        # 尝试合并消息
        async with self.group_lock:
            # 检查是否有匹配的活跃分组
            if session_id in self.active_groups:
                group = self.active_groups[session_id]
                
                if group.can_merge(message, context):
                    group.add_message(message, context)
                    logger.info(f"消息 {message_id} 已合并到分组 {group.group_id}，当前消息数: {len(group)}")
                    
                    # 检查是否应该立即处理
                    if group.should_process(self.debounce_window, self.min_messages, self.max_messages):
                        group.mark_as_ready()
                        logger.info(f"分组 {group.group_id} 已达到处理条件，从活跃分组中移除并处理")
                        # 从活跃分组中移除并处理
                        del self.active_groups[session_id]
                        
                        # 记录处理前的状态
                        logger.info(f"开始处理分组 {group.group_id}，包含 {len(group.messages)} 条消息，时间窗口: {self.debounce_window}秒")
                        asyncio.create_task(self._process_group(group, processor))
                    else:
                        logger.info(f"分组 {group.group_id} 尚未达到处理条件，继续等待更多消息或时间窗口")
                    
                    return True, group.group_id
                else:
                    logger.info(f"消息 {message_id} 无法合并到现有分组 {group.group_id}，创建新分组")
            else:
                logger.info(f"会话 {session_id} 没有活跃分组，创建新分组")
            
            # 如果没有匹配的分组或无法合并，创建新分组
            new_group = MessageGroup()
            new_group.add_message(message, context)
            self.active_groups[session_id] = new_group
            logger.info(f"为会话 {session_id} 创建新分组 {new_group.group_id}，当前包含 1 条消息")
            
            # 如果新分组只有一条消息且满足最小合并条件，需要等待后续消息
            if len(new_group) < self.min_messages:
                logger.info(f"分组 {new_group.group_id} 消息数量不足，等待更多消息，最小消息数要求: {self.min_messages}")
                return True, new_group.group_id
            
            # 否则立即处理
            new_group.mark_as_ready()
            logger.info(f"立即处理新分组 {new_group.group_id}，从活跃分组中移除")
            del self.active_groups[session_id]
            asyncio.create_task(self._process_group(new_group, processor))
            
            return True, new_group.group_id
    
    async def _check_groups(self) -> None:
        """定期检查消息分组，处理超时的分组"""
        logger.info("启动消息分组检查任务")
        
        while self.running:
            try:
                ready_groups = []
                
                async with self.group_lock:
                    # 查找应该处理的分组
                    for session_id, group in list(self.active_groups.items()):
                        if group.should_process(self.debounce_window, self.min_messages, self.max_messages):
                            ready_groups.append((session_id, group))
                    
                    # 从活跃分组中移除并标记为待处理
                    for session_id, group in ready_groups:
                        group.mark_as_ready()
                        del self.active_groups[session_id]
                
                # 处理待处理分组
                for _, group in ready_groups:
                    if self.processor:
                        asyncio.create_task(self._process_group(group, self.processor))
                
                # 等待下一次检查
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                logger.info("消息分组检查任务已取消")
                break
            except Exception as e:
                logger.error(f"检查消息分组时出错: {e}", exc_info=True)
                await asyncio.sleep(1)  # 出错后等待一段时间再重试
    
    async def _process_group(self, group: MessageGroup, processor: Callable) -> None:
        """
        处理消息分组
        
        Args:
            group: 消息分组
            processor: 处理函数
        """
        if len(group.messages) == 0:
            logger.warning(f"分组 {group.group_id} 不包含任何消息，跳过处理")
            return
        
        logger.info(f"开始处理分组 {group.group_id}，包含 {len(group.messages)} 条消息")
        start_time = time.time()
        
        try:
            # 记录分组中的消息IDs用于跟踪
            message_ids = [getattr(m, 'id', id(m)) for m in group.messages]
            user_ids = list(group.user_ids)
            session_ids = list(group.session_ids)
            
            logger.info(f"分组 {group.group_id} 详情: 消息IDs={message_ids}, 用户IDs={user_ids}, 会话IDs={session_ids}")
            
            # 调用处理函数
            await processor(group.messages, group.contexts, self.processor)
            
            # 记录处理耗时
            process_time = time.time() - start_time
            logger.info(f"分组 {group.group_id} 处理完成，耗时: {process_time:.3f}秒")
        except Exception as e:
            logger.error(f"处理分组 {group.group_id} 时出错: {e}", exc_info=True)
    
    async def _process_all_groups(self) -> None:
        """处理所有剩余的消息分组"""
        logger.info("处理所有剩余的消息分组")
        
        async with self.group_lock:
            remaining_groups = list(self.active_groups.values())
            self.active_groups.clear()
        
        if not remaining_groups:
            return
        
        logger.info(f"剩余 {len(remaining_groups)} 个消息分组待处理")
        
        for group in remaining_groups:
            if self.processor and len(group.messages) > 0:
                try:
                    await self._process_group(group, self.processor)
                except Exception as e:
                    logger.error(f"处理剩余消息分组 {group.group_id} 时出错: {e}", exc_info=True)
    
    def get_status(self) -> Dict[str, Any]:
        """
        获取状态信息
        
        Returns:
            状态信息字典
        """
        return {
            "running": self.running,
            "active_groups": len(self.active_groups),
            "debounce_window": self.debounce_window,
            "min_messages": self.min_messages,
            "max_messages": self.max_messages,
            "high_alert_only": self.high_alert_only,
            "processor_set": self.processor is not None
        }

    async def log_group_status(self, interval: float = 30.0):
        """定期记录分组状态信息"""
        logger.info("启动分组状态日志任务")
        
        while self.running:
            try:
                await self._log_detailed_status()
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                logger.info("分组状态日志任务已取消")
                break
            except Exception as e:
                logger.error(f"记录分组状态时出错: {e}", exc_info=True)
                await asyncio.sleep(5)  # 出错后短暂休息再重试
    
    async def _log_detailed_status(self) -> None:
        """记录详细的状态信息"""
        try:
            status = self.get_status()
            
            # 基本状态摘要
            logger.info(
                f"消息合并器状态: 活跃分组数={status['active_groups']}, "
                f"窗口={status['debounce_window']}秒, "
                f"最小消息数={status['min_messages']}, "
                f"最大消息数={status['max_messages']}, "
                f"高警戒专属={status['high_alert_only']}"
            )
            
            # 详细记录每个活跃分组的状态
            async with self.group_lock:
                if not self.active_groups:
                    logger.debug("当前没有活跃的消息分组")
                    return
                
                # 计算一些统计信息
                total_messages = sum(len(group.messages) for group in self.active_groups.values())
                oldest_group_time = min((time.time() - group.created_at) for group in self.active_groups.values())
                avg_group_age = sum((time.time() - group.created_at) for group in self.active_groups.values()) / len(self.active_groups)
                
                logger.info(
                    f"分组统计: 总消息数={total_messages}, "
                    f"最老分组存在时间={oldest_group_time:.1f}秒, "
                    f"平均分组年龄={avg_group_age:.1f}秒"
                )
                
                # 对分组进行排序，先显示更接近处理条件的分组
                sorted_groups = []
                for session_id, group in self.active_groups.items():
                    time_in_window = time.time() - group.last_update
                    progress = min(time_in_window / self.debounce_window, 1.0)
                    message_progress = len(group.messages) / self.min_messages if self.min_messages > 0 else 1.0
                    priority_score = max(progress, message_progress)
                    
                    sorted_groups.append((
                        session_id, 
                        group, 
                        time_in_window,
                        priority_score
                    ))
                
                sorted_groups.sort(key=lambda x: x[3], reverse=True)
                
                # 详细记录前几个高优先级分组
                max_details = min(5, len(sorted_groups))
                if max_details > 0:
                    logger.debug(f"高优先级分组详情 (显示前 {max_details} 个):")
                    
                    for i, (session_id, group, time_in_window, priority) in enumerate(sorted_groups[:max_details]):
                        meets_conditions = group.should_process(self.debounce_window, self.min_messages, self.max_messages)
                        
                        # 计算距离条件的进度
                        time_progress = f"{time_in_window:.1f}/{self.debounce_window}秒"
                        message_count_progress = f"{len(group.messages)}/{self.min_messages}条"
                        
                        logger.debug(
                            f"  {i+1}. 分组 {group.group_id} (会话 {session_id}): "
                            f"消息数={message_count_progress}, "
                            f"时间={time_progress}, "
                            f"优先级得分={priority:.2f}, "
                            f"满足处理条件={meets_conditions}, "
                            f"用户={list(group.user_ids)}"
                        )
                
                # 显示简短摘要
                if len(sorted_groups) > max_details:
                    logger.debug(f"其余 {len(sorted_groups) - max_details} 个分组未显示详情")
        except Exception as e:
            logger.error(f"记录详细状态信息时出错: {e}") 
        if not self.running:
            logger.warning("消息合并器未启动，无法合并消息")
            return False, None
        
        # 如果没有处理函数，直接返回未合并
        if processor is None:
            processor = self.processor
        if processor is None:
            logger.warning("未设置消息处理函数，无法合并消息")
            return False, None
        
        # 如果高警戒模式独占且当前非高警戒，直接返回未合并
        if self.high_alert_only and not is_high_alert:
            logger.info(f"消息 {message_id} 非高警戒模式，跳过合并")
            return False, None
        
        # 获取会话ID
        if not session_id:
            logger.warning(f"消息 {message_id} 未包含会话ID，无法合并")
            return False, None
        
        session_id = str(session_id)
        
        # 尝试合并消息
        async with self.group_lock:
            # 检查是否有匹配的活跃分组
            if session_id in self.active_groups:
                group = self.active_groups[session_id]
                
                if group.can_merge(message, context):
                    group.add_message(message, context)
                    logger.info(f"消息 {message_id} 已合并到分组 {group.group_id}，当前消息数: {len(group)}")
                    
                    # 检查是否应该立即处理
                    if group.should_process(self.debounce_window, self.min_messages, self.max_messages):
                        group.mark_as_ready()
                        logger.info(f"分组 {group.group_id} 已达到处理条件，从活跃分组中移除并处理")
                        # 从活跃分组中移除并处理
                        del self.active_groups[session_id]
                        
                        # 记录处理前的状态
                        logger.info(f"开始处理分组 {group.group_id}，包含 {len(group.messages)} 条消息，时间窗口: {self.debounce_window}秒")
                        asyncio.create_task(self._process_group(group, processor))
                    else:
                        logger.info(f"分组 {group.group_id} 尚未达到处理条件，继续等待更多消息或时间窗口")
                    
                    return True, group.group_id
                else:
                    logger.info(f"消息 {message_id} 无法合并到现有分组 {group.group_id}，创建新分组")
            else:
                logger.info(f"会话 {session_id} 没有活跃分组，创建新分组")
            
            # 如果没有匹配的分组或无法合并，创建新分组
            new_group = MessageGroup()
            new_group.add_message(message, context)
            self.active_groups[session_id] = new_group
            logger.info(f"为会话 {session_id} 创建新分组 {new_group.group_id}，当前包含 1 条消息")
            
            # 如果新分组只有一条消息且满足最小合并条件，需要等待后续消息
            if len(new_group) < self.min_messages:
                logger.info(f"分组 {new_group.group_id} 消息数量不足，等待更多消息，最小消息数要求: {self.min_messages}")
                return True, new_group.group_id
            
            # 否则立即处理
            new_group.mark_as_ready()
            logger.info(f"立即处理新分组 {new_group.group_id}，从活跃分组中移除")
            del self.active_groups[session_id]
            asyncio.create_task(self._process_group(new_group, processor))
            
            return True, new_group.group_id
    
    async def _check_groups(self) -> None:
        """定期检查消息分组，处理超时的分组"""
        logger.info("启动消息分组检查任务")
        
        while self.running:
            try:
                ready_groups = []
                
                async with self.group_lock:
                    # 查找应该处理的分组
                    for session_id, group in list(self.active_groups.items()):
                        if group.should_process(self.debounce_window, self.min_messages, self.max_messages):
                            ready_groups.append((session_id, group))
                    
                    # 从活跃分组中移除并标记为待处理
                    for session_id, group in ready_groups:
                        group.mark_as_ready()
                        del self.active_groups[session_id]
                
                # 处理待处理分组
                for _, group in ready_groups:
                    if self.processor:
                        asyncio.create_task(self._process_group(group, self.processor))
                
                # 等待下一次检查
                await asyncio.sleep(self.check_interval)
            except asyncio.CancelledError:
                logger.info("消息分组检查任务已取消")
                break
            except Exception as e:
                logger.error(f"检查消息分组时出错: {e}", exc_info=True)
                await asyncio.sleep(1)  # 出错后等待一段时间再重试
    
    async def _process_group(self, group: MessageGroup, processor: Callable) -> None:
        """
        处理消息分组
        
        Args:
            group: 消息分组
            processor: 处理函数
        """
        if len(group.messages) == 0:
            logger.warning(f"分组 {group.group_id} 不包含任何消息，跳过处理")
            return
        
        logger.info(f"开始处理分组 {group.group_id}，包含 {len(group.messages)} 条消息")
        start_time = time.time()
        
        try:
            # 记录分组中的消息IDs用于跟踪
            message_ids = [getattr(m, 'id', id(m)) for m in group.messages]
            user_ids = list(group.user_ids)
            session_ids = list(group.session_ids)
            
            logger.info(f"分组 {group.group_id} 详情: 消息IDs={message_ids}, 用户IDs={user_ids}, 会话IDs={session_ids}")
            
            # 调用处理函数
            await processor(group.messages, group.contexts, self.processor)
            
            # 记录处理耗时
            process_time = time.time() - start_time
            logger.info(f"分组 {group.group_id} 处理完成，耗时: {process_time:.3f}秒")
        except Exception as e:
            logger.error(f"处理分组 {group.group_id} 时出错: {e}", exc_info=True)
    
    async def _process_all_groups(self) -> None:
        """处理所有剩余的消息分组"""
        logger.info("处理所有剩余的消息分组")
        
        async with self.group_lock:
            remaining_groups = list(self.active_groups.values())
            self.active_groups.clear()
        
        if not remaining_groups:
            return
        
        logger.info(f"剩余 {len(remaining_groups)} 个消息分组待处理")
        
        for group in remaining_groups:
            if self.processor and len(group.messages) > 0:
                try:
                    await self._process_group(group, self.processor)
                except Exception as e:
                    logger.error(f"处理剩余消息分组 {group.group_id} 时出错: {e}", exc_info=True)
    
    def get_status(self) -> Dict[str, Any]:
        """
        获取状态信息
        
        Returns:
            状态信息字典
        """
        return {
            "running": self.running,
            "active_groups": len(self.active_groups),
            "debounce_window": self.debounce_window,
            "min_messages": self.min_messages,
            "max_messages": self.max_messages,
            "high_alert_only": self.high_alert_only,
            "processor_set": self.processor is not None
        }

    async def log_group_status(self, interval: float = 30.0):
        """定期记录分组状态信息"""
        logger.info("启动分组状态日志任务")
        
        while self.running:
            try:
                await self._log_detailed_status()
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                logger.info("分组状态日志任务已取消")
                break
            except Exception as e:
                logger.error(f"记录分组状态时出错: {e}", exc_info=True)
                await asyncio.sleep(5)  # 出错后短暂休息再重试
    
    async def _log_detailed_status(self) -> None:
        """记录详细的状态信息"""
        try:
            status = self.get_status()
            
            # 基本状态摘要
            logger.info(
                f"消息合并器状态: 活跃分组数={status['active_groups']}, "
                f"窗口={status['debounce_window']}秒, "
                f"最小消息数={status['min_messages']}, "
                f"最大消息数={status['max_messages']}, "
                f"高警戒专属={status['high_alert_only']}"
            )
            
            # 详细记录每个活跃分组的状态
            async with self.group_lock:
                if not self.active_groups:
                    logger.debug("当前没有活跃的消息分组")
                    return
                
                # 计算一些统计信息
                total_messages = sum(len(group.messages) for group in self.active_groups.values())
                oldest_group_time = min((time.time() - group.created_at) for group in self.active_groups.values())
                avg_group_age = sum((time.time() - group.created_at) for group in self.active_groups.values()) / len(self.active_groups)
                
                logger.info(
                    f"分组统计: 总消息数={total_messages}, "
                    f"最老分组存在时间={oldest_group_time:.1f}秒, "
                    f"平均分组年龄={avg_group_age:.1f}秒"
                )
                
                # 对分组进行排序，先显示更接近处理条件的分组
                sorted_groups = []
                for session_id, group in self.active_groups.items():
                    time_in_window = time.time() - group.last_update
                    progress = min(time_in_window / self.debounce_window, 1.0)
                    message_progress = len(group.messages) / self.min_messages if self.min_messages > 0 else 1.0
                    priority_score = max(progress, message_progress)
                    
                    sorted_groups.append((
                        session_id, 
                        group, 
                        time_in_window,
                        priority_score
                    ))
                
                sorted_groups.sort(key=lambda x: x[3], reverse=True)
                
                # 详细记录前几个高优先级分组
                max_details = min(5, len(sorted_groups))
                if max_details > 0:
                    logger.debug(f"高优先级分组详情 (显示前 {max_details} 个):")
                    
                    for i, (session_id, group, time_in_window, priority) in enumerate(sorted_groups[:max_details]):
                        meets_conditions = group.should_process(self.debounce_window, self.min_messages, self.max_messages)
                        
                        # 计算距离条件的进度
                        time_progress = f"{time_in_window:.1f}/{self.debounce_window}秒"
                        message_count_progress = f"{len(group.messages)}/{self.min_messages}条"
                        
                        logger.debug(
                            f"  {i+1}. 分组 {group.group_id} (会话 {session_id}): "
                            f"消息数={message_count_progress}, "
                            f"时间={time_progress}, "
                            f"优先级得分={priority:.2f}, "
                            f"满足处理条件={meets_conditions}, "
                            f"用户={list(group.user_ids)}"
                        )
                
                # 显示简短摘要
                if len(sorted_groups) > max_details:
                    logger.debug(f"其余 {len(sorted_groups) - max_details} 个分组未显示详情")
        except Exception as e:
            logger.error(f"记录详细状态信息时出错: {e}") 
# -*- coding: utf-8 -*-

"""
消息去重/合并器，用于实现消息的去重和合并处理。
实现辅助策略：Debouncing/Throttling
"""

import asyncio
import time
import uuid
from typing import Dict, List, Any, Set, Callable, Awaitable, Optional, Tuple
from dataclasses import dataclass, field
from collections import deque

from linjing.utils.logger import get_logger

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
    
    def add_message(self, message: Any, context: Any, processor: Callable) -> None:
        """添加消息到组"""
        self.messages.append(message)
        self.contexts.append(context)
        if processor not in self.processors:
            self.processors.append(processor)
        self.update_time = time.time()
    
    def count(self) -> int:
        """获取消息数量"""
        return len(self.messages)
    
    def should_process(self, max_wait: float, min_count: int, max_count: int) -> bool:
        """判断是否应该处理此消息组"""
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

class MessageDebouncer:
    """
    消息去重/合并器，将短时间内的多条消息合并为一个任务
    """
    def __init__(self, 
                debounce_window: float = 0.5,  # 去重窗口时间，单位秒
                min_messages_to_combine: int = 2,  # 最小合并消息数
                max_messages_to_combine: int = 5,  # 最大合并消息数
                high_alert_only: bool = True,  # 仅高警戒模式下合并
                check_interval: float = 0.1):  # 检查间隔，单位秒
        self.debounce_window = debounce_window
        self.min_messages_to_combine = min_messages_to_combine
        self.max_messages_to_combine = max_messages_to_combine
        self.high_alert_only = high_alert_only
        self.check_interval = check_interval
        
        self.active_groups: Dict[str, MessageGroup] = {}  # 活跃的消息组
        self.pending_groups: Dict[str, MessageGroup] = {}  # 等待处理的消息组
        self.lock = asyncio.Lock()  # 并发锁
        self.check_task = None  # 检查任务
        
        self.next_processor: Optional[Callable[[List[Any], List[Any], Callable], Awaitable[Any]]] = None
    
    def set_processor(self, processor: Callable[[List[Any], List[Any], Callable], Awaitable[Any]]) -> None:
        """设置下一步处理器"""
        self.next_processor = processor
    
    async def start(self) -> None:
        """启动消息去重器"""
        logger.info("启动消息去重/合并器")
        if self.check_task is None:
            self.check_task = asyncio.create_task(self._check_groups())
    
    async def stop(self) -> None:
        """停止消息去重器"""
        logger.info("停止消息去重/合并器")
        if self.check_task:
            self.check_task.cancel()
            try:
                await self.check_task
            except asyncio.CancelledError:
                pass
            self.check_task = None
    
    async def process_message(self, 
                             message: Any, 
                             context: Any, 
                             processor: Callable, 
                             is_high_alert: bool = False) -> Tuple[bool, str]:
        """
        处理消息，决定是立即处理还是合并处理
        
        Args:
            message: 消息对象
            context: 消息上下文
            processor: 处理函数
            is_high_alert: 是否处于高警戒模式
            
        Returns:
            (是否被合并, 消息组ID)
        """
        # 如果仅在高警戒模式下合并，但当前不是高警戒模式，则直接处理
        if self.high_alert_only and not is_high_alert:
            return False, ""
        
        # 获取聊天ID
        chat_id = self._get_chat_id(message, context)
        if not chat_id:
            return False, ""
        
        async with self.lock:
            # 检查是否有活跃的消息组
            if chat_id in self.active_groups:
                group = self.active_groups[chat_id]
                group.add_message(message, context, processor)
                logger.debug(f"将消息添加到现有消息组 {group.id}，当前组内消息数: {group.count()}")
                
                # 检查是否达到处理条件
                if group.should_process(
                    max_wait=self.debounce_window,
                    min_count=self.min_messages_to_combine,
                    max_count=self.max_messages_to_combine
                ):
                    self._move_to_pending(chat_id)
                
                return True, group.id
            else:
                # 创建新的消息组
                group = MessageGroup(chat_id=chat_id)
                group.add_message(message, context, processor)
                self.active_groups[chat_id] = group
                logger.debug(f"创建新的消息组 {group.id} 并添加消息")
                return True, group.id
    
    def _move_to_pending(self, chat_id: str) -> None:
        """将活跃消息组移动到待处理队列"""
        if chat_id in self.active_groups:
            group = self.active_groups.pop(chat_id)
            group.mark_ready()
            self.pending_groups[group.id] = group
            logger.debug(f"消息组 {group.id} 已移至待处理队列")
    
    async def _check_groups(self) -> None:
        """定期检查消息组，将达到条件的组移至待处理队列"""
        try:
            while True:
                await asyncio.sleep(self.check_interval)
                await self._check_active_groups()
                await self._process_pending_groups()
        except asyncio.CancelledError:
            logger.info("消息组检查任务已取消")
            raise
        except Exception as e:
            logger.error(f"消息组检查任务异常: {e}", exc_info=True)
    
    async def _check_active_groups(self) -> None:
        """检查活跃消息组"""
        async with self.lock:
            # 检查所有活跃消息组，将达到条件的移至待处理队列
            for chat_id in list(self.active_groups.keys()):
                group = self.active_groups[chat_id]
                if group.should_process(
                    max_wait=self.debounce_window,
                    min_count=self.min_messages_to_combine,
                    max_count=self.max_messages_to_combine
                ):
                    self._move_to_pending(chat_id)
    
    async def _process_pending_groups(self) -> None:
        """处理待处理消息组"""
        async with self.lock:
            pending_ids = list(self.pending_groups.keys())
        
        for group_id in pending_ids:
            async with self.lock:
                if group_id in self.pending_groups:
                    group = self.pending_groups.pop(group_id)
                else:
                    continue
            
            # 处理消息组
            if self.next_processor and group.count() > 0:
                try:
                    logger.info(f"处理消息组 {group.id}，包含 {group.count()} 条消息")
                    # 只使用第一个处理器，因为所有消息应该使用相同的处理流程
                    processor = group.processors[0] if group.processors else None
                    if processor:
                        await self.next_processor(group.messages, group.contexts, processor)
                    else:
                        logger.warning(f"消息组 {group.id} 没有处理器")
                except Exception as e:
                    logger.error(f"处理消息组 {group.id} 时出错: {e}", exc_info=True)
    
    def _get_chat_id(self, message: Any, context: Any) -> str:
        """从消息或上下文中获取聊天ID"""
        # 尝试从消息对象获取
        if hasattr(message, 'group_id') and message.group_id:
            return f"group_{message.group_id}"
        elif hasattr(message, 'user_id') and message.user_id:
            return f"private_{message.user_id}"
        
        # 尝试从消息元数据中获取
        meta = getattr(message, 'meta', {}) or {}
        group_id = meta.get('group_id')
        if group_id:
            return f"group_{group_id}"
        
        user_id = meta.get('user_id')
        if user_id:
            return f"private_{user_id}"
        
        # 尝试从上下文获取
        if hasattr(context, 'get_group_id'):
            group_id = context.get_group_id()
            if group_id:
                return f"group_{group_id}"
        
        if hasattr(context, 'get_user_id'):
            user_id = context.get_user_id()
            if user_id:
                return f"private_{user_id}"
        
        # 如果无法确定，使用消息ID作为备用
        msg_id = getattr(message, 'id', None) or str(id(message))
        return f"unknown_{msg_id}" 