#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
适配器包，用于与不同平台的通信。
"""

from linjing.adapters.message_types import Message, MessageSegment, SegmentType
from linjing.adapters.adapter_utils import (
    Bot, AdapterRegistry, ApiRateLimiter, retry_operation,
    MessageConverter, is_command, parse_command,
    escape_message_text, unescape_message_text, download_file
)
from linjing.adapters.onebot_adapter import OneBotAdapter

__all__ = [
    # 消息类型
    'Message',
    'MessageSegment',
    'SegmentType',
    
    # 适配器基类
    'Bot',
    
    # 适配器工具
    'AdapterRegistry',
    'ApiRateLimiter',
    'MessageConverter',
    'retry_operation',
    'is_command',
    'parse_command',
    'escape_message_text',
    'unescape_message_text',
    'download_file',
    
    # 适配器类
    'OneBotAdapter',
] 