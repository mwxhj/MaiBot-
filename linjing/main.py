#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
林静聊天机器人主程序入口。
"""

import sys

# 尝试显式移除旧的 config 模块缓存，以防万一
if 'linjing.config' in sys.modules:
    print("DEBUG: Removing 'linjing.config' from sys.modules") # 添加调试打印
    del sys.modules['linjing.config']
if 'linjing.config.config' in sys.modules: # 也移除可能的子模块缓存
     print("DEBUG: Removing 'linjing.config.config' from sys.modules") # 添加调试打印
     del sys.modules['linjing.config.config']

import os
# sys 已经导入过了
import signal
import asyncio
import argparse
import logging
import yaml     # 添加 yaml 导入
import dotenv   # 添加 dotenv 导入
from typing import Dict, Any, Optional

# 设置模块导入路径，确保能找到 linjing 包
# 将 MaiBot- 目录添加到 sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from linjing import ConfigManager # 直接从 linjing 包导入 ConfigManager 类
# 确定 .env 文件相对于 main.py 的路径
dotenv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.env'))
dotenv.load_dotenv(dotenv_path=dotenv_path)
logger_for_dotenv = logging.getLogger(__name__ + ".dotenv") # Use a specific logger
logger_for_dotenv.info(f"Attempting to load .env file from: {dotenv_path}")
if os.path.exists(dotenv_path):
    logger_for_dotenv.info(".env file loaded successfully.")
else:
    logger_for_dotenv.warning(".env file not found at the expected location.")


# ConfigManager class definition removed, now imported from linjing.config
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

    # 获取命令行指定的配置文件路径
    config_path_arg = args.config if args.config else None

    # 创建 ConfigManager 实例，如果命令行指定了路径，则使用它
    config_manager = ConfigManager(config_path=config_path_arg)
    logger.info(f"ConfigManager instance created. Using config file: {config_manager.config_path}")
    # 显式调用 load 方法来加载配置、覆盖环境变量和设置路径
    config_manager.load()

    # 设置日志级别 (现在可以安全地从已加载的配置中获取)
    log_level_from_config = config_manager.get("system.log_level", "INFO")
    # log_level = "DEBUG" if args.debug else log_level_from_config
    # 强制设置为 DEBUG 以便调试
    log_level = "DEBUG"
    logger.info(f"强制设置日志级别为 DEBUG 进行调试。命令行参数 --debug: {args.debug}, 配置级别: {log_level_from_config}")

    # 调用 setup_logger，传入 config_manager 实例
    # log_dir 参数现在是可选的，setup_logger 会从 config_manager 获取路径
    setup_logger(config_manager, level=log_level) # 强制使用 DEBUG 级别
    # 记录实际使用的日志目录 (从 config_manager 获取)
    actual_log_dir = getattr(config_manager, 'LOG_PATH', 'Unknown') # 获取实际路径用于记录
    logger.info(f"日志级别设置为: {log_level}")
    logger.info(f"日志文件目录: {actual_log_dir}")


    handle_signals()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        # 将全局配置字典传递给 main_async
        # 将 config_manager 的配置字典传递给 main_async
        loop.run_until_complete(main_async(config_manager.config))
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
