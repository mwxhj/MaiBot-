#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
配置管理模块，负责加载和管理全局配置。
"""

import os
import json
import logging
from typing import Dict, Any, Optional

import dotenv

# 加载环境变量
dotenv.load_dotenv()

class ConfigManager:
    """配置管理器，用于加载和访问配置项"""
    
    # 容器化路径配置
    DATA_PATH = os.getenv('DATA_PATH', os.path.join(os.path.dirname(__file__), '..', 'storage'))
    SQLITE_PATH = os.path.join(DATA_PATH, 'database.db')
    VECTOR_DB_PATH = os.path.join(DATA_PATH, 'vector_store')
    LOG_PATH = os.path.join(DATA_PATH, 'logs')
    
    def __init__(self, config_dir: str = "config"):
        """
        初始化配置管理器
        
        Args:
            config_dir: 配置文件目录
        """
        self.config_dir = config_dir
        self.config: Dict[str, Any] = {}
        self.default_config_path = os.path.join(config_dir, "default_config.json")
        self.user_config_path = os.path.join(config_dir, "user_config.json")
        
        # 加载配置
        self._load_config()
        
        # 设置日志级别
        log_level = self.get("bot.log_level", "INFO")
        logging.basicConfig(level=getattr(logging, log_level))
    
    def _load_config(self) -> None:
        """加载配置文件"""
        # 加载默认配置
        try:
            with open(self.default_config_path, "r", encoding="utf-8") as f:
                self.config = json.load(f)
        except FileNotFoundError:
            logging.error(f"默认配置文件不存在: {self.default_config_path}")
            self.config = {}
        except json.JSONDecodeError:
            logging.error("默认配置文件格式错误")
            self.config = {}
        
        # 加载用户配置（如果存在）
        try:
            with open(self.user_config_path, "r", encoding="utf-8") as f:
                user_config = json.load(f)
                # 递归合并配置
                self._merge_config(self.config, user_config)
        except FileNotFoundError:
            logging.warning(f"用户配置文件不存在: {self.user_config_path}")
        except json.JSONDecodeError:
            logging.error("用户配置文件格式错误")
        
        # 从环境变量覆盖一些敏感配置
        self._override_from_env()
        
        # 设置容器化路径
        self._set_container_paths()
    
    def _set_container_paths(self) -> None:
        """设置容器化路径配置"""
        self.set("storage.database_path", self.SQLITE_PATH)
        self.set("storage.vector_db_path", self.VECTOR_DB_PATH)
        self.set("logging.log_path", self.LOG_PATH)
    
    def _merge_config(self, base: Dict[str, Any], override: Dict[str, Any]) -> None:
        """
        递归合并配置
        
        Args:
            base: 基础配置
            override: 覆盖配置
        """
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_config(base[key], value)
            else:
                base[key] = value
    
    def _override_from_env(self) -> None:
        """从环境变量覆盖配置项"""
        # LLM API 密钥
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if openai_api_key:
            self.set("llm.providers.openai.api_key", openai_api_key)
        
        azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")
        if azure_api_key:
            self.set("llm.providers.azure.api_key", azure_api_key)
        
        # 天气插件 API 密钥
        weather_api_key = os.getenv("WEATHER_API_KEY")
        if weather_api_key:
            self.set("plugins.weather.api_key", weather_api_key)
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        获取配置项
        
        Args:
            key_path: 配置项路径，如 "llm.providers.openai.api_key"
            default: 默认值
            
        Returns:
            配置项的值
        """
        keys = key_path.split(".")
        config = self.config
        
        for key in keys:
            if isinstance(config, dict) and key in config:
                config = config[key]
            else:
                return default
        
        return config
    
    def set(self, key_path: str, value: Any) -> None:
        """
        设置配置项
        
        Args:
            key_path: 配置项路径
            value: 配置项的值
        """
        keys = key_path.split(".")
        config = self.config
        
        # 遍历路径直到倒数第二级
        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]
        
        # 设置最后一级的值
        config[keys[-1]] = value
    
    def save_user_config(self) -> bool:
        """
        保存用户配置
        
        Returns:
            保存是否成功
        """
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(self.user_config_path), exist_ok=True)
            
            with open(self.user_config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            logging.error(f"保存用户配置失败: {str(e)}")
            return False


# 全局配置实例
config_manager = ConfigManager()
