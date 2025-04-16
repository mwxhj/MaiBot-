#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import time
from typing import Dict, Any, List, Union, Optional
from dataclasses import dataclass, asdict, field

from utils.logger import get_logger


@dataclass
class MessageSegment:
    """消息段数据结构"""
    type: str
    data: Dict[str, Any] = field(default_factory=dict)
    
    def __str__(self) -> str:
        """转换为字符串表示"""
        if self.type == "text":
            return self.data.get("text", "")
        return f"[{self.type}:{json.dumps(self.data, ensure_ascii=False)}]"
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MessageSegment':
        """从字典创建消息段"""
        if isinstance(data, dict) and "type" in data and "data" in data:
            return cls(type=data["type"], data=data["data"])
        else:
            # 默认作为文本消息处理
            return cls(type="text", data={"text": str(data)})
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {"type": self.type, "data": self.data}


@dataclass
class Message:
    """消息数据结构"""
    segments: List[MessageSegment] = field(default_factory=list)
    
    def __str__(self) -> str:
        """转换为字符串表示"""
        return "".join(str(segment) for segment in self.segments)
    
    def append(self, segment: Union[MessageSegment, Dict[str, Any], str]) -> 'Message':
        """添加消息段"""
        if isinstance(segment, MessageSegment):
            self.segments.append(segment)
        elif isinstance(segment, dict):
            self.segments.append(MessageSegment.from_dict(segment))
        elif isinstance(segment, str):
            self.segments.append(MessageSegment(type="text", data={"text": segment}))
        return self
    
    @classmethod
    def from_list(cls, msg_list: List[Dict[str, Any]]) -> 'Message':
        """从OneBot消息段列表创建消息"""
        msg = cls()
        for item in msg_list:
            msg.append(MessageSegment.from_dict(item))
        return msg
    
    @classmethod
    def from_str(cls, msg_str: str) -> 'Message':
        """从字符串创建消息"""
        msg = cls()
        if msg_str:
            msg.append(MessageSegment(type="text", data={"text": msg_str}))
        return msg
    
    def to_list(self) -> List[Dict[str, Any]]:
        """转换为OneBot消息段列表"""
        return [segment.to_dict() for segment in self.segments]
    
    def extract_plain_text(self) -> str:
        """提取纯文本内容"""
        return "".join(
            segment.data.get("text", "") 
            for segment in self.segments 
            if segment.type == "text"
        )


class MessageAdapter:
    """消息适配器，处理消息格式转换"""
    
    def __init__(self):
        self.logger = get_logger("MessageAdapter")
    
    def is_valid_onebot_message(self, data: Any) -> bool:
        """检查是否为有效的OneBot消息"""
        if isinstance(data, list):
            for item in data:
                if not (isinstance(item, dict) and "type" in item and "data" in item):
                    return False
            return True
        return False
    
    def adapt_to_onebot(self, message: Any) -> List[Dict[str, Any]]:
        """将任意消息适配为OneBot格式"""
        if isinstance(message, Message):
            return message.to_list()
        
        if isinstance(message, list) and self.is_valid_onebot_message(message):
            return message
        
        if isinstance(message, str):
            return Message.from_str(message).to_list()
        
        if isinstance(message, dict) and "type" in message and "data" in message:
            return [message]
        
        # 其他情况，尝试转为字符串处理
        try:
            return Message.from_str(str(message)).to_list()
        except Exception as e:
            self.logger.error(f"消息适配失败: {e}")
            return [{"type": "text", "data": {"text": "[消息适配失败]"}}]
    
    def adapt_from_onebot(self, onebot_message: List[Dict[str, Any]]) -> Message:
        """将OneBot格式消息转换为内部Message对象"""
        try:
            return Message.from_list(onebot_message)
        except Exception as e:
            self.logger.error(f"从OneBot格式转换消息失败: {e}")
            return Message().append("[消息转换失败]")
    
    def adapt_to_napcat(self, onebot_message: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """将OneBot消息适配为napcat格式"""
        # napcat使用标准的OneBot v11协议，但可能有些特殊处理
        result = []
        
        for segment in onebot_message:
            segment_type = segment.get("type", "")
            segment_data = segment.get("data", {})
            
            # napcat可能对某些消息类型有特殊处理
            if segment_type == "image" and "url" in segment_data and "file" not in segment_data:
                # 将url字段转换为file字段
                segment_data["file"] = segment_data["url"]
            
            # 确保CQ码兼容性
            if segment_type != "text":
                # 添加cq码识别标记以增强兼容性
                segment["napcat_cq_type"] = segment_type
            
            result.append({"type": segment_type, "data": segment_data})
            
        return result
    
    def adapt_from_napcat(self, napcat_message: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """将napcat格式消息适配为标准OneBot格式"""
        result = []
        
        for segment in napcat_message:
            segment_type = segment.get("type", "")
            segment_data = segment.get("data", {}).copy()  # 创建副本避免修改原数据
            
            # 处理napcat特殊格式
            if segment_type == "image" and "file" in segment_data and segment_data["file"].startswith("http"):
                # 确保url字段存在
                segment_data["url"] = segment_data["file"]
            
            # 去除napcat特定字段
            if "napcat_cq_type" in segment:
                del segment["napcat_cq_type"]
                
            result.append({"type": segment_type, "data": segment_data})
            
        return result
    
    def create_reply_message(self, message_id: str, content: Union[str, Message, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """创建回复消息"""
        onebot_message = []
        
        # 添加回复段
        reply_segment = {
            "type": "reply",
            "data": {"id": message_id}
        }
        onebot_message.append(reply_segment)
        
        # 添加内容
        if isinstance(content, str):
            onebot_message.extend(Message.from_str(content).to_list())
        elif isinstance(content, Message):
            onebot_message.extend(content.to_list())
        elif isinstance(content, list):
            onebot_message.extend(content)
            
        return onebot_message 