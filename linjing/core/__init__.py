#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
林镜(LingJing) - 核心处理层
"""

from .message_processor import MessageProcessor
from .read_air import ReadAirProcessor
from .thought_generator import ThoughtGenerator
from .willingness_checker import WillingnessChecker
from .reply_composer import ReplyComposer
from .factory import (
    get_message_processor,
    get_read_air_processor,
    get_thought_generator,
    get_willingness_checker,
    get_reply_composer,
    initialize_all_processors
)

__all__ = [
    # 核心处理器类
    'MessageProcessor',
    'ReadAirProcessor',
    'ThoughtGenerator',
    'WillingnessChecker',
    'ReplyComposer',
    
    # 工厂函数
    'get_message_processor',
    'get_read_air_processor',
    'get_thought_generator',
    'get_willingness_checker',
    'get_reply_composer',
    'initialize_all_processors'
] 