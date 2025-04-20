#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
并发控制模块，提供消息队列、去重合并和资源锁等功能。
"""

from .resource_lock import ResourceLockManager, EasyResourceLock, ResourceType, LockType
from .queue_manager import QueueManager, MessageTask, ChatStreamQueue
from .message_debouncer import MessageDebouncer, MessageGroup

__all__ = [
    # 队列管理
    'QueueManager',
    'MessageTask',
    'ChatStreamQueue',
    
    # 消息去重/合并
    'MessageDebouncer',
    'MessageGroup',
    
    # 资源锁
    'ResourceLockManager',
    'EasyResourceLock',
    'ResourceType',
    'LockType'
] 