#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
机器人核心模块，包含机器人的主要组件。
"""

from linjing.bot.linjing_bot import LinjingBot, get_bot_instance
from linjing.bot.personality import Personality
from linjing.bot.message_pipeline import MessagePipeline, Processor, MessageContext
from linjing.bot.event_bus import EventBus, global_event_bus

__all__ = [
    'LinjingBot',
    'get_bot_instance',
    'Personality',
    'MessagePipeline',
    'Processor',
    'MessageContext',
    'EventBus',
    'global_event_bus',
] 