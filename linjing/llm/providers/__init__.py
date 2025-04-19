#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
LLM提供商模块，提供不同LLM服务的接口实现。
(Refactored to support OpenAI compatible providers)
"""

from .base_provider import BaseProvider
from .openai_compatible_provider import OpenAICompatibleProvider # Import the new provider

# model_router_provider is not typically exported directly

__all__ = [
    'BaseProvider',
    'OpenAICompatibleProvider',
]