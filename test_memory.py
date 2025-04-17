#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
记忆管理器测试脚本
"""

import asyncio
import logging
import os
import sys
import yaml
import json
import time
from typing import Any, Dict, List, Optional, Tuple, Union
from unittest.mock import patch

# 设置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# 添加路径，确保能够导入模块
sys.path.insert(0, os.path.abspath('.'))

# 导入必要的模块
from linjing.storage.database import DatabaseManager
from linjing.storage.vector_db import VectorDBManager
from linjing.memory.memory_manager import MemoryManager


class PatchedDatabaseManager(DatabaseManager):
    """
    重写的数据库管理器，可以直接接受字符串路径
    """
    def __init__(self, config=None):
        """
        初始化数据库管理器，处理字符串路径
        
        Args:
            config: 数据库配置字典或字符串路径
        """
        if isinstance(config, str):
            # 如果是字符串，则将其作为db_path
            super().__init__({"db_path": config})
        else:
            # 否则正常初始化
            super().__init__(config)


async def test_memory_manager():
    """测试记忆管理器"""
    try:
        # 加载配置
        config_path = "config.yaml"
        if not os.path.exists(config_path):
            logger.error(f"配置文件不存在: {config_path}")
            return
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        # 打印配置信息
        storage_config = config.get("storage", {})
        db_config = storage_config.get("database", {})
        vector_db_config = storage_config.get("vector_db", {})
        memory_config = config.get("memory", {})
        
        logger.info(f"数据库配置: {db_config}")
        logger.info(f"向量数据库配置: {vector_db_config}")
        logger.info(f"记忆配置: {memory_config}")
        
        # 准备记忆管理器配置
        memory_manager_config: Dict[str, Any] = {}
        
        # 设置数据库路径
        db_path = db_config.get("path", "data/linjing.db")
        memory_manager_config["db_path"] = db_path
        
        # 处理向量数据库配置
        vector_config = vector_db_config.copy()
        
        # 将path转换为location以匹配VectorDBManager的参数
        if "path" in vector_config:
            vector_config["location"] = vector_config.pop("path")
            logger.debug(f"将path转换为location: {vector_config['location']}")
        
        # 将dimension转换为vector_size以匹配VectorDBManager的参数
        if "dimension" in vector_config:
            vector_config["vector_size"] = vector_config.pop("dimension")
            logger.debug(f"将dimension转换为vector_size: {vector_config['vector_size']}")
        
        # 设置向量数据库配置
        memory_manager_config["vector_db"] = vector_config
        
        # 添加记忆系统的其他配置
        for key, value in memory_config.items():
            memory_manager_config[key] = value
        
        # 打印完整的记忆管理器配置
        logger.info(f"记忆管理器配置: {memory_manager_config}")
        
        # 使用补丁替换DatabaseManager
        with patch('linjing.memory.memory_manager.DatabaseManager', PatchedDatabaseManager):
            # 创建记忆管理器实例
            memory_manager = MemoryManager(config=memory_manager_config)
            logger.info(f"记忆管理器初始化完成：数据库路径={memory_manager.db_path}")
            
            # 初始化记忆管理器
            initialized = await memory_manager.initialize()
            logger.info(f"记忆管理器初始化状态: {initialized}")
            
            if initialized:
                # 测试添加对话记忆
                user_id = "test_user"
                session_id = "test_session"
                content = "这是一条测试消息"
                role = "user"
                metadata = {"source": "test_script", "test_id": 123}
                
                # 生成简单的测试嵌入向量 (实际应用中应使用真实的嵌入模型)
                import random
                vector_size = memory_manager.vector_db.vector_size
                test_embedding = [random.random() for _ in range(vector_size)]
                
                # 添加对话记忆（带嵌入向量）
                memory_id = await memory_manager.add_conversation_memory(
                    user_id=user_id,
                    session_id=session_id,
                    content=content,
                    role=role,
                    metadata=metadata,
                    embedding=test_embedding,
                    importance=0.8
                )
                logger.info(f"添加对话记忆成功，ID: {memory_id}")
                
                # 获取对话历史
                conversation_history = await memory_manager.get_conversation_history(
                    user_id=user_id,
                    session_id=session_id,
                    limit=5,
                    include_metadata=True
                )
                logger.info(f"获取对话历史数量: {len(conversation_history)}")
                
                for i, memory in enumerate(conversation_history):
                    logger.info(f"对话记忆 #{i+1}: ID={memory['id']}, 内容={memory['content'][:30]}...")
                    if 'metadata' in memory:
                        logger.debug(f"记忆 #{i+1} 元数据: {memory['metadata']}")
                
                # 测试相似度搜索
                similar_memories = await memory_manager.search_similar_memories(
                    query_embedding=test_embedding,
                    limit=5,
                    memory_type="conversation",
                    user_id=user_id
                )
                logger.info(f"相似记忆搜索结果数量: {len(similar_memories)}")
                
                for i, memory in enumerate(similar_memories):
                    logger.info(f"相似记忆 #{i+1}: ID={memory['id']}, 内容={memory['content'][:30]}..., 相似度={memory.get('similarity_score', 'N/A')}")
                
                # 测试获取会话列表
                sessions = await memory_manager.get_session_list(user_id)
                logger.info(f"获取会话列表数量: {len(sessions)}")
                
                for i, session in enumerate(sessions):
                    logger.info(f"会话 #{i+1}: ID={session['session_id']}, 消息数={session['message_count']}")
                
                # 测试删除对话记忆
                if memory_id:
                    deleted = await memory_manager.delete_conversation(memory_id)
                    logger.info(f"删除对话记忆结果: {'成功' if deleted else '失败'}")
                    
                    # 验证删除结果
                    verify_history = await memory_manager.get_conversation_history(
                        user_id=user_id,
                        session_id=session_id
                    )
                    logger.info(f"删除后对话历史数量: {len(verify_history)}")
                
                # 关闭记忆管理器
                await memory_manager.close()
                logger.info("记忆管理器关闭成功")
        
    except Exception as e:
        logger.error(f"测试失败: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(test_memory_manager()) 