#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
林静聊天机器人主程序入口。
"""

import os
import sys
import signal
import asyncio
import argparse
import logging
import yaml     # 添加 yaml 导入
import dotenv   # 添加 dotenv 导入
from typing import Dict, Any, Optional

# --- ConfigManager Class Definition Start ---
# (代码从 linjing/config.py 移动到这里)

# 加载环境变量 (移到类定义之前或之内，确保尽早加载)
dotenv.load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env')) # 指定 .env 文件路径

class ConfigManager:
    """配置管理器，用于加载和访问配置项"""

    # 容器化路径配置
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
        # 修正 PROJECT_ROOT 的计算，使其基于 main.py 的位置
        self.PROJECT_ROOT = os.path.abspath(os.path.dirname(os.path.dirname(__file__))) # main.py 在 linjing/ 下，上一级是 MaiBot-
        self.DATA_PATH = os.getenv('DATA_PATH', os.path.join(self.PROJECT_ROOT, 'data')) # 指向 MaiBot-/data
        self.SQLITE_PATH = os.path.join(self.DATA_PATH, 'database.db')
        self.VECTOR_DB_PATH = os.path.join(self.DATA_PATH, 'vector_store')
        self.LOG_PATH = os.path.join(self.DATA_PATH, 'logs')

        # 修正 config_path 的默认值计算
        self.config_path = config_path or os.path.join(self.PROJECT_ROOT, "config.yaml") # 默认加载 MaiBot-/config.yaml
        self.config: Dict[str, Any] = {}

        # 加载配置
        self._load_config()

        # 日志级别设置移到 main 函数中，在 setup_logger 调用前

    def _load_config(self) -> None:
        """加载配置文件"""
        try:
            logging.info(f"尝试从以下路径加载配置: {self.config_path}")
            # 确保使用绝对路径
            abs_config_path = os.path.abspath(self.config_path)
            if not os.path.exists(abs_config_path):
                 logging.error(f"配置文件不存在: {abs_config_path}")
                 self.config = {}
                 return

            with open(abs_config_path, "r", encoding="utf-8") as f:
                loaded_config = yaml.safe_load(f)
                if not isinstance(loaded_config, dict):
                     logging.error(f"配置文件顶层必须是字典格式: {abs_config_path}")
                     self.config = {}
                else:
                     self.config = loaded_config
        except FileNotFoundError: # 理论上上面的 exists 检查后不应触发，但保留
            logging.error(f"配置文件不存在: {abs_config_path}")
            self.config = {}
        except yaml.YAMLError as e:
            logging.error(f"配置文件格式错误: {e}")
            self.config = {}
        except Exception as e: # 捕获其他潜在错误
             logging.error(f"加载配置文件时发生未知错误: {e}", exc_info=True)
             self.config = {}


        # 从环境变量覆盖一些敏感配置
        self._override_from_env()

        # 设置容器化路径
        self._set_container_paths()

    def _set_container_paths(self) -> None:
        """设置容器化路径配置"""
        os.makedirs(self.DATA_PATH, exist_ok=True)
        os.makedirs(self.LOG_PATH, exist_ok=True)
        self.set("storage.database.path", self.SQLITE_PATH)
        self.set("storage.vector_db.path", self.VECTOR_DB_PATH)

    def _override_from_env(self) -> None:
        """从环境变量覆盖配置项"""
        providers = self.get("llm.providers", [])
        if isinstance(providers, list):
            for i, provider in enumerate(providers):
                if isinstance(provider, dict):
                    provider_id = provider.get("id")
                    if provider_id == "openai_main" or provider.get("type") == "openai_compatible":
                         env_key_name = f"PROVIDER_{i}_API_KEY"
                         api_key = os.getenv(env_key_name) or os.getenv("OPENAI_API_KEY")
                         if api_key:
                              self.set(f"llm.providers.{i}.api_key", api_key)
                    if provider_id == "mingwang_provider":
                         mingwang_api_key = os.getenv("MINGWANG_API_KEY")
                         if mingwang_api_key:
                              self.set(f"llm.providers.{i}.api_key", mingwang_api_key)
                         mingwang_base_url = os.getenv("MINGWANG_BASE_URL")
                         if mingwang_base_url:
                              self.set(f"llm.providers.{i}.api_base", mingwang_base_url)
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
        keys = key_path.split(".")
        value = self.config
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key, default)
                if value is default:
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

    def set(self, key_path: str, value: Any) -> None:
        keys = key_path.split(".")
        obj = self.config
        for i, key in enumerate(keys[:-1]):
            if isinstance(obj, list):
                 try:
                      idx = int(key)
                      if not (0 <= idx < len(obj)):
                           logging.warning(f"设置配置时索引 '{idx}' 超出列表范围: {key_path}")
                           return
                      if i + 1 < len(keys):
                           next_key = keys[i+1]
                           if not isinstance(obj[idx], (dict, list)):
                                try:
                                     int(next_key)
                                     obj[idx] = []
                                except ValueError:
                                     obj[idx] = {}
                      obj = obj[idx]
                 except (ValueError, IndexError):
                      logging.error(f"设置配置时无效的列表索引 '{key}': {key_path}")
                      return
            elif isinstance(obj, dict):
                 if key not in obj or not isinstance(obj[key], (dict, list)):
                      if i + 1 < len(keys):
                           next_key = keys[i+1]
                           try:
                                int(next_key)
                                obj[key] = []
                           except ValueError:
                                obj[key] = {}
                      else:
                           obj[key] = {}
                 obj = obj[key]
            else:
                 logging.error(f"设置配置时无法遍历非字典/列表对象: {key_path}")
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
                       logging.warning(f"设置配置时最终索引 '{idx}' 超出列表范围: {key_path}")
             except ValueError:
                  logging.error(f"设置配置时最终键 '{last_key}' 不是有效的列表索引: {key_path}")
        elif isinstance(obj, dict):
             obj[last_key] = value
        else:
             logging.error(f"设置配置时无法在非字典/列表对象上设置最终值: {key_path}")

# --- ConfigManager Class Definition End ---


# 设置模块导入路径 (可能不再需要，但保留以防万一)
# sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# 导入其他必要的类和函数
from linjing.constants import VERSION
from linjing.bot.linjing_bot import LinjingBot
from linjing.utils.logger import setup_logger

# 设置日志记录器
logger = logging.getLogger(__name__)

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="林静聊天机器人")
    parser.add_argument("-c", "--config", help="YAML 配置文件路径")
    parser.add_argument("-d", "--debug", action="store_true", help="启用调试模式 (覆盖配置文件中的日志级别)")
    parser.add_argument("-v", "--version", action="store_true", help="显示版本信息")
    return parser.parse_args()

def handle_signals() -> None:
    def signal_handler(sig, frame):
        logger.info("收到退出信号，正在关闭...")
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                loop.stop()
        except RuntimeError:
             logger.warning("无法获取正在运行的事件循环来停止。")
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

async def main_async(config: Dict[str, Any]) -> None:
    logger.info(f"林静聊天机器人 v{VERSION} 正在启动...")
    bot = None
    try:
        bot = LinjingBot(config)
        logger.info("正在初始化机器人...")
        if not await bot.initialize():
            logger.error("机器人初始化失败，退出。")
            return
        logger.info("机器人初始化完成。")
        logger.info("正在启动机器人...")
        await bot.start()
        logger.info("机器人启动完成，进入主循环。")
        stop_event = asyncio.Future()
        await stop_event
    except asyncio.CancelledError:
        logger.info("主任务被取消")
    except Exception as e:
        logger.exception(f"在机器人初始化或运行过程中发生致命错误: {e}")
    finally:
        if bot and hasattr(bot, 'is_running') and bot.is_running():
             logger.info("正在停止机器人...")
             await bot.stop()
             logger.info("机器人已停止。")
        else:
             logger.info("机器人未运行或未完全初始化，无需停止。")

def main() -> None:
    args = parse_args()
    if args.version:
        print(f"林静聊天机器人 v{VERSION}")
        sys.exit(0)

    # 使用定义在本文件中的 ConfigManager
    config_path = args.config if args.config else None
    config_manager_instance = ConfigManager(config_path=config_path) # 直接使用本文件定义的类

    # 设置日志级别
    log_level_from_config = config_manager_instance.get("system.log_level", "INFO")
    log_level = "DEBUG" if args.debug else log_level_from_config
    setup_logger(log_level)
    logger.info(f"日志级别设置为: {log_level}")

    handle_signals()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(main_async(config_manager_instance.config))
    except KeyboardInterrupt:
        logger.info("接收到键盘中断")
    finally:
        logger.info("开始关闭事件循环...")
        tasks = asyncio.all_tasks(loop)
        if tasks:
             logger.info(f"取消 {len(tasks)} 个剩余任务...")
             for task in tasks:
                  task.cancel()
             loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
             logger.info("剩余任务已处理。")
        loop.close()
        logger.info("事件循环已关闭。")

if __name__ == "__main__":
    main()
