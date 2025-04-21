#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
请求队列管理器模块，用于管理和处理并发请求。

提供以下功能：
1. 基于类型的资源隔离
2. 优先级队列管理
3. 请求超时与取消
4. 资源限制与自动回收
5. 详细的运行状态监控
6. 向后兼容的会话ID队列支持
"""

import asyncio
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, List, Optional, Set, Tuple, Union, TypeVar, Generic
from loguru import logger

from linjing.processors.message_context import MessageContext
from linjing.utils.logger import get_logger
from .typed_request_queue import TypedRequestQueue as ExternalTypedRequestQueue

# 获取日志记录器
logger = get_logger(__name__)

# 定义类型变量用于泛型
T = TypeVar('T')  # 请求类型
R = TypeVar('R')  # 结果类型


class RequestStatus(Enum):
    """请求状态枚举"""
    PENDING = "pending"         # 等待中
    PROCESSING = "processing"   # 处理中
    COMPLETED = "completed"     # 已完成
    FAILED = "failed"           # 失败
    CANCELLED = "cancelled"     # 已取消
    TIMEOUT = "timeout"         # 超时


class RequestQueueType(Enum):
    """请求队列类型枚举"""
    DEFAULT = "default"         # 默认队列
    MESSAGE = "message"         # 消息处理队列
    API = "api"                 # API调用队列
    DATABASE = "database"       # 数据库操作队列
    MEDIA = "media"             # 媒体处理队列
    FILE = "file"               # 文件操作队列
    NETWORK = "network"         # 网络请求队列
    SESSION = "session"         # 会话队列（用于兼容旧版本）


@dataclass
class RequestTask(Generic[T, R]):
    """请求任务，表示一个待处理的请求"""
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    request_type: RequestQueueType = RequestQueueType.DEFAULT
    data: T = None                                  # 请求数据
    metadata: Dict[str, Any] = field(default_factory=dict)  # 元数据
    created_at: float = field(default_factory=time.time)    # 创建时间
    started_at: float = 0.0                         # 开始处理时间
    completed_at: float = 0.0                       # 完成时间
    priority: int = 0                               # 优先级（值越小优先级越高）
    timeout: float = 60.0                           # 超时时间（秒）
    status: RequestStatus = RequestStatus.PENDING   # 请求状态
    result: Optional[R] = None                      # 处理结果
    error: Optional[Exception] = None               # 处理错误
    processor: Optional[Callable[[T], Awaitable[R]]] = None  # 处理函数
    future: Optional[asyncio.Future] = None         # 用于存储结果的Future

    def __post_init__(self):
        """初始化后处理"""
        if self.future is None:
            self.future = asyncio.Future()
    
    @property
    def elapsed_time(self) -> float:
        """获取请求已经花费的时间（秒）"""
        if self.status == RequestStatus.PENDING:
            return time.time() - self.created_at
        elif self.status == RequestStatus.PROCESSING:
            return time.time() - self.started_at
        elif self.status in (RequestStatus.COMPLETED, RequestStatus.FAILED, 
                            RequestStatus.CANCELLED, RequestStatus.TIMEOUT):
            return self.completed_at - self.created_at
        return 0.0
    
    def has_timed_out(self) -> bool:
        """检查请求是否已超时"""
        if self.status in (RequestStatus.COMPLETED, RequestStatus.FAILED, 
                          RequestStatus.CANCELLED, RequestStatus.TIMEOUT):
            return False
        
        if self.status == RequestStatus.PENDING:
            return time.time() - self.created_at > self.timeout
        
        return time.time() - self.started_at > self.timeout
    
    def mark_started(self) -> None:
        """标记请求开始处理"""
        self.status = RequestStatus.PROCESSING
        self.started_at = time.time()
    
    def mark_completed(self, result: R) -> None:
        """标记请求完成"""
        self.status = RequestStatus.COMPLETED
        self.completed_at = time.time()
        self.result = result
        if not self.future.done():
            self.future.set_result(result)
    
    def mark_failed(self, error: Exception) -> None:
        """标记请求失败"""
        self.status = RequestStatus.FAILED
        self.completed_at = time.time()
        self.error = error
        if not self.future.done():
            self.future.set_exception(error)
    
    def mark_cancelled(self) -> None:
        """标记请求被取消"""
        self.status = RequestStatus.CANCELLED
        self.completed_at = time.time()
        if not self.future.done():
            self.future.cancel()
    
    def mark_timeout(self) -> None:
        """标记请求超时"""
        self.status = RequestStatus.TIMEOUT
        self.completed_at = time.time()
        error = asyncio.TimeoutError(f"Request timed out after {self.timeout} seconds")
        self.error = error
        if not self.future.done():
            self.future.set_exception(error)


class RequestQueueManager:
    """
    请求队列管理器，管理不同类型的请求队列
    """
    
    def __init__(
        self,
        max_queues_per_type: int = 10,
        default_queue_size: int = 100,
        default_concurrent: int = 5,
        default_timeout: float = 60.0,
        idle_cleanup_interval: float = 300.0,
        event_bus: Optional[Any] = None
    ):
        """
        初始化请求队列管理器
        
        Args:
            max_queues_per_type: 每种类型的最大队列数
            default_queue_size: 默认队列大小
            default_concurrent: 默认并发数
            default_timeout: 默认超时时间（秒）
            idle_cleanup_interval: 空闲队列清理间隔（秒）
            event_bus: 事件总线实例 (可选)
        """
        self.max_queues_per_type = max_queues_per_type
        self.default_queue_size = default_queue_size
        self.default_concurrent = default_concurrent
        self.default_timeout = default_timeout
        self.idle_cleanup_interval = idle_cleanup_interval
        self.event_bus = event_bus
        
        # 队列类型 -> 队列实例字典
        self.queues: Dict[RequestQueueType, ExternalTypedRequestQueue] = {}
        
        # 会话ID -> 会话队列字典（用于兼容旧版本）
        self.session_queues: Dict[str, ExternalTypedRequestQueue] = {}
        
        # 类型特定的配置
        self.type_config: Dict[RequestQueueType, Dict[str, Any]] = {
            RequestQueueType.DEFAULT: {
                "max_size": default_queue_size,
                "max_concurrent": default_concurrent
            },
            RequestQueueType.MESSAGE: {
                "max_size": default_queue_size * 2,
                "max_concurrent": 10
            },
            RequestQueueType.API: {
                "max_size": default_queue_size,
                "max_concurrent": 20
            },
            RequestQueueType.DATABASE: {
                "max_size": default_queue_size,
                "max_concurrent": 15
            },
            RequestQueueType.MEDIA: {
                "max_size": 50,
                "max_concurrent": 3
            },
            RequestQueueType.FILE: {
                "max_size": 50,
                "max_concurrent": 5
            },
            RequestQueueType.NETWORK: {
                "max_size": default_queue_size * 2,
                "max_concurrent": 25
            },
            RequestQueueType.SESSION: {
                "max_size": 50,
                "max_concurrent": 1  # 会话队列按顺序处理
            }
        }
        
        self.manager_lock = asyncio.Lock()
        self.running = False
        self.cleanup_task: Optional[asyncio.Task] = None
        self.status_log_task: Optional[asyncio.Task] = None
        
        # 用于兼容旧版本的任务ID计数器
        self.task_id_counter = 0
        
        logger.info(
            f"初始化请求队列管理器，每类型最大队列数: {max_queues_per_type}，"
            f"默认队列大小: {default_queue_size}，默认并发数: {default_concurrent}"
        )
    
    async def start(self) -> None:
        """启动队列管理器"""
        if self.running:
            logger.warning("请求队列管理器已经在运行中")
            return
        
        self.running = True
        logger.info("启动请求队列管理器")
        
        # 启动清理任务
        self.cleanup_task = asyncio.create_task(self._cleanup_periodically())
        
        # 启动状态日志任务
        self.status_log_task = asyncio.create_task(self._log_status_periodically())
        
        logger.info("请求队列管理器已启动")
    
    async def stop(self) -> None:
        """停止队列管理器"""
        if not self.running:
            logger.warning("请求队列管理器未运行")
            return
        
        self.running = False
        logger.info("正在停止请求队列管理器")
        
        # 取消清理任务
        if self.cleanup_task and not self.cleanup_task.done():
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
        
        # 取消状态日志任务
        if self.status_log_task and not self.status_log_task.done():
            self.status_log_task.cancel()
            try:
                await self.status_log_task
            except asyncio.CancelledError:
                pass
        
        logger.info("请求队列管理器已停止")
    
    async def get_queue(self, queue_type: RequestQueueType) -> ExternalTypedRequestQueue:
        """
        获取指定类型的队列
        
        Args:
            queue_type: 队列类型
            
        Returns:
            类型化请求队列
        """
        async with self.manager_lock:
            if queue_type not in self.queues:
                # 创建新队列
                config = self.type_config.get(queue_type, {})
                max_size = config.get("max_size", self.default_queue_size)
                max_concurrent = config.get("max_concurrent", self.default_concurrent)
                
                queue = ExternalTypedRequestQueue(
                    queue_type=queue_type,
                    max_size=max_size,
                    max_concurrent=max_concurrent,
                    default_timeout=self.default_timeout,
                    event_bus=self.event_bus
                )
                
                self.queues[queue_type] = queue
                logger.info(f"创建 {queue_type.value} 队列 (使用外部实现)，最大大小: {max_size}，最大并发: {max_concurrent}")
            
            return self.queues[queue_type]
    
    async def get_session_queue(self, session_id: str) -> ExternalTypedRequestQueue:
        """
        获取指定会话ID的队列（用于兼容旧版本）
        
        Args:
            session_id: 会话ID
            
        Returns:
            类型化请求队列
        """
        async with self.manager_lock:
            if session_id not in self.session_queues:
                # 创建新会话队列
                config = self.type_config.get(RequestQueueType.SESSION, {})
                max_size = config.get("max_size", 50)
                max_concurrent = config.get("max_concurrent", 1)
                
                queue = ExternalTypedRequestQueue(
                    queue_type=RequestQueueType.SESSION,
                    max_size=max_size,
                    max_concurrent=max_concurrent,
                    default_timeout=self.default_timeout,
                    event_bus=self.event_bus
                )
                
                self.session_queues[session_id] = queue
                logger.info(f"创建会话队列 {session_id} (使用外部实现)，最大大小: {max_size}，最大并发: {max_concurrent}")
            
            return self.session_queues[session_id]
    
    async def add_request(
        self,
        queue_type: RequestQueueType,
        data: Any,
        processor: Callable,
        priority: int = 0,
        timeout: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> RequestTask:
        """
        添加请求到指定类型的队列
        
        Args:
            queue_type: 队列类型
            data: 请求数据
            processor: 处理函数
            priority: 优先级（值越小优先级越高）
            timeout: 超时时间（秒）
            metadata: 请求元数据
            
        Returns:
            请求任务对象
        """
        queue = await self.get_queue(queue_type)
        return await queue.add_request(
            data=data,
            processor=processor,
            priority=priority,
            timeout=timeout,
            metadata=metadata
        )
    
    async def cancel_request(self, queue_type: RequestQueueType, request_id: str) -> bool:
        """
        取消指定队列中的请求
        
        Args:
            queue_type: 队列类型
            request_id: 请求ID
            
        Returns:
            是否成功取消
        """
        if queue_type not in self.queues:
            logger.warning(f"队列类型 {queue_type.value} 不存在")
            return False
        
        return await self.queues[queue_type].cancel_request(request_id)
    
    async def get_status(self) -> Dict[str, Any]:
        """
        获取所有队列的状态
        
        Returns:
            状态字典
        """
        status = {
            "total_queues": len(self.queues) + len(self.session_queues),
            "running": self.running,
            "queues": {},
            "session_queues": {}
        }
        
        for queue_type, queue in self.queues.items():
            status["queues"][queue_type.value] = queue.get_status()
        
        for session_id, queue in self.session_queues.items():
            status["session_queues"][session_id] = queue.get_status()
        
        return status
    
    def log_queue_status(self) -> None:
        """记录所有队列状态"""
        total_pending = 0
        total_processing = 0
        
        # 普通队列状态
        for queue_type, queue in self.queues.items():
            queue_status = queue.get_status()
            queue_size = queue_status["queue_size"]
            processing = queue_status["processing"]
            total_pending += queue_size
            total_processing += processing
            
            logger.info(
                f"队列状态 - {queue_type.value}: 等待 {queue_size}，处理中 {processing}，"
                f"已处理 {queue_status['tasks_processed']}，失败 {queue_status['tasks_failed']}，"
                f"超时 {queue_status['tasks_timed_out']}，取消 {queue_status['tasks_cancelled']}"
            )
        
        # 会话队列状态
        if self.session_queues:
            session_pending = 0
            session_processing = 0
            
            for session_id, queue in self.session_queues.items():
                queue_status = queue.get_status()
                session_pending += queue_status["queue_size"]
                session_processing += queue_status["processing"]
            
            total_pending += session_pending
            total_processing += session_processing
            
            logger.info(
                f"会话队列状态 - 共 {len(self.session_queues)} 个会话: "
                f"等待 {session_pending}，处理中 {session_processing}"
            )
        
        logger.info(f"总体队列状态: 等待请求 {total_pending}，处理中请求 {total_processing}")
    
    async def cleanup_idle_queues(self) -> None:
        """清理空闲队列"""
        async with self.manager_lock:
            # 清理普通队列
            idle_queues = []
            for queue_type, queue in self.queues.items():
                if queue.is_idle(idle_threshold=self.idle_cleanup_interval):
                    idle_queues.append(queue_type)
            
            for queue_type in idle_queues:
                logger.info(f"清理空闲队列: {queue_type.value}")
                del self.queues[queue_type]
            
            # 清理会话队列
            idle_sessions = []
            for session_id, queue in self.session_queues.items():
                if queue.is_idle(idle_threshold=self.idle_cleanup_interval):
                    idle_sessions.append(session_id)
            
            for session_id in idle_sessions:
                logger.info(f"清理空闲会话队列: {session_id}")
                del self.session_queues[session_id]
    
    async def _cleanup_periodically(self) -> None:
        """定期清理空闲队列"""
        while self.running:
            try:
                await asyncio.sleep(self.idle_cleanup_interval)
                await self.cleanup_idle_queues()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"清理空闲队列时出错: {e}", exc_info=True)
    
    async def _log_status_periodically(self) -> None:
        """定期记录队列状态"""
        while self.running:
            try:
                await asyncio.sleep(30.0)  # 每30秒记录一次
                self.log_queue_status()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"记录队列状态时出错: {e}", exc_info=True)

    # 以下方法用于向后兼容旧版的QueueManager

    async def get_or_create_queue(self, session_id: str) -> ExternalTypedRequestQueue:
        """
        获取或创建会话队列（兼容旧版本）
        
        Args:
            session_id: 会话ID
            
        Returns:
            会话队列
        """
        return await self.get_session_queue(session_id)
    
    async def add_message(
        self,
        message: Any,
        context: Any,
        processor: Callable,
        priority: int = 0,
        timeout: float = None
    ) -> bool:
        """
        将消息添加到会话队列中进行处理（兼容旧版本）。

        Args:
            message: 原始消息对象
            context: 消息上下文
            processor: 处理函数 (期望接收 context 作为参数)
            priority: 优先级
            timeout: 超时时间（秒）

        Returns:
            是否成功添加
        """
        logger.debug(f"--- QueueManager.add_message START --- Context: {context}") # 新增日志
        if not message:
            logger.error("Context does not contain a message object.")
            return False

        platform = message.get_meta("platform", "unknown")
        session_id = context.session_id # <--- 修改这里
        if not session_id:
            # ... (尝试从 message 获取 session_id 的逻辑应该保留) ...
            session_id_from_msg = None
            if hasattr(message, 'get_session_id'):
                session_id_from_msg = message.get_session_id()
            session_id = session_id_from_msg or f"default_session_{context.user_id}" # 使用 context.user_id
            logger.warning(f"Could not determine session_id from context, using derived default: {session_id}")

        logger.debug(f"Determined platform: {platform}, session_id: {session_id}") # 新增日志

        # 收集元数据用于发送
        send_metadata = {
            "user_id": message.get_user_id(),
            "group_id": message.get_meta("group_id"),
            "message_type": message.get_meta("message_type", "unknown"),
            "platform": platform,
            "original_message": message # 保留原始消息对象用于潜在的回复引用等
        }
        logger.debug(f"Collected send_metadata: {send_metadata}") # 新增日志

        # 包装处理器以传递 send_metadata
        async def processor_wrapper(msg_data): # processor 在这里是闭包变量
            logger.debug(f"--- processor_wrapper START --- Received data type: {type(msg_data)}, value: {msg_data}") # 新增日志
            # 检查传入的数据是否是预期的 MessageContext
            if not isinstance(msg_data, MessageContext):
                logger.error(f"processor_wrapper received unexpected data type: {type(msg_data)}. Expected MessageContext.")
                return None # 或者抛出异常
            
            # --- 修正：直接使用外部作用域捕获的 processor ---
            # 移除: processor = msg_data.get_processor()
            if not processor: # 检查捕获的 processor 是否有效
                 logger.error("Actual processor function (captured) is None or invalid.")
                 return None
            # --- 修正结束 ---

            try:
                # --- 使用捕获的 processor --- 
                logger.debug(f"Calling actual processor: {processor.__name__}") # 新增日志
                reply = await processor(msg_data) # 传递完整的 context
                logger.debug(f"Processor {processor.__name__} finished. Reply: {reply}") # 新增日志
                # --- 修改结束 --- 
                return reply
            except Exception as e:
                 # --- 使用捕获的 processor 记录日志 --- 
                logger.error(f"Error executing processor {processor.__name__}: {e}", exc_info=True)
                 # --- 修改结束 --- 
                return None # 处理失败
            finally:
                 logger.debug(f"--- processor_wrapper END ---") # 新增日志

        # 对于消息处理，我们总是使用 SESSION 类型的队列
        queue_type = RequestQueueType.SESSION
        logger.debug(f"Determined queue_type: {queue_type}") # 现在会打印 RequestQueueType.SESSION

        # 根据正确的 queue_type 确定 queue_key
        queue_key = session_id if queue_type == RequestQueueType.SESSION else "global_resource_queue"
        logger.debug(f"Determined queue_key: {queue_key}") # 现在应该会打印 session_id

        try:
            logger.debug(f"Attempting to call _add_to_queue for key: {queue_key}")
            # 传递正确的 queue_type 枚举值
            await self._add_to_queue(queue_type, queue_key, context, processor_wrapper, send_metadata)
            logger.debug(f"--- QueueManager.add_message END (Success) --- for key: {queue_key}")
            return True
        except Exception as e:
            logger.error(f"Failed to add message to queue {queue_key}: {e}", exc_info=True)
            logger.debug(f"--- QueueManager.add_message END (Failure) --- for key: {queue_key}")
            return False

    async def _add_to_queue(self, queue_type: RequestQueueType, key: str, data: Any, processor: Callable, send_metadata: Dict[str, Any]):
        logger.debug(f"--- QueueManager._add_to_queue START --- Type: {queue_type}, Key: {key}")
        # --- 修正：根据 queue_type 选择正确的队列字典 ---
        queues = self.session_queues if queue_type == RequestQueueType.SESSION else self.queues

        if key not in queues:
            logger.info(f"Creating new queue for type {queue_type}, key {key}")
            # --- 修正：从 type_config 获取配置 ---
            queue_config = self.type_config.get(queue_type, {}) # 使用正确的 queue_type 获取配置
            max_size = queue_config.get("max_size", self.default_queue_size) # 使用 queue_config
            num_workers = queue_config.get("max_concurrent", self.default_concurrent) # 使用 queue_config
            logger.debug(f"Queue config for {key}: max_size={max_size}, num_workers={num_workers}")

            # --- 确保实例化 ExternalTypedRequestQueue 并传递正确的 queue_type ---
            try:
                queues[key] = ExternalTypedRequestQueue(
                    queue_type=queue_type, # 传递正确的枚举值
                    event_bus=self.event_bus,
                    max_size=max_size,
                    num_workers=num_workers
                )
                await queues[key].start_workers() # 启动工作协程
            except TypeError as te: # 捕获可能的 TypeError，提供更详细信息
                 logger.error(f"Error instantiating ExternalTypedRequestQueue for key {key}: {te}. Check constructor arguments.", exc_info=True)
                 raise # 重新抛出异常，以便外层能捕获到
            except Exception as e:
                 logger.error(f"Unexpected error creating queue for key {key}: {e}", exc_info=True)
                 raise

        queue = queues[key]
        logger.debug(f"Adding task to queue {key}. Current queue size: {queue.queue.qsize()}")
        await queue.add_task(processor=processor, data=data, send_metadata=send_metadata)
        logger.debug(f"--- QueueManager._add_to_queue END --- Task added to queue {key}")

    async def get_queue_status(self) -> Dict[str, Any]:
        """获取队列状态（兼容旧版本）"""
        status = await self.get_status()
        
        # 转换为旧格式
        legacy_status = {
            'total_queues': status['total_queues'],
            'running': status['running'],
            'queues': {}
        }
        
        # 添加普通队列状态
        for queue_type, queue_info in status['queues'].items():
            legacy_status['queues'][queue_type] = {
                'size': queue_info['queue_size'],
                'processing': queue_info['processing'] > 0,
                'processed': queue_info['tasks_processed'],
                'failed': queue_info['tasks_failed']
            }
        
        # 添加会话队列状态
        for session_id, queue_info in status['session_queues'].items():
            legacy_status['queues'][f"session_{session_id}"] = {
                'size': queue_info['queue_size'],
                'processing': queue_info['processing'] > 0,
                'processed': queue_info['tasks_processed'],
                'failed': queue_info['tasks_failed']
            }
        
        return legacy_status


# 为向后兼容性提供的旧类名映射
@dataclass
class MessageTask:
    """消息任务类（兼容旧版本）"""
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
    """
    聊天流队列（兼容旧版本）
    这是一个兼容层，实际使用TypedRequestQueue
    """
    
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
        self.queue = asyncio.Queue(maxsize=max_size)  # 仅用于兼容接口，不实际使用
        self.processing = False
        self.last_activity = time.time()
        self.tasks_processed = 0
        self.tasks_failed = 0
        self.processing_task = None
        
        # 警告消息
        logger.warning(
            "使用已弃用的ChatStreamQueue类，建议使用新的RequestQueueManager API。"
            "此兼容层将在未来版本中移除。"
        )
    
    def is_idle(self, idle_threshold: float = 300.0) -> bool:
        """
        检查队列是否空闲
        
        Args:
            idle_threshold: 空闲阈值（秒）
            
        Returns:
            是否空闲
        """
        return time.time() - self.last_activity > idle_threshold and not self.processing
    
    async def add_task(self, task: MessageTask) -> bool:
        """
        添加任务到队列
        
        Args:
            task: 消息任务
            
        Returns:
            是否成功添加
        """
        logger.warning("使用已弃用的add_task方法，建议使用新的RequestQueueManager.add_request方法")
        return False  # 此方法不再支持，应使用RequestQueueManager
    
    async def process_queue(self) -> None:
        """处理队列中的任务"""
        logger.warning("使用已弃用的process_queue方法，队列处理现在由RequestQueueManager自动管理")
        # 此方法不再支持，队列处理现在由RequestQueueManager自动管理


# 为向后兼容性设置QueueManager为RequestQueueManager的别名
QueueManager = RequestQueueManager 