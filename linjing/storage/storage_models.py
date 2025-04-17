#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
存储数据模型模块，定义数据模型的基类和常用模型。
"""

import json
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple, Union, TypeVar, Type, ClassVar

from ..utils.logger import get_logger

logger = get_logger(__name__)

T = TypeVar('T', bound='BaseModel')


class BaseModel:
    """
    数据模型基类，提供通用的数据操作方法。
    """
    
    # 子类需要覆盖这些类变量
    table_name: ClassVar[str] = ""
    primary_key: ClassVar[str] = "id"
    fields: ClassVar[List[str]] = []
    
    def __init__(self, **kwargs):
        """
        初始化模型实例。
        
        Args:
            **kwargs: 模型属性
        """
        # 设置ID，如果未提供则生成UUID
        if self.primary_key not in kwargs or not kwargs[self.primary_key]:
            kwargs[self.primary_key] = str(uuid.uuid4())
        
        # 设置属性
        for key, value in kwargs.items():
            setattr(self, key, value)
        
        # 设置创建时间，如果未提供
        if hasattr(self, 'created_at') and not getattr(self, 'created_at', None):
            self.created_at = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        """
        将模型转换为字典。
        
        Returns:
            模型属性字典
        """
        result = {}
        for field in self.fields:
            if hasattr(self, field):
                value = getattr(self, field)
                result[field] = value
        return result
    
    def to_json(self) -> str:
        """
        将模型转换为JSON字符串。
        
        Returns:
            JSON字符串
        """
        return json.dumps(self.to_dict(), ensure_ascii=False)
    
    @classmethod
    def from_dict(cls: Type[T], data: Dict[str, Any]) -> T:
        """
        从字典创建模型实例。
        
        Args:
            data: 模型属性字典
            
        Returns:
            模型实例
        """
        return cls(**data)
    
    @classmethod
    def from_json(cls: Type[T], json_str: str) -> T:
        """
        从JSON字符串创建模型实例。
        
        Args:
            json_str: JSON字符串
            
        Returns:
            模型实例
        """
        data = json.loads(json_str)
        return cls.from_dict(data)
    
    @classmethod
    async def create_table_sql(cls) -> str:
        """
        生成创建表的SQL语句。
        子类应该覆盖此方法以提供特定的表结构。
        
        Returns:
            创建表的SQL语句
        """
        raise NotImplementedError("子类必须实现create_table_sql方法")
    
    @classmethod
    async def get(cls: Type[T], db_manager, id_value: str) -> Optional[T]:
        """
        通过ID获取模型实例。
        
        Args:
            db_manager: 数据库管理器
            id_value: ID值
            
        Returns:
            模型实例，如果未找到则返回None
        """
        try:
            query = f"SELECT * FROM {cls.table_name} WHERE {cls.primary_key} = ?"
            results = await db_manager.execute_query(query, (id_value,))
            
            if not results:
                return None
                
            return cls.from_dict(results[0])
        except Exception as e:
            logger.error(f"获取{cls.__name__}实例失败: {e}")
            return None
    
    @classmethod
    async def get_all(cls: Type[T], db_manager, conditions: Dict[str, Any] = None, limit: int = 100) -> List[T]:
        """
        获取所有符合条件的模型实例。
        
        Args:
            db_manager: 数据库管理器
            conditions: 查询条件字典
            limit: 最大返回数量
            
        Returns:
            模型实例列表
        """
        try:
            query = f"SELECT * FROM {cls.table_name}"
            params = []
            
            if conditions:
                clauses = []
                for key, value in conditions.items():
                    clauses.append(f"{key} = ?")
                    params.append(value)
                
                query += " WHERE " + " AND ".join(clauses)
            
            query += f" LIMIT {limit}"
            results = await db_manager.execute_query(query, tuple(params))
            
            return [cls.from_dict(result) for result in results]
        except Exception as e:
            logger.error(f"获取{cls.__name__}列表失败: {e}")
            return []
    
    async def save(self, db_manager) -> bool:
        """
        保存模型实例到数据库。
        自动判断是插入新记录还是更新现有记录。
        
        Args:
            db_manager: 数据库管理器
            
        Returns:
            是否保存成功
        """
        try:
            # 检查是否存在
            primary_key_value = getattr(self, self.primary_key)
            existing = await self.__class__.get(db_manager, primary_key_value)
            
            if existing:
                # 更新
                return await self._update(db_manager)
            else:
                # 插入
                return await self._insert(db_manager)
        except Exception as e:
            logger.error(f"保存{self.__class__.__name__}实例失败: {e}")
            return False
    
    async def _insert(self, db_manager) -> bool:
        """
        插入模型实例到数据库。
        
        Args:
            db_manager: 数据库管理器
            
        Returns:
            是否插入成功
        """
        try:
            data = self.to_dict()
            fields = list(data.keys())
            placeholders = ["?" for _ in fields]
            values = [data[field] for field in fields]
            
            query = f"INSERT INTO {self.__class__.table_name} ({', '.join(fields)}) VALUES ({', '.join(placeholders)})"
            result = await db_manager.execute_insert(query, tuple(values))
            
            return result != -1
        except Exception as e:
            logger.error(f"插入{self.__class__.__name__}实例失败: {e}")
            return False
    
    async def _update(self, db_manager) -> bool:
        """
        更新数据库中的模型实例。
        
        Args:
            db_manager: 数据库管理器
            
        Returns:
            是否更新成功
        """
        try:
            data = self.to_dict()
            primary_key_value = data.pop(self.__class__.primary_key)
            
            set_clauses = [f"{field} = ?" for field in data.keys()]
            values = list(data.values()) + [primary_key_value]
            
            query = f"UPDATE {self.__class__.table_name} SET {', '.join(set_clauses)} WHERE {self.__class__.primary_key} = ?"
            result = await db_manager.execute_update(query, tuple(values))
            
            return result > 0
        except Exception as e:
            logger.error(f"更新{self.__class__.__name__}实例失败: {e}")
            return False
    
    async def delete(self, db_manager) -> bool:
        """
        从数据库删除模型实例。
        
        Args:
            db_manager: 数据库管理器
            
        Returns:
            是否删除成功
        """
        try:
            primary_key_value = getattr(self, self.__class__.primary_key)
            query = f"DELETE FROM {self.__class__.table_name} WHERE {self.__class__.primary_key} = ?"
            result = await db_manager.execute_update(query, (primary_key_value,))
            
            return result > 0
        except Exception as e:
            logger.error(f"删除{self.__class__.__name__}实例失败: {e}")
            return False


class UserModel(BaseModel):
    """用户模型，存储用户信息"""
    
    table_name = "users"
    primary_key = "id"
    fields = ["id", "name", "avatar", "created_at", "last_active", "settings", "metadata"]
    
    def __init__(
        self, 
        id: str = None,
        name: str = "", 
        avatar: str = "",
        created_at: float = None,
        last_active: float = None,
        settings: Dict[str, Any] = None,
        metadata: Dict[str, Any] = None
    ):
        """
        初始化用户模型
        
        Args:
            id: 用户ID，如未提供则自动生成
            name: 用户名称
            avatar: 用户头像URL
            created_at: 创建时间戳
            last_active: 最后活跃时间戳
            settings: 用户设置
            metadata: 用户元数据
        """
        super().__init__(
            id=id,
            name=name,
            avatar=avatar,
            created_at=created_at,
            last_active=last_active or time.time(),
            settings=settings or {},
            metadata=metadata or {}
        )
    
    @classmethod
    async def create_table_sql(cls) -> str:
        """
        生成创建用户表的SQL语句
        
        Returns:
            创建表的SQL语句
        """
        return """
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            avatar TEXT,
            created_at REAL,
            last_active REAL,
            settings TEXT,
            metadata TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_users_name ON users(name);
        CREATE INDEX IF NOT EXISTS idx_users_last_active ON users(last_active);
        """
    
    @property
    def settings_dict(self) -> Dict[str, Any]:
        """获取用户设置字典"""
        if isinstance(self.settings, str):
            try:
                return json.loads(self.settings)
            except:
                return {}
        return self.settings or {}
    
    @property
    def metadata_dict(self) -> Dict[str, Any]:
        """获取用户元数据字典"""
        if isinstance(self.metadata, str):
            try:
                return json.loads(self.metadata)
            except:
                return {}
        return self.metadata or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """
        将用户模型转换为字典
        
        Returns:
            用户属性字典
        """
        result = super().to_dict()
        
        # 确保settings和metadata是JSON字符串
        if isinstance(result.get("settings"), dict):
            result["settings"] = json.dumps(result["settings"], ensure_ascii=False)
            
        if isinstance(result.get("metadata"), dict):
            result["metadata"] = json.dumps(result["metadata"], ensure_ascii=False)
            
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UserModel':
        """
        从字典创建用户模型实例
        
        Args:
            data: 用户属性字典
            
        Returns:
            用户模型实例
        """
        # 解析JSON字符串
        if isinstance(data.get("settings"), str):
            try:
                data["settings"] = json.loads(data["settings"])
            except:
                data["settings"] = {}
                
        if isinstance(data.get("metadata"), str):
            try:
                data["metadata"] = json.loads(data["metadata"])
            except:
                data["metadata"] = {}
                
        return cls(**data)
    
    async def update_activity(self, db_manager) -> bool:
        """
        更新用户最后活跃时间
        
        Args:
            db_manager: 数据库管理器
            
        Returns:
            是否更新成功
        """
        self.last_active = time.time()
        return await self._update(db_manager)


class MemoryModel(BaseModel):
    """记忆模型，存储机器人记忆"""
    
    table_name = "memories"
    primary_key = "id"
    fields = [
        "id", "content", "memory_type", "importance", "creation_time", 
        "last_access_time", "access_count", "user_id", "session_id", 
        "metadata", "decay_rate"
    ]
    
    def __init__(
        self,
        id: str = None,
        content: str = "",
        memory_type: str = "general",
        importance: float = 0.5,
        creation_time: float = None,
        last_access_time: float = None,
        access_count: int = 0,
        user_id: str = None,
        session_id: str = None,
        metadata: Dict[str, Any] = None,
        decay_rate: float = 0.05
    ):
        """
        初始化记忆模型
        
        Args:
            id: 记忆ID，如未提供则自动生成
            content: 记忆内容
            memory_type: 记忆类型
            importance: 重要性(0-1)
            creation_time: 创建时间戳
            last_access_time: 最后访问时间戳
            access_count: 访问次数
            user_id: 相关用户ID
            session_id: 相关会话ID
            metadata: 记忆元数据
            decay_rate: 记忆衰减率
        """
        now = time.time()
        super().__init__(
            id=id,
            content=content,
            memory_type=memory_type,
            importance=importance,
            creation_time=creation_time or now,
            last_access_time=last_access_time or now,
            access_count=access_count,
            user_id=user_id,
            session_id=session_id,
            metadata=metadata or {},
            decay_rate=decay_rate
        )
    
    @classmethod
    async def create_table_sql(cls) -> str:
        """
        生成创建记忆表的SQL语句
        
        Returns:
            创建表的SQL语句
        """
        return """
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
    
    @property
    def metadata_dict(self) -> Dict[str, Any]:
        """获取记忆元数据字典"""
        if isinstance(self.metadata, str):
            try:
                return json.loads(self.metadata)
            except:
                return {}
        return self.metadata or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """
        将记忆模型转换为字典
        
        Returns:
            记忆属性字典
        """
        result = super().to_dict()
        
        # 确保metadata是JSON字符串
        if isinstance(result.get("metadata"), dict):
            result["metadata"] = json.dumps(result["metadata"], ensure_ascii=False)
            
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MemoryModel':
        """
        从字典创建记忆模型实例
        
        Args:
            data: 记忆属性字典
            
        Returns:
            记忆模型实例
        """
        # 解析JSON字符串
        if isinstance(data.get("metadata"), str):
            try:
                data["metadata"] = json.loads(data["metadata"])
            except:
                data["metadata"] = {}
                
        return cls(**data)
    
    async def increment_access(self, db_manager) -> bool:
        """
        增加访问次数并更新最后访问时间
        
        Args:
            db_manager: 数据库管理器
            
        Returns:
            是否更新成功
        """
        self.access_count += 1
        self.last_access_time = time.time()
        return await self._update(db_manager)
    
    def calculate_current_importance(self) -> float:
        """
        计算当前重要性，考虑时间衰减
        
        Returns:
            当前重要性值
        """
        # 基本重要性
        base_importance = self.importance
        
        # 时间衰减因子
        time_factor = 1.0
        if hasattr(self, "creation_time") and self.creation_time:
            elapsed_days = (time.time() - self.creation_time) / (24 * 3600)
            # 每天衰减 decay_rate
            time_factor = max(0.1, 1.0 - elapsed_days * self.decay_rate)
        
        # 访问频率提升因子
        access_factor = min(1.5, 1.0 + (self.access_count / 20.0))
        
        # 计算综合重要性
        current_importance = base_importance * time_factor * access_factor
        
        # 确保值在0-1范围内
        return max(0.0, min(1.0, current_importance))


