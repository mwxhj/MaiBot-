#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
import asyncio
import json
import os
import shutil
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

# 导入存储模块
from storage.mongodb_manager import MongoDBManager
from storage.redis_cache import RedisCache
from storage.vector_db import VectorDBManager, InMemoryVectorDB
from storage.storage_utils import StorageUtils
from storage.storage_schemas import (
    Message, User, Memory, Emotion, Relationship,
    MessageType, EmotionType, RelationshipLevel
)


class TestStorageUtils(unittest.TestCase):
    """测试存储工具函数"""
    
    def setUp(self):
        """设置测试环境"""
        self.test_dir = "test_storage_utils_dir"
        self.test_file = os.path.join(self.test_dir, "test_file.txt")
        self.test_json = os.path.join(self.test_dir, "test_file.json")
        
        # 创建测试目录
        if not os.path.exists(self.test_dir):
            os.makedirs(self.test_dir)
    
    def tearDown(self):
        """清理测试环境"""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_generate_id(self):
        """测试ID生成"""
        id1 = StorageUtils.generate_id()
        id2 = StorageUtils.generate_id()
        
        # ID应该是字符串
        self.assertIsInstance(id1, str)
        # 两个ID应该不同
        self.assertNotEqual(id1, id2)
        # ID长度应该符合预期
        self.assertTrue(len(id1) > 8)
    
    def test_generate_hash(self):
        """测试哈希生成"""
        # 测试字符串哈希
        hash1 = StorageUtils.generate_hash("test string")
        self.assertIsInstance(hash1, str)
        
        # 测试字典哈希
        hash2 = StorageUtils.generate_hash({"key": "value"})
        self.assertIsInstance(hash2, str)
        
        # 测试字节哈希
        hash3 = StorageUtils.generate_hash(b"test bytes")
        self.assertIsInstance(hash3, str)
    
    def test_timestamp_now(self):
        """测试当前时间戳"""
        ts = StorageUtils.timestamp_now()
        self.assertIsInstance(ts, float)
    
    def test_datetime_functions(self):
        """测试日期时间函数"""
        # 测试当前时间
        dt_now = StorageUtils.datetime_now()
        self.assertIsInstance(dt_now, datetime)
        
        # 测试日期时间转字符串
        dt_str = StorageUtils.datetime_to_str(dt_now)
        self.assertIsInstance(dt_str, str)
        
        # 测试字符串转日期时间
        dt_parsed = StorageUtils.str_to_datetime(dt_str)
        self.assertIsInstance(dt_parsed, datetime)
        
        # 确保转换前后相等
        self.assertEqual(dt_now.replace(microsecond=0), 
                         dt_parsed.replace(microsecond=0))
    
    def test_file_operations(self):
        """测试文件操作"""
        # 测试目录确保存在
        StorageUtils.ensure_dir(self.test_dir)
        self.assertTrue(os.path.exists(self.test_dir))
        
        # 测试写入文件
        test_content = "测试内容"
        StorageUtils.write_file(self.test_file, test_content)
        self.assertTrue(os.path.exists(self.test_file))
        
        # 测试检查文件存在
        self.assertTrue(StorageUtils.file_exists(self.test_file))
        
        # 测试读取文件
        content = StorageUtils.read_file(self.test_file)
        self.assertEqual(content, test_content)
        
        # 测试追加文件
        append_content = "追加内容"
        StorageUtils.append_to_file(self.test_file, append_content)
        new_content = StorageUtils.read_file(self.test_file)
        self.assertEqual(new_content, test_content + append_content)
    
    def test_json_operations(self):
        """测试JSON操作"""
        test_data = {
            "string": "测试字符串",
            "number": 123,
            "list": [1, 2, 3],
            "nested": {"key": "value"}
        }
        
        # 测试保存JSON
        StorageUtils.save_json(self.test_json, test_data)
        self.assertTrue(os.path.exists(self.test_json))
        
        # 测试加载JSON
        loaded_data = StorageUtils.load_json(self.test_json)
        self.assertEqual(loaded_data, test_data)
    
    def test_dict_operations(self):
        """测试字典操作"""
        # 测试深度更新
        base_dict = {"a": 1, "b": {"c": 2, "d": 3}}
        update_dict = {"b": {"c": 4, "e": 5}, "f": 6}
        result = StorageUtils.deep_update(base_dict, update_dict)
        expected = {"a": 1, "b": {"c": 4, "d": 3, "e": 5}, "f": 6}
        self.assertEqual(result, expected)
        
        # 测试过滤字典
        test_dict = {"a": 1, "b": 2, "c": 3, "d": 4}
        filtered = StorageUtils.filter_dict(test_dict, ["a", "c"])
        self.assertEqual(filtered, {"a": 1, "c": 3})
        
        # 测试排除键
        excluded = StorageUtils.exclude_keys(test_dict, ["b", "d"])
        self.assertEqual(excluded, {"a": 1, "c": 3})
        
        # 测试扁平化字典
        nested_dict = {"a": 1, "b": {"c": 2, "d": {"e": 3}}}
        flattened = StorageUtils.flatten_dict(nested_dict)
        expected_flat = {"a": 1, "b.c": 2, "b.d.e": 3}
        self.assertEqual(flattened, expected_flat)
        
        # 测试还原扁平化字典
        unflattened = StorageUtils.unflatten_dict(flattened)
        self.assertEqual(unflattened, nested_dict)


