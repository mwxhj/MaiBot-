#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
林镜(LingJing) - 消息数据模型
"""

from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from dataclasses import dataclass, field

@dataclass
class Sender:
    """发送者信息"""
    user_id: int
    nickname: str = ""
    card: str = ""
    role: str = ""
    title: str = ""
    is_admin: bool = False
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Sender':
        """从字典创建发送者对象"""
        return cls(
            user_id=data.get('user_id', 0),
            nickname=data.get('nickname', ''),
            card=data.get('card', ''),
            role=data.get('role', ''),
            title=data.get('title', ''),
            is_admin=data.get('is_admin', False)
        )

@dataclass
class MessageSegment:
    """消息段"""
    type: str
    data: Dict[str, str] = field(default_factory=dict)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MessageSegment':
        """从字典创建消息段对象"""
        return cls(
            type=data.get('type', 'text'),
            data=data.get('data', {})
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'type': self.type,
            'data': self.data
        }
    
    @classmethod
    def text(cls, text: str) -> 'MessageSegment':
        """创建文本消息段"""
        return cls(type='text', data={'text': text})
    
    @classmethod
    def image(cls, file: str, url: Optional[str] = None) -> 'MessageSegment':
        """创建图片消息段"""
        data = {'file': file}
        if url:
            data['url'] = url
        return cls(type='image', data=data)
    
    @classmethod
    def at(cls, user_id: Union[int, str]) -> 'MessageSegment':
        """创建@消息段"""
        return cls(type='at', data={'qq': str(user_id)})
    
    @classmethod
    def reply(cls, message_id: Union[int, str]) -> 'MessageSegment':
        """创建回复消息段"""
        return cls(type='reply', data={'id': str(message_id)})

@dataclass
class MessageContent:
    """消息内容"""
    segments: List[MessageSegment] = field(default_factory=list)
    raw_content: str = ""
    
    @classmethod
    def from_segments(cls, segments: List[Dict[str, Any]], raw_content: str = "") -> 'MessageContent':
        """从消息段列表创建消息内容对象"""
        return cls(
            segments=[MessageSegment.from_dict(segment) for segment in segments],
            raw_content=raw_content
        )
    
    def to_segments(self) -> List[Dict[str, Any]]:
        """转换为消息段列表"""
        return [segment.to_dict() for segment in self.segments]
    
    def get_plain_text(self) -> str:
        """获取纯文本内容"""
        return ''.join([
            segment.data.get('text', '') 
            for segment in self.segments 
            if segment.type == 'text'
        ])
    
    def contains_image(self) -> bool:
        """是否包含图片"""
        return any(segment.type == 'image' for segment in self.segments)
    
    def contains_at(self, user_id: Optional[Union[int, str]] = None) -> bool:
        """是否包含@"""
        if user_id is None:
            return any(segment.type == 'at' for segment in self.segments)
        else:
            user_id_str = str(user_id)
            return any(
                segment.type == 'at' and segment.data.get('qq', '') == user_id_str
                for segment in self.segments
            )
    
    def add_segment(self, segment: MessageSegment) -> 'MessageContent':
        """添加消息段"""
        self.segments.append(segment)
        return self
    
    def add_text(self, text: str) -> 'MessageContent':
        """添加文本"""
        self.segments.append(MessageSegment.text(text))
        return self
    
    def add_image(self, file: str, url: Optional[str] = None) -> 'MessageContent':
        """添加图片"""
        self.segments.append(MessageSegment.image(file, url))
        return self
    
    def add_at(self, user_id: Union[int, str]) -> 'MessageContent':
        """添加@"""
        self.segments.append(MessageSegment.at(user_id))
        return self
    
    def add_reply(self, message_id: Union[int, str]) -> 'MessageContent':
        """添加回复"""
        self.segments.append(MessageSegment.reply(message_id))
        return self

@dataclass
class Message:
    """消息"""
    id: str
    type: str
    message_type: str
    sender: Sender
    content: MessageContent
    time: datetime
    self_id: int
    group_id: Optional[int] = None
    sub_type: str = "normal"
    anonymous: Optional[Dict[str, Any]] = None
    original: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Message':
        """从字典创建消息对象"""
        return cls(
            id=data.get('id', ''),
            type=data.get('type', ''),
            message_type=data.get('message_type', ''),
            sender=Sender.from_dict(data.get('sender', {})),
            content=MessageContent.from_segments(
                data.get('content', []), 
                data.get('raw_content', '')
            ),
            time=data.get('time', datetime.now()),
            self_id=data.get('self_id', 0),
            group_id=data.get('group_id'),
            sub_type=data.get('sub_type', 'normal'),
            anonymous=data.get('anonymous'),
            original=data.get('original', {})
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'id': self.id,
            'type': self.type,
            'message_type': self.message_type,
            'sender': {
                'user_id': self.sender.user_id,
                'nickname': self.sender.nickname,
                'card': self.sender.card,
                'role': self.sender.role,
                'title': self.sender.title,
                'is_admin': self.sender.is_admin
            },
            'content': self.content.to_segments(),
            'raw_content': self.content.raw_content,
            'time': self.time,
            'self_id': self.self_id,
            'group_id': self.group_id,
            'sub_type': self.sub_type,
            'anonymous': self.anonymous
        }
    
    def is_group_message(self) -> bool:
        """是否是群消息"""
        return self.message_type == 'group'
    
    def is_private_message(self) -> bool:
        """是否是私聊消息"""
        return self.message_type == 'private'
    
    def get_plain_text(self) -> str:
        """获取纯文本内容"""
        return self.content.get_plain_text()
    
    def contains_at_me(self, self_id: Optional[int] = None) -> bool:
        """是否@了机器人"""
        target_id = self_id if self_id is not None else self.self_id
        return self.content.contains_at(target_id)
    
    def should_respond(self, self_id: Optional[int] = None) -> bool:
        """是否应该响应"""
        if self.is_private_message():
            return True
        if self.is_group_message():
            return self.contains_at_me(self_id)
        return False
    
    def create_reply(self, content: Union[str, List[MessageSegment], MessageContent]) -> 'Message':
        """创建回复消息"""
        if isinstance(content, str):
            msg_content = MessageContent().add_text(content)
        elif isinstance(content, list):
            msg_content = MessageContent(segments=content)
        else:
            msg_content = content
        
        # 添加回复引用
        if self.id:
            msg_content.segments.insert(0, MessageSegment.reply(self.id))
        
        return Message(
            id='',
            type=self.type,
            message_type=self.message_type,
            sender=Sender(user_id=self.self_id, nickname="机器人"),
            content=msg_content,
            time=datetime.now(),
            self_id=self.self_id,
            group_id=self.group_id if self.is_group_message() else None,
            sub_type='normal'
        ) 
# -*- coding: utf-8 -*-

"""
林镜(LingJing) - 消息数据模型
"""


@dataclass
class Sender:
    """发送者信息"""
    user_id: int
    nickname: str = ""
    card: str = ""
    role: str = ""
    title: str = ""
    is_admin: bool = False
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Sender':
        """从字典创建发送者对象"""
        return cls(
            user_id=data.get('user_id', 0),
            nickname=data.get('nickname', ''),
            card=data.get('card', ''),
            role=data.get('role', ''),
            title=data.get('title', ''),
            is_admin=data.get('is_admin', False)
        )

@dataclass
class MessageSegment:
    """消息段"""
    type: str
    data: Dict[str, str] = field(default_factory=dict)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MessageSegment':
        """从字典创建消息段对象"""
        return cls(
            type=data.get('type', 'text'),
            data=data.get('data', {})
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'type': self.type,
            'data': self.data
        }
    
    @classmethod
    def text(cls, text: str) -> 'MessageSegment':
        """创建文本消息段"""
        return cls(type='text', data={'text': text})
    
    @classmethod
    def image(cls, file: str, url: Optional[str] = None) -> 'MessageSegment':
        """创建图片消息段"""
        data = {'file': file}
        if url:
            data['url'] = url
        return cls(type='image', data=data)
    
    @classmethod
    def at(cls, user_id: Union[int, str]) -> 'MessageSegment':
        """创建@消息段"""
        return cls(type='at', data={'qq': str(user_id)})
    
    @classmethod
    def reply(cls, message_id: Union[int, str]) -> 'MessageSegment':
        """创建回复消息段"""
        return cls(type='reply', data={'id': str(message_id)})

@dataclass
class MessageContent:
    """消息内容"""
    segments: List[MessageSegment] = field(default_factory=list)
    raw_content: str = ""
    
    @classmethod
    def from_segments(cls, segments: List[Dict[str, Any]], raw_content: str = "") -> 'MessageContent':
        """从消息段列表创建消息内容对象"""
        return cls(
            segments=[MessageSegment.from_dict(segment) for segment in segments],
            raw_content=raw_content
        )
    
    def to_segments(self) -> List[Dict[str, Any]]:
        """转换为消息段列表"""
        return [segment.to_dict() for segment in self.segments]
    
    def get_plain_text(self) -> str:
        """获取纯文本内容"""
        return ''.join([
            segment.data.get('text', '') 
            for segment in self.segments 
            if segment.type == 'text'
        ])
    
    def contains_image(self) -> bool:
        """是否包含图片"""
        return any(segment.type == 'image' for segment in self.segments)
    
    def contains_at(self, user_id: Optional[Union[int, str]] = None) -> bool:
        """是否包含@"""
        if user_id is None:
            return any(segment.type == 'at' for segment in self.segments)
        else:
            user_id_str = str(user_id)
            return any(
                segment.type == 'at' and segment.data.get('qq', '') == user_id_str
                for segment in self.segments
            )
    
    def add_segment(self, segment: MessageSegment) -> 'MessageContent':
        """添加消息段"""
        self.segments.append(segment)
        return self
    
    def add_text(self, text: str) -> 'MessageContent':
        """添加文本"""
        self.segments.append(MessageSegment.text(text))
        return self
    
    def add_image(self, file: str, url: Optional[str] = None) -> 'MessageContent':
        """添加图片"""
        self.segments.append(MessageSegment.image(file, url))
        return self
    
    def add_at(self, user_id: Union[int, str]) -> 'MessageContent':
        """添加@"""
        self.segments.append(MessageSegment.at(user_id))
        return self
    
    def add_reply(self, message_id: Union[int, str]) -> 'MessageContent':
        """添加回复"""
        self.segments.append(MessageSegment.reply(message_id))
        return self

@dataclass
class Message:
    """消息"""
    id: str
    type: str
    message_type: str
    sender: Sender
    content: MessageContent
    time: datetime
    self_id: int
    group_id: Optional[int] = None
    sub_type: str = "normal"
    anonymous: Optional[Dict[str, Any]] = None
    original: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Message':
        """从字典创建消息对象"""
        return cls(
            id=data.get('id', ''),
            type=data.get('type', ''),
            message_type=data.get('message_type', ''),
            sender=Sender.from_dict(data.get('sender', {})),
            content=MessageContent.from_segments(
                data.get('content', []), 
                data.get('raw_content', '')
            ),
            time=data.get('time', datetime.now()),
            self_id=data.get('self_id', 0),
            group_id=data.get('group_id'),
            sub_type=data.get('sub_type', 'normal'),
            anonymous=data.get('anonymous'),
            original=data.get('original', {})
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'id': self.id,
            'type': self.type,
            'message_type': self.message_type,
            'sender': {
                'user_id': self.sender.user_id,
                'nickname': self.sender.nickname,
                'card': self.sender.card,
                'role': self.sender.role,
                'title': self.sender.title,
                'is_admin': self.sender.is_admin
            },
            'content': self.content.to_segments(),
            'raw_content': self.content.raw_content,
            'time': self.time,
            'self_id': self.self_id,
            'group_id': self.group_id,
            'sub_type': self.sub_type,
            'anonymous': self.anonymous
        }
    
    def is_group_message(self) -> bool:
        """是否是群消息"""
        return self.message_type == 'group'
    
    def is_private_message(self) -> bool:
        """是否是私聊消息"""
        return self.message_type == 'private'
    
    def get_plain_text(self) -> str:
        """获取纯文本内容"""
        return self.content.get_plain_text()
    
    def contains_at_me(self, self_id: Optional[int] = None) -> bool:
        """是否@了机器人"""
        target_id = self_id if self_id is not None else self.self_id
        return self.content.contains_at(target_id)
    
    def should_respond(self, self_id: Optional[int] = None) -> bool:
        """是否应该响应"""
        if self.is_private_message():
            return True
        if self.is_group_message():
            return self.contains_at_me(self_id)
        return False
    
    def create_reply(self, content: Union[str, List[MessageSegment], MessageContent]) -> 'Message':
        """创建回复消息"""
        if isinstance(content, str):
            msg_content = MessageContent().add_text(content)
        elif isinstance(content, list):
            msg_content = MessageContent(segments=content)
        else:
            msg_content = content
        
        # 添加回复引用
        if self.id:
            msg_content.segments.insert(0, MessageSegment.reply(self.id))
        
        return Message(
            id='',
            type=self.type,
            message_type=self.message_type,
            sender=Sender(user_id=self.self_id, nickname="机器人"),
            content=msg_content,
            time=datetime.now(),
            self_id=self.self_id,
            group_id=self.group_id if self.is_group_message() else None,
            sub_type='normal'
        ) 