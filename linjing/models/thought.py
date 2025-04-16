#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
林镜(LingJing) - 思考数据模型
负责结构化表示机器人的内部思考过程
"""

from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, field
import json
import time
from datetime import datetime

@dataclass
class Thought:
    """
    思考模型，表示机器人对消息的内部思考过程
    包含对消息的理解、情感反应和回应计划
    """
    message_id: str  # 关联的消息ID
    timestamp: float = field(default_factory=time.time)  # 思考生成时间戳
    understanding: Dict[str, Any] = field(default_factory=dict)  # 消息理解结果
    emotional_response: Dict[str, Any] = field(default_factory=dict)  # 情感反应
    response_plan: Dict[str, Any] = field(default_factory=dict)  # 回应计划
    raw_content: str = ""  # 原始消息内容
    metadata: Dict[str, Any] = field(default_factory=dict)  # 其他元数据
    thought_id: Optional[str] = None  # 思考ID，如果为None则使用message_id
    
    def __post_init__(self):
        """初始化后处理"""
        if not self.thought_id:
            self.thought_id = f"thought_{self.message_id}_{int(self.timestamp)}"
    
    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典
        
        Returns:
            思考字典表示
        """
        return {
            'thought_id': self.thought_id,
            'message_id': self.message_id,
            'timestamp': self.timestamp,
            'understanding': self.understanding,
            'emotional_response': self.emotional_response,
            'response_plan': self.response_plan,
            'raw_content': self.raw_content,
            'metadata': self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Thought':
        """
        从字典创建思考对象
        
        Args:
            data: 思考字典数据
            
        Returns:
            思考对象
        """
        return cls(
            thought_id=data.get('thought_id'),
            message_id=data.get('message_id', ''),
            timestamp=data.get('timestamp', time.time()),
            understanding=data.get('understanding', {}),
            emotional_response=data.get('emotional_response', {}),
            response_plan=data.get('response_plan', {}),
            raw_content=data.get('raw_content', ''),
            metadata=data.get('metadata', {})
        )
    
    def serialize(self) -> str:
        """
        序列化为JSON字符串
        
        Returns:
            JSON字符串
        """
        return json.dumps(self.to_dict(), ensure_ascii=False)
    
    @classmethod
    def deserialize(cls, data: str) -> 'Thought':
        """
        从JSON字符串反序列化
        
        Args:
            data: JSON字符串
            
        Returns:
            思考对象
        """
        return cls.from_dict(json.loads(data))
    
    def get_formatted_timestamp(self, format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
        """
        获取格式化的时间戳
        
        Args:
            format_str: 时间格式字符串
            
        Returns:
            格式化的时间戳字符串
        """
        return datetime.fromtimestamp(self.timestamp).strftime(format_str)
    
    def get_sender_id(self) -> Optional[str]:
        """
        获取发送者ID
        
        Returns:
            发送者ID，如果不存在则返回None
        """
        return self.metadata.get('sender_id')
    
    def get_message_type(self) -> str:
        """
        获取消息类型
        
        Returns:
            消息类型，如果不存在则返回'unknown'
        """
        return self.metadata.get('message_type', 'unknown')
    
    def is_group_message(self) -> bool:
        """
        判断是否为群组消息
        
        Returns:
            是否为群组消息
        """
        return self.get_message_type() == 'group'
    
    def get_group_id(self) -> Optional[str]:
        """
        获取群组ID
        
        Returns:
            群组ID，如果不是群组消息则返回None
        """
        return self.metadata.get('group_id') if self.is_group_message() else None
    
    def get_intent(self) -> str:
        """
        获取消息意图
        
        Returns:
            消息意图，如果不存在则返回'unknown'
        """
        return self.understanding.get('intent', 'unknown')
    
    def is_question(self) -> bool:
        """
        判断是否为问题
        
        Returns:
            是否为问题
        """
        return self.understanding.get('is_question', False) or self.get_intent() == 'question'
    
    def get_topic(self) -> str:
        """
        获取消息主题
        
        Returns:
            消息主题，如果不存在则返回'unknown'
        """
        return self.understanding.get('topic', 'unknown')
    
    def get_primary_emotion(self) -> str:
        """
        获取主要情感反应
        
        Returns:
            主要情感反应，如果不存在则返回'neutral'
        """
        return self.emotional_response.get('primary_emotion', 'neutral')
    
    def get_emotion_intensity(self) -> float:
        """
        获取情感强度
        
        Returns:
            情感强度，如果不存在则返回0.5
        """
        return self.emotional_response.get('emotion_intensity', 0.5)
    
    def get_response_priority(self) -> str:
        """
        获取回应优先级
        
        Returns:
            回应优先级，如果不存在则返回'low'
        """
        return self.response_plan.get('priority', 'low')
    
    def get_response_strategy(self) -> str:
        """
        获取回应策略
        
        Returns:
            回应策略，如果不存在则返回'conversational'
        """
        return self.response_plan.get('strategy', 'conversational')
    
    def get_response_tone(self) -> str:
        """
        获取回应语气
        
        Returns:
            回应语气，如果不存在则返回'neutral'
        """
        return self.response_plan.get('tone', 'neutral')
    
    def get_key_points(self) -> List[str]:
        """
        获取回应关键点
        
        Returns:
            回应关键点列表，如果不存在则返回空列表
        """
        return self.response_plan.get('key_points', [])
    
    def should_reference_memory(self) -> bool:
        """
        判断是否应引用记忆
        
        Returns:
            是否应引用记忆
        """
        return self.response_plan.get('should_reference_memory', False)
    
    def summarize(self) -> str:
        """
        生成思考摘要
        
        Returns:
            思考摘要文本
        """
        intent = self.get_intent()
        topic = self.get_topic()
        emotion = self.get_primary_emotion()
        strategy = self.get_response_strategy()
        priority = self.get_response_priority()
        
        return f"思考摘要: 理解为{intent}类消息，主题是{topic}，" \
               f"情感反应是{emotion}，回应策略是{strategy}，优先级{priority}" 