class TestSchemas(unittest.TestCase):
    """测试数据模型"""
    
    def test_message(self):
        """测试消息模型"""
        now = datetime.utcnow()
        msg = Message(
            id="msg123",
            user_id="user456",
            content="测试消息",
            message_type=MessageType.TEXT,
            created_at=now,
            is_from_user=True
        )
        
        # 测试转换为字典
        msg_dict = msg.to_dict()
        self.assertEqual(msg_dict["id"], "msg123")
        self.assertEqual(msg_dict["user_id"], "user456")
        self.assertEqual(msg_dict["content"], "测试消息")
        self.assertEqual(msg_dict["message_type"], "text")
        self.assertEqual(msg_dict["created_at"], now.isoformat())
        self.assertEqual(msg_dict["is_from_user"], True)
        
        # 测试从字典创建
        new_msg = Message.from_dict(msg_dict)
        self.assertEqual(new_msg.id, msg.id)
        self.assertEqual(new_msg.user_id, msg.user_id)
        self.assertEqual(new_msg.content, msg.content)
        self.assertEqual(new_msg.message_type, msg.message_type)
        self.assertEqual(new_msg.is_from_user, msg.is_from_user)
    
    def test_user(self):
        """测试用户模型"""
        now = datetime.utcnow()
        user = User(
            id="user123",
            username="testuser",
            nickname="测试用户",
            avatar="avatar.jpg",
            created_at=now,
            last_active_at=now
        )
        
        # 测试转换为字典
        user_dict = user.to_dict()
        self.assertEqual(user_dict["id"], "user123")
        self.assertEqual(user_dict["username"], "testuser")
        self.assertEqual(user_dict["nickname"], "测试用户")
        
        # 测试从字典创建
        new_user = User.from_dict(user_dict)
        self.assertEqual(new_user.id, user.id)
        self.assertEqual(new_user.username, user.username)
        self.assertEqual(new_user.nickname, user.nickname)
    
    def test_memory(self):
        """测试记忆模型"""
        now = datetime.utcnow()
        memory = Memory(
            id="mem123",
            user_id="user456",
            content="这是一个重要的记忆",
            importance=0.8,
            created_at=now,
            source="conversation",
            timestamp=now.timestamp()
        )
        
        # 测试转换为字典
        mem_dict = memory.to_dict()
        self.assertEqual(mem_dict["id"], "mem123")
        self.assertEqual(mem_dict["importance"], 0.8)
        
        # 测试从字典创建
        new_mem = Memory.from_dict(mem_dict)
        self.assertEqual(new_mem.id, memory.id)
        self.assertEqual(new_mem.importance, memory.importance)
    
    def test_emotion(self):
        """测试情绪模型"""
        now = datetime.utcnow()
        emotion = Emotion(
            id="emo123",
            user_id="user456",
            emotion_type=EmotionType.HAPPY,
            intensity=0.7,
            created_at=now
        )
        
        # 测试转换为字典
        emo_dict = emotion.to_dict()
        self.assertEqual(emo_dict["emotion_type"], "happy")
        
        # 测试从字典创建
        new_emo = Emotion.from_dict(emo_dict)
        self.assertEqual(new_emo.emotion_type, emotion.emotion_type)
    
    def test_relationship(self):
        """测试关系模型"""
        now = datetime.utcnow()
        rel = Relationship(
            id="rel123",
            user_id="user456",
            level=RelationshipLevel.FRIEND,
            created_at=now,
            updated_at=now,
            familiarity=0.6,
            closeness=0.5,
            trust=0.7
        )
        
        # 测试转换为字典
        rel_dict = rel.to_dict()
        self.assertEqual(rel_dict["level"], "friend")
        
        # 测试从字典创建
        new_rel = Relationship.from_dict(rel_dict)
        self.assertEqual(new_rel.level, rel.level)


