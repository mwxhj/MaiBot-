#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
简单测试脚本，只测试记忆管理器部分
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

async def test_memory_manager():
    """测试记忆管理器初始化"""
    try:
        # 添加当前目录到模块搜索路径
        sys.path.insert(0, os.path.abspath('.'))
        
        # 导入记忆管理器
        from linjing.memory.memory_manager import MemoryManager
        
        # 加载配置
        config_path = "config.yaml"
        if not os.path.exists(config_path):
            logger.error(f"配置文件不存在: {config_path}")
            return False
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        # 创建记忆管理器
        memory_config = config.get("memory", {})
        
        # 确保vector_db配置是字典而不是字符串
        vector_db_config = config.get("storage", {}).get("vector_db", {})
        if not isinstance(vector_db_config, dict):
            vector_db_config = {}
        
        # 在配置中添加向量数据库配置
        memory_config["vector_db"] = vector_db_config
        
        # 在配置中添加数据库路径
        memory_config["db_path"] = config.get("storage", {}).get("db_path", "data/database.db")
        
        # 创建记忆管理器
        logger.info("创建记忆管理器...")
        memory_manager = MemoryManager(config=memory_config)
        
        # 初始化记忆管理器
        logger.info("初始化记忆管理器...")
        initialized = await memory_manager.initialize()
        
        if initialized:
            logger.info("记忆管理器初始化成功！修复有效")
            
            # 关闭记忆管理器
            await memory_manager.close()
            return True
        else:
            logger.error("记忆管理器初始化失败")
            return False
        
    except Exception as e:
        logger.error(f"测试失败: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    success = asyncio.run(test_memory_manager())
    sys.exit(0 if success else 1) 