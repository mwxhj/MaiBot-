#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
请求队列管理器模块，用于管理和处理并发消息请求。

提供以下功能：
1. 基于会话ID的消息队列管理
2. 请求超时处理
3. 空闲队列自动清理
4. 优先级处理支持
5. 异步处理调度
"""

import asyncio
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union, Awaitable

from linjing.utils.logger import get_logger

# 获取日志记录器
logger = get_logger(__name__)


@dataclass
class MessageTask:
    """消息任务类，表示一个消息处理任务"""
    message: Any  # 原始消息对象
    context: Any  # 消息上下文
    processor: Callable  # 处理函数
    created_at: float = 0.0  # 创建时间
    priority: int = 0  # 优先级（值越小优先级越高）
    task_id: str = ""  # 任务ID
    timeout: float = 60.0  # 超时时间（秒）
    status: str = "pending"  # 任务状态：pending, processing, completed, failed, timeout
    result: Any = None  # 处理结果
    error: Optional[Exception] = None  # 处理错误


class ChatStreamQueue:
    """聊天流队列，用于管理特定会话的消息队列"""
    
    def __init__(self, session_id: str, max_size: int = 50, timeout: float = 600.0):
        """
        初始化聊天流队列
        
        Args:
            session_id: 会话ID
            max_size: 队列最大大小
            timeout: 队列超时时间（秒）
        """
        self.session_id = session_id
        self.max_size = max_size
        self.timeout = timeout
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=max_size)
        self.processing = False
        self.last_activity = time.time()
        self.tasks_processed = 0
        self.tasks_failed = 0
        self.processing_task: Optional[asyncio.Task] = None
    
    def is_idle(self, idle_threshold: float = 300.0) -> bool:
        """
        检查队列是否空闲
        
        Args:
            idle_threshold: 空闲阈值（秒）
            
        Returns:
            是否空闲
        """
        return (time.time() - self.last_activity > idle_threshold and 
                self.queue.empty() and not self.processing)
    
    async def add_task(self, task: MessageTask) -> bool:
        """
        添加任务到队列
        
        Args:
            task: 消息任务
            
        Returns:
            是否成功添加
        """
        if self.queue.full():
            logger.warning(f"队列 {self.session_id} 已满，拒绝新任务")
            return False
        
        task.created_at = time.time()
        self.last_activity = time.time()
        
        try:
            self.queue.put_nowait(task)
            logger.debug(f"任务已添加到队列 {self.session_id}，当前队列大小: {self.queue.qsize()}")
            return True
        except asyncio.QueueFull:
            logger.error(f"队列 {self.session_id} 添加任务失败")
            return False
    
    async def process_queue(self) -> None:
        """处理队列中的任务"""
        if self.processing:
            logger.debug(f"队列 {self.session_id} 正在处理中，跳过")
            return
        
        self.processing = True
        logger.info(f"开始处理队列 {self.session_id}，当前队列大小: {self.queue.qsize()}")
        
        try:
            while not self.queue.empty():
                task: MessageTask = await self.queue.get()
                self.last_activity = time.time()
                
                # 检查任务是否超时
                if time.time() - task.created_at > task.timeout:
                    logger.warning(f"任务 {task.task_id} 已超时 ({task.timeout}秒)，跳过处理")
                    task.status = "timeout"
                    task.error = TimeoutError(f"任务处理超时 ({task.timeout}秒)")
                    self.tasks_failed += 1
                    self.queue.task_done()
                    continue
                
                # 处理任务
                try:
                    logger.info(f"处理任务 {task.task_id}，优先级: {task.priority}，创建时间: {task.created_at}")
                    task.status = "processing"
                    
                    # 记录处理开始时间
                    start_time = time.time()
                    
                    # 调用处理函数
                    result = await task.processor(task.message, task.context)
                    
                    # 计算处理时间
                    process_time = time.time() - start_time
                    
                    task.result = result
                    task.status = "completed"
                    self.tasks_processed += 1
                    logger.info(f"任务 {task.task_id} 处理完成，耗时: {process_time:.3f}秒，结果类型: {type(result).__name__}")
                except Exception as e:
                    logger.error(f"处理任务 {task.task_id} 时出错: {e}", exc_info=True)
                    task.status = "failed"
                    task.error = e
                    self.tasks_failed += 1
                finally:
                    self.queue.task_done()
        finally:
            self.processing = False
            logger.info(f"队列 {self.session_id} 处理完成，已处理 {self.tasks_processed} 个任务，失败 {self.tasks_failed} 个")


class QueueManager:
    """请求队列管理器，管理多个会话队列"""
    
    def __init__(
        self,
        max_queues: int = 100,
        max_queue_size: int = 50,
        queue_timeout: float = 600.0,
        idle_cleanup_interval: float = 300.0
    ):
        """
        初始化队列管理器
        
        Args:
            max_queues: 最大队列数量
            max_queue_size: 每个队列的最大大小
            queue_timeout: 队列超时时间（秒）
            idle_cleanup_interval: 空闲队列清理间隔（秒）
        """
        self.max_queues = max_queues
        self.max_queue_size = max_queue_size
        self.queue_timeout = queue_timeout
        self.idle_cleanup_interval = idle_cleanup_interval
        
        self.queues: Dict[str, ChatStreamQueue] = {}
        # 添加队列最后访问时间字典
        self.queue_last_access: Dict[str, float] = {}
        self.queue_lock = asyncio.Lock()
        self.running = False
        self.cleanup_task: Optional[asyncio.Task] = None
        
        self.task_id_counter = 0
        
        logger.info(f"队列管理器初始化，最大队列数: {max_queues}，队列大小: {max_queue_size}")
    
    async def start(self) -> None:
        """启动队列管理器，开始处理消息和清理任务"""
        if self.running:
            logger.warning("队列管理器已经在运行中")
            return
        
        self.running = True
        logger.info(f"启动队列管理器，最大队列数: {self.max_queues}, 每队列最大消息数: {self.max_queue_size}")
        
        # 启动定期状态日志任务
        asyncio.create_task(self._log_status_periodically())
        # 启动定期清理任务
        asyncio.create_task(self._cleanup_periodically())
    
    async def stop(self) -> None:
        """停止队列管理器"""
        if not self.running:
            return
        
        self.running = False
        
        # 取消清理任务
        if self.cleanup_task and not self.cleanup_task.done():
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
        
        logger.info("队列管理器已停止")
    
    async def get_or_create_queue(self, session_id: str) -> ChatStreamQueue:
        """
        获取或创建会话队列
        
        Args:
            session_id: 会话ID
            
        Returns:
            会话队列
        """
        async with self.queue_lock:
            if session_id not in self.queues:
                if len(self.queues) >= self.max_queues:
                    # 移除最不活跃的队列
                    least_active_id = None
                    least_active_time = float('inf')
                    
                    for qid, queue in self.queues.items():
                        if queue.last_activity < least_active_time and queue.queue.empty():
                            least_active_id = qid
                            least_active_time = queue.last_activity
                    
                    if least_active_id:
                        logger.info(f"队列数量达到上限，移除最不活跃的队列: {least_active_id}")
                        del self.queues[least_active_id]
                        # 同时删除最后访问时间记录
                        if least_active_id in self.queue_last_access:
                            del self.queue_last_access[least_active_id]
                    else:
                        logger.warning("队列数量达到上限，且没有可移除的空闲队列")
                        # 返回一个临时队列，不保存到队列字典中
                        return ChatStreamQueue(
                            session_id=session_id,
                            max_size=self.max_queue_size,
                            timeout=self.queue_timeout
                        )
                
                # 创建新队列
                self.queues[session_id] = ChatStreamQueue(
                    session_id=session_id,
                    max_size=self.max_queue_size,
                    timeout=self.queue_timeout
                )
                # 初始化最后访问时间
                self.queue_last_access[session_id] = time.time()
                logger.info(f"创建新队列: {session_id}，当前队列数: {len(self.queues)}")
            else:
                # 更新最后访问时间
                self.queue_last_access[session_id] = time.time()
            
            return self.queues[session_id]
    
    async def add_message(
        self,
        message: Any,
        context: Any,
        processor: Callable,
        priority: int = 0,
        timeout: float = None
    ) -> bool:
        """
        添加消息到队列
        
        Args:
            message: 消息对象
            context: 消息上下文
            processor: 处理函数
            priority: 优先级（值越小优先级越高）
            timeout: 超时时间（秒），如果为None则使用默认值
            
        Returns:
            是否成功添加
        """
        if not self.running:
            logger.warning("队列管理器未启动，无法添加消息")
            return False
        
        # 获取会话ID
        session_id = context.session_id if hasattr(context, 'session_id') else (
            getattr(message, 'session_id', "default")
        )
        
        # 创建任务
        self.task_id_counter += 1
        task_id = f"task_{self.task_id_counter}_{int(time.time())}"
        
        task = MessageTask(
            message=message,
            context=context,
            processor=processor,
            priority=priority,
            task_id=task_id,
            timeout=timeout or self.queue_timeout
        )
        
        # 获取消息ID或其他标识用于日志
        message_id = getattr(message, 'id', id(message))
        logger.info(f"正在将消息 {message_id} 添加到会话 {session_id} 的队列，任务ID: {task_id}，优先级: {priority}")
        
        # 获取或创建队列并更新最后访问时间
        queue = await self.get_or_create_queue(session_id)
        
        # 添加任务到队列
        success = await queue.add_task(task)
        if success:
            logger.info(f"成功将消息 {message_id} 添加到队列 {session_id}，当前队列大小: {queue.queue.qsize()}")
            
            # 启动队列处理
            if queue.processing_task is None or queue.processing_task.done():
                logger.info(f"启动队列 {session_id} 的处理任务")
                queue.processing_task = asyncio.create_task(queue.process_queue())
        else:
            logger.warning(f"未能将消息 {message_id} 添加到队列 {session_id}")
        
        return success
    
    async def cleanup_idle_queues(self) -> None:
        """清理空闲队列"""
        idle_queues = []
        
        try:
            async with self.queue_lock:
                # 查找空闲队列
                for session_id, queue in list(self.queues.items()):
                    if queue.is_idle(self.idle_cleanup_interval):
                        idle_queues.append(session_id)
                
                # 移除空闲队列
                for session_id in idle_queues:
                    logger.info(f"移除空闲队列: {session_id}")
                    del self.queues[session_id]
                    if session_id in self.queue_last_access:
                        del self.queue_last_access[session_id]
            
            if idle_queues:
                logger.info(f"已清理 {len(idle_queues)} 个空闲队列")
            else:
                logger.debug("没有可清理的空闲队列")
        except Exception as e:
            logger.error(f"清理空闲队列时出错: {e}", exc_info=True)
    
    async def get_queue_status(self) -> Dict[str, Any]:
        """
        获取队列状态
        
        Returns:
            队列状态信息
        """
        result = {
            "queue_count": len(self.queues),
            "max_queues": self.max_queues,
            "running": self.running,
            "total_messages": 0,
            "active_queues": 0,
            "queues": {}
        }
        
        async with self.queue_lock:
            for session_id, queue in self.queues.items():
                queue_size = queue.queue.qsize()
                is_active = queue_size > 0 or queue.processing
                
                result["total_messages"] += queue_size
                if is_active:
                    result["active_queues"] += 1
                
                result["queues"][session_id] = {
                    "queue_size": queue_size,
                    "max_size": queue.max_size,
                    "processing": queue.processing,
                    "last_activity": queue.last_activity,
                    "tasks_processed": queue.tasks_processed,
                    "tasks_failed": queue.tasks_failed,
                    "idle": queue.is_idle()
                }
        
        return result
    
    def log_queue_status(self) -> None:
        """记录队列状态"""
        try:
            # 收集基本状态信息
            total_messages = 0
            active_queues = 0
            
            for session_id, queue in self.queues.items():
                queue_size = queue.queue.qsize()
                total_messages += queue_size
                if queue_size > 0 or queue.processing:
                    active_queues += 1
            
            # 记录总体状态摘要
            logger.info(f"队列管理器状态: {active_queues}/{len(self.queues)} 个活跃队列, "
                        f"共 {total_messages} 条待处理消息")
            
            # 详细记录每个非空队列的状态
            if active_queues > 0:
                logger.debug("活跃队列详情:")
                for session_id, queue in self.queues.items():
                    if not queue.queue.empty() or queue.processing:
                        queue_age = time.time() - queue.last_activity 
                        logger.debug(f"  - 会话 {session_id}: {queue.queue.qsize()} 条消息, "
                                    f"闲置时间: {queue_age:.1f}秒, 处理中: {queue.processing}")
            
            # 如果有空闲队列，记录它们的信息
            idle_queues = []
            for session_id, queue in self.queues.items():
                if queue.is_idle(self.idle_cleanup_interval / 2):  # 使用一半的清理间隔作为提前警告
                    idle_time = time.time() - queue.last_activity
                    idle_queues.append((session_id, idle_time))
            
            if idle_queues:
                idle_queues.sort(key=lambda x: x[1], reverse=True)  # 按闲置时间排序
                logger.debug(f"即将清理的闲置队列: {len(idle_queues)} 个")
                for i, (session_id, idle_time) in enumerate(idle_queues[:5]):  # 只显示前5个
                    logger.debug(f"  - 会话 {session_id}: 闲置 {idle_time:.1f}秒")
                
                if len(idle_queues) > 5:
                    logger.debug(f"  ... 以及 {len(idle_queues) - 5} 个其他闲置队列")
        except Exception as e:
            logger.error(f"记录队列状态时出错: {e}", exc_info=True)
    
    async def _log_status_periodically(self) -> None:
        """定期记录队列状态"""
        try:
            while self.running:
                self.log_queue_status()
                # 每10秒记录一次状态
                await asyncio.sleep(10)
        except asyncio.CancelledError:
            logger.info("定期记录队列状态任务已取消")
        except Exception as e:
            logger.error(f"定期记录队列状态任务出错: {e}", exc_info=True)
            
    async def _cleanup_periodically(self) -> None:
        """定期清理闲置队列"""
        try:
            while self.running:
                await self.cleanup_idle_queues()
                # 每30秒检查一次闲置队列
                await asyncio.sleep(30)
        except asyncio.CancelledError:
            logger.info("定期清理队列任务已取消")
        except Exception as e:
            logger.error(f"定期清理队列任务出错: {e}", exc_info=True) 