class TestMongoDBManager(unittest.TestCase):
    """测试MongoDB管理器"""
    
    def setUp(self):
        """设置测试环境"""
        self.config = {
            "host": "localhost",
            "port": 27017,
            "username": "testuser",
            "password": "testpass",
            "database": "testdb"
        }
        # 创建模拟MongoDB客户端
        self.mongo_client_mock = MagicMock()
        self.mongo_db_mock = MagicMock()
        self.mongo_collection_mock = MagicMock()
        
        # 设置模拟返回值
        self.mongo_client_mock.__getitem__.return_value = self.mongo_db_mock
        self.mongo_db_mock.__getitem__.return_value = self.mongo_collection_mock
        
        # 创建补丁
        self.mongo_client_patch = patch('motor.motor_asyncio.AsyncIOMotorClient', 
                                        return_value=self.mongo_client_mock)
        
        # 启动补丁
        self.mongo_client_mock = self.mongo_client_patch.start()
    
    def tearDown(self):
        """清理测试环境"""
        # 停止补丁
        self.mongo_client_patch.stop()
    
    def test_init(self):
        """测试初始化"""
        mongodb = MongoDBManager(self.config)
        self.assertEqual(mongodb.database_name, "testdb")
        self.assertIsNone(mongodb.client)
        self.assertIsNone(mongodb.db)
    
    async def async_test_connect(self):
        """测试连接"""
        mongodb = MongoDBManager(self.config)
        # 设置ping方法的返回值
        self.mongo_client_mock.admin.command.return_value = {"ok": 1}
        
        # 测试连接
        result = await mongodb.connect()
        self.assertTrue(result)
        self.assertIsNotNone(mongodb.client)
        self.assertIsNotNone(mongodb.db)
        
        # 测试关闭连接
        await mongodb.close()
    
    def test_connect(self):
        """运行异步测试"""
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.async_test_connect())
    
    async def async_test_collection_operations(self):
        """测试集合操作"""
        mongodb = MongoDBManager(self.config)
        # 设置ping方法的返回值
        self.mongo_client_mock.admin.command.return_value = {"ok": 1}
        
        # 测试连接
        await mongodb.connect()
        
        # 设置集合操作的返回值
        self.mongo_collection_mock.insert_one.return_value = MagicMock(inserted_id="doc123")
        self.mongo_collection_mock.find_one.return_value = {"_id": "doc123", "data": "test"}
        self.mongo_collection_mock.update_one.return_value = MagicMock(modified_count=1)
        self.mongo_collection_mock.delete_one.return_value = MagicMock(deleted_count=1)
        self.mongo_collection_mock.count_documents.return_value = 5
        
        # 测试获取集合
        collection = await mongodb.get_collection("test_collection")
        self.assertEqual(collection, self.mongo_collection_mock)
        
        # 测试插入文档
        doc = {"data": "test"}
        result = await mongodb.insert_one("test_collection", doc)
        self.assertEqual(result, "doc123")
        
        # 测试查找文档
        doc = await mongodb.find_one("test_collection", {"_id": "doc123"})
        self.assertEqual(doc["data"], "test")
        
        # 测试更新文档
        result = await mongodb.update_one("test_collection", {"_id": "doc123"}, {"$set": {"data": "updated"}})
        self.assertEqual(result, 1)
        
        # 测试删除文档
        result = await mongodb.delete_one("test_collection", {"_id": "doc123"})
        self.assertEqual(result, 1)
        
        # 测试计数
        count = await mongodb.count("test_collection", {})
        self.assertEqual(count, 5)
        
        # 测试关闭连接
        await mongodb.close()
    
    def test_collection_operations(self):
        """运行异步测试"""
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.async_test_collection_operations())


