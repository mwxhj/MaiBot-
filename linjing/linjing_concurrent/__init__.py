#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
并发处理模块，提供消息队列、资源锁和请求队列等机制。
"""

from .message_debouncer import MessageDebouncer, MessageGroup
from .queue_manager import (
    QueueManager,
    MessageTask,
    ChatStreamQueue,
    RequestQueueManager,
    RequestQueueType,
    RequestStatus,
    RequestTask
)
from .typed_request_queue import TypedRequestQueue
from .resource_lock import (
    ResourceLockManager, 
    EasyResourceLock,
    ResourceType, 
    LockType
)

__all__ = [
    # 队列管理
    "QueueManager",
    "MessageTask",
    "ChatStreamQueue",
    
    # 消息去重/合并
    "MessageDebouncer",
    "MessageGroup",
    
    # 资源锁
    "ResourceLockManager",
    "EasyResourceLock",
    "ResourceType",
    "LockType",
    
    # 请求队列
    "RequestQueueManager",
    "RequestQueueType",
    "RequestStatus",
    "RequestTask",
    "TypedRequestQueue"
] 