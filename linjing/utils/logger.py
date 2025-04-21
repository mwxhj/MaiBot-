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
# 导入 ConfigManager 类型提示，如果需要的话
from typing import Optional, TYPE_CHECKING
if TYPE_CHECKING:
    from .. import ConfigManager # ConfigManager 现在位于上层 linjing 包的 __init__.py
    # 注意：如果 ConfigManager 类本身不在 linjing/config.py 中，需要调整

from loguru import logger
# 移除顶层 config_manager 导入

# 修改函数签名，接收 config_manager 实例
def setup_logger(config_manager: 'ConfigManager', level: str = "INFO", log_dir: Optional[str] = None) -> None:
    """
    设置日志记录器

    Args:
        config_manager: ConfigManager 实例.
        level: 日志级别.
        log_dir: 日志文件目录 (可选, 如果提供则覆盖配置中的路径).
    """
    # 确定日志目录，优先使用传入的 log_dir，其次是配置，最后是默认值 'logs'
    # 确保从 config_manager 获取 LOG_PATH
    log_path_from_config = getattr(config_manager, 'LOG_PATH', None)
    if not log_path_from_config:
        # 如果实例上没有 LOG_PATH，尝试从配置字典获取
        log_path_from_config = config_manager.get("system.logging.log_dir", 'logs')

    actual_log_dir = log_dir or log_path_from_config

    # 创建日志目录
    os.makedirs(actual_log_dir, exist_ok=True)
    
    # 移除默认处理器
    logger.remove()
    
    # 设置日志格式
    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )
    
    # 从配置获取日志保留天数，默认为30天
    # 从传入的 config_manager 获取日志保留天数
    retention_days = config_manager.get("system.logging.retention_days", 30)
    
    # 控制台处理器
    logger.add(
        sys.stderr,
        format=log_format,
        level="INFO",
        colorize=True,
    )
    
    # 添加文件处理器 (按日期分割)
    logger.add(
        os.path.join(actual_log_dir, "linjing_{time:YYYY-MM-DD}.log"), # 使用 actual_log_dir
        format=log_format,
        level=level,
        rotation="00:00",  # 每天午夜轮换
        retention=f"{retention_days} days",
        compression="zip",  # 压缩旧日志
        encoding="utf-8",
    )
    
    # 添加错误日志文件处理器
    logger.add(
        os.path.join(actual_log_dir, "error_{time:YYYY-MM-DD}.log"), # 使用 actual_log_dir
        format=log_format,
        level="ERROR",
        rotation="00:00",
        retention=f"{retention_days} days",
        compression="zip",
        encoding="utf-8",
    )
    
    # --- 新增：全方位观察日志 Sinks --- 
    # 是否启用观察日志 (可以从配置读取)
    enable_observation_logs = config_manager.get("system.logging.enable_observation_logs", True)

    if enable_observation_logs:
        obs_log_dir = os.path.join(actual_log_dir, "observation")
        os.makedirs(obs_log_dir, exist_ok=True)
        logger.info(f"启用全方位观察日志，将保存到: {obs_log_dir}")

        # 1. 林镜发言日志
        logger.add(
            os.path.join(obs_log_dir, "linjing_speech_{time:YYYY-MM-DD}.log"),
            level="INFO", rotation="10 MB", retention="7 days", encoding="utf-8",
            filter=lambda record: "准备发布 SEND_MESSAGE_REQUEST 事件" in record["message"],
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | REPLY | {extra[reply_content]}",
            enqueue=True 
        )

        # 2. 林镜想法日志
        logger.add(
            os.path.join(obs_log_dir, "linjing_thoughts_{time:YYYY-MM-DD}.jsonl"),
            level="DEBUG", rotation="50 MB", retention="14 days", encoding="utf-8",
            filter=lambda record: "thought_input" in record["extra"],
            format="{extra[thought_input]}",
            serialize=True,
            enqueue=True
        )
        
        # 3. 林镜读空气日志
        logger.add(
            os.path.join(obs_log_dir, "linjing_read_air_{time:YYYY-MM-DD}.jsonl"),
            level="DEBUG", rotation="10 MB", retention="7 days", encoding="utf-8",
            filter=lambda record: record["extra"].get("component_name") == "读空气分析",
            format="{extra[report_data]}",
            serialize=True,
            enqueue=True
        )

        # 4. 林镜情绪日志
        logger.add(
            os.path.join(obs_log_dir, "linjing_emotion_{time:YYYY-MM-DD}.jsonl"),
            level="DEBUG", rotation="10 MB", retention="14 days", encoding="utf-8",
            filter=lambda record: record["extra"].get("component_name") == "情绪状态",
            format="{extra[report_data]}",
            serialize=True,
            enqueue=True
        )

        # 5. 聊天消息日志
        logger.add(
            os.path.join(obs_log_dir, "chat_messages_{time:YYYY-MM-DD}.log"),
            level="DEBUG", rotation="50 MB", retention="7 days", encoding="utf-8",
            filter=lambda record: "msg_content" in record["extra"],
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | CHAT | User: {extra[user_id]} | Group: {extra[group_id]} | Msg: {extra[msg_content]}",
            enqueue=True
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
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

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