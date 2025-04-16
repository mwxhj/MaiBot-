#!/usr/bin/env python
# -*- coding: utf-8 -*-

from typing import Dict, Any, List, Optional, Union, Tuple, TypedDict, Literal
from enum import Enum, auto
from dataclasses import dataclass, field, asdict
from datetime import datetime

"""
存储Schema定义模块
定义MongoDB集合的文档结构和索引
"""

# 枚举定义
class MessageType(str, Enum):
    """消息类型枚举"""
    TEXT = "text"                # 文本消息
    IMAGE = "image"              # 图片消息
    VOICE = "voice"              # 语音消息
    VIDEO = "video"              # 视频消息
    FILE = "file"                # 文件消息
    LOCATION = "location"        # 位置消息
    CONTACT = "contact"          # 联系人
    SYSTEM = "system"            # 系统消息


class EmotionType(str, Enum):
    """情绪类型枚举"""
    HAPPY = "happy"              # 开心
    SAD = "sad"                  # 悲伤
    ANGRY = "angry"              # 生气
    DISGUSTED = "disgusted"      # 厌恶
    FEARFUL = "fearful"          # 恐惧
    SURPRISED = "surprised"      # 惊讶
    NEUTRAL = "neutral"          # 中性
    EXCITED = "excited"          # 兴奋
    TIRED = "tired"              # 疲惫
    BORED = "bored"              # 无聊
    CONFUSED = "confused"        # 困惑
    ANXIOUS = "anxious"          # 焦虑


class RelationshipLevel(str, Enum):
    """关系等级枚举"""
    STRANGER = "stranger"        # 陌生人
    ACQUAINTANCE = "acquaintance"  # 熟人
    FRIEND = "friend"            # 朋友
    CLOSE_FRIEND = "close_friend"  # 好友
    BEST_FRIEND = "best_friend"  # 挚友


# TypedDict定义
class MessageContentDict(TypedDict):
    """消息内容字典"""
    type: str                    # 内容类型
    data: Dict[str, Any]         # 内容数据


class MemoryDict(TypedDict):
    """记忆字典"""
    id: str                      # 记忆ID
    user_id: str                 # 用户ID
    content: str                 # 记忆内容
    importance: float            # 重要性
    created_at: str              # 创建时间
    vector: Optional[List[float]]  # 向量表示
    timestamp: float             # 时间戳
    source: str                  # 来源
    related_memory_ids: List[str]  # 相关记忆ID
    metadata: Dict[str, Any]     # 元数据
    tags: List[str]              # 标签


