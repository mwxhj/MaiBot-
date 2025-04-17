#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
数据库管理器模块，基于SQLite提供异步数据库操作。
"""

import logging
import os
import aiosqlite
import json
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    数据库管理器，提供异步SQL操作接口。
    
    基于SQLite实现，支持异步操作，用于存储结构化数据。
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        初始化数据库管理器。
        
        Args:
            config: 数据库配置字典，包含连接参数
        """
        self.config = config or {}
        self.db_path = self.config.get("db_path", "data/linjing.db")
        self._connection = None
        self._initialized = False
        
        # 确保db_path目录存在
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        logger.info(f"数据库管理器初始化，数据库路径：{self.db_path}")
    
    async def connect(self) -> bool:
        """
        连接到数据库
        
        Returns:
            是否连接成功
        """
        try:
            if self._connection is None:
                self._connection = await aiosqlite.connect(self.db_path)
                # 启用外键约束
                await self._connection.execute("PRAGMA foreign_keys = ON")
                # 设置行工厂，使查询结果返回字典
                self._connection.row_factory = self._dict_factory
                
                logger.info("成功连接到SQLite数据库")
                
                # 初始化数据库表
                await self._initialize_tables()
                
                self._initialized = True
                return True
            return True
        except Exception as e:
            logger.error(f"连接数据库失败: {e}", exc_info=True)
            return False
    
    async def disconnect(self) -> None:
        """
        断开数据库连接
        """
        if self._connection:
            await self._connection.close()
            self._connection = None
            self._initialized = False
            logger.info("已断开数据库连接")
    
    async def execute_query(self, query: str, params: Tuple = ()) -> List[Dict[str, Any]]:
        """
        执行查询操作
        
        Args:
            query: SQL查询语句
            params: 查询参数元组
            
        Returns:
            查询结果列表，每项为一个字典
        """
        if not self._initialized:
            await self.connect()
        
        try:
            async with self._connection.execute(query, params) as cursor:
                return await cursor.fetchall()
        except Exception as e:
            logger.error(f"执行查询失败: {e}", exc_info=True)
            logger.debug(f"查询: {query}, 参数: {params}")
            return []
    
    async def execute_insert(self, query: str, params: Tuple = ()) -> int:
        """
        执行插入操作
        
        Args:
            query: SQL插入语句
            params: 插入参数元组
            
        Returns:
            最后插入行的ID，如果插入失败则返回-1
        """
        if not self._initialized:
            await self.connect()
        
        try:
            async with self._connection.execute(query, params) as cursor:
                await self._connection.commit()
                return cursor.lastrowid or -1
        except Exception as e:
            logger.error(f"执行插入失败: {e}", exc_info=True)
            logger.debug(f"查询: {query}, 参数: {params}")
            return -1
    
    async def execute_update(self, query: str, params: Tuple = ()) -> int:
        """
        执行更新操作
        
        Args:
            query: SQL更新语句
            params: 更新参数元组
            
        Returns:
            受影响的行数，如果更新失败则返回-1
        """
        if not self._initialized:
            await self.connect()
        
        try:
            async with self._connection.execute(query, params) as cursor:
                await self._connection.commit()
                return cursor.rowcount
        except Exception as e:
            logger.error(f"执行更新失败: {e}", exc_info=True)
            logger.debug(f"查询: {query}, 参数: {params}")
            return -1
    
    async def execute_transaction(self, queries: List[Tuple[str, Tuple]]) -> bool:
        """
        执行事务操作
        
        Args:
            queries: 查询列表，每项为(query, params)元组
            
        Returns:
            事务是否执行成功
        """
        if not self._initialized:
            await self.connect()
        
        try:
            async with self._connection.cursor() as cursor:
                await cursor.execute("BEGIN TRANSACTION")
                try:
                    for query, params in queries:
                        await cursor.execute(query, params)
                    await self._connection.commit()
                    return True
                except Exception as e:
                    await self._connection.rollback()
                    logger.error(f"事务执行失败，已回滚: {e}", exc_info=True)
                    return False
        except Exception as e:
            logger.error(f"事务处理失败: {e}", exc_info=True)
            return False
    
    async def table_exists(self, table_name: str) -> bool:
        """
        检查表是否存在
        
        Args:
            table_name: 表名
            
        Returns:
            表是否存在
        """
        if not self._initialized:
            await self.connect()
        
        try:
            query = "SELECT name FROM sqlite_master WHERE type='table' AND name=?"
            result = await self.execute_query(query, (table_name,))
            return len(result) > 0
        except Exception as e:
            logger.error(f"检查表存在失败: {e}", exc_info=True)
            return False
    
    async def execute_script(self, script: str) -> bool:
        """
        执行SQL脚本
        
        Args:
            script: SQL脚本内容
            
        Returns:
            脚本是否执行成功
        """
        if not self._initialized:
            await self.connect()
        
        try:
            await self._connection.executescript(script)
            await self._connection.commit()
            return True
        except Exception as e:
            logger.error(f"执行脚本失败: {e}", exc_info=True)
            return False
    
    async def _initialize_tables(self) -> None:
        """
        初始化数据库表
        """
        # 创建记忆表
        memories_table = """
        CREATE TABLE IF NOT EXISTS memories (
            id TEXT PRIMARY KEY,
            content TEXT NOT NULL,
            memory_type TEXT NOT NULL,
            importance REAL DEFAULT 0.5,
            creation_time REAL,
            last_access_time REAL,
            access_count INTEGER DEFAULT 0,
            user_id TEXT,
            session_id TEXT,
            metadata TEXT,
            decay_rate REAL DEFAULT 0.05
        );
        CREATE INDEX IF NOT EXISTS idx_memories_user_id ON memories(user_id);
        CREATE INDEX IF NOT EXISTS idx_memories_memory_type ON memories(memory_type);
        CREATE INDEX IF NOT EXISTS idx_memories_creation_time ON memories(creation_time);
        """
        
        # 创建会话表
        sessions_table = """
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            start_time REAL,
            end_time REAL,
            metadata TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
        """
        
        # 创建用户表
        users_table = """
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            name TEXT,
            platform TEXT,
            platform_id TEXT,
            created_at REAL,
            last_active_at REAL,
            metadata TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_users_platform_id ON users(platform, platform_id);
        """
        
        # 执行创建表操作
        tables_script = memories_table + sessions_table + users_table
        await self.execute_script(tables_script)
        
        logger.info("数据库表初始化完成")
    
    def _dict_factory(self, cursor, row):
        """
        将查询结果行转换为字典
        
        Args:
            cursor: 游标对象
            row: 结果行
            
        Returns:
            字典形式的结果行
        """
        d = {}
        for idx, col in enumerate(cursor.description):
            value = row[idx]
            # 尝试解析JSON字符串
            if col[0] == 'metadata' and isinstance(value, str):
                try:
                    d[col[0]] = json.loads(value)
                except json.JSONDecodeError:
                    d[col[0]] = value
            else:
                d[col[0]] = value
        return d 