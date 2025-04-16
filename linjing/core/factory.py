#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
林镜(LingJing) - 核心处理层工厂
"""

import asyncio
from typing import Dict, Any, Optional

from ..utils.logger import get_logger
from .message_processor import MessageProcessor
from .read_air import ReadAirProcessor
from .thought_generator import ThoughtGenerator
from .willingness_checker import WillingnessChecker
from .reply_composer import ReplyComposer

# 单例实例存储
_message_processor_instance = None
_read_air_processor_instance = None
_thought_generator_instance = None
_willingness_checker_instance = None
_reply_composer_instance = None

# 日志记录器
logger = get_logger('linjing.core.factory')

async def get_message_processor() -> MessageProcessor:
    """
    获取消息处理器实例
    
    Returns:
        MessageProcessor: 消息处理器实例
    """
    global _message_processor_instance
    
    if _message_processor_instance is None:
        logger.info("初始化消息处理器...")
        _message_processor_instance = MessageProcessor()
        await _message_processor_instance.initialize()
        
    return _message_processor_instance

async def get_read_air_processor() -> ReadAirProcessor:
    """
    获取读空气处理器实例
    
    Returns:
        ReadAirProcessor: 读空气处理器实例
    """
    global _read_air_processor_instance
    
    if _read_air_processor_instance is None:
        logger.info("初始化读空气处理器...")
        _read_air_processor_instance = ReadAirProcessor()
        await _read_air_processor_instance.initialize()
        
    return _read_air_processor_instance

async def get_thought_generator() -> ThoughtGenerator:
    """
    获取思考生成器实例
    
    Returns:
        ThoughtGenerator: 思考生成器实例
    """
    global _thought_generator_instance
    
    if _thought_generator_instance is None:
        logger.info("初始化思考生成器...")
        _thought_generator_instance = ThoughtGenerator()
        await _thought_generator_instance.initialize()
        
    return _thought_generator_instance

async def get_willingness_checker() -> WillingnessChecker:
    """
    获取意愿检查器实例
    
    Returns:
        WillingnessChecker: 意愿检查器实例
    """
    global _willingness_checker_instance
    
    if _willingness_checker_instance is None:
        logger.info("初始化意愿检查器...")
        _willingness_checker_instance = WillingnessChecker()
        await _willingness_checker_instance.initialize()
        
    return _willingness_checker_instance

async def get_reply_composer() -> ReplyComposer:
    """
    获取回复组合器实例
    
    Returns:
        ReplyComposer: 回复组合器实例
    """
    global _reply_composer_instance
    
    if _reply_composer_instance is None:
        logger.info("初始化回复组合器...")
        _reply_composer_instance = ReplyComposer()
        await _reply_composer_instance.initialize()
        
    return _reply_composer_instance

async def initialize_all_processors() -> Dict[str, Any]:
    """
    初始化所有处理器
    
    Returns:
        Dict[str, Any]: 处理器实例字典
    """
    logger.info("初始化所有核心处理器...")
    
    # 并行初始化所有处理器
    processors = await asyncio.gather(
        get_message_processor(),
        get_read_air_processor(),
        get_thought_generator(),
        get_willingness_checker(),
        get_reply_composer()
    )
    
    # 构建处理器字典
    processor_dict = {
        "message_processor": processors[0],
        "read_air_processor": processors[1],
        "thought_generator": processors[2],
        "willingness_checker": processors[3],
        "reply_composer": processors[4]
    }
    
    logger.info("所有核心处理器初始化完成")
    
    return processor_dict 
# -*- coding: utf-8 -*-

"""
林镜(LingJing) - 核心处理层工厂
"""



# 单例实例存储
_message_processor_instance = None
_read_air_processor_instance = None
_thought_generator_instance = None
_willingness_checker_instance = None
_reply_composer_instance = None

# 日志记录器
logger = get_logger('linjing.core.factory')

async def get_message_processor() -> MessageProcessor:
    """
    获取消息处理器实例
    
    Returns:
        MessageProcessor: 消息处理器实例
    """
    global _message_processor_instance
    
    if _message_processor_instance is None:
        logger.info("初始化消息处理器...")
        _message_processor_instance = MessageProcessor()
        await _message_processor_instance.initialize()
        
    return _message_processor_instance

async def get_read_air_processor() -> ReadAirProcessor:
    """
    获取读空气处理器实例
    
    Returns:
        ReadAirProcessor: 读空气处理器实例
    """
    global _read_air_processor_instance
    
    if _read_air_processor_instance is None:
        logger.info("初始化读空气处理器...")
        _read_air_processor_instance = ReadAirProcessor()
        await _read_air_processor_instance.initialize()
        
    return _read_air_processor_instance

async def get_thought_generator() -> ThoughtGenerator:
    """
    获取思考生成器实例
    
    Returns:
        ThoughtGenerator: 思考生成器实例
    """
    global _thought_generator_instance
    
    if _thought_generator_instance is None:
        logger.info("初始化思考生成器...")
        _thought_generator_instance = ThoughtGenerator()
        await _thought_generator_instance.initialize()
        
    return _thought_generator_instance

async def get_willingness_checker() -> WillingnessChecker:
    """
    获取意愿检查器实例
    
    Returns:
        WillingnessChecker: 意愿检查器实例
    """
    global _willingness_checker_instance
    
    if _willingness_checker_instance is None:
        logger.info("初始化意愿检查器...")
        _willingness_checker_instance = WillingnessChecker()
        await _willingness_checker_instance.initialize()
        
    return _willingness_checker_instance

async def get_reply_composer() -> ReplyComposer:
    """
    获取回复组合器实例
    
    Returns:
        ReplyComposer: 回复组合器实例
    """
    global _reply_composer_instance
    
    if _reply_composer_instance is None:
        logger.info("初始化回复组合器...")
        _reply_composer_instance = ReplyComposer()
        await _reply_composer_instance.initialize()
        
    return _reply_composer_instance

async def initialize_all_processors() -> Dict[str, Any]:
    """
    初始化所有处理器
    
    Returns:
        Dict[str, Any]: 处理器实例字典
    """
    logger.info("初始化所有核心处理器...")
    
    # 并行初始化所有处理器
    processors = await asyncio.gather(
        get_message_processor(),
        get_read_air_processor(),
        get_thought_generator(),
        get_willingness_checker(),
        get_reply_composer()
    )
    
    # 构建处理器字典
    processor_dict = {
        "message_processor": processors[0],
        "read_air_processor": processors[1],
        "thought_generator": processors[2],
        "willingness_checker": processors[3],
        "reply_composer": processors[4]
    }
    
    logger.info("所有核心处理器初始化完成")
    
    return processor_dict 