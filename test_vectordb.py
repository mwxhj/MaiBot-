#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
向量数据库测试脚本

用于测试向量数据库的连接、存储、检索功能
"""

import argparse
import asyncio
import json
import logging
import os
import random
import sys
import uuid

# 设置日志格式
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger("VectorDBTest")

async def test_vector_db():
    """测试向量数据库功能"""
    try:
        # 解析命令行参数
        parser = argparse.ArgumentParser(description="向量数据库测试工具")
        parser.add_argument("--config", help="配置文件路径")
        parser.add_argument("--collection", help="集合名称", default="test_collection")
        parser.add_argument("--dimension", type=int, help="向量维度", default=384)
        args = parser.parse_args()
        
        # 读取配置
        config_path = args.config
        vector_db_config = {}
        
        if config_path and os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                vector_db_config = config.get("storage", {}).get("vector_db", {})
        
        # 设置默认配置
        if not vector_db_config:
            vector_db_config = {
                "collection_name": args.collection,
                "vector_size": args.dimension,
                "similarity": "cosine",
                "local": True,
                "local_path": os.path.expanduser("~/.linjing/data/test_vectors")
            }
        
        # 检查collection_name
        if "collection_name" not in vector_db_config:
            vector_db_config["collection_name"] = args.collection
        
        # 转换dimension为vector_size (兼容性处理)
        if "dimension" in vector_db_config:
            vector_db_config["vector_size"] = vector_db_config.pop("dimension")
            logger.debug(f"将dimension转换为vector_size: {vector_db_config['vector_size']}")
        
        # 导入向量数据库管理器工厂
        from linjing.storage.vector_db_manager_factory import VectorDBManagerFactory
        
        # 创建向量数据库管理器
        vector_db = VectorDBManagerFactory.create(config=vector_db_config)
        logger.info(f"向量数据库管理器初始化完成: {vector_db.config.collection_name}, {vector_db.config.vector_size}")
        
        # 连接到向量数据库
        connected = await vector_db.connect()
        logger.info(f"连接状态: {connected}")
        
        if connected:
            # 测试添加向量
            import random
            import uuid
            
            # 生成测试向量
            vector = [random.random() for _ in range(vector_db.config.vector_size)]
            payload = {"type": "test", "content": "测试向量", "timestamp": 1234567890}
            
            # 自定义向量ID
            test_id = str(uuid.uuid4())
            logger.debug(f"准备添加向量，ID: {test_id}, 载荷: {payload}")
            
            # 添加向量
            added = await vector_db.add_vector(test_id, vector, payload)
            logger.info(f"添加向量结果: {'成功' if added else '失败'}, ID: {test_id}")
            
            # 测试获取向量
            result = await vector_db.get_vector(test_id)
            if result:
                logger.info(f"获取向量成功，ID: {result.get('id')}")
                logger.debug(f"获取的向量载荷: {result.get('metadata')}")
            else:
                logger.error(f"获取向量失败，ID: {test_id}")
            
            # 测试搜索向量
            logger.debug(f"准备搜索相似向量，查询向量长度: {len(vector)}")
            search_results = await vector_db.search_similar(vector, limit=5)
            logger.info(f"搜索向量结果数量: {len(search_results)}")
            
            # 打印搜索结果
            for i, result in enumerate(search_results):
                logger.info(f"搜索结果 #{i+1}: ID={result['id']}, 得分={result['score']}")
                logger.debug(f"结果 #{i+1} 载荷: {result['metadata']}")
            
            # 测试删除向量
            logger.debug(f"准备删除向量，ID: {test_id}")
            deleted = await vector_db.delete_vector(test_id)
            logger.info(f"删除向量结果: {'成功' if deleted else '失败'}")
            
            # 验证删除是否成功
            check_result = await vector_db.get_vector(test_id)
            if check_result:
                logger.warning(f"向量删除失败，仍然可以获取到向量: {check_result}")
            else:
                logger.info("向量删除验证成功，无法再获取到已删除的向量")
            
            # 断开连接
            await vector_db.disconnect()
            logger.info("测试完成")
        
    except Exception as e:
        logger.error(f"测试失败: {e}", exc_info=True)

if __name__ == "__main__":
    sys.path.insert(0, os.path.abspath('.'))
    asyncio.run(test_vector_db()) 