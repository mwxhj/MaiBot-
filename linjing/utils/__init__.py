#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
工具包，提供各种实用功能。
"""

from linjing.utils.logger import setup_logger, get_logger, log_execution_time
from linjing.utils.string_utils import (
    generate_uuid, md5, is_json, safe_json_loads, extract_urls,
    truncate_text, extract_mentions, remove_mentions,
    is_chinese_char, count_chinese_chars, has_chinese,
    normalize_chinese_punctuation, camel_to_snake, snake_to_camel,
    levenshtein_distance
)
from linjing.utils.async_tools import (
    AsyncLimiter, gather_with_concurrency, gather_with_timeout,
    run_sync, AsyncRetry, AsyncCache
)
from linjing.utils.security import (
    generate_key, derive_key, encrypt, decrypt,
    hash_password, verify_password, mask_sensitive_data,
    contains_sensitive_data, generate_strong_password,
    is_safe_url, sanitize_input
)

__all__ = [
    # logger
    'setup_logger', 'get_logger', 'log_execution_time',
    
    # string_utils
    'generate_uuid', 'md5', 'is_json', 'safe_json_loads', 'extract_urls',
    'truncate_text', 'extract_mentions', 'remove_mentions',
    'is_chinese_char', 'count_chinese_chars', 'has_chinese',
    'normalize_chinese_punctuation', 'camel_to_snake', 'snake_to_camel',
    'levenshtein_distance',
    
    # async_tools
    'AsyncLimiter', 'gather_with_concurrency', 'gather_with_timeout',
    'run_sync', 'AsyncRetry', 'AsyncCache',
    
    # security
    'generate_key', 'derive_key', 'encrypt', 'decrypt',
    'hash_password', 'verify_password', 'mask_sensitive_data',
    'contains_sensitive_data', 'generate_strong_password',
    'is_safe_url', 'sanitize_input',
] 