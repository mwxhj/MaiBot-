#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
配置管理模块，负责加载和管理全局配置。
"""

import os
import sys # 导入 sys 以便在方法中使用路径操作
import logging
from typing import Dict, Any, Optional

import dotenv
import yaml

# 加载环境变量
# 确定 .env 文件相对于 config.py 的路径
# config.py 位于 linjing/ 目录下, 因此 '..' 指向 MaiBot- 目录
project_root_for_dotenv = os.path.abspath(os.path.join(os.path.dirname(__file__), '..')) # MaiBot- 目录
dotenv_path = os.path.join(project_root_for_dotenv, '.env')
dotenv.load_dotenv(dotenv_path=dotenv_path)
# 使用标准 logging 记录 .env 加载状态，因为 loguru 可能尚未配置
logger_for_dotenv = logging.getLogger(__name__ + ".dotenv_config") # 使用特定的记录器名称
logger_for_dotenv.info(f"Attempting to load .env file from config.py context: {dotenv_path}")
if os.path.exists(dotenv_path):
    logger_for_dotenv.info(".env file loaded successfully from config.py.")
else:
    logger_for_dotenv.warning(".env file not found at the expected location from config.py.")


class ConfigManager:
    """配置管理器，用于加载和访问配置项"""

    # 修正 PROJECT_ROOT 的计算，使其基于 config.py 的位置
    PROJECT_ROOT = os.path.abspath(os.path.dirname(os.path.dirname(__file__))) # MaiBot- 目录
    # 调整 DATA_PATH 相对于新的 PROJECT_ROOT
    DATA_PATH = os.getenv('DATA_PATH', os.path.join(PROJECT_ROOT, 'data')) # MaiBot-/data
    SQLITE_PATH = os.path.join(DATA_PATH, 'database.db')
    VECTOR_DB_PATH = os.path.join(DATA_PATH, 'vector_store')
    LOG_PATH = os.path.join(DATA_PATH, 'logs')


    def __init__(self, config_path: Optional[str] = None): # 允许外部传入路径
        """
        初始化配置管理器

        Args:
            config_path: YAML 配置文件路径 (可选)
        """
        # 修正 config_path 的默认值计算
        self.config_path = config_path or os.path.join(self.PROJECT_ROOT, "config.yaml") # 默认加载 MaiBot-/config.yaml
        self.config: Dict[str, Any] = {}
        # 使用标准 logging，因为 loguru 可能尚未配置
        logging.info(f"ConfigManager initialized. Expecting config file at: {self.config_path}")


        # 加载配置
        self._load_config()

        # 日志级别设置移到 main 函数中，在 setup_logger 调用前

    def _load_config(self) -> None:
        """加载配置文件"""
        try:
            # 确保使用绝对路径
            abs_config_path = os.path.abspath(self.config_path)
            logging.info(f"Attempting to load config from absolute path: {abs_config_path}")
            if not os.path.exists(abs_config_path):
                 logging.error(f"Config file does not exist: {abs_config_path}")
                 self.config = {} # 如果文件不存在，初始化为空字典
                 return

            with open(abs_config_path, "r", encoding="utf-8") as f:
                loaded_config = yaml.safe_load(f)
                if not isinstance(loaded_config, dict):
                     logging.error(f"Config file top level must be a dictionary: {abs_config_path}")
                     self.config = {}
                else:
                     self.config = loaded_config
                     logging.info(f"Successfully loaded config from: {abs_config_path}")
        except FileNotFoundError: # 理论上会被 exists 检查捕获，但保留是好习惯
            logging.error(f"Config file not found (exception): {abs_config_path}")
            self.config = {}
        except yaml.YAMLError as e:
            logging.error(f"Config file format error: {e}")
            self.config = {}
        except Exception as e: # 捕获其他潜在错误
             logging.error(f"Unknown error loading config file: {e}", exc_info=True)
             self.config = {}


        # 从环境变量覆盖一些敏感配置
        self._override_from_env()

        # 设置容器化路径
        self._set_container_paths()

    def _set_container_paths(self) -> None:
        """设置容器化路径配置"""
        logging.debug(f"Setting container paths. DATA_PATH: {self.DATA_PATH}, LOG_PATH: {self.LOG_PATH}")
        # 在设置配置路径前确保目录存在
        os.makedirs(self.DATA_PATH, exist_ok=True)
        os.makedirs(self.LOG_PATH, exist_ok=True)
        self.set("storage.database.path", self.SQLITE_PATH)
        self.set("storage.vector_db.path", self.VECTOR_DB_PATH)
        # 同时在配置中设置日志路径，以便其他地方（如日志设置）使用
        self.set("system.logging.log_dir", self.LOG_PATH) # 假设使用此键结构
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
                    # 示例简化逻辑，根据实际提供者类型调整
                    env_key_name_key = f"PROVIDER_{i}_API_KEY"
                    env_key_name_base = f"PROVIDER_{i}_API_BASE"
                    # 通用 OpenAI 兼容性检查
                    if provider.get("type") == "openai_compatible":
                         api_key = os.getenv(env_key_name_key) or os.getenv("OPENAI_API_KEY") # 允许通用回退
                         if api_key:
                              logging.info(f"Overriding API key for provider index {i} ({provider_id}) from environment.")
                              self.set(f"llm.providers.{i}.api_key", api_key)
                         api_base = os.getenv(env_key_name_base) or os.getenv("OPENAI_API_BASE") # 允许通用回退
                         if api_base:
                              logging.info(f"Overriding API base for provider index {i} ({provider_id}) from environment.")
                              self.set(f"llm.providers.{i}.api_base", api_base)
                    # 特定提供者检查 (如 mingwang)
                    elif provider_id == "mingwang_provider":
                         mingwang_api_key = os.getenv("MINGWANG_API_KEY")
                         if mingwang_api_key:
                              logging.info(f"Overriding API key for mingwang_provider (index {i}) from MINGWANG_API_KEY.")
                              self.set(f"llm.providers.{i}.api_key", mingwang_api_key)
                         mingwang_base_url = os.getenv("MINGWANG_BASE_URL")
                         if mingwang_base_url:
                              logging.info(f"Overriding API base for mingwang_provider (index {i}) from MINGWANG_BASE_URL.")
                              self.set(f"llm.providers.{i}.api_base", mingwang_base_url)
                    # 如果需要，在此处添加其他特定提供者的覆盖

        # OneBot 覆盖
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
                        # logging.debug(f"Key '{key}' not found in dict for path '{key_path}'. Returning default.")
                        return default
                elif isinstance(value, list):
                     try:
                          idx = int(key)
                          if 0 <= idx < len(value):
                               value = value[idx]
                          else:
                               # logging.debug(f"Index '{idx}' out of bounds for list in path '{key_path}'. Returning default.")
                               return default
                     except (ValueError, IndexError):
                          # logging.debug(f"Invalid index '{key}' for list in path '{key_path}'. Returning default.")
                          return default
                else:
                    # logging.debug(f"Cannot traverse non-dict/list at path '{key_path}'. Returning default.")
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
                          # 确保目标元素存在，并且如果需要，它是一个容器
                          if is_last_parent:
                              # 如果下一个键看起来像索引，确保列表元素是列表
                              # 如果下一个键看起来像字典键，确保列表元素是字典
                              try:
                                  int(next_key) # 检查下一个键是否是索引
                                  if not isinstance(obj[idx], list):
                                      logging.warning(f"Setting config: trying to access index '{next_key}' but element at '{idx}' is not a list in '{key_path}'. Creating list.")
                                      obj[idx] = []
                              except ValueError: # 下一个键不是索引，假定是字典键
                                  if not isinstance(obj[idx], dict):
                                      logging.warning(f"Setting config: trying to access key '{next_key}' but element at '{idx}' is not a dict in '{key_path}'. Creating dict.")
                                      obj[idx] = {}
                          obj = obj[idx]
                     except (ValueError, IndexError):
                          logging.error(f"Setting config: invalid list index '{key}': {key_path}")
                          return
                elif isinstance(obj, dict):
                     # 确保目标元素存在，并且如果需要，它是一个容器
                     if key not in obj or not isinstance(obj.get(key), (dict, list)):
                         if is_last_parent:
                             try:
                                 int(next_key) # 检查下一个键是否是索引
                                 obj[key] = [] # 如果下一个键是索引，创建列表
                             except ValueError:
                                 obj[key] = {} # 否则创建字典
                         else: # 如果不是最后一个父级，默认创建字典
                              obj[key] = {}
                     obj = obj[key]
                else:
                     logging.error(f"Setting config: cannot traverse non-dict/list object at key '{key}': {key_path}")
                     return

            # 设置最终值
            last_key = keys[-1]
            if isinstance(obj, list):
                 try:
                      idx = int(last_key)
                      if 0 <= idx < len(obj):
                           obj[idx] = value
                      elif idx == len(obj): # 允许追加
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


# 全局配置实例
config_manager = ConfigManager()

# 可选：添加一个函数以方便地获取日志目录
def get_log_directory() -> str:
    """返回配置的日志目录路径。"""
    # 确保 LOG_PATH 在实例上可用
    if hasattr(config_manager, 'LOG_PATH'):
        return config_manager.LOG_PATH
    else:
        # 提供一个回退值，以防 LOG_PATH 未设置
        logging.warning("ConfigManager.LOG_PATH not found, returning default log path.")
        # 使用与 ConfigManager 中相同的逻辑计算默认值
        default_project_root = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
        return os.path.join(default_project_root, 'data', 'logs')
