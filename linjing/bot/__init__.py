#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
机器人核心模块，包含机器人的主要组件。
"""

from .linjing_bot import LinjingBot, get_bot_instance # 使用相对导入
from .message_pipeline import MessagePipeline # 只导入 MessagePipeline
# 直接从 processors 导入 MessageContext 和 Processor (BaseProcessor 的别名)
from ..processors.message_context import MessageContext
from ..processors.base_processor import BaseProcessor as Processor
from linjing.bot.event_bus import EventBus, global_event_bus

__all__ = [
    'LinjingBot',
    'get_bot_instance',
    'MessagePipeline',
    'Processor', # 导出正确的 Processor (BaseProcessor 别名)
    'MessageContext', # 导出正确的 MessageContext
    'EventBus',
    'global_event_bus',
] 