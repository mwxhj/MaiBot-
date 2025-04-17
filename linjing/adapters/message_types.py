#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
消息类型模块，用于处理各种平台的消息格式。
包含两个主要类：
- MessageSegment：消息段，表示消息的最小单位，如文本、图片等
- Message：消息，由多个消息段组成
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Any, Optional, Union, Iterator

from linjing.utils.string_utils import generate_uuid
from linjing.constants import MessageType

class SegmentType(Enum):
    """消息段类型枚举"""
    TEXT = auto()           # 纯文本
    IMAGE = auto()          # 图片
    AT = auto()             # @某人
    FACE = auto()           # 表情
    AUDIO = auto()          # 语音
    VIDEO = auto()          # 视频
    FILE = auto()           # 文件
    LOCATION = auto()       # 位置
    REPLY = auto()          # 回复
    FORWARD = auto()        # 合并转发
    CUSTOM = auto()         # 自定义类型
    UNKNOWN = auto()        # 未知类型


@dataclass
class MessageSegment:
    """
    消息段，表示消息的最小单位
    """
    type: SegmentType
    data: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def text(cls, text: str) -> "MessageSegment":
        """创建文本消息段"""
        return cls(SegmentType.TEXT, {"text": text})
    
    @classmethod
    def image(cls, url: str, **kwargs) -> "MessageSegment":
        """创建图片消息段"""
        data = {"url": url}
        data.update(kwargs)
        return cls(SegmentType.IMAGE, data)
    
    @classmethod
    def at(cls, user_id: str, name: Optional[str] = None) -> "MessageSegment":
        """创建@某人消息段"""
        data = {"user_id": user_id}
        if name:
            data["name"] = name
        return cls(SegmentType.AT, data)
    
    @classmethod
    def face(cls, id: str, **kwargs) -> "MessageSegment":
        """创建表情消息段"""
        data = {"id": id}
        data.update(kwargs)
        return cls(SegmentType.FACE, data)
    
    @classmethod
    def audio(cls, url: str, **kwargs) -> "MessageSegment":
        """创建语音消息段"""
        data = {"url": url}
        data.update(kwargs)
        return cls(SegmentType.AUDIO, data)
    
    @classmethod
    def video(cls, url: str, **kwargs) -> "MessageSegment":
        """创建视频消息段"""
        data = {"url": url}
        data.update(kwargs)
        return cls(SegmentType.VIDEO, data)
    
    @classmethod
    def file(cls, url: str, name: Optional[str] = None, **kwargs) -> "MessageSegment":
        """创建文件消息段"""
        data = {"url": url}
        if name:
            data["name"] = name
        data.update(kwargs)
        return cls(SegmentType.FILE, data)
    
    @classmethod
    def location(cls, lat: float, lon: float, title: Optional[str] = None, 
                content: Optional[str] = None, **kwargs) -> "MessageSegment":
        """创建位置消息段"""
        data = {"lat": lat, "lon": lon}
        if title:
            data["title"] = title
        if content:
            data["content"] = content
        data.update(kwargs)
        return cls(SegmentType.LOCATION, data)
    
    @classmethod
    def reply(cls, message_id: str, **kwargs) -> "MessageSegment":
        """创建回复消息段"""
        data = {"message_id": message_id}
        data.update(kwargs)
        return cls(SegmentType.REPLY, data)
    
    @classmethod
    def custom(cls, subtype: str, **kwargs) -> "MessageSegment":
        """创建自定义消息段"""
        data = {"subtype": subtype}
        data.update(kwargs)
        return cls(SegmentType.CUSTOM, data)
    
    def __str__(self) -> str:
        """转换为字符串表示"""
        if self.type == SegmentType.TEXT:
            return self.data.get("text", "")
        return f"[{self.type.name.lower()}:{','.join([f'{k}={v}' for k, v in self.data.items()])}]"
    
    def is_text(self) -> bool:
        """判断是否为文本消息段"""
        return self.type == SegmentType.TEXT


