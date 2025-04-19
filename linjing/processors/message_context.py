#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
消息上下文模块，定义消息处理过程中的上下文对象。
消息上下文在处理链中传递，包含消息内容、用户信息、会话状态等。
"""

import time
import copy
from collections import defaultdict, deque
from typing import Any, Dict, List, Optional, Union, Set
from linjing.config import ConfigManager

from linjing.adapters import Message


class MessageContext:
    """
    消息上下文，包含消息处理过程中的各种信息。
    用于在处理器之间传递数据和状态。
    """
    
    def __init__(
        self,
        message: Message,
        user_id: str,
        session_id: Optional[str] = None,
        platform: str = "unknown"
    ):
        """
        初始化消息上下文
        
        Args:
            message: 原始消息对象
            user_id: 发送者用户ID
            session_id: 会话ID，如果为None则自动生成
            platform: 消息来源平台
        """
        self.message = message  # 原始消息
        self.user_id = user_id  # 用户ID
        self.session_id = session_id or f"session_{user_id}_{int(time.time())}"  # 会话ID
        self.platform = platform  # 平台标识
        
        self.response: Optional[Message] = None  # 回复消息
        self.processed = False  # 是否已处理完成
        self.aborted = False  # 是否中止处理
        
        # 处理过程中的中间状态和数据
        self._state: Dict[str, Any] = {}
        
        # 历史消息记录
        self.history: List[Message] = []
        # 群组历史记录 {group_id: deque}
        config = ConfigManager.get_config()
        group_max_history = config.get("processors", {}).get("read_air", {}).get("group_max_history", 30)
        group_user_max_history = config.get("processors", {}).get("read_air", {}).get("group_user_max_history", 10)
        
        self.group_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=group_max_history))
        # 用户群组历史记录 {(group_id, user_id): deque}
        self.group_user_history: Dict[tuple, deque] = defaultdict(lambda: deque(maxlen=group_user_max_history))
        
        # 关联的记忆
        self.memories: List[Any] = []
        
        # 情绪状态
        self.emotion_state: Dict[str, float] = {}
        
        # 错误信息
        self.error: Optional[Exception] = None
        
        # 处理器处理记录
        self.processor_log: List[str] = []
        
        # 创建时间
        self.created_at = time.time()
        
        # 额外的元数据
        self.metadata: Dict[str, Any] = {}
    
    def with_history(self, history: List[Message]) -> 'MessageContext':
        """
        添加历史消息
        
        Args:
            history: 历史消息列表
            
        Returns:
            更新后的上下文对象
        """
        self.history = history
        return self
    
    def with_emotion(self, emotion_state: Dict[str, float]) -> 'MessageContext':
        """
        添加情绪状态
        
        Args:
            emotion_state: 情绪状态字典
            
        Returns:
            更新后的上下文对象
        """
        self.emotion_state = emotion_state
        return self
    
    def with_memories(self, memories: List[Any]) -> 'MessageContext':
        """
        添加关联记忆
        
        Args:
            memories: 记忆列表
            
        Returns:
            更新后的上下文对象
        """
        self.memories = memories
        return self
    
    def with_metadata(self, metadata: Dict[str, Any]) -> 'MessageContext':
        """
        添加元数据
        
        Args:
            metadata: 元数据字典
            
        Returns:
            更新后的上下文对象
        """
        self.metadata.update(metadata)
        return self
    
    def set_state(self, key: str, value: Any) -> 'MessageContext':
        """
        设置状态值
        
        Args:
            key: 状态键
            value: 状态值
            
        Returns:
            当前上下文对象
        """
        self._state[key] = value
        return self
    
    def get_state(self, key: str, default: Any = None) -> Any:
        """
        获取状态值
        
        Args:
            key: 状态键
            default: 默认值
            
        Returns:
            状态值或默认值
        """
        return self._state.get(key, default)
    
    def has_state(self, key: str) -> bool:
        """
        检查是否存在指定状态
        
        Args:
            key: 状态键
            
        Returns:
            是否存在
        """
        return key in self._state
    
    def create_response(self, response: Union[Message, str]) -> 'MessageContext':
        """
        创建回复消息
        
        Args:
            response: 回复消息或文本
            
        Returns:
            当前上下文对象
        """
        if isinstance(response, str):
            from linjing.adapters import Message, MessageSegment
            self.response = Message(MessageSegment.text(response))
        else:
            self.response = response
        
        return self
    
    def get_response(self) -> Optional[Message]:
        """
        获取回复消息
        
        Returns:
            回复消息对象，如果没有则返回None
        """
        return self.response
    
    def abort(self) -> 'MessageContext':
        """
        中止处理流程
        
        Returns:
            当前上下文对象
        """
        self.aborted = True
        return self
    
    def set_processed(self) -> 'MessageContext':
        """
        标记为已处理完成
        
        Returns:
            当前上下文对象
        """
        self.processed = True
        return self
    
    def set_error(self, error: Exception) -> 'MessageContext':
        """
        设置错误信息
        
        Args:
            error: 异常对象
            
        Returns:
            当前上下文对象
        """
        self.error = error
        return self
    
    def log_processor(self, processor_name: str, message: str) -> 'MessageContext':
        """
        记录处理器日志
        
        Args:
            processor_name: 处理器名称
            message: 日志消息
            
        Returns:
            当前上下文对象
        """
        self.processor_log.append(f"[{processor_name}] {message}")
        return self
    
    def copy(self) -> 'MessageContext':
        """
        创建上下文的深拷贝
        
        Returns:
            上下文副本
        """
        return copy.deepcopy(self)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        将上下文转换为字典
        
        Returns:
            字典表示
        """
        return {
            "user_id": self.user_id,
            "session_id": self.session_id,
            "platform": self.platform,
            "processed": self.processed,
            "aborted": self.aborted,
            "created_at": self.created_at,
            "message": self.message.to_dict() if self.message else None,
            "response": self.response.to_dict() if self.response else None,
            "metadata": self.metadata
        }
    
    def get_processing_time(self) -> float:
        """
        获取处理耗时（秒）
        
        Returns:
            处理耗时
        """
        return time.time() - self.created_at
    
    def is_command(self) -> bool:
        """
        检查消息是否是命令
        
        Returns:
            是否是命令
        """
        from linjing.adapters.adapter_utils import is_command
        return is_command(self.message)
    
    def parse_command(self) -> Optional[Dict[str, Any]]:
        """
        解析命令
        
        Returns:
            解析后的命令信息，非命令则返回None
        """
        from linjing.adapters.adapter_utils import parse_command
        return parse_command(self.message)
    
    def __str__(self) -> str:
        """字符串表示"""
        return f"MessageContext(user={self.user_id}, session={self.session_id}, platform={self.platform})"

    def add_message(self, message: Message, group_id: Optional[str] = None) -> 'MessageContext':
        """
        添加消息到历史记录
        
        Args:
            message: 要添加的消息
            group_id: 群组ID(可选)
            
        Returns:
            当前上下文对象
        """
        self.history.append(message)
        
        if group_id:
            self.group_history[group_id].append(message)
            self.group_user_history[(group_id, self.user_id)].append(message)
            
        return self

    def build_context(self, max_history: int = 5, group_id: Optional[str] = None) -> List[Message]:
        """
        构建上下文消息列表
        
        Args:
            max_history: 最大历史消息数
            group_id: 群组ID(可选)
            
        Returns:
            上下文消息列表
        """
        if group_id:
            # 获取群组上下文(最近的群组消息+用户在该群组的消息)
            group_msgs = list(self.group_history.get(group_id, deque()))[-max_history//2:]
            user_msgs = list(self.group_user_history.get((group_id, self.user_id), deque()))[-max_history//2:]
            return group_msgs + user_msgs
        else:
            # 获取个人上下文
            return self.history[-max_history:]
