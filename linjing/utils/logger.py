#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
日志工具模块，提供日志配置和工具函数。
"""

import os
import sys
import time
import logging
from logging.handlers import RotatingFileHandler
from typing import Optional

from loguru import logger

def setup_logger(level: str = "INFO", log_dir: str = "logs") -> None:
    """
    设置日志记录器
    
    Args:
        level: 日志级别
        log_dir: 日志文件目录
    """
    # 创建日志目录
    os.makedirs(log_dir, exist_ok=True)
    
    # 移除默认处理器
    logger.remove()
    
    # 设置日志格式
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )
    
    # 添加控制台处理器
    logger.add(
        sys.stderr,
        format=log_format,
        level=level,
        colorize=True,
    )
    
    # 添加文件处理器 (按日期分割)
    logger.add(
        os.path.join(log_dir, "linjing_{time:YYYY-MM-DD}.log"),
        format=log_format,
        level=level,
        rotation="00:00",  # 每天午夜轮换
        retention="30 days",  # 保留30天
        compression="zip",  # 压缩旧日志
        encoding="utf-8",
    )
    
    # 添加错误日志文件处理器
    logger.add(
        os.path.join(log_dir, "error_{time:YYYY-MM-DD}.log"),
        format=log_format,
        level="ERROR",
        rotation="00:00",
        retention="30 days",
        compression="zip",
        encoding="utf-8",
    )
    
    # 配置标准库日志与loguru的兼容
    class InterceptHandler(logging.Handler):
        def emit(self, record):
            # 获取对应的loguru级别
            try:
                level = logger.level(record.levelname).name
            except ValueError:
                level = record.levelno
            
            # 寻找调用者
            frame, depth = logging.currentframe(), 2
            while frame.f_code.co_filename == logging.__file__:
                frame = frame.f_back
                depth += 1
            
            # 使用loguru记录
            logger.opt(depth=depth, exception=record.exc_info).log(
                level, record.getMessage()
            )
    
    # 将所有标准库日志重定向到loguru
    logging.basicConfig(handlers=[InterceptHandler()], level=0)

def get_logger(name: str) -> logger:
    """
    获取指定名称的logger实例
    
    Args:
        name: 日志记录器名称
        
    Returns:
        日志记录器实例
    """
    return logger.bind(name=name)

def log_execution_time(func):
    """
    装饰器：记录函数执行时间
    
    Args:
        func: 被装饰的函数
        
    Returns:
        装饰后的函数
    """
    async def async_wrapper(*args, **kwargs):
        start_time = time.time()
        result = await func(*args, **kwargs)
        duration = time.time() - start_time
        logger.debug(f"{func.__name__} 执行时间: {duration:.4f}秒")
        return result
    
    def sync_wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        duration = time.time() - start_time
        logger.debug(f"{func.__name__} 执行时间: {duration:.4f}秒")
        return result
    
    # 根据函数类型选择装饰器
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    return sync_wrapper

# 确保asyncio导入，用于装饰器判断异步函数
import asyncio 