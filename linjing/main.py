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
import importlib # 导入 importlib
from typing import Dict, Any, Optional

# 设置模块导入路径
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# 导入必要的类和函数
from linjing.config import ConfigManager # 导入 ConfigManager 类
from linjing.constants import VERSION
from linjing.bot.linjing_bot import LinjingBot
from linjing.utils.logger import setup_logger

# 设置日志记录器
logger = logging.getLogger(__name__)

def parse_args() -> argparse.Namespace:
    """
    解析命令行参数

    Returns:
        解析后的参数
    """
    parser = argparse.ArgumentParser(description="林静聊天机器人")
    parser.add_argument("-c", "--config", help="YAML 配置文件路径") # 更新帮助文本
    parser.add_argument("-d", "--debug", action="store_true", help="启用调试模式 (覆盖配置文件中的日志级别)")
    parser.add_argument("-v", "--version", action="store_true", help="显示版本信息")
    return parser.parse_args()

def handle_signals() -> None:
    """设置信号处理函数"""
    def signal_handler(sig, frame):
        logger.info("收到退出信号，正在关闭...")
        # 通知主循环退出
        # 尝试获取正在运行的循环，如果失败则忽略
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                loop.stop()
        except RuntimeError:
             logger.warning("无法获取正在运行的事件循环来停止。")

    # 注册信号处理
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

async def main_async(config: Dict[str, Any]) -> None: # 接收配置字典
    """
    异步主函数
    """
    logger.info(f"林静聊天机器人 v{VERSION} 正在启动...")

    bot = None # 初始化 bot 变量
    try:
        # 创建机器人实例
        bot = LinjingBot(config) # 使用传入的配置

        # 初始化
        logger.info("正在初始化机器人...")
        if not await bot.initialize():
            logger.error("机器人初始化失败，退出。")
            return
        logger.info("机器人初始化完成。")

        # 启动机器人
        logger.info("正在启动机器人...")
        await bot.start()
        logger.info("机器人启动完成，进入主循环。")

        # 保持运行直到收到停止信号
        # 使用 asyncio.Future 来优雅地等待停止信号
        stop_event = asyncio.Future()
        # 将 stop_event 传递给信号处理器或其他可以触发停止的地方
        # 例如，可以在 signal_handler 中调用 stop_event.set_result(None)
        # 这里简化处理，假设 loop.stop() 会中断下面的 await
        await stop_event

    except asyncio.CancelledError:
        logger.info("主任务被取消")
    except Exception as e:
        logger.exception(f"在机器人初始化或运行过程中发生致命错误: {e}")
    finally:
        # 确保即使启动失败也尝试关闭
        if bot and hasattr(bot, 'is_running') and bot.is_running():
             logger.info("正在停止机器人...")
             await bot.stop()
             logger.info("机器人已停止。")
        else:
             logger.info("机器人未运行或未完全初始化，无需停止。")

def main() -> None:
    """
    主函数
    """
    # 解析命令行参数
    args = parse_args()

    # 显示版本信息
    if args.version:
        print(f"林静聊天机器人 v{VERSION}")
        sys.exit(0)

    # === 修改配置加载和日志设置逻辑 ===
    config_path = args.config if args.config else None # 获取命令行指定的路径，可能为 None

    # 强制重新加载 config 模块
    try:
        import linjing.config # 确保模块被导入
        importlib.reload(linjing.config) # 强制重新加载
        logger.debug("已强制重新加载 linjing.config 模块")
        # 现在再从重新加载后的模块导入 ConfigManager
        from linjing.config import ConfigManager
    except ImportError as e:
         logger.error(f"无法导入 linjing.config: {e}")
         sys.exit(1)
    except Exception as e:
         logger.error(f"重新加载 linjing.config 时出错: {e}")
         # 可以选择继续尝试，或者退出
         from linjing.config import ConfigManager # 尝试正常导入

    config_manager_instance = ConfigManager(config_path=config_path) # 实例化 ConfigManager

    # 在加载配置后设置日志级别
    # 如果命令行指定了 -d (debug)，则强制使用 DEBUG 级别
    log_level_from_config = config_manager_instance.get("system.log_level", "INFO")
    log_level = "DEBUG" if args.debug else log_level_from_config
    setup_logger(log_level)
    logger.info(f"日志级别设置为: {log_level}") # 确认日志级别

    # 设置信号处理
    handle_signals()

    # 创建事件循环
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        # 运行主函数
        loop.run_until_complete(main_async(config_manager_instance.config)) # 传递加载的配置
    except KeyboardInterrupt:
        logger.info("接收到键盘中断")
    finally:
        logger.info("开始关闭事件循环...")
        # 关闭所有剩余任务
        tasks = asyncio.all_tasks(loop)
        if tasks:
             logger.info(f"取消 {len(tasks)} 个剩余任务...")
             for task in tasks:
                  task.cancel()
             # 等待任务完成取消
             loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
             logger.info("剩余任务已处理。")

        # 关闭事件循环
        loop.close()
        logger.info("事件循环已关闭。")

if __name__ == "__main__":
    main()
