#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
修复导入问题的补丁
"""

# 创建修复后的导入语句
FIXED_IMPORTS = """
import os
import sys
import asyncio
import importlib
import inspect
from typing import Dict, List, Any, Optional, Tuple, Type, Callable

from linjing.utils.logger import get_logger
from linjing.constants import EventType, ProcessorName
from linjing.bot.event_bus import EventBus
from linjing.bot.personality import Personality
from linjing.bot.message_pipeline import MessagePipeline
from linjing.processors.message_context import MessageContext
from linjing.processors.base_processor import BaseProcessor as Processor
"""

# 打印修复后的导入语句，以便复制粘贴
print(FIXED_IMPORTS)

# 说明如何使用
print("\n请将上面的导入语句替换到 linjing/bot/linjing_bot.py 文件的开头部分")
print("替换这一行: from linjing.bot.message_pipeline import MessagePipeline, Processor, MessageContext") 