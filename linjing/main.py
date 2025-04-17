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
from typing import Dict, Any, Optional

# 设置模块导入路径
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from linjing.config import config_manager
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
    parser.add_argument("-c", "--config", help="配置文件路径")
    parser.add_argument("-d", "--debug", action="store_true", help="启用调试模式")
    parser.add_argument("-v", "--version", action="store_true", help="显示版本信息")
    return parser.parse_args()

def handle_signals() -> None:
    """设置信号处理函数"""
    def signal_handler(sig, frame):
        logger.info("收到退出信号，正在关闭...")
        # 通知主循环退出
        asyncio.get_event_loop().stop()
    
    # 注册信号处理
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

async def main_async() -> None:
    """
    异步主函数
    """
    logger.info(f"林静聊天机器人 v{VERSION} 正在启动...")
    
    # 创建机器人实例
    bot = LinjingBot(config_manager.config)
    
    # 初始化
    if not await bot.initialize():
        logger.error("机器人初始化失败")
        return
    
    # 启动机器人
    await bot.start()
    
    try:
        # 保持运行直到收到停止信号
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        logger.info("任务被取消")
    finally:
        # 关闭机器人
        await bot.stop()
        logger.info("机器人已关闭")

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
    
    # 设置日志级别
    log_level = "DEBUG" if args.debug else config_manager.get("bot.log_level", "INFO")
    setup_logger(log_level)
    
    # 如果指定了配置文件路径，重新加载配置
    if args.config:
        config_dir = os.path.dirname(args.config)
        config_file = os.path.basename(args.config)
        config_manager.__init__(config_dir)
    
    # 设置信号处理
    handle_signals()
    
    # 创建事件循环
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        # 运行主函数
        loop.run_until_complete(main_async())
    except KeyboardInterrupt:
        logger.info("接收到键盘中断")
    finally:
        # 关闭所有任务
        tasks = asyncio.all_tasks(loop)
        for task in tasks:
            task.cancel()
        
        # 运行未完成的任务直到完成
        if tasks:
            loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
        
        # 关闭事件循环
        loop.close()
        logger.info("事件循环已关闭")

if __name__ == "__main__":
    main() 