#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
林镜(LingJing) - 全局配置管理
"""

import os
import json
import logging
from typing import Dict, Any

# 配置文件路径
DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config', 'default_config.json')

# 缓存配置
_config_cache = {}

def load_config(config_path: str = None) -> Dict[str, Any]:
    """
    加载配置文件
    
    Args:
        config_path: 配置文件路径，如果为None则使用默认路径
        
    Returns:
        配置字典
    """
    global _config_cache
    
    # 如果已缓存且未指定特定路径，则返回缓存
    if _config_cache and config_path is None:
        return _config_cache
    
    # 确定配置文件路径
    config_file = config_path if config_path else DEFAULT_CONFIG_PATH
    
    # 检查文件是否存在
    if not os.path.exists(config_file):
        logging.warning(f"配置文件 {config_file} 不存在，将使用默认配置")
        _config_cache = _get_default_config()
        return _config_cache
    
    # 加载配置文件
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # 缓存配置
        if config_path is None:
            _config_cache = config
            
        return config
    except Exception as e:
        logging.error(f"加载配置文件 {config_file} 失败: {e}")
        _config_cache = _get_default_config()
        return _config_cache

def get_config(key: str = None, default=None) -> Any:
    """
    获取配置项
    
    Args:
        key: 配置项键名，如果为None则返回整个配置
        default: 默认值，当键不存在时返回
        
    Returns:
        配置项值
    """
    if not _config_cache:
        load_config()
    
    if key is None:
        return _config_cache
    
    return _config_cache.get(key, default)

async def async_get_config(key: str = None, default=None) -> Any:
    """
    异步获取配置项
    
    Args:
        key: 配置项键名，如果为None则返回整个配置
        default: 默认值，当键不存在时返回
        
    Returns:
        配置项值
    """
    # 异步版本实际上执行相同的操作，但允许使用await调用
    if not _config_cache:
        load_config()
    
    if key is None:
        return _config_cache
    
    return _config_cache.get(key, default)

def update_config(key: str, value: Any) -> None:
    """
    更新配置项
    
    Args:
        key: 配置项键名
        value: 配置项值
    """
    if not _config_cache:
        load_config()
    
    _config_cache[key] = value

def save_config(config_path: str = None) -> bool:
    """
    保存配置到文件
    
    Args:
        config_path: 配置文件路径，如果为None则使用默认路径
        
    Returns:
        是否保存成功
    """
    # 确定配置文件路径
    config_file = config_path if config_path else DEFAULT_CONFIG_PATH
    
    try:
        # 确保目录存在
        os.makedirs(os.path.dirname(config_file), exist_ok=True)
        
        # 写入配置文件
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(_config_cache, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        logging.error(f"保存配置文件 {config_file} 失败: {e}")
        return False

def _get_default_config() -> Dict[str, Any]:
    """
    获取默认配置
    
    Returns:
        默认配置字典
    """
    return {
        "server": {
            "host": "127.0.0.1",
            "port": 8080,
            "access_token": "",
            "http_timeout": 30,
            "websocket_timeout": 60
        },
        "logging": {
            "level": "INFO",
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            "file": "logs/linjing.log",
            "max_size": 1024 * 1024 * 10,  # 10MB
            "backup_count": 5
        },
        "llm": {
            "provider": "openai",
            "api_key": "",
            "model": "gpt-3.5-turbo",
            "temperature": 0.7,
            "max_tokens": 2000,
            "timeout": 60
        },
        "memory": {
            "db_uri": "mongodb://localhost:27017/",
            "db_name": "linjing",
            "vector_dimensions": 1536,
            "max_context_length": 20
        },
        "emotion": {
            "base_decay_rate": 0.1,
            "update_interval": 3600,
            "default_mood": "neutral"
        },
        "plugins": {
            "enabled": ["weather", "calculator"],
            "plugin_dir": "plugins/builtin"
        }
    } 