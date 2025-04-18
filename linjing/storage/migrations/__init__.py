#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
数据库迁移模块，用于管理数据库结构版本变更。
"""

import os
import re
import logging
import importlib
from typing import List, Dict, Any

from ...utils.logger import get_logger

logger = get_logger(__name__)


class MigrationManager:
    """数据库迁移管理器，负责执行数据库迁移"""
    
    def __init__(self, db_manager):
        """
        初始化迁移管理器
        
        Args:
            db_manager: 数据库管理器实例
        """
        self.db_manager = db_manager
        self.migrations_dir = os.path.dirname(os.path.abspath(__file__))
        self.version_table = "schema_version"
    
    async def initialize(self) -> bool:
        """
        初始化迁移管理器，创建版本跟踪表
        
        Returns:
            是否初始化成功
        """
        try:
            # 创建版本跟踪表
            query = f"""
            CREATE TABLE IF NOT EXISTS {self.version_table} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version INTEGER NOT NULL,
                migration_name TEXT NOT NULL,
                applied_at REAL NOT NULL
            )
            """
            await self.db_manager.execute_query(query)
            return True
        except Exception as e:
            logger.error(f"初始化迁移管理器失败: {e}")
            return False
    
    async def get_current_version(self) -> int:
        """
        获取当前数据库架构版本
        
        Returns:
            当前版本号，如果没有应用过迁移则返回0
        """
        try:
            query = f"SELECT MAX(version) as version FROM {self.version_table}"
            results = await self.db_manager.execute_query(query)
            
            if results and results[0]["version"] is not None:
                return results[0]["version"]
            return 0
        except Exception as e:
            logger.error(f"获取当前版本失败: {e}")
            return 0
    
    async def get_applied_migrations(self) -> List[str]:
        """
        获取已应用的迁移列表
        
        Returns:
            已应用迁移名称列表
        """
        try:
            query = f"SELECT migration_name FROM {self.version_table} ORDER BY version ASC"
            results = await self.db_manager.execute_query(query)
            
            return [row["migration_name"] for row in results]
        except Exception as e:
            logger.error(f"获取已应用迁移列表失败: {e}")
            return []
    
    def get_available_migrations(self) -> List[Dict[str, Any]]:
        """
        获取可用的迁移文件
        
        Returns:
            迁移信息列表，每项包含version和name
        """
        migrations = []
        try:
            # 查找所有迁移文件
            file_pattern = re.compile(r"^(\d+)_(.+)\.py$")
            for filename in os.listdir(self.migrations_dir):
                match = file_pattern.match(filename)
                if match and not filename.startswith("__"):
                    version = int(match.group(1))
                    name = match.group(2)
                    migrations.append({
                        "version": version,
                        "name": name,
                        "filename": filename
                    })
            
            # 按版本号排序
            migrations.sort(key=lambda x: x["version"])
            return migrations
        except Exception as e:
            logger.error(f"获取可用迁移列表失败: {e}")
            return []
    
    async def run_migrations(self, target_version: int = None) -> bool:
        """
        运行迁移，更新数据库结构
        
        Args:
            target_version: 目标版本，如果未指定则迁移到最新版本
            
        Returns:
            是否成功完成迁移
        """
        try:
            # 确保版本表存在
            await self.initialize()
            
            # 获取当前版本和可用迁移
            current_version = await self.get_current_version()
            available_migrations = self.get_available_migrations()
            applied_migrations = await self.get_applied_migrations()
            
            # 确定目标版本
            if target_version is None and available_migrations:
                target_version = available_migrations[-1]["version"]
            elif target_version is None:
                target_version = current_version
            
            # 没有需要执行的迁移
            if current_version == target_version:
                logger.info(f"数据库已经是最新版本: {current_version}")
                return True
            
            # 找出需要执行的迁移
            migrations_to_run = []
            if target_version > current_version:
                # 向上迁移
                for migration in available_migrations:
                    if current_version < migration["version"] <= target_version:
                        migrations_to_run.append((migration, "up"))
            else:
                # 向下迁移
                for migration in reversed(available_migrations):
                    if target_version < migration["version"] <= current_version:
                        migrations_to_run.append((migration, "down"))
            
            # 执行迁移
            for migration, direction in migrations_to_run:
                # 检查迁移是否已应用
                migration_name = migration["name"]
                if direction == "up" and migration_name in applied_migrations:
                    logger.warning(f"迁移 {migration_name} 已应用，跳过")
                    continue
                
                # 导入迁移模块
                module_name = f"linjing.storage.migrations.{migration['filename'][:-3]}"
                module = importlib.import_module(module_name)
                
                # 执行迁移
                logger.info(f"执行迁移 {migration_name} ({direction})")
                if direction == "up":
                    if hasattr(module, "up"):
                        success = await module.up(self.db_manager)
                        if success:
                            # 记录迁移版本
                            await self._record_migration(migration["version"], migration_name)
                        else:
                            logger.error(f"迁移 {migration_name} 执行失败")
                            return False
                    else:
                        logger.error(f"迁移 {migration_name} 缺少up方法")
                        return False
                else:
                    if hasattr(module, "down"):
                        success = await module.down(self.db_manager)
                        if success:
                            # 删除迁移记录
                            await self._remove_migration(migration["version"])
                        else:
                            logger.error(f"迁移 {migration_name} 回滚失败")
                            return False
                    else:
                        logger.error(f"迁移 {migration_name} 缺少down方法")
                        return False
            
            logger.info(f"数据库迁移完成，当前版本: {target_version}")
            return True
        except Exception as e:
            logger.error(f"执行迁移失败: {e}")
            return False
    
    async def _record_migration(self, version: int, name: str) -> bool:
        """
        记录迁移版本
        
        Args:
            version: 版本号
            name: 迁移名称
            
        Returns:
            是否成功记录
        """
        try:
            import time
            query = f"""
            INSERT INTO {self.version_table} (version, migration_name, applied_at)
            VALUES (?, ?, ?)
            """
            await self.db_manager.execute_insert(query, (version, name, time.time()))
            return True
        except Exception as e:
            logger.error(f"记录迁移版本失败: {e}")
            return False
    
    async def _remove_migration(self, version: int) -> bool:
        """
        删除迁移版本记录
        
        Args:
            version: 版本号
            
        Returns:
            是否成功删除
        """
        try:
            query = f"DELETE FROM {self.version_table} WHERE version = ?"
            await self.db_manager.execute_update(query, (version,))
            return True
        except Exception as e:
            logger.error(f"删除迁移版本记录失败: {e}")
            return False 