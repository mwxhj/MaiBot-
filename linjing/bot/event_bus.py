#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
事件总线模块，实现发布-订阅模式的事件系统。
"""

import asyncio
import inspect
from typing import Any, Callable, Dict, List, Set, Union, Optional
import logging

from linjing.utils.logger import get_logger

# 获取日志记录器
logger = get_logger(__name__)

# 事件处理器类型定义
EventHandler = Callable[..., Any]
AsyncEventHandler = Callable[..., asyncio.coroutine]

class EventBus:
    """事件总线，用于在组件间传递事件"""
    
    def __init__(self):
        """初始化事件总线"""
        # 事件处理器映射表: 事件类型 -> 处理器集合
        self._handlers: Dict[str, Set[EventHandler]] = {}
        # 异步事件处理锁
        self._lock = asyncio.Lock()
    
    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """
        订阅事件
        
        Args:
            event_type: 事件类型
            handler: 事件处理函数
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = set()
        
        self._handlers[event_type].add(handler)
        logger.debug(f"已订阅事件 {event_type}: {handler.__name__}")
    
    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        """
        取消订阅事件
        
        Args:
            event_type: 事件类型
            handler: 事件处理函数
        """
        if event_type in self._handlers and handler in self._handlers[event_type]:
            self._handlers[event_type].remove(handler)
            logger.debug(f"已取消订阅事件 {event_type}: {handler.__name__}")
            
            # 如果没有处理器了，清除该事件类型
            if not self._handlers[event_type]:
                del self._handlers[event_type]
    
    def unsubscribe_all(self, event_type: Optional[str] = None) -> None:
        """
        取消所有订阅
        
        Args:
            event_type: 事件类型，如果为None则取消所有类型的订阅
        """
        if event_type is None:
            self._handlers.clear()
            logger.debug("已取消所有事件订阅")
        elif event_type in self._handlers:
            del self._handlers[event_type]
            logger.debug(f"已取消所有 {event_type} 事件订阅")
    
    async def publish(self, event_type: str, data: Any = None) -> None:
        """
        发布事件
        
        Args:
            event_type: 事件类型
            data: 事件数据
        """
        if event_type not in self._handlers:
            return
        
        logger.debug(f"发布事件 {event_type}")
        
        # 使用锁确保在并发情况下处理器集合不会改变
        async with self._lock:
            handlers = self._handlers.get(event_type, set()).copy()
        
        # 并行执行所有处理器
        tasks = []
        for handler in handlers:
            try:
                # 区分同步和异步处理器
                if asyncio.iscoroutinefunction(handler):
                    # 异步处理器直接调用
                    task = asyncio.create_task(handler(event_type, data))
                else:
                    # 同步处理器在线程池中执行
                    loop = asyncio.get_event_loop()
                    task = loop.run_in_executor(None, lambda: handler(event_type, data))
                
                tasks.append(task)
            except Exception as e:
                logger.error(f"事件处理器执行错误 {handler.__name__}: {str(e)}")
        
        # 等待所有任务完成
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    def publish_sync(self, event_type: str, data: Any = None) -> None:
        """
        同步发布事件（不等待异步处理器完成）
        
        Args:
            event_type: 事件类型
            data: 事件数据
        """
        if event_type not in self._handlers:
            return
        
        logger.debug(f"同步发布事件 {event_type}")
        
        handlers = self._handlers.get(event_type, set()).copy()
        
        # 执行所有同步处理器
        for handler in handlers:
            try:
                # 只执行同步处理器
                if not asyncio.iscoroutinefunction(handler):
                    handler(event_type, data)
            except Exception as e:
                logger.error(f"同步事件处理器执行错误 {handler.__name__}: {str(e)}")
    
    def get_subscribers(self, event_type: str) -> List[EventHandler]:
        """
        获取某事件类型的所有订阅者
        
        Args:
            event_type: 事件类型
            
        Returns:
            处理器列表
        """
        return list(self._handlers.get(event_type, set()))
    
    def has_subscribers(self, event_type: str) -> bool:
        """
        检查某事件类型是否有订阅者
        
        Args:
            event_type: 事件类型
            
        Returns:
            是否有订阅者
        """
        return event_type in self._handlers and bool(self._handlers[event_type])


# 全局事件总线实例
global_event_bus = EventBus() 