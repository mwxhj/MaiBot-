#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
林镜(LingJing) - QQ群机器人主程序入口
"""

import asyncio
import logging
from .server.onebot_proxy import OneBotProxy
from .core.message_processor import MessageProcessor
from .utils.logger import setup_logger
from .config import load_config

async def main():
    """主函数"""
    # 加载配置
    config = load_config()
    
    # 设置日志
    setup_logger(config.get('logging', {}))
    logger = logging.getLogger('linjing')
    logger.info("林镜(LingJing)启动中...")
    
    # 初始化消息处理器
    message_processor = MessageProcessor()
    await message_processor.initialize()
    
    # 初始化OneBot代理
    onebot_proxy = OneBotProxy()
    onebot_proxy.register_handler(message_processor.process_message)
    
    # 启动服务器
    host = config.get('server', {}).get('host', '127.0.0.1')
    port = config.get('server', {}).get('port', 8080)
    
    try:
        await onebot_proxy.start_server(host, port)
        logger.info(f"OneBot服务器已启动于 {host}:{port}")
        
        # 保持运行
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        logger.info("接收到终止信号，正在关闭...")
    except Exception as e:
        logger.error(f"发生错误: {e}", exc_info=True)
    finally:
        await onebot_proxy.stop_server()
        logger.info("林镜(LingJing)已关闭")

if __name__ == "__main__":
    asyncio.run(main()) 