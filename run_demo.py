#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
林镜(LingJing) - 简化版演示脚本
"""

import sys
import os

# 确保项目根目录在Python路径中
project_dir = os.path.dirname(os.path.abspath(__file__))
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)

# 尝试导入核心模块
try:
    from linjing.models import ChatStream, Message
    from linjing.core import MessageProcessor
    from linjing.utils.logger import get_logger
    from linjing.server.onebot_proxy import OneBotProxy
    from linjing.config import load_config
    
    print("成功导入核心模块!")
    
    # 创建实例
    chat_stream = ChatStream()
    print(f"创建聊天流: {chat_stream}")
    
    # 加载配置
    config = load_config()
    print(f"加载配置: {config is not None}")
    
    # 初始化日志
    logger = get_logger('demo')
    logger.info("测试日志输出")
    print("日志系统初始化成功")
    
except Exception as e:
    print(f"导入失败: {e}")
    import traceback
    traceback.print_exc()

print("演示脚本执行完毕") 