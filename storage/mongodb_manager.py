#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
MongoDB数据库管理器
负责MongoDB连接管理和基本操作封装
"""

import logging
import motor.motor_asyncio
from urllib.parse import quote_plus
from typing import Dict, List, Any, Optional, Union, Tuple

from storage.storage_utils import StorageUtils


class MongoDBManager:
    """MongoDB数据库管理器"""

    def __init__(self, config: Dict[str, Any]):
        """
        初始化MongoDB管理器
        
        Args:
            config: MongoDB配置字典
                {
                    "host": "localhost",
                    "port": 27017,
                    "username": "user",
                    "password": "pass",
                    "database": "db_name",
                    "auth_source": "admin",  # 可选
                    "replica_set": None,     # 可选
                    "max_pool_size": 100     # 可选
                }
        """
        self.config = config
        self.host = config.get("host", "localhost")
        self.port = config.get("port", 27017)
        self.username = config.get("username")
        self.password = config.get("password")
        self.database_name = config.get("database", "maibot")
        self.auth_source = config.get("auth_source", "admin")
        self.replica_set = config.get("replica_set")
        self.max_pool_size = config.get("max_pool_size", 100)
        
        # 初始化客户端和数据库连接为None，在connect方法中建立连接
        self.client = None
        self.db = None
        self.logger = logging.getLogger("mongodb")
    
    async def connect(self) -> bool:
        """
        连接到MongoDB数据库
        
        Returns:
            bool: 连接是否成功
        """
        try:
            # 构建MongoDB连接URI
            if self.username and self.password:
                uri = f"mongodb://{quote_plus(self.username)}:{quote_plus(self.password)}@{self.host}:{self.port}/{self.database_name}?authSource={self.auth_source}"
            else:
                uri = f"mongodb://{self.host}:{self.port}/{self.database_name}"
            
            # 如果有复制集设置
            if self.replica_set:
                uri += f"&replicaSet={self.replica_set}"
            
            # 创建异步MongoDB客户端
            self.client = motor.motor_asyncio.AsyncIOMotorClient(
                uri,
                maxPoolSize=self.max_pool_size
            )
            
            # 获取数据库实例
            self.db = self.client[self.database_name]
            
            # 测试连接
            await self.client.admin.command("ping")
            self.logger.info(f"已连接到MongoDB: {self.host}:{self.port}/{self.database_name}")
            return True
        
        except Exception as e:
            self.logger.error(f"MongoDB连接失败: {str(e)}")
            self.client = None
            self.db = None
            return False
    
    async def close(self) -> None:
        """关闭MongoDB连接"""
        if self.client:
            self.client.close()
            self.client = None
            self.db = None
            self.logger.info("MongoDB连接已关闭")
    
    async def get_collection(self, collection_name: str):
        """
        获取指定名称的集合
        
        Args:
            collection_name: 集合名称
            
        Returns:
            AsyncIOMotorCollection: MongoDB集合对象
        """
        if not self.db:
            await self.connect()
        
        return self.db[collection_name]
    
    async def create_indexes(self, collection_name: str, indexes: List[Dict]) -> bool:
        """
        创建索引
        
        Args:
            collection_name: 集合名称
            indexes: 索引定义列表，例如：
                [
                    {
                        "keys": [("field1", 1), ("field2", -1)],
                        "name": "index_name",
                        "unique": True,
                        "background": True
                    }
                ]
                
        Returns:
            bool: 是否成功创建索引
        """
        try:
            collection = await self.get_collection(collection_name)
            for index in indexes:
                keys = index.pop("keys")
                name = index.pop("name", None)
                
                # 创建索引
                await collection.create_index(keys, name=name, **index)
            
            self.logger.info(f"成功为集合 {collection_name} 创建了 {len(indexes)} 个索引")
            return True
        
        except Exception as e:
            self.logger.error(f"为集合 {collection_name} 创建索引失败: {str(e)}")
            return False
    
    async def list_collections(self) -> List[str]:
        """
        列出所有集合名称
        
        Returns:
            List[str]: 集合名称列表
        """
        if not self.db:
            await self.connect()
        
        collections = []
        async for collection in self.db.list_collections():
            collections.append(collection["name"])
        
        return collections
    
    async def drop_collection(self, collection_name: str) -> bool:
        """
        删除集合
        
        Args:
            collection_name: 集合名称
            
        Returns:
            bool: 是否成功删除
        """
        try:
            if not self.db:
                await self.connect()
            
            await self.db.drop_collection(collection_name)
            self.logger.info(f"成功删除集合: {collection_name}")
            return True
        
        except Exception as e:
            self.logger.error(f"删除集合 {collection_name} 失败: {str(e)}")
            return False
    
    # 基本CRUD操作
    async def insert_one(self, collection_name: str, document: Dict) -> str:
        """
        插入单个文档
        
        Args:
            collection_name: 集合名称
            document: 要插入的文档
            
        Returns:
            str: 插入文档的ID
        """
        collection = await self.get_collection(collection_name)
        result = await collection.insert_one(document)
        return str(result.inserted_id)
    
    async def insert_many(self, collection_name: str, documents: List[Dict]) -> List[str]:
        """
        插入多个文档
        
        Args:
            collection_name: 集合名称
            documents: 要插入的文档列表
            
        Returns:
            List[str]: 插入文档的ID列表
        """
        collection = await self.get_collection(collection_name)
        result = await collection.insert_many(documents)
        return [str(id) for id in result.inserted_ids]
    
    async def find_one(self, collection_name: str, query: Dict, projection: Dict = None) -> Optional[Dict]:
        """
        查找单个文档
        
        Args:
            collection_name: 集合名称
            query: 查询条件
            projection: 投影，指定返回的字段
            
        Returns:
            Optional[Dict]: 找到的文档，未找到返回None
        """
        collection = await self.get_collection(collection_name)
        return await collection.find_one(query, projection)
    
    async def find(self, collection_name: str, query: Dict, projection: Dict = None, 
                  sort: List[Tuple] = None, skip: int = 0, limit: int = 0) -> List[Dict]:
        """
        查找多个文档
        
        Args:
            collection_name: 集合名称
            query: 查询条件
            projection: 投影，指定返回的字段
            sort: 排序条件，如 [("field1", 1), ("field2", -1)]
            skip: 跳过的文档数
            limit: 返回的最大文档数，0表示不限制
            
        Returns:
            List[Dict]: 找到的文档列表
        """
        collection = await self.get_collection(collection_name)
        cursor = collection.find(query, projection)
        
        if sort:
            cursor = cursor.sort(sort)
        
        if skip:
            cursor = cursor.skip(skip)
        
        if limit:
            cursor = cursor.limit(limit)
        
        documents = []
        async for document in cursor:
            documents.append(document)
        
        return documents
    
    async def count(self, collection_name: str, query: Dict) -> int:
        """
        计算匹配查询条件的文档数量
        
        Args:
            collection_name: 集合名称
            query: 查询条件
            
        Returns:
            int: 匹配的文档数量
        """
        collection = await self.get_collection(collection_name)
        return await collection.count_documents(query)
    
    async def update_one(self, collection_name: str, query: Dict, update: Dict, 
                       upsert: bool = False) -> int:
        """
        更新单个文档
        
        Args:
            collection_name: 集合名称
            query: 查询条件
            update: 更新操作
            upsert: 是否在文档不存在时插入
            
        Returns:
            int: 更新的文档数量
        """
        collection = await self.get_collection(collection_name)
        result = await collection.update_one(query, update, upsert=upsert)
        return result.modified_count
    
    async def update_many(self, collection_name: str, query: Dict, update: Dict, 
                        upsert: bool = False) -> int:
        """
        更新多个文档
        
        Args:
            collection_name: 集合名称
            query: 查询条件
            update: 更新操作
            upsert: 是否在文档不存在时插入
            
        Returns:
            int: 更新的文档数量
        """
        collection = await self.get_collection(collection_name)
        result = await collection.update_many(query, update, upsert=upsert)
        return result.modified_count
    
    async def replace_one(self, collection_name: str, query: Dict, replacement: Dict, 
                        upsert: bool = False) -> int:
        """
        替换单个文档
        
        Args:
            collection_name: 集合名称
            query: 查询条件
            replacement: 替换的文档
            upsert: 是否在文档不存在时插入
            
        Returns:
            int: 替换的文档数量
        """
        collection = await self.get_collection(collection_name)
        result = await collection.replace_one(query, replacement, upsert=upsert)
        return result.modified_count
    
    async def delete_one(self, collection_name: str, query: Dict) -> int:
        """
        删除单个文档
        
        Args:
            collection_name: 集合名称
            query: 查询条件
            
        Returns:
            int: 删除的文档数量
        """
        collection = await self.get_collection(collection_name)
        result = await collection.delete_one(query)
        return result.deleted_count
    
    async def delete_many(self, collection_name: str, query: Dict) -> int:
        """
        删除多个文档
        
        Args:
            collection_name: 集合名称
            query: 查询条件
            
        Returns:
            int: 删除的文档数量
        """
        collection = await self.get_collection(collection_name)
        result = await collection.delete_many(query)
        return result.deleted_count
    
    async def aggregate(self, collection_name: str, pipeline: List[Dict]) -> List[Dict]:
        """
        执行聚合管道操作
        
        Args:
            collection_name: 集合名称
            pipeline: 聚合管道
            
        Returns:
            List[Dict]: 聚合结果
        """
        collection = await self.get_collection(collection_name)
        results = []
        async for result in collection.aggregate(pipeline):
            results.append(result)
        
        return results
    
    async def bulk_write(self, collection_name: str, operations: List, ordered: bool = True) -> Dict:
        """
        执行批量写入操作
        
        Args:
            collection_name: 集合名称
            operations: 批量操作列表
            ordered: 是否按顺序执行操作
            
        Returns:
            Dict: 批量写入结果
        """
        collection = await self.get_collection(collection_name)
        result = await collection.bulk_write(operations, ordered=ordered)
        
        return {
            "inserted_count": result.inserted_count,
            "matched_count": result.matched_count,
            "modified_count": result.modified_count,
            "deleted_count": result.deleted_count,
            "upserted_count": result.upserted_count,
            "upserted_ids": [str(id) for id in result.upserted_ids.values()]
        }
    
    async def create_session(self):
        """
        创建MongoDB会话
        
        Returns:
            ClientSession: MongoDB会话对象
        """
        if not self.client:
            await self.connect()
        
        return await self.client.start_session()
    
    async def ping(self) -> bool:
        """
        测试MongoDB连接
        
        Returns:
            bool: 连接是否正常
        """
        try:
            if not self.client:
                return False
            
            await self.client.admin.command("ping")
            return True
        
        except Exception as e:
            self.logger.error(f"MongoDB ping失败: {str(e)}")
            return False 