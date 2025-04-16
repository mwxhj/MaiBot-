#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
林镜(LingJing) - 聊天流数据模型
"""

from typing import Dict, Any, List, Optional, Iterator, Deque
from datetime import datetime, timedelta
from collections import deque
import json

from .message_models import Message

class ChatStream:
    """聊天流，管理一个对话的消息流"""
    
    def __init__(self, max_size: int = 50, ttl: int = 3600):
        """
        初始化聊天流
        
        Args:
            max_size: 最大消息数
            ttl: 消息存活时间（秒）
        """
        self._messages: Deque[Message] = deque(maxlen=max_size)
        self._ttl = ttl
        self._last_active = datetime.now()
        self._context: Dict[str, Any] = {}
        self._temporary_context: Dict[str, Any] = {}
    
    def add_message(self, message: Message) -> None:
        """
        添加消息
        
        Args:
            message: 消息对象
        """
        self._messages.append(message)
        self._last_active = datetime.now()
        
        # 清除过期的临时上下文
        self._clear_temporary_context()
    
    def get_messages(self, limit: Optional[int] = None) -> List[Message]:
        """
        获取消息列表
        
        Args:
            limit: 限制返回的消息数量，如果为None则返回所有消息
            
        Returns:
            消息列表
        """
        messages = list(self._messages)
        if limit is not None and len(messages) > limit:
            return messages[-limit:]
        return messages
    
    def get_last_message(self) -> Optional[Message]:
        """
        获取最后一条消息
        
        Returns:
            最后一条消息，如果没有消息则返回None
        """
        if not self._messages:
            return None
        return self._messages[-1]
    
    def get_messages_by_user(self, user_id: int, limit: Optional[int] = None) -> List[Message]:
        """
        获取指定用户的消息
        
        Args:
            user_id: 用户ID
            limit: 限制返回的消息数量，如果为None则返回所有消息
            
        Returns:
            消息列表
        """
        user_messages = [msg for msg in self._messages if msg.sender.user_id == user_id]
        if limit is not None and len(user_messages) > limit:
            return user_messages[-limit:]
        return user_messages
    
    def get_messages_by_time(self, start_time: datetime, end_time: Optional[datetime] = None) -> List[Message]:
        """
        获取指定时间范围内的消息
        
        Args:
            start_time: 开始时间
            end_time: 结束时间，如果为None则使用当前时间
            
        Returns:
            消息列表
        """
        if end_time is None:
            end_time = datetime.now()
        
        return [msg for msg in self._messages if start_time <= msg.time <= end_time]
    
    def get_context(self, key: str, default: Any = None) -> Any:
        """
        获取上下文值
        
        Args:
            key: 键
            default: 默认值
            
        Returns:
            上下文值
        """
        # 优先从临时上下文获取
        temp_value = self._temporary_context.get(key)
        if temp_value is not None and temp_value[1] > datetime.now():
            return temp_value[0]
        
        # 从持久上下文获取
        return self._context.get(key, default)
    
    def set_context(self, key: str, value: Any) -> None:
        """
        设置上下文值
        
        Args:
            key: 键
            value: 值
        """
        self._context[key] = value
    
    def set_temporary_context(self, key: str, value: Any, ttl: int = 300) -> None:
        """
        设置临时上下文值
        
        Args:
            key: 键
            value: 值
            ttl: 存活时间（秒）
        """
        expiration = datetime.now() + timedelta(seconds=ttl)
        self._temporary_context[key] = (value, expiration)
    
    def remove_context(self, key: str) -> None:
        """
        移除上下文值
        
        Args:
            key: 键
        """
        if key in self._context:
            del self._context[key]
        
        if key in self._temporary_context:
            del self._temporary_context[key]
    
    def clear_context(self) -> None:
        """清空上下文"""
        self._context.clear()
        self._temporary_context.clear()
    
    def _clear_temporary_context(self) -> None:
        """清除过期的临时上下文"""
        now = datetime.now()
        expired_keys = [
            key for key, (_, expiration) in self._temporary_context.items()
            if expiration <= now
        ]
        
        for key in expired_keys:
            del self._temporary_context[key]
    
    def is_expired(self) -> bool:
        """
        检查聊天流是否过期
        
        Returns:
            是否过期
        """
        return (datetime.now() - self._last_active).total_seconds() > self._ttl
    
    def update_last_active(self) -> None:
        """更新最后活跃时间"""
        self._last_active = datetime.now()
    
    def get_last_active(self) -> datetime:
        """
        获取最后活跃时间
        
        Returns:
            最后活跃时间
        """
        return self._last_active
    
    def clear_messages(self) -> None:
        """清空消息"""
        self._messages.clear()
    
    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典
        
        Returns:
            字典表示
        """
        return {
            'messages': [msg.to_dict() for msg in self._messages],
            'last_active': self._last_active.isoformat(),
            'context': self._context,
            'temporary_context': {
                key: (value, expiration.isoformat())
                for key, (value, expiration) in self._temporary_context.items()
            }
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ChatStream':
        """
        从字典创建聊天流
        
        Args:
            data: 字典数据
            
        Returns:
            聊天流对象
        """
        chat_stream = cls()
        
        # 恢复消息
        for msg_data in data.get('messages', []):
            chat_stream.add_message(Message.from_dict(msg_data))
        
        # 恢复最后活跃时间
        last_active = data.get('last_active')
        if last_active:
            chat_stream._last_active = datetime.fromisoformat(last_active)
        
        # 恢复上下文
        chat_stream._context = data.get('context', {})
        
        # 恢复临时上下文
        for key, (value, expiration_str) in data.get('temporary_context', {}).items():
            expiration = datetime.fromisoformat(expiration_str)
            if expiration > datetime.now():
                chat_stream._temporary_context[key] = (value, expiration)
        
        return chat_stream
    
    def serialize(self) -> str:
        """
        序列化为JSON字符串
        
        Returns:
            JSON字符串
        """
        return json.dumps(self.to_dict(), ensure_ascii=False)
    
    @classmethod
    def deserialize(cls, data: str) -> 'ChatStream':
        """
        从JSON字符串反序列化
        
        Args:
            data: JSON字符串
            
        Returns:
            聊天流对象
        """
        return cls.from_dict(json.loads(data))
    
    def __iter__(self) -> Iterator[Message]:
        """
        迭代消息
        
        Returns:
            消息迭代器
        """
        return iter(self._messages)
    
    def __len__(self) -> int:
        """
        获取消息数量
        
        Returns:
            消息数量
        """
        return len(self._messages) 
# -*- coding: utf-8 -*-

"""
林镜(LingJing) - 聊天流数据模型
"""



class ChatStream:
    """聊天流，管理一个对话的消息流"""
    
    def __init__(self, max_size: int = 50, ttl: int = 3600):
        """
        初始化聊天流
        
        Args:
            max_size: 最大消息数
            ttl: 消息存活时间（秒）
        """
        self._messages: Deque[Message] = deque(maxlen=max_size)
        self._ttl = ttl
        self._last_active = datetime.now()
        self._context: Dict[str, Any] = {}
        self._temporary_context: Dict[str, Any] = {}
    
    def add_message(self, message: Message) -> None:
        """
        添加消息
        
        Args:
            message: 消息对象
        """
        self._messages.append(message)
        self._last_active = datetime.now()
        
        # 清除过期的临时上下文
        self._clear_temporary_context()
    
    def get_messages(self, limit: Optional[int] = None) -> List[Message]:
        """
        获取消息列表
        
        Args:
            limit: 限制返回的消息数量，如果为None则返回所有消息
            
        Returns:
            消息列表
        """
        messages = list(self._messages)
        if limit is not None and len(messages) > limit:
            return messages[-limit:]
        return messages
    
    def get_last_message(self) -> Optional[Message]:
        """
        获取最后一条消息
        
        Returns:
            最后一条消息，如果没有消息则返回None
        """
        if not self._messages:
            return None
        return self._messages[-1]
    
    def get_messages_by_user(self, user_id: int, limit: Optional[int] = None) -> List[Message]:
        """
        获取指定用户的消息
        
        Args:
            user_id: 用户ID
            limit: 限制返回的消息数量，如果为None则返回所有消息
            
        Returns:
            消息列表
        """
        user_messages = [msg for msg in self._messages if msg.sender.user_id == user_id]
        if limit is not None and len(user_messages) > limit:
            return user_messages[-limit:]
        return user_messages
    
    def get_messages_by_time(self, start_time: datetime, end_time: Optional[datetime] = None) -> List[Message]:
        """
        获取指定时间范围内的消息
        
        Args:
            start_time: 开始时间
            end_time: 结束时间，如果为None则使用当前时间
            
        Returns:
            消息列表
        """
        if end_time is None:
            end_time = datetime.now()
        
        return [msg for msg in self._messages if start_time <= msg.time <= end_time]
    
    def get_context(self, key: str, default: Any = None) -> Any:
        """
        获取上下文值
        
        Args:
            key: 键
            default: 默认值
            
        Returns:
            上下文值
        """
        # 优先从临时上下文获取
        temp_value = self._temporary_context.get(key)
        if temp_value is not None and temp_value[1] > datetime.now():
            return temp_value[0]
        
        # 从持久上下文获取
        return self._context.get(key, default)
    
    def set_context(self, key: str, value: Any) -> None:
        """
        设置上下文值
        
        Args:
            key: 键
            value: 值
        """
        self._context[key] = value
    
    def set_temporary_context(self, key: str, value: Any, ttl: int = 300) -> None:
        """
        设置临时上下文值
        
        Args:
            key: 键
            value: 值
            ttl: 存活时间（秒）
        """
        expiration = datetime.now() + timedelta(seconds=ttl)
        self._temporary_context[key] = (value, expiration)
    
    def remove_context(self, key: str) -> None:
        """
        移除上下文值
        
        Args:
            key: 键
        """
        if key in self._context:
            del self._context[key]
        
        if key in self._temporary_context:
            del self._temporary_context[key]
    
    def clear_context(self) -> None:
        """清空上下文"""
        self._context.clear()
        self._temporary_context.clear()
    
    def _clear_temporary_context(self) -> None:
        """清除过期的临时上下文"""
        now = datetime.now()
        expired_keys = [
            key for key, (_, expiration) in self._temporary_context.items()
            if expiration <= now
        ]
        
        for key in expired_keys:
            del self._temporary_context[key]
    
    def is_expired(self) -> bool:
        """
        检查聊天流是否过期
        
        Returns:
            是否过期
        """
        return (datetime.now() - self._last_active).total_seconds() > self._ttl
    
    def update_last_active(self) -> None:
        """更新最后活跃时间"""
        self._last_active = datetime.now()
    
    def get_last_active(self) -> datetime:
        """
        获取最后活跃时间
        
        Returns:
            最后活跃时间
        """
        return self._last_active
    
    def clear_messages(self) -> None:
        """清空消息"""
        self._messages.clear()
    
    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典
        
        Returns:
            字典表示
        """
        return {
            'messages': [msg.to_dict() for msg in self._messages],
            'last_active': self._last_active.isoformat(),
            'context': self._context,
            'temporary_context': {
                key: (value, expiration.isoformat())
                for key, (value, expiration) in self._temporary_context.items()
            }
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ChatStream':
        """
        从字典创建聊天流
        
        Args:
            data: 字典数据
            
        Returns:
            聊天流对象
        """
        chat_stream = cls()
        
        # 恢复消息
        for msg_data in data.get('messages', []):
            chat_stream.add_message(Message.from_dict(msg_data))
        
        # 恢复最后活跃时间
        last_active = data.get('last_active')
        if last_active:
            chat_stream._last_active = datetime.fromisoformat(last_active)
        
        # 恢复上下文
        chat_stream._context = data.get('context', {})
        
        # 恢复临时上下文
        for key, (value, expiration_str) in data.get('temporary_context', {}).items():
            expiration = datetime.fromisoformat(expiration_str)
            if expiration > datetime.now():
                chat_stream._temporary_context[key] = (value, expiration)
        
        return chat_stream
    
    def serialize(self) -> str:
        """
        序列化为JSON字符串
        
        Returns:
            JSON字符串
        """
        return json.dumps(self.to_dict(), ensure_ascii=False)
    
    @classmethod
    def deserialize(cls, data: str) -> 'ChatStream':
        """
        从JSON字符串反序列化
        
        Args:
            data: JSON字符串
            
        Returns:
            聊天流对象
        """
        return cls.from_dict(json.loads(data))
    
    def __iter__(self) -> Iterator[Message]:
        """
        迭代消息
        
        Returns:
            消息迭代器
        """
        return iter(self._messages)
    
    def __len__(self) -> int:
        """
        获取消息数量
        
        Returns:
            消息数量
        """
        return len(self._messages) 