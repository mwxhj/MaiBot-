#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
数据库管理器模块，基于SQLite提供异步数据库操作。
"""

import logging
import os # <--- 导入 os 用于读取环境变量
import asyncio # <--- 导入 asyncio 模块
# import aiosqlite # <-- 不再需要 aiosqlite
import asyncpg # <--- 导入 asyncpg 用于异步操作
import json
# import traceback # <--- 移除不再需要的导入
# from pathlib import Path # <--- 移除未使用的 Path
from typing import Any, Dict, List, Optional, Tuple, Union # <--- 重新添加 Union

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
        # --- DEBUG LOGGING START ---
        logger.debug(f"DatabaseManager received config: {self.config}")
        # --- DEBUG LOGGING END ---
        self.db_type = self.config.get("type", "postgresql") # <--- 默认改为 postgresql

        if self.db_type == "postgresql":
            # PostgreSQL 连接参数
            self.db_host = self.config.get("host", "localhost")
            # --- DEBUG LOGGING START ---
            logger.debug(f"DatabaseManager determined db_host: {self.db_host}")
            # --- DEBUG LOGGING END ---
            self.db_port = self.config.get("port", 5432)
            self.db_user = self.config.get("user", "postgres")
            # 从环境变量读取密码，环境变量名称来自配置，默认为 "DB_PASSWORD"
            password_env_var = self.config.get("password", "DB_PASSWORD").strip('${}') # 移除 ${}
            self.db_password = os.getenv(password_env_var)
            self.db_name = self.config.get("database", "postgres")
            self.pool: Optional[asyncpg.Pool] = None # <--- 使用连接池
            logger.info(f"数据库管理器初始化 (PostgreSQL)，目标: {self.db_name}@{self.db_host}:{self.db_port}")
            if not self.db_password:
                 logger.warning(f"数据库密码环境变量 {password_env_var} 未设置!")
        elif self.db_type == "sqlite":
             self.db_path = self.config.get("path", "data/linjing.db") # SQLite 路径
             self._connection: Optional[aiosqlite.Connection] = None # SQLite 连接对象
             # 确保db_path目录存在
             os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
             logger.info(f"数据库管理器初始化 (SQLite)，数据库路径：{self.db_path}")
        else:
             raise ValueError(f"不支持的数据库类型: {self.db_type}")

        self.connection_config = self.config.get("connection", {})
        self.create_tables = self.config.get("create_tables_on_connect", True)
        self._initialized = False
        # --- 移除调试日志 ---
        # if self.db_type == "postgresql":
        #     logger.critical(f"!!! DB MANAGER INIT PARSED: host={self.db_host}, port={self.db_port}, user={self.db_user}, db={self.db_name}")
        # --- 移除结束 ---
    
    async def connect(self) -> bool:
        """
        连接到数据库
        
        Returns:
            是否连接成功
        """
        if self._initialized:
             logger.debug(f"数据库 ({self.db_type}) 已连接/初始化")
             return True
             
        try:
            if self.db_type == "postgresql":
                if self.pool is None:
                    if not self.db_password:
                         logger.warning(f"数据库密码环境变量 {self.config.get('password', 'DB_PASSWORD').strip('${}')} 未设置!")

                    # --- DEBUG LOGGING START ---
                    # 打印将要传递给 create_pool 的 host 和 port 值
                    host_to_use = self.db_host # 恢复使用 self.db_host
                    port_to_use = self.db_port
                    logger.debug(f"DatabaseManager.connect attempting to create pool with host: {host_to_use}, port: {port_to_use}") # 打印将要使用的值
                    # --- DEBUG LOGGING END ---
                    # 修正后的连接配置（优先使用DSN并强制IPv4）
                    # 不再需要 asyncpg.URI 来处理密码，直接在 DSN 中使用原始密码
                    # encoded_password = asyncpg.URI(self.db_password).password # <--- 移除或注释掉此行

                    # --- 添加日志检查密码 ---
                    password_env_var_name = self.config.get('password', 'DB_PASSWORD').strip('${}')
                    if not self.db_password:
                        logger.error(f"数据库密码环境变量 '{password_env_var_name}' 未设置或为空！无法构建有效的 DSN。")
                        # 考虑在这里直接返回失败，避免无效尝试
                        # return False # 或者 raise ValueError("数据库密码未配置")
                    else:
                         # 为了安全，不直接打印密码，只确认存在且长度不为0
                         logger.debug(f"从环境变量 '{password_env_var_name}' 获取的数据库密码存在且非空。")
                    # --- 日志检查结束 ---

                    # 移除 DSN 中的 connect_timeout，它不是标准的 PostgreSQL 参数
                    final_dsn = (
                        f"postgresql://{self.db_user}:{self.db_password}@"
                        f"{host_to_use}:{port_to_use}/{self.db_name}"
                        "?sslmode=disable" # <--- 移除 connect_timeout=10
                    )

                    # 不再需要手动构建 DSN 字符串
                    # logger.debug(f"最终连接DSN: {final_dsn.split('@')[0]}@[host]:{port_to_use}/[dbname]")

                    # 使用关键字参数代替 DSN 调用 create_pool，避免 DSN 解析问题
                    connection_timeout = self.connection_config.get("timeout", 30)
                    # 恢复使用配置文件中的主机名
                    # --- 移除调试日志 ---
                    # logger.critical(f"!!! PRE-CREATE-POOL CHECK: host={host_to_use}, port={port_to_use}, user={self.db_user}, db={self.db_name}, ssl=False, timeout=connection_timeout")
                    # --- 移除结束 ---
                    self.pool = await asyncpg.create_pool(
                        host=host_to_use, # <--- 使用配置文件中的主机名
                        port=port_to_use, # <--- 修正变量名
                        user=self.db_user, # <--- 修正变量名
                        password=self.db_password, # <--- 修正变量名 (直接传递密码)
                        database=self.db_name, # <--- 修正变量名
                        ssl=False, # <--- 修正变量名 (明确禁用 SSL)
                        timeout=connection_timeout, # <--- 修正变量名 (连接超时)
                        command_timeout=self.connection_config.get("timeout", 30), # <--- 修正变量名 (命令超时)
                        min_size=self.connection_config.get("min_size", 1), # <--- 修正变量名
                        max_size=self.connection_config.get("max_size", 5), # <--- 修正变量名
                        max_cached_statement_lifetime=self.connection_config.get("max_cached_statement_lifetime", 0), # 保留原始获取方式
                        max_queries=self.connection_config.get("max_queries", 50000), # 保留原始获取方式
                        max_inactive_connection_lifetime=self.connection_config.get("max_inactive_connection_lifetime", 300), # 保留原始获取方式
                        statement_cache_size=self.connection_config.get("statement_cache_size", 0) # 保留原始获取方式
                    )
                    logger.info(f"成功创建 PostgreSQL 连接池: {self.db_name}@{self.db_host}")
                else:
                     logger.debug("PostgreSQL 连接池已存在")

            elif self.db_type == "sqlite":
                 if self._connection is None:
                     # 确保目录存在 (已在 __init__ 中处理)
                     # os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
                     
                     # 重新导入 aiosqlite，因为它只在这里使用
                     import aiosqlite
                     self._connection = await aiosqlite.connect(
                         self.db_path,
                         timeout=self.connection_config.get("timeout", 30),
                         isolation_level=self.connection_config.get("isolation_level")
                     )
                     self._connection.row_factory = self._dict_factory # 使用自定义的行工厂
                     
                     # 应用 PRAGMA 设置
                     pragma_config = self.connection_config.get("pragma", {"foreign_keys": "ON"}) # 默认开启外键
                     for key, value in pragma_config.items():
                         await self._connection.execute(f"PRAGMA {key}={value}")
                     await self._connection.commit()
                     
                     logger.info(f"成功连接到 SQLite 数据库: {self.db_path}")
                 else:
                      logger.debug("SQLite 连接已存在")
            else:
                raise ValueError(f"不支持的数据库类型: {self.db_type}")
                
            # 在调用可能触发递归的操作之前，先标记为已初始化
            self._initialized = True

            # 初始化表结构 (仅在首次成功连接后执行)
            # 注意：现在 _initialized 已经是 True，所以这个条件需要调整
            # 或者，我们可以依赖 connect 方法只被成功调用一次的逻辑
            # 让我们假设 connect 成功后就应该初始化表（如果配置允许）
            # 移除 not self._initialized 条件检查似乎更合理
            if self.create_tables: # 只检查配置项
                 # 检查表是否真的需要初始化可能更好，但先简化逻辑
                 logger.debug("配置了创建表，尝试初始化...")
                 await self._initialize_tables()
            # self._initialized = True # 已上移
            return True
            
        except Exception as e:
            logger.error(f"连接数据库 ({self.db_type}) 失败: {e}", exc_info=True)
            # 清理可能部分创建的连接/池
            if self.db_type == "postgresql" and self.pool:
                 await self.pool.close()
                 self.pool = None
            elif self.db_type == "sqlite" and self._connection:
                 await self._connection.close()
                 self._connection = None
            self._initialized = False
            return False
    
    async def disconnect(self) -> None:
        """
        断开数据库连接或关闭连接池
        """
        if self.db_type == "postgresql":
            if self.pool:
                try:
                    await self.pool.close()
                    self.pool = None
                    logger.info("PostgreSQL 连接池已关闭")
                except Exception as e:
                    logger.error(f"关闭 PostgreSQL 连接池失败: {e}", exc_info=True)
        elif self.db_type == "sqlite":
            # 重新导入 aiosqlite，因为它可能只在这里需要
            import aiosqlite
            if self._connection:
                try:
                    await self._connection.close()
                    self._connection = None
                    logger.info("SQLite 数据库连接已断开")
                except Exception as e:
                    logger.error(f"断开 SQLite 连接失败: {e}", exc_info=True)
        
        # 确保 _initialized 总是被重置
        self._initialized = False
    
    # 注意：此方法对于 PostgreSQL 返回 List[asyncpg.Record]，对于 SQLite 返回 List[Dict]。
    # 调用者需要根据 db_type 处理不同的返回类型。
    async def execute_query(self, query: str, params: Tuple = ()) -> List[Union[asyncpg.Record, Dict[str, Any]]]:
        """
        执行查询操作 (SELECT)。

        Args:
            query: SQL查询语句 (统一使用 ? 作为占位符)。
            params: 查询参数元组。

        Returns:
            查询结果列表。
            对于 PostgreSQL，列表项为 asyncpg.Record 对象。
            对于 SQLite，列表项为字典 (通过 _dict_factory 转换)。
            如果出错则返回空列表。
        """
        if not self._initialized:
            # 尝试自动连接（如果尚未连接）
            if not await self.connect():
                 logger.error("数据库未连接，无法执行查询")
                 return [] # 连接失败则返回空列表

        if self.db_type == "postgresql":
            # --- PostgreSQL 查询逻辑 ---
            if not self.pool:
                raise ConnectionError("PostgreSQL 连接池未初始化")
            try:
                async with self.pool.acquire() as conn:
                    # 将 ? 占位符替换为 $1, $2...
                    prepared_query = query
                    for i in range(1, len(params) + 1):
                        prepared_query = prepared_query.replace("?", f"${i}", 1)
                        
                    return await conn.fetch(prepared_query, *params)
            except Exception as e:
                logger.error(f"执行 PostgreSQL 查询失败: {e}", exc_info=True)
                logger.debug(f"查询: {query}, 参数: {params}")
                return [] # 查询失败返回空列表
        elif self.db_type == "sqlite":
             # --- SQLite 查询逻辑 ---
             if not self._connection:
                 # 理论上 connect() 应该已处理，但再次检查以防万一
                 logger.error("SQLite 数据库未连接，无法执行查询")
                 return []
             try:
                 # 重新导入 aiosqlite
                 import aiosqlite
                 async with self._connection.execute(query, params) as cursor:
                     # 使用 _dict_factory 将结果转换为字典列表
                     rows = await cursor.fetchall()
                     # 注意：这里返回的是字典列表，与 PostgreSQL 返回类型不同
                     # 可能需要在调用处处理这种差异，或统一返回格式
                     return rows # 返回的是字典列表
             except Exception as e:
                 logger.error(f"执行 SQLite 查询失败: {e}", exc_info=True)
                 logger.debug(f"查询: {query}, 参数: {params}")
                 return []
        else:
             raise ValueError(f"不支持的数据库类型: {self.db_type}")
    
    # 注意：此方法对于 PostgreSQL 可能返回 RETURNING 子句的值或 None，
    # 对于 SQLite 返回 lastrowid (int) 或 -1。调用者需处理差异。
    async def execute_insert(self, query: str, params: Tuple = ()) -> Optional[Any]:
        """
        执行插入操作 (INSERT)。

        Args:
            query: SQL插入语句 (统一使用 ? 作为占位符)。
            params: 插入参数元组。

        Returns:
            - PostgreSQL: 如果查询包含 RETURNING 子句，则返回 fetchval 的结果；否则返回 None。
            - SQLite: 返回最后插入行的 ID (lastrowid)。
            - 操作失败时：PostgreSQL 抛出异常，SQLite 返回 -1。
        """
        if not self._initialized:
            if not await self.connect():
                 logger.error("数据库未连接，无法执行插入")
                 # 对于插入操作，失败时应更明确地指示，例如抛出异常
                 raise ConnectionError("数据库未连接，无法执行插入")

        if self.db_type == "postgresql":
            # --- PostgreSQL 插入逻辑 ---
            if not self.pool:
                raise ConnectionError("PostgreSQL 连接池未初始化")
            try:
                async with self.pool.acquire() as conn:
                    # 将 ? 占位符替换为 $1, $2...
                    prepared_query = query
                    param_count = len(params)
                    for i in range(1, param_count + 1):
                        # 确保只替换参数占位符，避免误伤 SQL 中的 '?'
                        prepared_query = prepared_query.replace("?", f"${i}", 1)
                        
                    # 检查是否有 RETURNING 子句
                    if "RETURNING" in prepared_query.upper():
                         # 使用 fetchval 获取单个返回值 (例如 RETURNING id)
                         # 使用 fetchrow 获取整行 (例如 RETURNING *)
                         # 这里假设返回单个值
                         return await conn.fetchval(prepared_query, *params)
                    else:
                         # 否则只执行
                         await conn.execute(prepared_query, *params)
                         return None # 或者可以返回影响的行数 status
            except Exception as e:
                logger.error(f"执行 PostgreSQL 插入失败: {e}", exc_info=True)
                logger.debug(f"查询: {query}, 参数: {params}")
                raise # 重新抛出异常，让调用者处理
        elif self.db_type == "sqlite":
             # --- SQLite 插入逻辑 ---
             if not self._connection:
                 logger.error("SQLite 数据库未连接，无法执行插入")
                 return -1 # 返回 -1 表示失败
             try:
                 # 重新导入 aiosqlite
                 import aiosqlite
                 async with self._connection.execute(query, params) as cursor:
                     await self._connection.commit()
                     return cursor.lastrowid # SQLite 返回 lastrowid
             except Exception as e:
                 logger.error(f"执行 SQLite 插入失败: {e}", exc_info=True)
                 logger.debug(f"查询: {query}, 参数: {params}")
                 return -1 # SQLite 插入失败返回 -1
        else:
             raise ValueError(f"不支持的数据库类型: {self.db_type}")
    
    # 注意：此方法对于 PostgreSQL 返回解析状态字符串得到的行数，可能为 0；
    # 对于 SQLite 返回 cursor.rowcount。失败时都返回 -1。
    async def execute_update(self, query: str, params: Tuple = ()) -> int:
        """
        执行更新 (UPDATE) 或删除 (DELETE) 操作。

        Args:
            query: SQL 更新/删除语句 (统一使用 ? 作为占位符)。
            params: 参数元组。

        Returns:
            受影响的行数。如果操作失败则返回 -1。
            (注意：PostgreSQL 的行数是从状态字符串解析的，可能不完全精确或在某些情况下为0)。
        """
        if not self._initialized:
            if not await self.connect():
                 logger.error("数据库未连接，无法执行更新/删除")
                 return -1 # 返回 -1 表示失败

        if self.db_type == "postgresql":
            # --- PostgreSQL 更新/删除逻辑 ---
            if not self.pool:
                raise ConnectionError("PostgreSQL 连接池未初始化")
            try:
                async with self.pool.acquire() as conn:
                    # 将 ? 占位符替换为 $1, $2...
                    prepared_query = query
                    param_count = len(params)
                    for i in range(1, param_count + 1):
                        prepared_query = prepared_query.replace("?", f"${i}", 1)
                        
                    status = await conn.execute(prepared_query, *params)
                    # 从状态字符串解析影响的行数，例如 'UPDATE 1' 或 'DELETE 1'
                    try:
                        # 提取命令后的数字
                        rows_affected_str = status.split()[-1]
                        rows_affected = int(rows_affected_str)
                        return rows_affected
                    except (IndexError, ValueError):
                        logger.warning(f"无法从状态 '{status}' 解析受影响的行数")
                        return 0 # 解析失败则返回0
            except Exception as e:
                logger.error(f"执行 PostgreSQL 更新/删除失败: {e}", exc_info=True)
                logger.debug(f"查询: {query}, 参数: {params}")
                return -1 # 返回 -1 表示失败
        elif self.db_type == "sqlite":
             # --- SQLite 更新/删除逻辑 ---
             if not self._connection:
                 logger.error("SQLite 数据库未连接，无法执行更新/删除")
                 return -1 # 返回 -1 表示失败
             try:
                 # 重新导入 aiosqlite
                 import aiosqlite
                 async with self._connection.execute(query, params) as cursor:
                     await self._connection.commit()
                     return cursor.rowcount # SQLite 直接返回 rowcount
             except Exception as e:
                 logger.error(f"执行 SQLite 更新/删除失败: {e}", exc_info=True)
                 logger.debug(f"查询: {query}, 参数: {params}")
                 return -1 # 返回 -1 表示失败
        else:
             raise ValueError(f"不支持的数据库类型: {self.db_type}")
    
    async def execute_transaction(self, queries: List[Tuple[str, Tuple]]) -> bool:
        """
        在单个事务中执行多个 SQL 语句。

        Args:
            queries: 查询列表，每项为 (query, params) 元组 (查询语句统一使用 ? 作为占位符)。

        Returns:
            事务是否成功提交 (True 表示成功, False 表示失败并已回滚)。
        """
        if not self._initialized:
            if not await self.connect():
                 logger.error("数据库未连接，无法执行事务")
                 return False # 返回 False 表示失败

        if self.db_type == "postgresql":
            # --- PostgreSQL 事务逻辑 ---
            if not self.pool:
                raise ConnectionError("PostgreSQL 连接池未初始化")
            # 使用连接池的事务接口
            async with self.pool.acquire() as conn:
                async with conn.transaction(): # asyncpg 的事务管理
                    try:
                        for query, params in queries:
                            # 将 ? 占位符替换为 $1, $2...
                            prepared_query = query
                            param_count = len(params)
                            for i in range(1, param_count + 1):
                                prepared_query = prepared_query.replace("?", f"${i}", 1)
                            await conn.execute(prepared_query, *params)
                        # 成功则自动提交
                        logger.debug("PostgreSQL 事务成功提交")
                        return True
                    except Exception as e:
                        logger.error(f"PostgreSQL 事务执行失败，将自动回滚: {e}", exc_info=True)
                        # asyncpg 的 transaction() 会自动处理回滚
                        return False
        elif self.db_type == "sqlite":
             # --- SQLite 事务逻辑 ---
             if not self._connection:
                 logger.error("SQLite 数据库未连接，无法执行事务")
                 return False # 返回 False 表示失败
             try:
                 # 重新导入 aiosqlite
                 import aiosqlite
                 # SQLite 的事务处理
                 await self._connection.execute("BEGIN TRANSACTION")
                 try:
                     for query, params in queries:
                         await self._connection.execute(query, params)
                     await self._connection.commit()
                     logger.debug("SQLite 事务成功提交")
                     return True
                 except Exception as e:
                     await self._connection.rollback()
                     logger.error(f"SQLite 事务执行失败，已回滚: {e}", exc_info=True)
                     return False
             except Exception as e:
                 logger.error(f"SQLite 事务处理失败: {e}", exc_info=True)
                 return False
        else:
             raise ValueError(f"不支持的数据库类型: {self.db_type}")
    
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
            if self.db_type == "postgresql":
                # PostgreSQL 查询 information_schema
                query = """
                SELECT EXISTS (
                   SELECT FROM information_schema.tables
                   WHERE table_schema = 'public'
                   AND table_name = $1
                );
                """
                # 注意：execute_query 返回 Record 列表，我们需要获取第一个记录的第一个值
                result = await self.execute_query(query.replace("$1", "?"), (table_name,)) # 临时用 ? 占位符
                return result[0][0] if result else False
            elif self.db_type == "sqlite":
                 # SQLite 查询 sqlite_master
                 query = "SELECT name FROM sqlite_master WHERE type='table' AND name=?"
                 result = await self.execute_query(query, (table_name,))
                 # SQLite 返回字典列表
                 return len(result) > 0
            else:
                 raise ValueError(f"不支持的数据库类型: {self.db_type}")
        except Exception as e:
            logger.error(f"检查表 '{table_name}' 是否存在失败 ({self.db_type}): {e}", exc_info=True)
            return False
    
    async def execute_script(self, script: str) -> bool:
        """
        执行包含多条语句的 SQL 脚本。

        警告: 对于 PostgreSQL，此方法尝试在单个事务中执行整个脚本。
              如果脚本包含事务控制语句 (BEGIN, COMMIT, ROLLBACK) 或
              不支持在事务块中执行的命令，可能会失败。
              对于复杂的 PostgreSQL 脚本，建议手动管理事务或分步执行。

        Args:
            script: SQL 脚本内容 (多条语句通常用 ; 分隔)。

        Returns:
            脚本是否执行成功。
        """
        if not self._initialized:
            if not await self.connect():
                 logger.error("数据库未连接，无法执行脚本")
                 return False # 返回 False 表示失败

        if self.db_type == "postgresql":
            # --- PostgreSQL 脚本执行逻辑 (在事务中尝试) ---
            if not self.pool:
                raise ConnectionError("PostgreSQL 连接池未初始化")
            # asyncpg 需要手动分割和执行语句，或者在事务中执行
            async with self.pool.acquire() as conn:
                async with conn.transaction(): # 在事务中执行以确保原子性
                    try:
                        # 简单的分割方式，可能不适用于复杂的脚本
                        # statements = [s.strip() for s in script.split(';') if s.strip()]
                        # for statement in statements:
                        #     await conn.execute(statement)
                        # 更健壮的方式是直接执行整个脚本
                        await conn.execute(script)
                        logger.debug("PostgreSQL 脚本执行成功 (在事务中)")
                        return True
                    except Exception as e:
                        logger.error(f"执行 PostgreSQL 脚本失败: {e}", exc_info=True)
                        # 事务会自动回滚
                        return False
        elif self.db_type == "sqlite":
             # --- SQLite 脚本执行逻辑 (使用 executescript) ---
             if not self._connection:
                 logger.error("SQLite 数据库未连接，无法执行脚本")
                 return False # 返回 False 表示失败
             try:
                 # 重新导入 aiosqlite
                 import aiosqlite
                 await self._connection.executescript(script)
                 await self._connection.commit()
                 logger.debug("SQLite 脚本执行成功")
                 return True
             except Exception as e:
                 logger.error(f"执行 SQLite 脚本失败: {e}", exc_info=True)
                 return False
        else:
             raise ValueError(f"不支持的数据库类型: {self.db_type}")
    
    async def _initialize_tables(self) -> None:
        """
        初始化数据库表 (适配 PostgreSQL 和 SQLite)
        """
        tables_script = ""
        if self.db_type == "postgresql":
            # PostgreSQL specific CREATE TABLE statements
            # 使用 TEXT 作为主键 (例如 UUID)
            # 使用 TIMESTAMPTZ 存储带时区的时间戳 (更精确)
            # 使用 JSONB 存储 metadata (查询性能更好)
            memories_table = """
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                memory_type TEXT NOT NULL,
                importance REAL DEFAULT 0.5,
                creation_time TIMESTAMPTZ DEFAULT NOW(),
                last_access_time TIMESTAMPTZ,
                access_count INTEGER DEFAULT 0,
                user_id TEXT,
                session_id TEXT,
                metadata JSONB,
                decay_rate REAL DEFAULT 0.05
            );
            CREATE INDEX IF NOT EXISTS idx_memories_user_id ON memories(user_id);
            CREATE INDEX IF NOT EXISTS idx_memories_memory_type ON memories(memory_type);
            CREATE INDEX IF NOT EXISTS idx_memories_creation_time ON memories(creation_time);
            """
            
            users_table = """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                name TEXT,
                platform TEXT,
                platform_id TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                last_active_at TIMESTAMPTZ,
                metadata JSONB
            );
            CREATE INDEX IF NOT EXISTS idx_users_platform_id ON users(platform, platform_id);
            """
            
            sessions_table = """
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE, -- 添加外键约束
                start_time TIMESTAMPTZ DEFAULT NOW(),
                end_time TIMESTAMPTZ,
                metadata JSONB
            );
            CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
            """
            
            # 添加 user_moods 表 (PostgreSQL)
            moods_table = """
            CREATE TABLE IF NOT EXISTS user_moods (
                id SERIAL PRIMARY KEY, -- 再次修正 PostgreSQL 语法
                user_id TEXT NOT NULL,
                mood_data JSONB NOT NULL, -- 使用 JSONB 存储情绪数据
                timestamp TIMESTAMPTZ DEFAULT NOW()
            );
            -- 索引优化情绪查询
            CREATE INDEX IF NOT EXISTS idx_user_moods_user_id_timestamp ON user_moods(user_id, timestamp DESC);
            """
            
            tables_script = memories_table + users_table + sessions_table + moods_table
            
        elif self.db_type == "sqlite":
            # SQLite specific CREATE TABLE statements
            memories_table = """
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                memory_type TEXT NOT NULL, -- 记忆类型 (e.g., 'conversation', 'knowledge')
                importance REAL DEFAULT 0.5, -- 记忆重要性评分
                creation_time REAL, -- 创建时间 (Unix epoch)
                last_access_time REAL, -- 最后访问时间 (Unix epoch)
                access_count INTEGER DEFAULT 0, -- 访问次数
                user_id TEXT,
                session_id TEXT,
                metadata TEXT, -- SQLite 使用 TEXT 存储 JSON
                decay_rate REAL DEFAULT 0.05
            );
            CREATE INDEX IF NOT EXISTS idx_memories_user_id ON memories(user_id);
            CREATE INDEX IF NOT EXISTS idx_memories_memory_type ON memories(memory_type);
            CREATE INDEX IF NOT EXISTS idx_memories_creation_time ON memories(creation_time);
            """
            
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
            
            sessions_table = """
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                start_time REAL,
                end_time REAL,
                metadata TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE -- SQLite 也支持外键
            );
            CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
            """
            
            # 添加 user_moods 表 (SQLite)
            moods_table = """
            CREATE TABLE IF NOT EXISTS user_moods (
                id INTEGER PRIMARY KEY AUTOINCREMENT, -- SQLite 语法
                user_id TEXT NOT NULL,
                mood_data TEXT NOT NULL, -- SQLite 使用 TEXT 存储 JSON
                timestamp REAL NOT NULL
            );
            -- 索引优化情绪查询
            CREATE INDEX IF NOT EXISTS idx_user_moods_user_id_timestamp ON user_moods(user_id, timestamp DESC);
            """
            
            tables_script = memories_table + users_table + sessions_table + moods_table
        else:
             raise ValueError(f"不支持的数据库类型: {self.db_type}")

        # 执行创建表操作
        if tables_script:
             success = await self.execute_script(tables_script)
             if success:
                  logger.info(f"数据库表 ({self.db_type}) 初始化/验证完成")
             else:
                  logger.error(f"数据库表 ({self.db_type}) 初始化失败")
        else:
             logger.warning("没有为数据库类型 {self.db_type} 定义初始化脚本")
    
    def _dict_factory(self, cursor, row):
        """
        将 SQLite 查询结果行 (元组) 转换为字典。
        注意：此方法仅用于 SQLite (aiosqlite)。
              asyncpg 返回的 Record 对象本身支持按列名访问 (record['column_name'])。
        
        Args:
            cursor: aiosqlite 游标对象
            row: 结果行元组
            
        Returns:
            字典形式的结果行
        """
        if self.db_type != "sqlite":
             # 对于非 SQLite 类型，此工厂不适用
             logger.warning("_dict_factory 被非 SQLite 连接调用，这通常是不必要的。")
             # 返回空字典或原始行，取决于调用者期望
             return {}
             
        d = {}
        try:
            # cursor.description 包含列信息 (name, type_code, display_size, internal_size, precision, scale, null_ok)
            for idx, col_info in enumerate(cursor.description):
                col_name = col_info[0]
                value = row[idx]
                # 尝试将 metadata 和 mood_data 列的值解析为 JSON (如果它们是字符串)
                if col_name in ['metadata', 'mood_data'] and isinstance(value, str):
                    try:
                        # 只有非空字符串才尝试解析
                        if value:
                             d[col_name] = json.loads(value)
                        else:
                             d[col_name] = None # 或 {}，取决于业务逻辑
                    except json.JSONDecodeError:
                        # 如果解析失败，保留原始字符串，并记录警告
                        logger.warning(f"无法将列 '{col_name}' 的值 '{value}' 解析为 JSON，保留原始字符串。")
                        d[col_name] = value
                else:
                    d[col_name] = value
        except Exception as e:
             logger.error(f"SQLite _dict_factory 执行出错: {e}", exc_info=True)
             # 出错时返回部分转换结果或空字典
             return d
             
        return d