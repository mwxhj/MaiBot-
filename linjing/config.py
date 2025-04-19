#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
配置管理模块，负责加载和管理全局配置。
"""

import os
import logging
from typing import Dict, Any, Optional

import dotenv
import yaml # 导入 yaml 库

# 加载环境变量
dotenv.load_dotenv()

class ConfigManager:
    """配置管理器，用于加载和访问配置项"""

    # 容器化路径配置
    # 修正 DATA_PATH 的计算，使其指向项目根目录下的 data 文件夹
    PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')) # 获取项目根目录 (linjing 的上两级)
    DATA_PATH = os.getenv('DATA_PATH', os.path.join(PROJECT_ROOT, 'MaiBot-', 'data')) # 指向 MaiBot-/data
    SQLITE_PATH = os.path.join(DATA_PATH, 'database.db')
    VECTOR_DB_PATH = os.path.join(DATA_PATH, 'vector_store')
    LOG_PATH = os.path.join(DATA_PATH, 'logs')

    def __init__(self, config_path: Optional[str] = None): # 允许外部传入路径
        """
        初始化配置管理器

        Args:
            config_path: YAML 配置文件路径 (可选)
        """
        self.config_path = config_path or os.path.join(self.PROJECT_ROOT, "MaiBot-", "config.yaml") # 默认加载 MaiBot-/config.yaml
        self.config: Dict[str, Any] = {}

        # 加载配置
        self._load_config()

        # 设置日志级别 (加载配置后)
        log_level = self.get("system.log_level", "INFO") # 从 system 获取 log_level
        # 注意：日志库的全局配置可能需要在 main.py 中进行，以确保覆盖默认设置
        # logging.basicConfig(level=getattr(logging, log_level))

    def _load_config(self) -> None:
        """加载配置文件"""
        # 加载 YAML 配置
        try:
            logging.info(f"尝试从以下路径加载配置: {self.config_path}")
            with open(self.config_path, "r", encoding="utf-8") as f:
                loaded_config = yaml.safe_load(f)
                if not isinstance(loaded_config, dict):
                     logging.error(f"配置文件顶层必须是字典格式: {self.config_path}")
                     self.config = {}
                else:
                     self.config = loaded_config
        except FileNotFoundError:
            logging.error(f"配置文件不存在: {self.config_path}")
            self.config = {}
        except yaml.YAMLError as e:
            logging.error(f"配置文件格式错误: {e}")
            self.config = {}

        # 从环境变量覆盖一些敏感配置
        self._override_from_env()

        # 设置容器化路径
        self._set_container_paths()

    def _set_container_paths(self) -> None:
        """设置容器化路径配置"""
        # 确保路径存在，如果不存在则创建
        os.makedirs(self.DATA_PATH, exist_ok=True)
        os.makedirs(self.LOG_PATH, exist_ok=True)
        # 注意：这里假设 YAML 结构与之前的 JSON 结构类似，如果不同需要调整 key_path
        self.set("storage.database.path", self.SQLITE_PATH) # 调整路径以匹配 YAML
        self.set("storage.vector_db.path", self.VECTOR_DB_PATH) # 调整路径以匹配 YAML
        # 日志路径通常由日志库配置，这里可能不需要设置

    def _override_from_env(self) -> None:
        """从环境变量覆盖配置项"""
        # 遍历 providers 列表来覆盖 API 密钥和 URL
        providers = self.get("llm.providers", [])
        if isinstance(providers, list):
            for i, provider in enumerate(providers):
                if isinstance(provider, dict):
                    provider_id = provider.get("id")
                    # OpenAI/Compatible API Key
                    if provider_id == "openai_main" or provider.get("type") == "openai_compatible":
                         env_key_name = f"PROVIDER_{i}_API_KEY" # e.g., PROVIDER_0_API_KEY
                         api_key = os.getenv(env_key_name) or os.getenv("OPENAI_API_KEY") # Fallback to OPENAI_API_KEY for first compatible
                         if api_key:
                              self.set(f"llm.providers.{i}.api_key", api_key)

                    # MingWang Specific (Example based on previous config)
                    if provider_id == "mingwang_provider":
                         mingwang_api_key = os.getenv("MINGWANG_API_KEY")
                         if mingwang_api_key:
                              self.set(f"llm.providers.{i}.api_key", mingwang_api_key)
                         mingwang_base_url = os.getenv("MINGWANG_BASE_URL")
                         if mingwang_base_url:
                              self.set(f"llm.providers.{i}.api_base", mingwang_base_url)

                    # Add other provider-specific env overrides here if needed

        # OneBot Access Token
        onebot_token = os.getenv("ONEBOT_ACCESS_TOKEN")
        if onebot_token:
             self.set("adapters.onebot.access_token", onebot_token)
        onebot_host = os.getenv("ONEBOT_HOST")
        if onebot_host:
             self.set("adapters.onebot.reverse_ws_host", onebot_host)
        onebot_port = os.getenv("ONEBOT_PORT")
        if onebot_port:
             try:
                  self.set("adapters.onebot.reverse_ws_port", int(onebot_port))
             except ValueError:
                  logging.warning(f"环境变量 ONEBOT_PORT ('{onebot_port}') 不是有效的端口号，将使用默认值。")


    def get(self, key_path: str, default: Any = None) -> Any:
        """
        获取配置项

        Args:
            key_path: 配置项路径，如 "llm.providers.0.api_key"
            default: 默认值

        Returns:
            配置项的值
        """
        keys = key_path.split(".")
        value = self.config

        for key in keys:
            if isinstance(value, dict):
                value = value.get(key, default)
                if value is default: # Key not found or value is None and default is None
                    return default
            elif isinstance(value, list):
                 try:
                      idx = int(key)
                      if 0 <= idx < len(value):
                           value = value[idx]
                      else:
                           return default # Index out of bounds
                 except (ValueError, IndexError):
                      return default # Invalid index format or out of bounds
            else:
                return default # Cannot traverse further

        return value

    def set(self, key_path: str, value: Any) -> None:
        """
        设置配置项

        Args:
            key_path: 配置项路径
            value: 配置项的值
        """
        keys = key_path.split(".")
        obj = self.config

        for i, key in enumerate(keys[:-1]):
            if isinstance(obj, list):
                 try:
                      idx = int(key)
                      if not (0 <= idx < len(obj)):
                           # Handle index out of bounds if necessary, e.g., append or raise error
                           logging.warning(f"设置配置时索引 '{idx}' 超出列表范围: {key_path}")
                           return
                      if i + 1 < len(keys): # Check if not the last key part
                           next_key = keys[i+1]
                           if not isinstance(obj[idx], (dict, list)):
                                try:
                                     int(next_key) # Check if next key is an index
                                     obj[idx] = [] # Overwrite with list if next key is index
                                except ValueError:
                                     obj[idx] = {} # Overwrite with dict otherwise
                      obj = obj[idx]
                 except (ValueError, IndexError):
                      logging.error(f"设置配置时无效的列表索引 '{key}': {key_path}")
                      return
            elif isinstance(obj, dict):
                 if key not in obj or not isinstance(obj[key], (dict, list)):
                      # Look ahead to see if the next key is an integer (list index)
                      if i + 1 < len(keys):
                           next_key = keys[i+1]
                           try:
                                int(next_key)
                                obj[key] = [] # Create list if next key is index
                           except ValueError:
                                obj[key] = {} # Create dict otherwise
                      else: # Last key part, create dict
                           obj[key] = {}
                 obj = obj[key]
            else:
                 logging.error(f"设置配置时无法遍历非字典/列表对象: {key_path}")
                 return

        # Set the final value
        last_key = keys[-1]
        if isinstance(obj, list):
             try:
                  idx = int(last_key)
                  if 0 <= idx < len(obj):
                       obj[idx] = value
                  elif idx == len(obj): # Allow appending
                       obj.append(value)
                  else:
                       logging.warning(f"设置配置时最终索引 '{idx}' 超出列表范围: {key_path}")
             except ValueError:
                  logging.error(f"设置配置时最终键 '{last_key}' 不是有效的列表索引: {key_path}")
        elif isinstance(obj, dict):
             obj[last_key] = value
        else:
             logging.error(f"设置配置时无法在非字典/列表对象上设置最终值: {key_path}")


# 全局配置实例
# 实例化 ConfigManager 时不立即加载，允许 main.py 控制加载时机和路径
config_manager = None # 定义一个全局变量，稍后在 main.py 中实例化