class Message:
    """
    消息类，由多个消息段组成
    """
    def __init__(self, message: Optional[Union[str, List[MessageSegment], "Message", MessageSegment]] = None):
        self.segments: List[MessageSegment] = []
        
        if message is None:
            pass
        elif isinstance(message, str):
            self.segments.append(MessageSegment.text(message))
        elif isinstance(message, MessageSegment):
            self.segments.append(message)
        elif isinstance(message, Message):
            self.segments.extend(message.segments)
        elif isinstance(message, list):
            for seg in message:
                if isinstance(seg, MessageSegment):
                    self.segments.append(seg)
                else:
                    raise TypeError(f"类型错误：期望MessageSegment类型，得到{type(seg)}")
        else:
            raise TypeError(f"类型错误：无法从{type(message)}创建Message")
    
    def append(self, message: Union[str, MessageSegment, "Message"]) -> "Message":
        """添加消息段"""
        if isinstance(message, str):
            self.segments.append(MessageSegment.text(message))
        elif isinstance(message, MessageSegment):
            self.segments.append(message)
        elif isinstance(message, Message):
            self.segments.extend(message.segments)
        else:
            raise TypeError(f"类型错误：无法添加类型为{type(message)}的消息")
        return self
    
    def extend(self, message: Union[List[MessageSegment], "Message"]) -> "Message":
        """扩展消息段"""
        if isinstance(message, Message):
            self.segments.extend(message.segments)
        elif isinstance(message, list):
            for seg in message:
                if isinstance(seg, MessageSegment):
                    self.segments.append(seg)
                else:
                    raise TypeError(f"类型错误：期望MessageSegment类型，得到{type(seg)}")
        else:
            raise TypeError(f"类型错误：无法扩展类型为{type(message)}的消息")
        return self
    
    def __add__(self, other: Union[str, MessageSegment, "Message"]) -> "Message":
        """加法运算符重载，用于拼接消息"""
        result = Message(self)
        return result.append(other)
    
    def __iadd__(self, other: Union[str, MessageSegment, "Message"]) -> "Message":
        """+=运算符重载，用于拼接消息"""
        return self.append(other)
    
    def __iter__(self) -> Iterator[MessageSegment]:
        """迭代器，用于遍历消息段"""
        return iter(self.segments)
    
    def __str__(self) -> str:
        """转换为字符串表示"""
        return "".join(str(seg) for seg in self.segments)
    
    def __len__(self) -> int:
        """获取消息段数量"""
        return len(self.segments)
    
    def extract_plain_text(self) -> str:
        """提取纯文本"""
        return "".join(str(seg) for seg in self.segments if seg.is_text())
    
    def is_text_only(self) -> bool:
        """判断是否只包含文本消息段"""
        return all(seg.is_text() for seg in self.segments)
    
    def copy(self) -> "Message":
        """复制一个消息实例"""
        return Message(self)
    
    def to_dict(self) -> List[Dict[str, Any]]:
        """转换为字典表示，用于序列化"""
        return [
            {
                "type": seg.type.name.lower(),
                "data": seg.data
            }
            for seg in self.segments
        ]
    
    @classmethod
    def from_dict(cls, data: List[Dict[str, Any]]) -> "Message":
        """从字典表示创建消息，用于反序列化"""
        msg = cls()
        for item in data:
            type_name = item.get("type", "unknown").upper()
            try:
                seg_type = SegmentType[type_name]
            except KeyError:
                seg_type = SegmentType.UNKNOWN
            
            msg.segments.append(MessageSegment(seg_type, item.get("data", {})))
        return msg

    def id(self) -> str:
        """获取消息ID"""
        return generate_uuid()

    def timestamp(self) -> Optional[float]:
        """获取消息时间戳"""
        return None

    def sender(self) -> Optional[Dict[str, Any]]:
        """获取消息发送者"""
        return None

    def meta(self) -> Dict[str, Any]:
        """获取消息元数据"""
        return {}

    def set_id(self, message_id: str) -> 'Message':
        """设置消息ID"""
        # This method is not provided in the original file or the new implementation
        # It's assumed to exist as it's called in the to_onebot_format method
        return self

    def set_timestamp(self, timestamp: float) -> 'Message':
        """设置消息时间戳"""
        # This method is not provided in the original file or the new implementation
        # It's assumed to exist as it's called in the to_onebot_format method
        return self

    def set_sender(self, sender: Dict[str, Any]) -> 'Message':
        """设置消息发送者"""
        # This method is not provided in the original file or the new implementation
        # It's assumed to exist as it's called in the to_onebot_format method
        return self

    def set_meta(self, key: str, value: Any) -> 'Message':
        """设置元数据"""
        # This method is not provided in the original file or the new implementation
        # It's assumed to exist as it's called in the to_onebot_format method
        return self

    def get_meta(self, key: str, default: Any = None) -> Any:
        """获取元数据"""
        # This method is not provided in the original file or the new implementation
        # It's assumed to exist as it's called in the to_onebot_format method
        return default

    def get_user_id(self) -> Optional[str]:
        """获取消息发送者ID"""
        # This method is not provided in the original file or the new implementation
        # It's assumed to exist as it's called in the get_session_id method
        return None

    def get_session_id(self) -> str:
        """获取会话ID"""
        user_id = self.get_user_id()
        if not user_id:
            return "unknown"
        
        # 检查是否是群消息
        group_id = self.get_meta("group_id")
        if group_id:
            return f"group_{group_id}"
        
        return f"private_{user_id}"

    def to_onebot_format(self) -> List[Dict[str, Any]]:
        """转换为OneBot消息格式"""
        onebot_segments = []
        
        for seg in self.segments:
            if seg.type == SegmentType.TEXT:
                onebot_segments.append({
                    "type": "text",
                    "data": {
                        "text": seg.data["text"]
                    }
                })
            
            elif seg.type == SegmentType.IMAGE:
                # 处理图片格式
                data = {"file": seg.data["url"]}
                onebot_segments.append({
                    "type": "image",
                    "data": data
                })
            
            elif seg.type == SegmentType.AT:
                onebot_segments.append({
                    "type": "at",
                    "data": {
                        "qq": seg.data["user_id"]
                    }
                })
            
            elif seg.type == SegmentType.REPLY:
                onebot_segments.append({
                    "type": "reply",
                    "data": {
                        "id": seg.data["message_id"]
                    }
                })
            
            # 其他类型可以根据需要添加转换逻辑
        
        return onebot_segments

    @classmethod
    def from_onebot_event(cls, event: Dict[str, Any]) -> 'Message':
        """从OneBot事件创建消息"""
        message_list = event.get("message", [])
        if isinstance(message_list, str):
            # 纯文本消息
            segments = [MessageSegment.text(message_list)]
        else:
            # 复合消息
            segments = []
            for seg in message_list:
                seg_type = seg.get("type")
                seg_data = seg.get("data", {})
                
                if seg_type == "text":
                    segments.append(MessageSegment.text(seg_data.get("text", "")))
                
                elif seg_type == "image":
                    file = seg_data.get("file", "")
                    segments.append(MessageSegment.image(file))
                
                elif seg_type == "at":
                    qq = seg_data.get("qq", "")
                    segments.append(MessageSegment.at(qq))
                
                elif seg_type == "reply":
                    id_ = seg_data.get("id", "")
                    segments.append(MessageSegment.reply(id_))
                
                # 其他类型可以根据需要添加转换逻辑
        
        msg = cls(segments)
        
        # 设置消息元数据
        msg.set_id(event.get("message_id", ""))
        
        # 设置发送者信息
        sender = event.get("sender", {})
        msg.set_sender(sender)
        
        # 设置群组信息
        if "group_id" in event:
            msg.set_meta("group_id", event["group_id"])
        
        return msg 