#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
林镜(LingJing) - 日志工具
"""

import os
import logging
import sys
from logging.handlers import RotatingFileHandler
from typing import Dict, Any, Optional

# 默认日志格式
DEFAULT_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# 日志级别映射
LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL
}

# 全局日志配置
_log_config = {
    "level": "INFO",
    "format": DEFAULT_FORMAT,
    "file": None,
    "max_size": 10 * 1024 * 1024,  # 10MB
    "backup_count": 5
}

def setup_logger(config: Dict[str, Any] = None) -> None:
    """
    设置日志配置
    
    Args:
        config: 日志配置字典，包含level、format、file、max_size、backup_count等字段
    """
    global _log_config
    
    # 更新日志配置
    if config:
        _log_config.update(config)
    
    # 获取根日志记录器
    root_logger = logging.getLogger()
    
    # 清除现有处理器
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # 设置日志级别
    level_name = _log_config.get("level", "INFO")
    level = LOG_LEVELS.get(level_name, logging.INFO)
    root_logger.setLevel(level)
    
    # 创建格式化器
    formatter = logging.Formatter(_log_config.get("format", DEFAULT_FORMAT))
    
    # 添加控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # 添加文件处理器（如果指定了文件）
    log_file = _log_config.get("file")
    if log_file:
        # 确保日志目录存在
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        
        # 创建文件处理器
        max_size = _log_config.get("max_size", 10 * 1024 * 1024)
        backup_count = _log_config.get("backup_count", 5)
        file_handler = RotatingFileHandler(
            log_file, 
            maxBytes=max_size, 
            backupCount=backup_count, 
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    # 设置第三方库的日志级别
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    
    # 记录设置完成的消息
    root_logger.debug(f"日志设置完成，级别: {level_name}, 文件: {log_file if log_file else '无'}")

def get_logger(name: str, level: Optional[str] = None) -> logging.Logger:
    """
    获取指定名称的日志记录器
    
    Args:
        name: 日志记录器名称
        level: 日志级别，可选
        
    Returns:
        日志记录器
    """
    logger = logging.getLogger(name)
    
    # 设置特定级别（如果指定）
    if level:
        logger.setLevel(LOG_LEVELS.get(level, logging.INFO))
    
    return logger

def set_log_level(level: str) -> None:
    """
    设置全局日志级别
    
    Args:
        level: 日志级别，可以是DEBUG、INFO、WARNING、ERROR、CRITICAL
    """
    if level in LOG_LEVELS:
        logging.getLogger().setLevel(LOG_LEVELS[level])
        logging.info(f"日志级别已设置为 {level}")
    else:
        logging.warning(f"无效的日志级别: {level}")

def get_log_level() -> str:
    """
    获取当前全局日志级别
    
    Returns:
        日志级别字符串
    """
    level = logging.getLogger().getEffectiveLevel()
    for name, value in LOG_LEVELS.items():
        if value == level:
            return name
    return "UNKNOWN"

# 设置默认日志配置
setup_logger() 
# -*- coding: utf-8 -*-

"""
林镜(LingJing) - 日志工具
"""


# 默认日志格式
DEFAULT_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# 日志级别映射
LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL
}

# 全局日志配置
_log_config = {
    "level": "INFO",
    "format": DEFAULT_FORMAT,
    "file": None,
    "max_size": 10 * 1024 * 1024,  # 10MB
    "backup_count": 5
}

def setup_logger(config: Dict[str, Any] = None) -> None:
    """
    设置日志配置
    
    Args:
        config: 日志配置字典，包含level、format、file、max_size、backup_count等字段
    """
    global _log_config
    
    # 更新日志配置
    if config:
        _log_config.update(config)
    
    # 获取根日志记录器
    root_logger = logging.getLogger()
    
    # 清除现有处理器
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # 设置日志级别
    level_name = _log_config.get("level", "INFO")
    level = LOG_LEVELS.get(level_name, logging.INFO)
    root_logger.setLevel(level)
    
    # 创建格式化器
    formatter = logging.Formatter(_log_config.get("format", DEFAULT_FORMAT))
    
    # 添加控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # 添加文件处理器（如果指定了文件）
    log_file = _log_config.get("file")
    if log_file:
        # 确保日志目录存在
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        
        # 创建文件处理器
        max_size = _log_config.get("max_size", 10 * 1024 * 1024)
        backup_count = _log_config.get("backup_count", 5)
        file_handler = RotatingFileHandler(
            log_file, 
            maxBytes=max_size, 
            backupCount=backup_count, 
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    # 设置第三方库的日志级别
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    
    # 记录设置完成的消息
    root_logger.debug(f"日志设置完成，级别: {level_name}, 文件: {log_file if log_file else '无'}")

def get_logger(name: str, level: Optional[str] = None) -> logging.Logger:
    """
    获取指定名称的日志记录器
    
    Args:
        name: 日志记录器名称
        level: 日志级别，可选
        
    Returns:
        日志记录器
    """
    logger = logging.getLogger(name)
    
    # 设置特定级别（如果指定）
    if level:
        logger.setLevel(LOG_LEVELS.get(level, logging.INFO))
    
    return logger

def set_log_level(level: str) -> None:
    """
    设置全局日志级别
    
    Args:
        level: 日志级别，可以是DEBUG、INFO、WARNING、ERROR、CRITICAL
    """
    if level in LOG_LEVELS:
        logging.getLogger().setLevel(LOG_LEVELS[level])
        logging.info(f"日志级别已设置为 {level}")
    else:
        logging.warning(f"无效的日志级别: {level}")

def get_log_level() -> str:
    """
    获取当前全局日志级别
    
    Returns:
        日志级别字符串
    """
    level = logging.getLogger().getEffectiveLevel()
    for name, value in LOG_LEVELS.items():
        if value == level:
            return name
    return "UNKNOWN"

# 设置默认日志配置
setup_logger() 