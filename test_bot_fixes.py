#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
验证机器人修复脚本
"""

import os
import sys
import asyncio
import logging
import yaml

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

async def test_bot_initialization():
    """测试机器人初始化"""
    try:
        # 添加当前目录到模块搜索路径
        sys.path.insert(0, os.path.abspath('.'))
        
        # 导入机器人类
        from linjing.bot.linjing_bot import LinjingBot
        
        # 加载配置
        config_path = "config.yaml"
        if not os.path.exists(config_path):
            logger.error(f"配置文件不存在: {config_path}")
            return False
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        # 创建并初始化机器人
        logger.info("创建机器人实例...")
        bot = LinjingBot(config)
        
        logger.info("开始初始化机器人...")
        initialized = await bot.initialize()
        
        if initialized:
            logger.info("机器人初始化成功！修复有效")
            return True
        else:
            logger.error("机器人初始化失败")
            return False
            
    except Exception as e:
        logger.error(f"测试失败: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    success = asyncio.run(test_bot_initialization())
    sys.exit(0 if success else 1) 