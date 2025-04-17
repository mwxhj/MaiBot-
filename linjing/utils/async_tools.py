#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
异步工具模块，提供异步操作相关的实用函数。
"""

import asyncio
import functools
import time
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set, TypeVar, Union

# 定义泛型类型
T = TypeVar('T')
R = TypeVar('R')

class AsyncLimiter:
    """
    异步限流器，用于限制同时进行的异步操作数量
    """
    
    def __init__(self, max_concurrent: int):
        """
        初始化限流器
        
        Args:
            max_concurrent: 最大并发数
        """
        self.semaphore = asyncio.Semaphore(max_concurrent)
    
    async def __aenter__(self):
        await self.semaphore.acquire()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        self.semaphore.release()

async def gather_with_concurrency(
    max_concurrent: int, *tasks: Coroutine[Any, Any, T]
) -> List[T]:
    """
    限制并发数量的异步任务收集器
    
    Args:
        max_concurrent: 最大并发数
        tasks: 要执行的异步任务列表
        
    Returns:
        所有任务的结果列表
    """
    limiter = AsyncLimiter(max_concurrent)
    
    async def wrap_task(task):
        async with limiter:
            return await task
    
    return await asyncio.gather(*(wrap_task(task) for task in tasks))

async def gather_with_timeout(
    timeout: float, *tasks: Coroutine[Any, Any, T], cancel_on_timeout: bool = True
) -> List[Optional[T]]:
    """
    带超时的异步任务收集器
    
    Args:
        timeout: 超时时间（秒）
        tasks: 要执行的异步任务列表
        cancel_on_timeout: 超时时是否取消剩余任务
        
    Returns:
        所有任务的结果列表，超时的任务结果为None
    """
    gathered_tasks = []
    for task in tasks:
        # 创建任务
        gathered_tasks.append(asyncio.create_task(task))
    
    # 添加超时
    try:
        return await asyncio.wait_for(asyncio.gather(*gathered_tasks), timeout=timeout)
    except asyncio.TimeoutError:
        if cancel_on_timeout:
            # 取消所有未完成的任务
            for task in gathered_tasks:
                if not task.done():
                    task.cancel()
        
        # 返回已完成任务的结果，未完成任务返回None
        return [
            task.result() if task.done() and not task.cancelled() else None
            for task in gathered_tasks
        ]

def run_sync(func: Callable[..., T]) -> Callable[..., Coroutine[Any, Any, T]]:
    """
    装饰器：将同步函数转换为异步函数，在线程池中执行
    
    Args:
        func: 同步函数
        
    Returns:
        转换后的异步函数
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, functools.partial(func, *args, **kwargs)
        )
    
    return wrapper

class AsyncRetry:
    """
    异步重试装饰器，支持指数退避策略
    """
    
    def __init__(
        self,
        max_retries: int = 3,
        delay: float = 1.0,
        backoff: float = 2.0,
        exceptions: Union[List[Exception], Exception] = Exception,
    ):
        """
        初始化重试装饰器
        
        Args:
            max_retries: 最大重试次数
            delay: 初始延迟时间（秒）
            backoff: 退避系数
            exceptions: 触发重试的异常类型
        """
        self.max_retries = max_retries
        self.delay = delay
        self.backoff = backoff
        if isinstance(exceptions, list):
            self.exceptions = tuple(exceptions)
        else:
            self.exceptions = (exceptions,)
    
    def __call__(self, func: Callable[..., Coroutine[Any, Any, T]]) -> Callable[..., Coroutine[Any, Any, T]]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            retry_count = 0
            current_delay = self.delay
            
            while True:
                try:
                    return await func(*args, **kwargs)
                except self.exceptions as e:
                    retry_count += 1
                    if retry_count > self.max_retries:
                        raise
                    
                    # 等待延迟时间
                    await asyncio.sleep(current_delay)
                    
                    # 计算下一次延迟
                    current_delay *= self.backoff
        
        return wrapper

class AsyncCache:
    """
    异步缓存装饰器，缓存异步函数的结果
    """
    
    def __init__(self, ttl: Optional[float] = None, max_size: Optional[int] = None):
        """
        初始化缓存装饰器
        
        Args:
            ttl: 缓存过期时间（秒），None表示永不过期
            max_size: 最大缓存条目数，None表示无限制
        """
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.ttl = ttl
        self.max_size = max_size
        self.keys_by_time: List[str] = []  # 按添加时间排序的键
    
    def __call__(self, func: Callable[..., Coroutine[Any, Any, T]]) -> Callable[..., Coroutine[Any, Any, T]]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # 创建缓存键
            key = str((args, frozenset(kwargs.items())))
            
            # 检查缓存
            if key in self.cache:
                entry = self.cache[key]
                if self.ttl is None or time.time() - entry["time"] < self.ttl:
                    return entry["result"]
            
            # 执行函数
            result = await func(*args, **kwargs)
            
            # 控制缓存大小
            if self.max_size is not None and len(self.cache) >= self.max_size:
                # 移除最旧的条目
                oldest_key = self.keys_by_time.pop(0)
                self.cache.pop(oldest_key, None)
            
            # 更新缓存
            self.cache[key] = {"result": result, "time": time.time()}
            if self.max_size is not None:
                self.keys_by_time.append(key)
            
            return result
        
        return wrapper 