#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
林静聊天机器人主程序入口。
"""

import os
import sys # Import sys
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

from linjing.config import config_manager, get_log_directory # 从独立模块导入配置管理器和日志目录函数
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

    # 使用从 linjing.config 导入的全局 config_manager 实例
    config_path = args.config if args.config else None
    if config_path:
        # 如果命令行指定了配置文件，需要重新加载配置
        # 注意：这假设 config_manager 实例已经存在，并且可以重新加载
        # 如果 config_manager 设计为单例且不允许重载，则需要调整逻辑
        logger.info(f"Command line specified config path: {config_path}. Reloading configuration.")
        # 假设 ConfigManager 有一个 reload 方法，或者需要重新实例化
        # config_manager.reload(config_path) # 示例：如果存在 reload 方法
        # 或者，如果必须重新实例化（不推荐，因为会丢失之前的状态）:
        # global config_manager
        # config_manager = ConfigManager(config_path=config_path)
        # 这里我们暂时假设 config_manager 在启动时已正确加载默认或环境变量指定的配置
        # 并且命令行参数主要用于覆盖，或者在 ConfigManager 内部处理
        # 最简单的处理方式是让 ConfigManager 在初始化时检查 args.config
        # 但这会引入 main 对 config 的反向依赖，所以最好是在 main 中处理
        # 目前，我们仅记录日志，并依赖 config_manager 已被正确初始化
        logger.warning("Command line config path provided, but reloading logic is not fully implemented here. Ensure ConfigManager handles this or was initialized correctly.")


    # 设置日志级别 (现在从导入的 config_manager 获取)
    log_level_from_config = config_manager.get("system.log_level", "INFO")
    log_level = "DEBUG" if args.debug else log_level_from_config
    # 确保 setup_logger 使用正确的 log_path (从 config_manager 获取)
    # 注意：config_manager 需要暴露 LOG_PATH 属性或提供 get_log_path 方法
    # 假设 config_manager.LOG_PATH 存在
    log_dir = get_log_directory() # 使用导入的函数获取日志目录
    setup_logger(level=log_level, log_dir=log_dir) # 传递 log_dir
    logger.info(f"日志级别设置为: {log_level}")
    logger.info(f"日志文件目录: {log_dir}")


    handle_signals()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        # 将全局配置字典传递给 main_async
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
