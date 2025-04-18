#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
SQLite数据库管理器模块，提供异步数据库操作。
支持连接管理、查询执行、事务处理和表管理功能。
"""

import asyncio
import json
import logging
import os
import sqlite3
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple, Union

import aiosqlite

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    SQLite数据库管理器，提供异步数据库操作。
    
    提供以下功能：
    - 异步连接管理
    - SQL查询执行
    - 事务处理
    - 表结构管理
    """
    
    def __init__(self, db_path: str, config: Dict[str, Any] = None):
        """
        初始化数据库管理器
        
        Args:
            db_path: 数据库文件路径
            config: 配置字典
        """
        self.db_path = db_path
        self.config = config or {}
        
        self.connection = None
        self.connection_lock = asyncio.Lock()
        self.is_connected = False
        
        # 确保数据库目录存在
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        
        logger.info(f"SQLite数据库管理器初始化完成，路径：{db_path}")
    
    async def connect(self) -> None:
        """
        异步连接到数据库
        """
        if self.is_connected:
            return
        
        async with self.connection_lock:
            if self.is_connected:
                return
            
            try:
                logger.info(f"连接到SQLite数据库：{self.db_path}")
                self.connection = await aiosqlite.connect(self.db_path)
                
                # 启用外键约束
                await self.connection.execute("PRAGMA foreign_keys = ON")
                
                # 设置连接参数
                await self.connection.execute("PRAGMA journal_mode = WAL")
                await self.connection.execute("PRAGMA synchronous = NORMAL")
                
                self.is_connected = True
                logger.info("SQLite数据库连接成功")
            except Exception as e:
                logger.error(f"连接SQLite数据库失败: {e}", exc_info=True)
                raise
    
    async def disconnect(self) -> None:
        """
        断开数据库连接
        """
        if not self.is_connected:
            return
        
        async with self.connection_lock:
            if not self.is_connected:
                return
            
            try:
                logger.info("断开SQLite数据库连接")
                await self.connection.close()
                self.connection = None
                self.is_connected = False
                logger.info("SQLite数据库连接已关闭")
            except Exception as e:
                logger.error(f"断开SQLite数据库连接失败: {e}", exc_info=True)
                raise
    
    async def execute_query(
        self, 
        query: str, 
        params: Tuple = (), 
        fetch_all: bool = True
    ) -> Union[List[Tuple], Optional[Tuple], None]:
        """
        执行SQL查询并返回结果
        
        Args:
            query: SQL查询语句
            params: 查询参数
            fetch_all: 是否返回所有结果
            
        Returns:
            查询结果，如果是SELECT查询则返回结果集，否则返回None
        """
        if not self.is_connected:
            await self.connect()
        
        try:
            async with self.connection.execute(query, params) as cursor:
                if query.strip().upper().startswith(("SELECT", "PRAGMA")):
                    if fetch_all:
                        return await cursor.fetchall()
                    else:
                        return await cursor.fetchone()
                else:
                    await self.connection.commit()
                    return None
        except Exception as e:
            logger.error(f"执行SQL查询失败: {e}\nQuery: {query}\nParams: {params}", exc_info=True)
            raise
    
    async def execute_many(self, query: str, params_list: List[Tuple]) -> None:
        """
        批量执行SQL语句
        
        Args:
            query: SQL语句
            params_list: 参数列表
        """
        if not self.is_connected:
            await self.connect()
        
        try:
            async with self.connection.executemany(query, params_list) as cursor:
                await self.connection.commit()
        except Exception as e:
            logger.error(f"批量执行SQL失败: {e}\nQuery: {query}", exc_info=True)
            raise
    
    async def execute_transaction(self, queries: List[Dict[str, Any]]) -> bool:
        """
        在事务中执行多个SQL查询
        
        Args:
            queries: 包含查询和参数的字典列表，每个字典包含 'query' 和 'params' 键
            
        Returns:
            事务是否成功执行
        """
        if not self.is_connected:
            await self.connect()
        
        try:
            async with self.connection.cursor() as cursor:
                await cursor.execute("BEGIN TRANSACTION")
                
                for query_data in queries:
                    query = query_data.get("query", "")
                    params = query_data.get("params", ())
                    
                    await cursor.execute(query, params)
                
                await self.connection.commit()
                return True
        except Exception as e:
            logger.error(f"执行事务失败: {e}", exc_info=True)
            await self.connection.rollback()
            return False
    
    async def table_exists(self, table_name: str) -> bool:
        """
        检查表是否存在
        
        Args:
            table_name: 表名
            
        Returns:
            表是否存在
        """
        try:
            query = "SELECT name FROM sqlite_master WHERE type='table' AND name=?"
            result = await self.execute_query(query, (table_name,))
            return bool(result)
        except Exception as e:
            logger.error(f"检查表 {table_name} 是否存在失败: {e}", exc_info=True)
            return False
    
    async def get_table_columns(self, table_name: str) -> List[str]:
        """
        获取表的列名
        
        Args:
            table_name: 表名
            
        Returns:
            列名列表
        """
        try:
            query = f"PRAGMA table_info({table_name})"
            result = await self.execute_query(query)
            
            if not result:
                return []
                
            return [row[1] for row in result]  # 列名是每行的第二个元素
        except Exception as e:
            logger.error(f"获取表 {table_name} 的列名失败: {e}", exc_info=True)
            return []
    
    def generate_id(self) -> str:
        """
        生成唯一ID
        
        Returns:
            唯一ID字符串
        """
        return str(uuid.uuid4())
    
    async def add_column_if_not_exists(self, table_name: str, column_name: str, column_type: str) -> bool:
        """
        如果列不存在，则添加新列
        
        Args:
            table_name: 表名
            column_name: 列名
            column_type: 列类型
            
        Returns:
            操作是否成功
        """
        try:
            # 获取表的列名
            columns = await self.get_table_columns(table_name)
            
            # 如果列已存在，直接返回
            if column_name in columns:
                return True
            
            # 添加新列
            query = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
            await self.execute_query(query)
            logger.info(f"已向表 {table_name} 添加新列 {column_name}")
            return True
        except Exception as e:
            logger.error(f"向表 {table_name} 添加列 {column_name} 失败: {e}", exc_info=True)
            return False
    
    async def create_index_if_not_exists(
        self,
        table_name: str,
        column_names: List[str],
        index_name: str = None,
        unique: bool = False
    ) -> bool:
        """
        如果索引不存在，则创建索引
        
        Args:
            table_name: 表名
            column_names: 列名列表
            index_name: 索引名，默认自动生成
            unique: 是否为唯一索引
            
        Returns:
            操作是否成功
        """
        try:
            # 自动生成索引名
            if not index_name:
                index_name = f"idx_{table_name}_{'_'.join(column_names)}"
            
            # 检查索引是否存在
            query = "SELECT name FROM sqlite_master WHERE type='index' AND name=?"
            result = await self.execute_query(query, (index_name,))
            
            if result:
                return True
            
            # 创建索引
            unique_str = "UNIQUE" if unique else ""
            columns_str = ", ".join(column_names)
            query = f"CREATE {unique_str} INDEX {index_name} ON {table_name} ({columns_str})"
            
            await self.execute_query(query)
            logger.info(f"已在表 {table_name} 上创建索引 {index_name}")
            return True
        except Exception as e:
            logger.error(f"在表 {table_name} 上创建索引 {index_name} 失败: {e}", exc_info=True)
            return False 