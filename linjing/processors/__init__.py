#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
处理器模块，提供消息处理的各个组件。
"""

from linjing.processors.message_context import MessageContext
from linjing.processors.processor_registry import ProcessorRegistry
from linjing.processors.base_processor import BaseProcessor
# 使用别名解决Processor导入问题
from linjing.processors.base_processor import BaseProcessor as Processor
from linjing.processors.processor_pipeline import ProcessorPipeline
from linjing.processors.read_air import ReadAirProcessor
from linjing.processors.thought_generator import ThoughtGenerator
from linjing.processors.response_composer import ResponseComposer

__all__ = [
    'MessageContext',
    'Processor',
    'ProcessorRegistry',
    'BaseProcessor',
    'ProcessorPipeline',
    'ReadAirProcessor',
    'ThoughtGenerator',
    'ResponseComposer',
] 