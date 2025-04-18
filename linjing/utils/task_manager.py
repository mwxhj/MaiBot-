#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
异步任务管理器。
负责创建、跟踪和管理异步任务，提供任务状态监控和异常处理。
"""

import asyncio
import functools
import sys
import traceback
from typing import Any, Callable, Dict, List, Optional, Set, TypeVar, Union

from linjing.utils.logger import logger

T = TypeVar("T")


class TaskManager:
    """
    异步任务管理器。
    用于创建、监控和管理异步任务，提供统一的异常处理和任务生命周期管理。
    """

    def __init__(self):
        """初始化任务管理器"""
        self._tasks: Set[asyncio.Task] = set()
        self._closed = False

    def create_task(
        self, 
        coroutine: Any, 
        name: Optional[str] = None,
        callback: Optional[Callable[[asyncio.Task], None]] = None
    ) -> asyncio.Task:
        """
        创建并注册异步任务
        
        Args:
            coroutine: 要执行的协程
            name: 任务名称，用于日志记录
            callback: 任务完成时的回调函数
            
        Returns:
            创建的任务对象
        """
        if self._closed:
            raise RuntimeError("TaskManager已关闭，无法创建新任务")
        
        task_name = name or f"Task-{id(coroutine)}"
        
        task = asyncio.create_task(coroutine, name=task_name)
        self._tasks.add(task)
        
        # 设置回调函数
        task.add_done_callback(functools.partial(self._on_task_done, task_name))
        if callback:
            task.add_done_callback(callback)
            
        logger.debug(f"任务 {task_name} 已创建")
        return task
    
    def _on_task_done(self, name: str, task: asyncio.Task) -> None:
        """
        任务完成时的内部回调
        
        Args:
            name: 任务名称
            task: 完成的任务对象
        """
        self._tasks.discard(task)
        
        # 检查任务是否有异常
        if not task.cancelled():
            try:
                exc = task.exception()
                if exc:
                    logger.error(f"任务 {name} 失败: {exc}")
                    # 获取更详细的异常信息
                    tb = "".join(traceback.format_exception(
                        type(exc), exc, task.__exception__.__traceback__
                    ))
                    logger.debug(f"任务 {name} 异常详情:\n{tb}")
                else:
                    logger.debug(f"任务 {name} 成功完成")
            except asyncio.CancelledError:
                logger.debug(f"任务 {name} 被取消")
    
    def cancel_all(self) -> None:
        """取消所有正在运行的任务"""
        for task in self._tasks:
            if not task.done():
                logger.debug(f"取消任务: {task.get_name()}")
                task.cancel()
    
    async def wait_all(self, timeout: Optional[float] = None) -> None:
        """
        等待所有任务完成
        
        Args:
            timeout: 超时时间，None表示无限等待
        """
        if not self._tasks:
            return
            
        pending = list(self._tasks)
        logger.debug(f"等待 {len(pending)} 个任务完成")
        
        try:
            await asyncio.wait(pending, timeout=timeout)
        except asyncio.CancelledError:
            logger.debug("等待任务时被取消")
            raise
    
    def get_running_tasks(self) -> List[asyncio.Task]:
        """
        获取当前正在运行的任务列表
        
        Returns:
            任务列表
        """
        return [task for task in self._tasks if not task.done()]
    
    def get_task_count(self) -> int:
        """
        获取当前任务数量
        
        Returns:
            任务数量
        """
        return len(self._tasks)
    
    async def close(self) -> None:
        """
        关闭任务管理器，取消所有任务并等待它们完成
        """
        if self._closed:
            return
            
        self._closed = True
        self.cancel_all()
        await self.wait_all(timeout=5.0)
        logger.debug(f"任务管理器已关闭，{len(self.get_running_tasks())} 个任务仍在运行")
    
    def is_closed(self) -> bool:
        """
        检查任务管理器是否已关闭
        
        Returns:
            是否已关闭
        """
        return self._closed


# 全局任务管理器实例
global_task_manager = TaskManager()


def create_task(
    coroutine: Any, 
    name: Optional[str] = None,
    callback: Optional[Callable[[asyncio.Task], None]] = None
) -> asyncio.Task:
    """
    使用全局任务管理器创建任务的便捷函数
    
    Args:
        coroutine: 要执行的协程
        name: 任务名称
        callback: 任务完成时的回调函数
        
    Returns:
        创建的任务对象
    """
    return global_task_manager.create_task(coroutine, name, callback) 