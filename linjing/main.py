#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
林镜聊天机器人主程序入口。
"""

import sys
import os
import signal
import asyncio
import argparse
import logging # 保留基础 logging 用于早期错误
from typing import Dict, Any # <-- 重新导入 Dict 和 Any

# 设置模块导入路径
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from linjing import ConfigManager, VERSION
from linjing.app import Application # 导入新的 Application 类
from loguru import logger as loguru_logger # 保留 Loguru 用于日志设置

# --- 全局变量 --- # 移除，这些由 Application 管理
# logger = None
# stop_event = asyncio.Event()

def parse_args() -> argparse.Namespace:
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="林镜聊天机器人")
    parser.add_argument("-c", "--config", help="YAML 配置文件路径")
    parser.add_argument("-d", "--debug", action="store_true", help="启用调试模式 (覆盖配置文件中的日志级别)")
    parser.add_argument("-v", "--version", action="store_true", help="显示版本信息")
    return parser.parse_args()

def setup_logging(config: Dict[str, Any], debug_mode: bool) -> bool:
    """配置日志系统 (Loguru)。"""
    logger_setup_done = False
    try:
        log_level_from_config = config.get("system", {}).get("log_level", "INFO")
        log_level = "DEBUG" if debug_mode else log_level_from_config
        log_file_path_pattern = config.get("system", {}).get("log_file", "logs/linjing_{time:YYYY-MM-DD}.log")
        log_dir = os.path.dirname(log_file_path_pattern)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)

        loguru_logger.remove() # 移除默认处理器
        loguru_logger.add(
            sys.stderr,
            level=log_level,
            format=(
                "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
                "<level>{message}</level>"
            ),
            colorize=True
        )
        loguru_logger.add(
            log_file_path_pattern,
            level=log_level,
            rotation="00:00",
            retention=config.get("system", {}).get("log_retention", "7 days"),
            compression=config.get("system", {}).get("log_compression", "zip"),
            encoding="utf-8",
            format=(
                "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
                "{level: <8} | "
                "{name}:{function}:{line} - "
                "{message}"
            )
        )
        # loguru_logger.info("日志系统初始化完成。") # 由 Application 记录更合适
        logger_setup_done = True
    except Exception as e_log:
        # Fallback basic logging if loguru setup fails
        logging.basicConfig(level=logging.ERROR)
        logging.error(f"初始化日志系统时出错: {e_log}，将使用基本日志记录。", exc_info=True)
    return logger_setup_done

# --- 移除所有旧的 main_async, run_bot_async, 辅助函数等 --- 
# --- 移除 handle_signals, logging_consumer, simulate_input --- 
# --- 移除硬编码 CONFIG --- 

# --- 程序入口点 ---
if __name__ == "__main__":
    args = parse_args()
    if args.version:
        print(f"林镜聊天机器人 v{VERSION}")
        sys.exit(0)

    # 1. 加载配置
    config_manager = ConfigManager(config_path=args.config)
    try:
        config_manager.load()
        config = config_manager.config
        logger_setup_done = False
    except FileNotFoundError as e:
        logging.basicConfig(level=logging.ERROR)
        logging.error(f"错误：无法加载配置文件: {e}")
        sys.exit(1)
    except Exception as e_cfg:
        logging.basicConfig(level=logging.ERROR)
        logging.error(f"加载配置时发生意外错误: {e_cfg}", exc_info=True)
        sys.exit(1)

    # 2. 设置日志
    logger_setup_done = setup_logging(config, args.debug)
    # 获取主 logger (即使设置失败也会是 basic logger)
    entry_logger = loguru_logger if logger_setup_done else logging.getLogger(__name__)
    entry_logger.info("日志系统已配置。")
    entry_logger.debug(f"使用的配置文件: {config_manager.config_path}")

    # 3. 创建并运行 Application
    app = Application(config)
    
    # 4. 运行事件循环
    try:
        # 使用 asyncio.run() 可以简化事件循环管理
        asyncio.run(app.run(), debug=args.debug)
    except KeyboardInterrupt:
        entry_logger.info("收到 KeyboardInterrupt，程序即将退出。")
        # app.run() 的 finally 块应该已经处理了关闭
    except Exception as e_main:
        entry_logger.critical(f"应用程序运行时发生未捕获的顶层错误: {e_main}", exc_info=True)
        sys.exit(1)
    finally:
        entry_logger.info("主程序退出。")

    sys.exit(0)
