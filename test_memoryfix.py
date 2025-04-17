#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
记忆管理器修复测试
"""

import asyncio
import logging
import os
import sys

# 设置日志 - 强制输出所有级别的日志
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)

# 添加控制台处理器
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
root_logger.addHandler(console_handler)

logger = logging.getLogger(__name__)
# 强制输出测试日志
logger.setLevel(logging.DEBUG)
print("日志级别已设置为DEBUG，开始测试...")

async def test_memory_fix():
    """测试记忆管理器修复"""
    try:
        # 添加当前目录到模块搜索路径
        sys.path.insert(0, os.path.abspath('.'))
        
        print("正在导入记忆管理器模块...")
        # 导入记忆管理器
        from linjing.memory.memory_manager import MemoryManager
        
        # 测试配置
        test_config = {
            "db_path": "data/test_memory.db",
            "vector_db": {
                "location": "data/test_vectors",
                "vector_size": 128,
                "similarity": "cosine"
            }
        }
        
        # 创建记忆管理器
        print("创建记忆管理器...")
        memory_manager = MemoryManager(config=test_config)
        
        # 初始化记忆管理器
        print("初始化记忆管理器...")
        await memory_manager.initialize()
        
        print("记忆管理器初始化成功！修复有效")
        
        # 关闭记忆管理器
        await memory_manager.close()
        
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    print("开始执行测试...")
    asyncio.run(test_memory_fix())
    print("测试完成") 