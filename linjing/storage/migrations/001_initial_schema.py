#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
初始数据库结构迁移

创建基本的数据库表结构，包括用户、会话和记忆表。
"""

import logging
from typing import Any, Dict, List, Optional

from ...utils.logger import get_logger
from ..storage_models import UserModel, SessionModel, MemoryModel

logger = get_logger(__name__)


async def up(db_manager) -> bool:
    """
    创建初始数据库结构
    
    Args:
        db_manager: 数据库管理器
        
    Returns:
        是否执行成功
    """
    try:
        # 创建用户表
        user_table_sql = await UserModel.create_table_sql()
        success = await db_manager.execute_script(user_table_sql)
        if not success:
            logger.error("创建用户表失败")
            return False
        
        # 创建会话表
        session_table_sql = await SessionModel.create_table_sql()
        success = await db_manager.execute_script(session_table_sql)
        if not success:
            logger.error("创建会话表失败")
            return False
        
        # 创建记忆表
        memory_table_sql = await MemoryModel.create_table_sql()
        success = await db_manager.execute_script(memory_table_sql)
        if not success:
            logger.error("创建记忆表失败")
            return False
        
        # 创建情绪表
        emotion_table_sql = """
        CREATE TABLE IF NOT EXISTS user_emotions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            emotion_data TEXT NOT NULL,
            timestamp REAL NOT NULL,
            UNIQUE(user_id, timestamp)
        );
        CREATE INDEX IF NOT EXISTS idx_user_emotions_user_id_timestamp 
        ON user_emotions(user_id, timestamp);
        """
        success = await db_manager.execute_script(emotion_table_sql)
        if not success:
            logger.error("创建情绪表失败")
            return False
        
        logger.info("初始数据库结构创建成功")
        return True
    except Exception as e:
        logger.error(f"创建初始数据库结构失败: {e}")
        return False


async def down(db_manager) -> bool:
    """
    回滚初始数据库结构
    
    Args:
        db_manager: 数据库管理器
        
    Returns:
        是否执行成功
    """
    try:
        # 删除表（按依赖关系的反序删除）
        tables = [
            "user_emotions",
            "memories",
            "sessions",
            "users"
        ]
        
        for table in tables:
            query = f"DROP TABLE IF EXISTS {table}"
            success = await db_manager.execute_query(query)
            if not success:
                logger.error(f"删除表 {table} 失败")
                return False
        
        logger.info("初始数据库结构已回滚")
        return True
    except Exception as e:
        logger.error(f"回滚初始数据库结构失败: {e}")
        return False 