#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
记忆管理器模块，负责机器人的记忆存储、检索和管理。
整合SQLite数据库和向量数据库，提供统一的记忆管理接口。
"""

import json
import logging
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

from linjing.storage.database import DatabaseManager
from linjing.storage.vector_db_manager_factory import VectorDBManagerFactory
from linjing.storage.storage_models import MemoryModel

# 导入MemoryModel并重命名为Memory
Memory = MemoryModel

logger = logging.getLogger(__name__)


class MemoryManager:
    """
    记忆管理器，负责存储、检索和管理机器人的记忆。
    
    整合SQLite和向量数据库，提供统一的记忆管理接口。
    记忆类型包括：
    - 对话记忆：用户与机器人的对话历史
    - 用户信息：用户的个人信息、偏好设置等
    - 知识记忆：机器人的知识库
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        初始化记忆管理器
        
        Args:
            config: 配置字典，包含数据库和向量数据库的配置参数
        """
        self.config = config or {}
        
        # 获取配置
        self.db_path = self.config.get("db_path", "data/database.db")
        self.vector_db_config = self.config.get("vector_db", {})
        
        # 确保数据目录存在
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        # 初始化数据库管理器 - 将db_path包装为字典
        self.db = DatabaseManager({"db_path": self.db_path})
        self.vector_db = VectorDBManagerFactory.create(self.vector_db_config)
        
        self._initialized = False
        logger.info("记忆管理器初始化完成")
    
    async def initialize(self) -> bool:
        """
        初始化记忆管理器，连接数据库
        
        Returns:
            初始化是否成功
        """
        if self._initialized:
            return True
        
        try:
            # 连接数据库
            await self.db.connect()
            await self.vector_db.connect()
            
            # 创建记忆表结构（如果不存在）
            await self._create_memory_tables()
            
            self._initialized = True
            logger.info("记忆管理器初始化成功")
            return True
        except Exception as e:
            logger.error(f"记忆管理器初始化失败: {e}", exc_info=True)
            return False
    
    async def _create_memory_tables(self) -> None:
        """
        创建记忆相关的数据库表结构
        """
        # 创建对话记忆表
        await self.db.execute_query("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                content TEXT NOT NULL,
                role TEXT NOT NULL,
                metadata TEXT,
                vector_id TEXT,
                importance REAL DEFAULT 1.0,
                embedding_generated BOOLEAN DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        
        # 创建用户信息表
        await self.db.execute_query("""
            CREATE TABLE IF NOT EXISTS user_info (
                user_id TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                metadata TEXT,
                PRIMARY KEY (user_id, key),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        
        # 创建知识记忆表
        await self.db.execute_query("""
            CREATE TABLE IF NOT EXISTS knowledge (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                source TEXT,
                category TEXT,
                timestamp INTEGER NOT NULL,
                vector_id TEXT,
                importance REAL DEFAULT 1.0,
                metadata TEXT,
                embedding_generated BOOLEAN DEFAULT 0
            )
        """)
        
        # 创建索引
        await self.db.execute_query("""
            CREATE INDEX IF NOT EXISTS idx_conversations_user_session 
            ON conversations(user_id, session_id)
        """)
        await self.db.execute_query("""
            CREATE INDEX IF NOT EXISTS idx_conversations_timestamp 
            ON conversations(timestamp)
        """)
        await self.db.execute_query("""
            CREATE INDEX IF NOT EXISTS idx_knowledge_category 
            ON knowledge(category)
        """)
    
    async def close(self) -> None:
        """
        关闭记忆管理器，断开数据库连接
        """
        if self._initialized:
            await self.db.disconnect()
            await self.vector_db.disconnect()
            self._initialized = False
            logger.info("记忆管理器已关闭")
    
    async def add_conversation_memory(
        self, 
        user_id: str, 
        session_id: str, 
        content: str, 
        role: str, 
        metadata: Dict[str, Any] = None,
        embedding: List[float] = None,
        importance: float = 1.0,
        id: str = None
    ) -> str:
        """
        添加对话记忆
        
        Args:
            user_id: 用户ID
            session_id: 会话ID
            content: 对话内容
            role: 角色（'user'或'assistant'）
            metadata: 附加元数据
            embedding: 内容的向量嵌入，如不提供则不生成向量索引
            importance: 重要性分数
            id: 记忆ID，默认自动生成
            
        Returns:
            记忆ID
        """
        if not self._initialized:
            await self.initialize()
        
        # 生成记忆ID和时间戳
        from uuid import uuid4
        memory_id = id or str(uuid4())
        timestamp = int(time.time())
        
        # 序列化元数据
        metadata_json = json.dumps(metadata) if metadata else None
        
        vector_id = None
        embedding_generated = 0
        
        # 如果提供了嵌入向量，则存入向量数据库
        if embedding:
            vector_id = await self.vector_db.add_vector(
                vector_id=memory_id,
                vector=embedding,
                metadata={
                    "memory_id": memory_id,
                    "user_id": user_id,
                    "session_id": session_id,
                    "role": role,
                    "content": content,
                    "timestamp": timestamp,
                    "type": "conversation"
                }
            )
            embedding_generated = 1 if vector_id else 0
        
        # 存入关系数据库
        try:
            # 构建 INSERT 语句
            columns = ["id", "user_id", "session_id", "timestamp", "content", "role", "metadata", "vector_id", "importance", "embedding_generated"]
            placeholders = ", ".join(["?"] * len(columns))
            sql = f"INSERT INTO conversations ({', '.join(columns)}) VALUES ({placeholders})"

            # 构建参数元组 (顺序必须与 columns 一致)
            params = (
                memory_id,
                user_id,
                session_id,
                timestamp,
                content,
                role,
                metadata_json,
                vector_id,
                importance,
                embedding_generated
            )
            await self.db.execute_insert(sql, params)
            logger.debug(f"已添加对话记忆: {memory_id}")
            return memory_id
        except Exception as e:
            logger.error(f"添加对话记忆失败: {e}", exc_info=True)
            return ""
    
    async def add_knowledge_memory(
        self,
        content: str,
        category: str = None,
        source: str = None,
        metadata: Dict[str, Any] = None,
        embedding: List[float] = None,
        importance: float = 1.0,
        id: str = None
    ) -> str:
        """
        添加知识记忆
        
        Args:
            content: 知识内容
            category: 知识类别
            source: 知识来源
            metadata: 附加元数据
            embedding: 内容的向量嵌入，如不提供则不生成向量索引
            importance: 重要性分数
            id: 记忆ID，默认自动生成
            
        Returns:
            记忆ID
        """
        if not self._initialized:
            await self.initialize()
        
        # 生成记忆ID和时间戳
        from uuid import uuid4
        memory_id = id or str(uuid4())
        timestamp = int(time.time())
        
        # 序列化元数据
        metadata_json = json.dumps(metadata) if metadata else None
        
        vector_id = None
        embedding_generated = 0
        
        # 如果提供了嵌入向量，则存入向量数据库
        if embedding:
            vector_id = await self.vector_db.add_vector(
                vector_id=memory_id,
                vector=embedding,
                metadata={
                    "memory_id": memory_id,
                    "content": content,
                    "category": category,
                    "source": source,
                    "timestamp": timestamp,
                    "type": "knowledge"
                }
            )
            embedding_generated = 1 if vector_id else 0
        
        # 存入关系数据库
        try:
            # 构建 INSERT 语句
            columns = ["id", "content", "source", "category", "timestamp", "vector_id", "importance", "metadata", "embedding_generated"]
            placeholders = ", ".join(["?"] * len(columns))
            sql = f"INSERT INTO knowledge ({', '.join(columns)}) VALUES ({placeholders})"

            # 构建参数元组 (顺序必须与 columns 一致)
            params = (
                memory_id,
                content,
                source,
                category,
                timestamp,
                vector_id,
                importance,
                metadata_json,
                embedding_generated
            )
            await self.db.execute_insert(sql, params)
            logger.debug(f"已添加知识记忆: {memory_id}")
            return memory_id
        except Exception as e:
            logger.error(f"添加知识记忆失败: {e}", exc_info=True)
            return ""
    
    async def add_user_info(
        self,
        user_id: str,
        key: str,
        value: str,
        metadata: Dict[str, Any] = None
    ) -> bool:
        """
        添加或更新用户信息
        
        Args:
            user_id: 用户ID
            key: 信息键名
            value: 信息值
            metadata: 附加元数据
            
        Returns:
            是否成功
        """
        if not self._initialized:
            await self.initialize()
        
        timestamp = int(time.time())
        metadata_json = json.dumps(metadata) if metadata else None
        
        try:
            # 使用REPLACE语法，存在则更新，不存在则插入
            await self.db.execute_query(
                """
                INSERT OR REPLACE INTO user_info 
                (user_id, key, value, timestamp, metadata) 
                VALUES (?, ?, ?, ?, ?)
                """,
                (user_id, key, value, timestamp, metadata_json)
            )
            logger.debug(f"已更新用户信息: {user_id}.{key}")
            return True
        except Exception as e:
            logger.error(f"更新用户信息失败: {e}", exc_info=True)
            return False
    
    async def get_user_info(self, user_id: str, key: str = None) -> Union[Dict[str, Any], str, None]:
        """
        获取用户信息
        
        Args:
            user_id: 用户ID
            key: 信息键名，如为None则返回所有信息
            
        Returns:
            用户信息值或字典
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            if key:
                # 获取特定键值
                result = await self.db.execute_query(
                    "SELECT value, metadata FROM user_info WHERE user_id = ? AND key = ?",
                    (user_id, key)
                )
                
                if not result:
                    return None
                
                value, metadata_json = result[0]
                
                # 处理元数据
                if metadata_json:
                    try:
                        metadata = json.loads(metadata_json)
                        return {"value": value, "metadata": metadata}
                    except:
                        pass
                
                return value
            else:
                # 获取所有用户信息
                results = await self.db.execute_query(
                    "SELECT key, value, metadata FROM user_info WHERE user_id = ?",
                    (user_id,)
                )
                
                if not results:
                    return {}
                
                user_data = {}
                for key, value, metadata_json in results:
                    if metadata_json:
                        try:
                            metadata = json.loads(metadata_json)
                            user_data[key] = {"value": value, "metadata": metadata}
                        except:
                            user_data[key] = value
                    else:
                        user_data[key] = value
                
                return user_data
        except Exception as e:
            logger.error(f"获取用户信息失败: {e}", exc_info=True)
            return None
    
    async def get_conversation_history(
        self,
        user_id: str,
        session_id: str = None,
        limit: int = 20,
        offset: int = 0,
        include_metadata: bool = False
    ) -> List[Dict[str, Any]]:
        """
        获取对话历史
        
        Args:
            user_id: 用户ID
            session_id: 会话ID，如为None则获取所有会话
            limit: 返回记录数量限制
            offset: 分页偏移量
            include_metadata: 是否包含元数据
            
        Returns:
            对话记录列表
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            query = "SELECT id, session_id, timestamp, content, role"
            params = [user_id]
            
            if include_metadata:
                query += ", metadata"
            
            query += " FROM conversations WHERE user_id = ?"
            
            if session_id:
                query += " AND session_id = ?"
                params.append(session_id)
            
            query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            
            results = await self.db.execute_query(query, params)
            
            conversations = []
            for row in results:
                conv = {
                    "id": row[0],
                    "session_id": row[1],
                    "timestamp": row[2],
                    "content": row[3],
                    "role": row[4],
                }
                
                if include_metadata and len(row) > 5 and row[5]:
                    try:
                        conv["metadata"] = json.loads(row[5])
                    except:
                        conv["metadata"] = {}
                
                conversations.append(conv)
            
            return conversations
        except Exception as e:
            logger.error(f"获取对话历史失败: {e}", exc_info=True)
            return []
    
    async def get_session_list(self, user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        获取用户的会话列表
        
        Args:
            user_id: 用户ID
            limit: 返回的会话数量限制
            
        Returns:
            会话列表，每个会话包含会话ID和最后一条消息
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            # 获取所有会话ID及其最新消息
            query = """
                SELECT c1.session_id, c1.timestamp, c1.content, c1.role
                FROM conversations c1
                INNER JOIN (
                    SELECT session_id, MAX(timestamp) as max_time
                    FROM conversations
                    WHERE user_id = ?
                    GROUP BY session_id
                ) c2 ON c1.session_id = c2.session_id AND c1.timestamp = c2.max_time
                WHERE c1.user_id = ?
                ORDER BY c1.timestamp DESC
                LIMIT ?
            """
            
            results = await self.db.execute_query(query, (user_id, user_id, limit))
            
            sessions = []
            for session_id, timestamp, content, role in results:
                # 获取会话的消息数量
                count_query = """
                    SELECT COUNT(*) FROM conversations 
                    WHERE user_id = ? AND session_id = ?
                """
                count_result = await self.db.execute_query(count_query, (user_id, session_id))
                message_count = count_result[0][0] if count_result else 0
                
                # 获取会话的第一条消息时间
                first_query = """
                    SELECT MIN(timestamp) FROM conversations 
                    WHERE user_id = ? AND session_id = ?
                """
                first_result = await self.db.execute_query(first_query, (user_id, session_id))
                first_timestamp = first_result[0][0] if first_result else timestamp
                
                # 计算会话时长
                duration = timestamp - first_timestamp
                
                sessions.append({
                    "session_id": session_id,
                    "last_timestamp": timestamp,
                    "last_message": content,
                    "last_role": role,
                    "message_count": message_count,
                    "start_timestamp": first_timestamp,
                    "duration": duration
                })
            
            return sessions
        except Exception as e:
            logger.error(f"获取会话列表失败: {e}", exc_info=True)
            return []
    
    async def search_similar_memories(
        self,
        query_embedding: List[float],
        limit: int = 5,
        memory_type: str = "all",
        user_id: str = None,
        session_id: str = None,
        score_threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        搜索语义相似的记忆
        
        Args:
            query_embedding: 查询向量
            limit: 返回数量限制
            memory_type: 记忆类型，可选 'all', 'conversation', 'knowledge'
            user_id: 用户ID，用于过滤对话记忆
            session_id: 会话ID，用于过滤对话记忆
            score_threshold: 相似度分数阈值
            
        Returns:
            相似记忆列表
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            # 构建过滤条件
            filter_conditions = {}
            
            if memory_type != "all":
                filter_conditions["type"] = memory_type
            
            if user_id and memory_type in ["all", "conversation"]:
                filter_conditions["user_id"] = user_id
            
            if session_id and memory_type in ["all", "conversation"]:
                filter_conditions["session_id"] = session_id
            
            # 执行向量搜索
            search_results = await self.vector_db.search_similar(
                query_vector=query_embedding,
                limit=limit,
                score_threshold=score_threshold,
                filter_condition=filter_conditions
            )
            
            # 从关系数据库获取完整记录
            memories = []
            for result in search_results:
                payload = result["payload"]
                memory_id = payload.get("memory_id")
                memory_type = payload.get("type")
                
                if memory_type == "conversation":
                    # 从conversations表获取完整信息
                    query = "SELECT * FROM conversations WHERE id = ?"
                    db_result = await self.db.execute_query(query, (memory_id,))
                    
                    if db_result:
                        row = db_result[0]
                        metadata = json.loads(row[6]) if row[6] else {}
                        
                        memory = {
                            "id": row[0],
                            "user_id": row[1],
                            "session_id": row[2],
                            "timestamp": row[3],
                            "content": row[4],
                            "role": row[5],
                            "metadata": metadata,
                            "importance": row[8],
                            "similarity_score": result["score"],
                            "memory_type": "conversation"
                        }
                        memories.append(memory)
                
                elif memory_type == "knowledge":
                    # 从knowledge表获取完整信息
                    query = "SELECT * FROM knowledge WHERE id = ?"
                    db_result = await self.db.execute_query(query, (memory_id,))
                    
                    if db_result:
                        row = db_result[0]
                        metadata = json.loads(row[7]) if row[7] else {}
                        
                        memory = {
                            "id": row[0],
                            "content": row[1],
                            "source": row[2],
                            "category": row[3],
                            "timestamp": row[4],
                            "importance": row[6],
                            "metadata": metadata,
                            "similarity_score": result["score"],
                            "memory_type": "knowledge"
                        }
                        memories.append(memory)
            
            # 按相似度降序排序
            memories.sort(key=lambda x: x["similarity_score"], reverse=True)
            
            return memories
        except Exception as e:
            logger.error(f"搜索相似记忆失败: {e}", exc_info=True)
            return []
    
    async def delete_conversation(self, memory_id: str) -> bool:
        """
        删除对话记忆
        
        Args:
            memory_id: 记忆ID
            
        Returns:
            是否删除成功
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            # 查询是否存在向量ID
            query = "SELECT vector_id FROM conversations WHERE id = ?"
            result = await self.db.execute_query(query, (memory_id,))
            
            if result and result[0][0]:
                vector_id = result[0][0]
                # 删除向量数据库中的记录
                await self.vector_db.delete_vector(vector_id)
            
            # 删除关系数据库中的记录
            await self.db.execute_query(
                "DELETE FROM conversations WHERE id = ?",
                (memory_id,)
            )
            
            logger.debug(f"已删除对话记忆: {memory_id}")
            return True
        except Exception as e:
            logger.error(f"删除对话记忆失败: {e}", exc_info=True)
            return False
    
    async def delete_session(self, user_id: str, session_id: str) -> bool:
        """
        删除整个会话
        
        Args:
            user_id: 用户ID
            session_id: 会话ID
            
        Returns:
            是否删除成功
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            # 查询所有需要删除的向量ID
            query = "SELECT id, vector_id FROM conversations WHERE user_id = ? AND session_id = ?"
            results = await self.db.execute_query(query, (user_id, session_id))
            
            # 删除向量数据库中的记录
            for _, vector_id in results:
                if vector_id:
                    await self.vector_db.delete_vector(vector_id)
            
            # 删除关系数据库中的记录
            await self.db.execute_query(
                "DELETE FROM conversations WHERE user_id = ? AND session_id = ?",
                (user_id, session_id)
            )
            
            logger.info(f"已删除用户 {user_id} 的会话 {session_id}")
            return True
        except Exception as e:
            logger.error(f"删除会话失败: {e}", exc_info=True)
            return False
    
    async def update_memory_embedding(
        self, 
        memory_id: str, 
        memory_type: str,
        embedding: List[float]
    ) -> bool:
        """
        更新记忆的向量嵌入
        
        Args:
            memory_id: 记忆ID
            memory_type: 记忆类型，'conversation' 或 'knowledge'
            embedding: 新的向量嵌入
            
        Returns:
            是否更新成功
        """
        if not self._initialized:
            await self.initialize()
        
        try:
            # 确定表名和查询字段
            if memory_type == "conversation":
                table = "conversations"
                query = """
                    SELECT id, user_id, session_id, content, role, timestamp, vector_id
                    FROM conversations WHERE id = ?
                """
            elif memory_type == "knowledge":
                table = "knowledge"
                query = """
                    SELECT id, content, category, source, timestamp, vector_id
                    FROM knowledge WHERE id = ?
                """
            else:
                logger.error(f"不支持的记忆类型: {memory_type}")
                return False
            
            # 查询记忆信息
            result = await self.db.execute_query(query, (memory_id,))
            if not result:
                logger.warning(f"未找到记忆: {memory_id}")
                return False
            
            row = result[0]
            old_vector_id = row[-1]  # vector_id在最后一列
            
            # 准备向量数据库的payload
            if memory_type == "conversation":
                payload = {
                    "memory_id": row[0],
                    "user_id": row[1],
                    "session_id": row[2],
                    "content": row[3],
                    "role": row[4],
                    "timestamp": row[5],
                    "type": "conversation"
                }
            else:  # knowledge
                payload = {
                    "memory_id": row[0],
                    "content": row[1],
                    "category": row[2],
                    "source": row[3],
                    "timestamp": row[4],
                    "type": "knowledge"
                }
            
            # 如果已有向量ID，则更新向量
            if old_vector_id:
                success = await self.vector_db.update_vector(
                    id=old_vector_id,
                    vector=embedding,
                    payload=payload
                )
                vector_id = old_vector_id if success else None
            else:
                # 添加新向量
                vector_id = await self.vector_db.add_vector(
                    vector=embedding,
                    payload=payload
                )
            
            if not vector_id:
                logger.error(f"更新向量失败: {memory_id}")
                return False
            
            # 更新关系数据库中的记录
            await self.db.execute_query(
                f"UPDATE {table} SET vector_id = ?, embedding_generated = 1 WHERE id = ?",
                (vector_id, memory_id)
            )
            
            logger.debug(f"已更新记忆向量: {memory_id}")
            return True
        except Exception as e:
            logger.error(f"更新记忆向量失败: {e}", exc_info=True)
            return False

    async def ensure_user_exists(
        self,
        user_id: str,
        platform: str = "unknown", # Default platform if not provided
        name: str = None # Optional user name
    ) -> bool:
        """
        确保用户记录存在于 users 表中，如果不存在则创建。

        Args:
            user_id: 用户ID (主键)
            platform: 用户来源平台 (e.g., 'qq', 'discord')
            name: 用户昵称 (可选)

        Returns:
            操作是否成功 (True 表示用户已存在或已成功创建)
        """
        if not self._initialized:
            await self.initialize()

        try:
            # 1. 检查用户是否存在
            check_query = "SELECT id FROM users WHERE id = ?"
            existing_user = await self.db.execute_query(check_query, (user_id,))

            if existing_user:
                # 用户已存在，可以选择更新 last_active_at (如果需要)
                # update_query = "UPDATE users SET last_active_at = ? WHERE id = ?"
                # await self.db.execute_update(update_query, (int(time.time()), user_id))
                return True # 用户已存在

            # 2. 用户不存在，创建新记录
            insert_query = """
            INSERT INTO users (id, platform, name, created_at, last_active_at, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
            """
            current_time = int(time.time())
            # 基础元数据，可以根据需要扩展
            metadata_json = json.dumps({"platform_id": user_id}) # Store original ID in metadata too

            params = (
                user_id,
                platform,
                name, # Might be None
                current_time,
                current_time,
                metadata_json
            )

            insert_result = await self.db.execute_insert(insert_query, params)

            if insert_result != -1:
                logger.info(f"已为用户 {user_id} (平台: {platform}) 创建新的用户记录")
                return True
            else:
                logger.error(f"为用户 {user_id} 创建记录失败")
                return False

        except Exception as e:
            logger.error(f"检查或创建用户 {user_id} 时出错: {e}", exc_info=True)
            return False