class SessionModel(BaseModel):
    """会话模型，存储用户对话会话"""
    
    table_name = "sessions"
    primary_key = "id"
    fields = ["id", "user_id", "start_time", "end_time", "metadata"]
    
    def __init__(
        self,
        id: str = None,
        user_id: str = None,
        start_time: float = None,
        end_time: float = None,
        metadata: Dict[str, Any] = None
    ):
        """
        初始化会话模型
        
        Args:
            id: 会话ID，如未提供则自动生成
            user_id: 用户ID
            start_time: 开始时间戳
            end_time: 结束时间戳
            metadata: 会话元数据
        """
        super().__init__(
            id=id,
            user_id=user_id,
            start_time=start_time or time.time(),
            end_time=end_time,
            metadata=metadata or {}
        )
    
    @classmethod
    async def create_table_sql(cls) -> str:
        """
        生成创建会话表的SQL语句
        
        Returns:
            创建表的SQL语句
        """
        return """
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            start_time REAL NOT NULL,
            end_time REAL,
            metadata TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id);
        CREATE INDEX IF NOT EXISTS idx_sessions_start_time ON sessions(start_time);
        """
    
    @property
    def is_active(self) -> bool:
        """会话是否活跃"""
        return self.end_time is None
    
    @property
    def duration(self) -> float:
        """会话持续时间（秒）"""
        if not self.start_time:
            return 0
            
        end = self.end_time or time.time()
        return end - self.start_time
    
    @property
    def metadata_dict(self) -> Dict[str, Any]:
        """获取会话元数据字典"""
        if isinstance(self.metadata, str):
            try:
                return json.loads(self.metadata)
            except:
                return {}
        return self.metadata or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """
        将会话模型转换为字典
        
        Returns:
            会话属性字典
        """
        result = super().to_dict()
        
        # 确保metadata是JSON字符串
        if isinstance(result.get("metadata"), dict):
            result["metadata"] = json.dumps(result["metadata"], ensure_ascii=False)
            
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SessionModel':
        """
        从字典创建会话模型实例
        
        Args:
            data: 会话属性字典
            
        Returns:
            会话模型实例
        """
        # 解析JSON字符串
        if isinstance(data.get("metadata"), str):
            try:
                data["metadata"] = json.loads(data["metadata"])
            except:
                data["metadata"] = {}
                
        return cls(**data)
    
    async def end_session(self, db_manager) -> bool:
        """
        结束会话
        
        Args:
            db_manager: 数据库管理器
            
        Returns:
            是否更新成功
        """
        if not self.end_time:
            self.end_time = time.time()
            return await self._update(db_manager)
        return True 