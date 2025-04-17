#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
测试脚本：验证修复后的Qdrant Windows路径处理逻辑
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

# 设置日志
logging.basicConfig(level=logging.DEBUG, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("test_qdrant_path")

# 获取当前文件所在目录，即storage目录
current_dir = os.path.dirname(os.path.abspath(__file__))
# 获取项目根目录
project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
# 将项目根目录添加到系统路径
sys.path.insert(0, project_root)

from linjing.storage.vector_db_enhanced import VectorDBManagerEnhanced

async def test_windows_path():
    """测试Windows路径处理逻辑"""
    
    # 创建测试目录
    test_dir = os.path.join(current_dir, "test_qdrant_data")
    os.makedirs(test_dir, exist_ok=True)
    
    logger.info(f"测试目录: {test_dir}")
    logger.info(f"系统名称: {os.name}")
    
    # 创建配置
    config = {
        "collection_name": "test_collection",
        "vector_size": 128,
        "local": True,
        "local_path": test_dir,
    }
    
    # 初始化向量数据库管理器
    db_manager = VectorDBManagerEnhanced(config)
    
    try:
        # 尝试连接
        logger.info("尝试连接...")
        connected = await db_manager.connect()
        logger.info(f"连接结果: {connected}")
        
        if connected:
            # 添加测试向量
            vector_id = "test_vector_1"
            vector = [0.1] * 128  # 128维向量
            metadata = {"name": "测试向量", "test": True}
            
            logger.info(f"添加向量: {vector_id}")
            success = await db_manager.add_vector(vector_id, vector, metadata)
            logger.info(f"添加结果: {success}")
            
            # 获取向量
            logger.info(f"获取向量: {vector_id}")
            result = await db_manager.get_vector(vector_id)
            logger.info(f"获取结果: {'成功' if result else '失败'}")
            
            if result:
                logger.info(f"获取到的向量元数据: {result['metadata']}")
            
            # 断开连接
            await db_manager.disconnect()
            
        return connected
    
    except Exception as e:
        logger.error(f"测试过程中发生错误: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    logger.info("开始Windows路径处理测试")
    asyncio.run(test_windows_path())
    logger.info("测试完成") 