# 数据类定义
@dataclass
class Message:
    """消息模型"""
    id: str                      # 消息ID
    user_id: str                 # 用户ID
    content: Union[str, List[MessageContentDict]]  # 消息内容
    message_type: str            # 消息类型
    created_at: datetime         # 创建时间
    is_from_user: bool           # 是否来自用户
    group_id: Optional[str] = None  # 群组ID，私聊为None
    reply_to: Optional[str] = None  # 回复消息ID
    processed: bool = False      # 是否处理过
    metadata: Dict[str, Any] = field(default_factory=dict)  # 元数据
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = asdict(self)
        result["created_at"] = self.created_at.isoformat()
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Message':
        """从字典创建"""
        if isinstance(data.get("created_at"), str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        return cls(**data)


@dataclass
class User:
    """用户模型"""
    id: str                      # 用户ID
    username: Optional[str]      # 用户名
    nickname: Optional[str]      # 昵称
    avatar: Optional[str]        # 头像
    created_at: datetime         # 创建时间
    last_active_at: datetime     # 最后活跃时间
    metadata: Dict[str, Any] = field(default_factory=dict)  # 元数据
    is_bot: bool = False         # 是否为机器人
    settings: Dict[str, Any] = field(default_factory=dict)  # 用户设置
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = asdict(self)
        result["created_at"] = self.created_at.isoformat()
        result["last_active_at"] = self.last_active_at.isoformat()
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'User':
        """从字典创建"""
        if isinstance(data.get("created_at"), str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if isinstance(data.get("last_active_at"), str):
            data["last_active_at"] = datetime.fromisoformat(data["last_active_at"])
        return cls(**data)


@dataclass
class Memory:
    """记忆模型"""
    id: str                      # 记忆ID
    user_id: str                 # 用户ID
    content: str                 # 记忆内容
    importance: float            # 重要性（0-1）
    created_at: datetime         # 创建时间
    source: str                  # 来源（对话、总结等）
    timestamp: float             # 时间戳
    related_memory_ids: List[str] = field(default_factory=list)  # 相关记忆ID
    metadata: Dict[str, Any] = field(default_factory=dict)  # 元数据
    tags: List[str] = field(default_factory=list)  # 标签
    vector_id: Optional[str] = None  # 向量存储ID
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = asdict(self)
        result["created_at"] = self.created_at.isoformat()
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Memory':
        """从字典创建"""
        if isinstance(data.get("created_at"), str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        return cls(**data)


@dataclass
class Emotion:
    """情绪模型"""
    id: str                      # 情绪ID
    user_id: str                 # 用户ID
    emotion_type: str            # 情绪类型
    intensity: float             # 强度（0-1）
    created_at: datetime         # 创建时间
    trigger: Optional[str] = None  # 触发因素
    message_id: Optional[str] = None  # 相关消息ID
    metadata: Dict[str, Any] = field(default_factory=dict)  # 元数据
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = asdict(self)
        result["created_at"] = self.created_at.isoformat()
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Emotion':
        """从字典创建"""
        if isinstance(data.get("created_at"), str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        return cls(**data)


@dataclass
class Relationship:
    """关系模型"""
    id: str                      # 关系ID
    user_id: str                 # 用户ID
    level: str                   # 关系等级
    created_at: datetime         # 创建时间
    updated_at: datetime         # 更新时间
    familiarity: float = 0.0     # 熟悉度（0-1）
    closeness: float = 0.0       # 亲密度（0-1）
    trust: float = 0.0           # 信任度（0-1）
    interactions_count: int = 0  # 互动次数
    metadata: Dict[str, Any] = field(default_factory=dict)  # 元数据
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = asdict(self)
        result["created_at"] = self.created_at.isoformat()
        result["updated_at"] = self.updated_at.isoformat()
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Relationship':
        """从字典创建"""
        if isinstance(data.get("created_at"), str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if isinstance(data.get("updated_at"), str):
            data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        return cls(**data)


@dataclass
class ChatStream:
    """聊天流模型"""
    id: str                      # 聊天流ID
    user_id: str                 # 用户ID
    group_id: Optional[str]      # 群组ID
    created_at: datetime         # 创建时间
    updated_at: datetime         # 更新时间
    last_message_id: Optional[str] = None  # 最后消息ID
    messages_count: int = 0      # 消息数量
    metadata: Dict[str, Any] = field(default_factory=dict)  # 元数据
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        result = asdict(self)
        result["created_at"] = self.created_at.isoformat()
        result["updated_at"] = self.updated_at.isoformat()
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ChatStream':
        """从字典创建"""
        if isinstance(data.get("created_at"), str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if isinstance(data.get("updated_at"), str):
            data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        return cls(**data)


# 索引定义
MONGODB_INDEXES = {
    "messages": [
        [("user_id", 1), ("created_at", -1)],  # 用户消息时间倒序
        [("group_id", 1), ("created_at", -1)],  # 群组消息时间倒序
        [("reply_to", 1)],  # 回复消息
        [("processed", 1)]  # 处理状态
    ],
    "users": [
        [("username", 1)],  # 用户名唯一索引
        [("last_active_at", -1)]  # 最后活跃时间
    ],
    "memories": [
        [("user_id", 1), ("importance", -1)],  # 用户重要记忆
        [("user_id", 1), ("created_at", -1)],  # 用户最近记忆
        [("vector_id", 1)]  # 向量存储ID
    ],
    "emotions": [
        [("user_id", 1), ("created_at", -1)],  # 用户近期情绪
        [("user_id", 1), ("emotion_type", 1), ("created_at", -1)]  # 用户特定情绪
    ],
    "relationships": [
        [("user_id", 1)],  # 用户关系
        [("user_id", 1), ("level", 1)]  # 用户特定等级关系
    ],
    "chat_streams": [
        [("user_id", 1), ("updated_at", -1)],  # 用户最近聊天
        [("group_id", 1), ("updated_at", -1)]  # 群组最近聊天
    ]
}

# 向量集合定义
VECTOR_COLLECTIONS = {
    "user_memories": {  # 用户记忆向量集合
        "dimension": 1536,  # 向量维度
        "metric": "cosine"  # 相似度度量方式
    },
    "message_embeddings": {  # 消息嵌入向量集合
        "dimension": 1536,
        "metric": "cosine"
    }
}

# 缓存键前缀
CACHE_KEY_PREFIXES = {
    "user": "user:",  # 用户缓存
    "message": "msg:",  # 消息缓存
    "memory": "mem:",  # 记忆缓存
    "chat": "chat:",  # 聊天缓存
    "emotion": "emo:",  # 情绪缓存
    "relationship": "rel:",  # 关系缓存
    "stats": "stats:",  # 统计缓存
    "rate_limit": "rate:"  # 速率限制
}

# 导出所有模型
__all__ = [
    'MessageType',
    'EmotionType',
    'RelationshipLevel',
    'MessageContentDict',
    'MemoryDict',
    'Message',
    'User',
    'Memory',
    'Emotion',
    'Relationship',
    'ChatStream',
    'MONGODB_INDEXES',
    'VECTOR_COLLECTIONS',
    'CACHE_KEY_PREFIXES'
] 