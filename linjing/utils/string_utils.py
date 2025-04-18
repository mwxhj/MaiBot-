#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
字符串处理工具模块。
"""

import re
import json
import hashlib
import uuid
from typing import Any, Dict, List, Optional, Tuple, Union

def generate_uuid() -> str:
    """
    生成UUID字符串
    
    Returns:
        UUID字符串
    """
    return str(uuid.uuid4())

def md5(text: str) -> str:
    """
    计算字符串的MD5哈希值
    
    Args:
        text: 输入字符串
        
    Returns:
        MD5哈希值
    """
    return hashlib.md5(text.encode('utf-8')).hexdigest()

def is_json(text: str) -> bool:
    """
    检查字符串是否为有效的JSON
    
    Args:
        text: 输入字符串
        
    Returns:
        是否为有效JSON
    """
    try:
        json.loads(text)
        return True
    except (ValueError, TypeError):
        return False

def safe_json_loads(text: str, default: Any = None) -> Any:
    """
    安全加载JSON字符串，出错时返回默认值
    
    Args:
        text: JSON字符串
        default: 默认值
        
    Returns:
        解析后的对象或默认值
    """
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        return default

def extract_urls(text: str) -> List[str]:
    """
    从文本中提取URL
    
    Args:
        text: 输入文本
        
    Returns:
        提取出的URL列表
    """
    url_pattern = r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+'
    return re.findall(url_pattern, text)

def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """
    截断文本到指定长度
    
    Args:
        text: 输入文本
        max_length: 最大长度
        suffix: 截断后添加的后缀
        
    Returns:
        截断后的文本
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix

def extract_mentions(text: str) -> List[str]:
    """
    从文本中提取@提及
    
    Args:
        text: 输入文本
        
    Returns:
        提及的用户ID列表
    """
    # 匹配 @123456 格式
    mention_pattern = r'@(\d+)'
    return re.findall(mention_pattern, text)

def remove_mentions(text: str) -> str:
    """
    移除文本中的@提及
    
    Args:
        text: 输入文本
        
    Returns:
        移除提及后的文本
    """
    mention_pattern = r'@\d+'
    return re.sub(mention_pattern, '', text).strip()

def is_chinese_char(char: str) -> bool:
    """
    判断一个字符是否为中文字符
    
    Args:
        char: 单个字符
        
    Returns:
        是否为中文字符
    """
    if len(char) != 1:
        return False
    # Unicode汉字范围
    return '\u4e00' <= char <= '\u9fff'

def count_chinese_chars(text: str) -> int:
    """
    计算文本中中文字符的数量
    
    Args:
        text: 输入文本
        
    Returns:
        中文字符数量
    """
    return sum(1 for char in text if is_chinese_char(char))

def has_chinese(text: str) -> bool:
    """
    检查文本是否包含中文字符
    
    Args:
        text: 输入文本
        
    Returns:
        是否包含中文字符
    """
    for char in text:
        if is_chinese_char(char):
            return True
    return False

def normalize_chinese_punctuation(text: str) -> str:
    """
    将中文标点符号标准化
    
    Args:
        text: 输入文本
        
    Returns:
        标准化后的文本
    """
    # 定义标点映射表
    mapping = {
        '，': ',', 
        '。': '.', 
        '！': '!', 
        '？': '?', 
        '；': ';', 
        '：': ':', 
        '"': '"', 
        '"': '"', 
        ''': "'", 
        ''': "'", 
        '（': '(', 
        '）': ')', 
        '【': '[', 
        '】': ']', 
        '《': '<', 
        '》': '>'
    }
    
    for ch, en in mapping.items():
        text = text.replace(ch, en)
    
    return text

def camel_to_snake(text: str) -> str:
    """
    驼峰命名法转蛇形命名法
    
    Args:
        text: 驼峰命名字符串
        
    Returns:
        蛇形命名字符串
    """
    pattern = re.compile(r'(?<!^)(?=[A-Z])')
    return pattern.sub('_', text).lower()

def snake_to_camel(text: str) -> str:
    """
    蛇形命名法转驼峰命名法
    
    Args:
        text: 蛇形命名字符串
        
    Returns:
        驼峰命名字符串
    """
    components = text.split('_')
    return components[0] + ''.join(x.title() for x in components[1:])

def levenshtein_distance(s1: str, s2: str) -> int:
    """
    计算两个字符串的编辑距离（Levenshtein距离）
    
    Args:
        s1: 第一个字符串
        s2: 第二个字符串
        
    Returns:
        编辑距离
    """
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    
    if len(s2) == 0:
        return len(s1)
    
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    
    return previous_row[-1] 