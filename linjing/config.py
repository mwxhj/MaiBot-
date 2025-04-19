#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
配置管理模块，负责加载和管理全局配置。
"""

import os
import logging
from typing import Dict, Any, Optional

import dotenv
import yaml

# 加载环境变量
dotenv.load_dotenv()

class ConfigManager:
    """配置管理器，用于加载和访问配置项"""

    PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    DATA_PATH = os.getenv('DATA_PATH', os.path.join(PROJECT_ROOT, 'MaiBot-', 'data'))
    SQLITE_PATH = os.path.join(DATA_PATH, 'database.db')
    VECTOR_DB_PATH = os.path.join(DATA_PATH, 'vector_store')
    LOG_PATH = os.path.join(DATA_PATH, 'logs')

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or os.path.join(self.PROJECT_ROOT, "MaiBot-", "config.yaml")
        self.config: Dict[str, Any] = {}
        self._load_config()

    # 保留原有 ConfigManager 的所有方法...
    # 包括 _load_config, _set_container_paths, _override_from_env, get, set 等方法

# 全局配置实例
config_manager = ConfigManager()
