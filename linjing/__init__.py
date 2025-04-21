#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
林镜(Linjing) - 一个有个性的AI聊天机器人
包含核心配置管理器。
"""

# 标准库导入
import os
import sys
import logging
from typing import Dict, Any, Optional

# 第三方库导入
import dotenv
import yaml

# 本地导入 (保持现有)
from .constants import VERSION

__version__ = VERSION
__author__ = "LinjingBot Team"
__email__ = "author@example.com"

# --- ConfigManager 类定义 ---
class ConfigManager:
    """配置管理器，用于加载和访问配置项"""

    # --- 路径计算调整 ---
    # __file__ 现在指向 linjing/__init__.py
    # PROJECT_ROOT 现在是 linjing 目录
    PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
    # MAIBOT_ROOT 是上一级目录 (MaiBot-)
    MAIBOT_ROOT = os.path.abspath(os.path.join(PROJECT_ROOT, '..'))
    # DATA_PATH 相对于 MAIBOT_ROOT
    DATA_PATH = os.getenv('DATA_PATH', os.path.join(MAIBOT_ROOT, 'data')) # MaiBot-/data
    SQLITE_PATH = os.path.join(DATA_PATH, 'database.db')
    VECTOR_DB_PATH = os.path.join(DATA_PATH, 'vector_store')
    LOG_PATH = os.path.join(DATA_PATH, 'logs')
    # --- 路径计算结束 ---

    def __init__(self, config_path: Optional[str] = None):
        """
        初始化配置管理器 (轻量级)。
        仅设置路径和空的配置字典。

        Args:
            config_path: YAML 配置文件路径 (可选)
        """
        # 默认配置文件路径相对于 MAIBOT_ROOT
        self.config_path = config_path or os.path.join(self.MAIBOT_ROOT, "config.yaml") # MaiBot-/config.yaml
        self.config: Dict[str, Any] = {}
        # 不在此处执行加载或记录日志

    def load(self) -> None:
        """
        加载配置、覆盖环境变量并设置路径。
        这个方法应该在所有模块导入完成后，在 main 函数中调用。
        """
        # --- .env 加载逻辑移至此处 ---
        try:
            # .env 文件路径相对于 MAIBOT_ROOT
            dotenv_path = os.path.join(self.MAIBOT_ROOT, '.env')
            dotenv.load_dotenv(dotenv_path=dotenv_path)
            logger_for_dotenv = logging.getLogger(__name__ + ".dotenv_init") # 使用特定 logger
            logger_for_dotenv.info(f"Attempting to load .env file from __init__.py context: {dotenv_path}")
            if os.path.exists(dotenv_path):
                logger_for_dotenv.info(".env file loaded successfully from __init__.py.")
            else:
                 logger_for_dotenv.warning(".env file not found at the expected location from __init__.py.")
        except Exception as e:
             # 使用标准 logging 记录错误，以防 loguru 未配置
             logging.error(f"Error loading .env file in ConfigManager.load: {e}", exc_info=True)
        # --- .env 加载逻辑结束 ---

        logging.info(f"Loading configuration from: {self.config_path}")
        self._load_config()
        self._override_from_env()
        self._set_container_paths()
        logging.info("Configuration loaded successfully.")

    def _load_config(self) -> None:
        """加载配置文件"""
        try:
            abs_config_path = os.path.abspath(self.config_path)
            logging.info(f"Attempting to load config from absolute path: {abs_config_path}")
            if not os.path.exists(abs_config_path):
                 logging.error(f"Config file does not exist: {abs_config_path}")
                 self.config = {}
                 return

            with open(abs_config_path, "r", encoding="utf-8") as f:
                loaded_config = yaml.safe_load(f)
                if not isinstance(loaded_config, dict):
                     logging.error(f"Config file top level must be a dictionary: {abs_config_path}")
                     self.config = {}
                else:
                     self.config = loaded_config
                     logging.info(f"Successfully loaded config from: {abs_config_path}")
        except FileNotFoundError:
            logging.error(f"Config file not found (exception): {abs_config_path}")
            self.config = {}
        except yaml.YAMLError as e:
            logging.error(f"Config file format error: {e}")
            self.config = {}
        except Exception as e:
             logging.error(f"Unknown error loading config file: {e}", exc_info=True)
             self.config = {}

    def _set_container_paths(self) -> None:
        """设置容器化路径配置"""
        logging.debug(f"Setting container paths. DATA_PATH: {self.DATA_PATH}, LOG_PATH: {self.LOG_PATH}")
        os.makedirs(self.DATA_PATH, exist_ok=True)
        os.makedirs(self.LOG_PATH, exist_ok=True)
        self.set("storage.database.path", self.SQLITE_PATH)
        self.set("storage.vector_db.path", self.VECTOR_DB_PATH)
        self.set("system.logging.log_dir", self.LOG_PATH)
        logging.debug(f"Database path set to: {self.SQLITE_PATH}")
        logging.debug(f"Vector DB path set to: {self.VECTOR_DB_PATH}")
        logging.debug(f"Log directory set in config: {self.LOG_PATH}")

    def _override_from_env(self) -> None:
        """从环境变量覆盖配置项"""
        logging.debug("Overriding configuration from environment variables...")
        providers = self.get("llm.providers", [])
        if isinstance(providers, list):
            for i, provider in enumerate(providers):
                if isinstance(provider, dict):
                    provider_id = provider.get("id")
                    logging.debug(f"Checking environment variables for provider index {i}, id: {provider_id}")
                    env_key_name_key = f"PROVIDER_{i}_API_KEY"
                    env_key_name_base = f"PROVIDER_{i}_API_BASE"
                    if provider.get("type") == "openai_compatible":
                         api_key = os.getenv(env_key_name_key) or os.getenv("OPENAI_API_KEY")
                         if api_key:
                              logging.info(f"Overriding API key for provider index {i} ({provider_id}) from environment.")
                              self.set(f"llm.providers.{i}.api_key", api_key)
                         api_base = os.getenv(env_key_name_base) or os.getenv("OPENAI_API_BASE")
                         if api_base:
                              logging.info(f"Overriding API base for provider index {i} ({provider_id}) from environment.")
                              self.set(f"llm.providers.{i}.api_base", api_base)
                    elif provider_id == "mingwang_provider":
                         mingwang_api_key = os.getenv("MINGWANG_API_KEY")
                         if mingwang_api_key:
                              logging.info(f"Overriding API key for mingwang_provider (index {i}) from MINGWANG_API_KEY.")
                              self.set(f"llm.providers.{i}.api_key", mingwang_api_key)
                         mingwang_base_url = os.getenv("MINGWANG_BASE_URL")
                         if mingwang_base_url:
                              logging.info(f"Overriding API base for mingwang_provider (index {i}) from MINGWANG_BASE_URL.")
                              self.set(f"llm.providers.{i}.api_base", mingwang_base_url)

        onebot_token = os.getenv("ONEBOT_ACCESS_TOKEN")
        if onebot_token:
             logging.info("Overriding OneBot access token from ONEBOT_ACCESS_TOKEN.")
             self.set("adapters.onebot.access_token", onebot_token)
        onebot_host = os.getenv("ONEBOT_HOST")
        if onebot_host:
             logging.info("Overriding OneBot host from ONEBOT_HOST.")
             self.set("adapters.onebot.reverse_ws_host", onebot_host)
        onebot_port = os.getenv("ONEBOT_PORT")
        if onebot_port:
             try:
                  port_int = int(onebot_port)
                  logging.info(f"Overriding OneBot port from ONEBOT_PORT to {port_int}.")
                  self.set("adapters.onebot.reverse_ws_port", port_int)
             except ValueError:
                  logging.warning(f"Environment variable ONEBOT_PORT ('{onebot_port}') is not a valid port number, using default.")
        logging.debug("Finished overriding configuration from environment variables.")

    def get(self, key_path: str, default: Any = None) -> Any:
        """安全地获取嵌套配置项"""
        keys = key_path.split(".")
        value = self.config
        try:
            for key in keys:
                if isinstance(value, dict):
                    if key in value:
                        value = value[key]
                    else:
                        return default
                elif isinstance(value, list):
                     try:
                          idx = int(key)
                          if 0 <= idx < len(value):
                               value = value[idx]
                          else:
                               return default
                     except (ValueError, IndexError):
                          return default
                else:
                    return default
            return value
        except Exception as e:
            logging.error(f"Error getting config key '{key_path}': {e}", exc_info=True)
            return default

    def set(self, key_path: str, value: Any) -> None:
        """安全地设置嵌套配置项，支持列表索引"""
        keys = key_path.split(".")
        obj = self.config
        try:
            for i, key in enumerate(keys[:-1]):
                is_last_parent = (i == len(keys) - 2)
                next_key = keys[i+1]

                if isinstance(obj, list):
                     try:
                          idx = int(key)
                          if not (0 <= idx < len(obj)):
                               logging.warning(f"Setting config: index '{idx}' out of bounds for list: {key_path}")
                               return
                          if is_last_parent:
                              try:
                                  int(next_key)
                                  if not isinstance(obj[idx], list):
                                      logging.warning(f"Setting config: trying to access index '{next_key}' but element at '{idx}' is not a list in '{key_path}'. Creating list.")
                                      obj[idx] = []
                              except ValueError:
                                  if not isinstance(obj[idx], dict):
                                      logging.warning(f"Setting config: trying to access key '{next_key}' but element at '{idx}' is not a dict in '{key_path}'. Creating dict.")
                                      obj[idx] = {}
                          obj = obj[idx]
                     except (ValueError, IndexError):
                          logging.error(f"Setting config: invalid list index '{key}': {key_path}")
                          return
                elif isinstance(obj, dict):
                     if key not in obj or not isinstance(obj.get(key), (dict, list)):
                         if is_last_parent:
                             try:
                                 int(next_key)
                                 obj[key] = []
                             except ValueError:
                                 obj[key] = {}
                         else:
                              obj[key] = {}
                     obj = obj[key]
                else:
                     logging.error(f"Setting config: cannot traverse non-dict/list object at key '{key}': {key_path}")
                     return

            last_key = keys[-1]
            if isinstance(obj, list):
                 try:
                      idx = int(last_key)
                      if 0 <= idx < len(obj):
                           obj[idx] = value
                      elif idx == len(obj):
                           obj.append(value)
                      else:
                           logging.warning(f"Setting config: final index '{idx}' out of bounds for list: {key_path}")
                 except ValueError:
                      logging.error(f"Setting config: final key '{last_key}' is not a valid list index: {key_path}")
            elif isinstance(obj, dict):
                 obj[last_key] = value
            else:
                 logging.error(f"Setting config: cannot set final value on non-dict/list object: {key_path}")

        except Exception as e:
             logging.error(f"Error setting config key '{key_path}': {e}", exc_info=True)

# --- ConfigManager 类定义结束 ---

# 显式导出 ConfigManager 和 VERSION
__all__ = ['ConfigManager', 'VERSION']