class TestRedisCache(unittest.TestCase):
    """测试Redis缓存"""
    
    def setUp(self):
        """设置测试环境"""
        self.config = {
            "host": "localhost",
            "port": 6379,
            "db": 0,
            "password": None
        }
        # 创建模拟Redis客户端
        self.redis_client_mock = MagicMock()
        
        # 创建补丁
        self.redis_client_patch = patch('aioredis.from_url', return_value=self.redis_client_mock)
        
        # 启动补丁
        self.redis_client_mock = self.redis_client_patch.start()
    
    def tearDown(self):
        """清理测试环境"""
        # 停止补丁
        self.redis_client_patch.stop()
    
    def test_init(self):
        """测试初始化"""
        redis = RedisCache(self.config)
        self.assertIsNone(redis.client)
        self.assertEqual(redis.default_ttl, 86400)
    
    async def async_test_connect(self):
        """测试连接"""
        redis = RedisCache(self.config)
        # 设置ping方法的返回值
        self.redis_client_mock.ping.return_value = True
        
        # 测试连接
        result = await redis.connect()
        self.assertTrue(result)
        self.assertIsNotNone(redis.client)
        
        # 测试关闭连接
        await redis.close()
    
    def test_connect(self):
        """运行异步测试"""
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.async_test_connect())
    
    async def async_test_cache_operations(self):
        """测试缓存操作"""
        redis = RedisCache(self.config)
        # 设置ping方法的返回值
        self.redis_client_mock.ping.return_value = True
        
        # 测试连接
        await redis.connect()
        
        # 设置方法返回值
        self.redis_client_mock.set.return_value = True
        self.redis_client_mock.get.return_value = b'{"data":"test"}'
        self.redis_client_mock.delete.return_value = 1
        self.redis_client_mock.exists.return_value = 1
        self.redis_client_mock.ttl.return_value = 3600
        self.redis_client_mock.expire.return_value = True
        self.redis_client_mock.incr.return_value = 6
        self.redis_client_mock.decr.return_value = 4
        
        # 测试设置缓存
        result = await redis.set("test_key", {"data": "test"})
        self.assertTrue(result)
        
        # 测试获取缓存
        value = await redis.get("test_key")
        self.assertEqual(value, {"data": "test"})
        
        # 测试删除缓存
        result = await redis.delete("test_key")
        self.assertEqual(result, 1)
        
        # 测试检查键是否存在
        result = await redis.exists("test_key")
        self.assertTrue(result)
        
        # 测试获取过期时间
        ttl = await redis.ttl("test_key")
        self.assertEqual(ttl, 3600)
        
        # 测试设置过期时间
        result = await redis.expire("test_key", 7200)
        self.assertTrue(result)
        
        # 测试增加计数
        count = await redis.incr("counter_key")
        self.assertEqual(count, 6)
        
        # 测试减少计数
        count = await redis.decr("counter_key")
        self.assertEqual(count, 4)
        
        # 测试关闭连接
        await redis.close()
    
    def test_cache_operations(self):
        """运行异步测试"""
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.async_test_cache_operations())


class TestVectorDBManager(unittest.TestCase):
    """测试向量数据库管理器"""
    
    def setUp(self):
        """设置测试环境"""
        self.config = {
            "db_type": "inmemory",
            "dimension": 128,
            "similarity": "cosine"
        }
    
    def test_init(self):
        """测试初始化"""
        vdb = VectorDBManager(self.config)
        self.assertEqual(vdb.db_type, "inmemory")
        self.assertEqual(vdb.dimension, 128)
    
    async def async_test_connect(self):
        """测试连接"""
        vdb = VectorDBManager(self.config)
        
        # 测试连接
        result = await vdb.connect()
        self.assertTrue(result)
        self.assertIsInstance(vdb.client, InMemoryVectorDB)
        
        # 测试ping
        result = await vdb.ping()
        self.assertTrue(result)
        
        # 测试关闭连接
        await vdb.close()
    
    def test_connect(self):
        """运行异步测试"""
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.async_test_connect())
    
    async def async_test_vector_operations(self):
        """测试向量操作"""
        vdb = VectorDBManager(self.config)
        
        # 测试连接
        await vdb.connect()
        
        # 测试创建集合
        result = await vdb.create_collection("test_collection")
        self.assertTrue(result)
        
        # 测试列出集合
        collections = await vdb.list_collections()
        self.assertIn("test_collection", collections)
        
        # 生成测试向量
        test_vectors = [
            [0.1 * i for i in range(128)],
            [0.2 * i for i in range(128)]
        ]
        test_docs = [
            {"id": "doc1", "text": "测试文档1"},
            {"id": "doc2", "text": "测试文档2"}
        ]
        test_ids = ["1", "2"]
        
        # 测试添加向量
        ids = await vdb.add_vectors("test_collection", test_vectors, test_docs, test_ids)
        self.assertEqual(ids, test_ids)
        
        # 测试搜索向量
        query_vector = [0.1 * i for i in range(128)]
        results = await vdb.search_vectors("test_collection", query_vector, limit=1)
        self.assertEqual(len(results), 1)
        
        # 测试获取向量
        docs = await vdb.get_vectors("test_collection", ["1"])
        self.assertEqual(len(docs), 1)
        self.assertEqual(docs[0]["metadata"]["id"], "doc1")
        
        # 测试计数向量
        count = await vdb.count_vectors("test_collection")
        self.assertEqual(count, 2)
        
        # 测试更新向量
        updated_vec = [0.3 * i for i in range(128)]
        updated_doc = {"id": "doc1", "text": "更新的测试文档1"}
        result = await vdb.update_vectors("test_collection", "1", updated_vec, updated_doc)
        self.assertTrue(result)
        
        # 测试删除向量
        result = await vdb.delete_vectors("test_collection", ["1"])
        self.assertTrue(result)
        
        # 测试删除集合
        result = await vdb.delete_collection("test_collection")
        self.assertTrue(result)
        
        # 测试关闭连接
        await vdb.close()
    
    def test_vector_operations(self):
        """运行异步测试"""
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.async_test_vector_operations())


if __name__ == '__main__':
    unittest.main() 