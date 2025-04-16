#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
林镜(LingJing) - 消息处理器
"""

import logging
import asyncio
from typing import Dict, Any, Optional, Union, List, Set
from datetime import datetime
import uuid

from ..constants import MessageType, EventType
from ..models.message_models import Message
from ..models import ChatStream
from ..exceptions import MessageProcessError
from ..utils.logger import get_logger
from ..server.message_adapter import MessageAdapter
from .read_air import ReadAirProcessor
from .thought_generator import ThoughtGenerator
from .willingness_checker import WillingnessChecker
from .reply_composer import ReplyComposer

class MessageProcessor:
    """核心消息处理器，协调消息处理流程"""
    
    def __init__(self):
        """初始化消息处理器"""
        self.logger = get_logger('linjing.core.message_processor')
        self.message_adapter = MessageAdapter()
        self.chat_streams: Dict[str, ChatStream] = {}
        self.read_air_processor: Optional[ReadAirProcessor] = None
        self.thought_generator: Optional[ThoughtGenerator] = None
        self.willingness_checker: Optional[WillingnessChecker] = None
        self.reply_composer: Optional[ReplyComposer] = None
        self.onebot_proxy = None  # 将在初始化时设置
    
    async def initialize(self) -> None:
        """初始化处理器和依赖组件"""
        self.logger.info("初始化消息处理器...")
        
        # 创建依赖组件
        self.read_air_processor = ReadAirProcessor()
        await self.read_air_processor.initialize()
        
        self.thought_generator = ThoughtGenerator()
        await self.thought_generator.initialize()
        
        self.willingness_checker = WillingnessChecker()
        await self.willingness_checker.initialize()
        
        self.reply_composer = ReplyComposer()
        await self.reply_composer.initialize()
        
        self.logger.info("消息处理器初始化完成")
    
    def set_onebot_proxy(self, onebot_proxy) -> None:
        """
        设置OneBot代理
        
        Args:
            onebot_proxy: OneBot代理实例
        """
        self.onebot_proxy = onebot_proxy
        self.logger.info("已设置OneBot代理")
    
    async def process_message(self, data: Dict[str, Any]) -> None:
        """
        处理消息
        
        Args:
            data: 消息数据
        """
        try:
            # 转换为内部消息格式
            internal_message = self.message_adapter.convert_to_internal(data)
            
            # 检查是否为消息事件，其他类型事件交给其他处理器
            if internal_message.get('type') != EventType.MESSAGE:
                await self._handle_non_message_event(internal_message)
                return
            
            # 构建消息对象
            message = Message.from_dict(internal_message)
            
            # 根据消息类型分发处理
            if message.is_private_message():
                await self._handle_private_message(message)
            elif message.is_group_message():
                await self._handle_group_message(message)
            else:
                self.logger.warning(f"未知的消息类型: {message.message_type}")
        
        except Exception as e:
            self.logger.error(f"处理消息时发生错误: {e}", exc_info=True)
            raise MessageProcessError(f"处理消息时发生错误: {e}")
    
    async def _handle_private_message(self, message: Message) -> None:
        """
        处理私聊消息
        
        Args:
            message: 消息对象
        """
        self.logger.debug(f"处理私聊消息: {message.id}")
        
        # 获取或创建聊天流
        chat_stream_id = f"private_{message.sender.user_id}"
        chat_stream = self._get_or_create_chat_stream(chat_stream_id)
        
        # 添加消息到聊天流
        chat_stream.add_message(message)
        
        # 消息处理流程
        await self._process_message_flow(message, chat_stream)
    
    async def _handle_group_message(self, message: Message) -> None:
        """
        处理群聊消息
        
        Args:
            message: 消息对象
        """
        self.logger.debug(f"处理群聊消息: {message.id}")
        
        # 获取或创建聊天流
        chat_stream_id = f"group_{message.group_id}"
        chat_stream = self._get_or_create_chat_stream(chat_stream_id)
        
        # 添加消息到聊天流
        chat_stream.add_message(message)
        
        # 消息处理流程
        await self._process_message_flow(message, chat_stream)
    
    async def _handle_non_message_event(self, event: Dict[str, Any]) -> None:
        """
        处理非消息事件
        
        Args:
            event: 事件数据
        """
        event_type = event.get('type')
        
        if event_type == EventType.NOTICE:
            await self._handle_notice_event(event)
        elif event_type == EventType.REQUEST:
            await self._handle_request_event(event)
        elif event_type == EventType.META:
            await self._handle_meta_event(event)
        else:
            self.logger.debug(f"未处理的事件类型: {event_type}")
    
    async def _handle_notice_event(self, event: Dict[str, Any]) -> None:
        """
        处理通知事件
        
        Args:
            event: 通知事件数据
        """
        notice_type = event.get('notice_type')
        self.logger.debug(f"处理通知事件: {notice_type}")
        
        # TODO: 实现通知事件处理逻辑
        pass
    
    async def _handle_request_event(self, event: Dict[str, Any]) -> None:
        """
        处理请求事件
        
        Args:
            event: 请求事件数据
        """
        request_type = event.get('request_type')
        self.logger.debug(f"处理请求事件: {request_type}")
        
        # TODO: 实现请求事件处理逻辑
        pass
    
    async def _handle_meta_event(self, event: Dict[str, Any]) -> None:
        """
        处理元事件
        
        Args:
            event: 元事件数据
        """
        meta_event_type = event.get('meta_event_type')
        self.logger.debug(f"处理元事件: {meta_event_type}")
        
        # TODO: 实现元事件处理逻辑
        pass
    
    async def _process_message_flow(self, message: Message, chat_stream: ChatStream) -> None:
        """
        消息处理流程
        
        Args:
            message: 消息对象
            chat_stream: 聊天流
        """
        try:
            # 1. 读空气分析
            should_reply = await self.read_air_processor.process(message, chat_stream)
            
            if not should_reply:
                self.logger.debug(f"读空气决定不回复消息: {message.id}")
                return
            
            # 2. 生成内心想法
            inner_thought = await self.thought_generator.generate_thought(
                "如何回应这条消息", message, chat_stream
            )
            
            # 3. 检查表达意愿
            should_express = await self.willingness_checker.should_express(inner_thought, message)
            
            if not should_express:
                self.logger.debug(f"决定不表达想法: {message.id}")
                return
            
            # 4. 生成回复内容
            reply_message = await self.reply_composer.compose_reply(inner_thought, message, chat_stream)
            
            # 5. 发送回复消息
            if reply_message and self.onebot_proxy:
                await self._send_reply(reply_message)
            
        except Exception as e:
            self.logger.error(f"消息处理流程发生错误: {e}", exc_info=True)
    
    async def _send_reply(self, reply_message: Message) -> None:
        """
        发送回复消息
        
        Args:
            reply_message: 回复消息对象
        """
        if not self.onebot_proxy:
            self.logger.error("无法发送回复: OneBot代理未设置")
            return
        
        try:
            # 将消息转换为OneBot格式
            onebot_message = self.message_adapter.convert_to_external(reply_message)
            
            # 根据消息类型发送
            if reply_message.is_private_message():
                await self.onebot_proxy.send_private_message(
                    user_id=reply_message.sender.user_id,
                    message=onebot_message
                )
            elif reply_message.is_group_message():
                await self.onebot_proxy.send_group_message(
                    group_id=reply_message.group_id,
                    message=onebot_message
                )
            
            self.logger.debug(f"已发送回复消息")
        except Exception as e:
            self.logger.error(f"发送回复消息时发生错误: {e}", exc_info=True)
    
    def _get_or_create_chat_stream(self, chat_stream_id: str) -> ChatStream:
        """
        获取或创建聊天流
        
        Args:
            chat_stream_id: 聊天流ID
            
        Returns:
            聊天流对象
        """
        # 检查是否存在
        if chat_stream_id in self.chat_streams:
            chat_stream = self.chat_streams[chat_stream_id]
            # 检查是否过期
            if chat_stream.is_expired():
                self.logger.debug(f"聊天流已过期，重新创建: {chat_stream_id}")
                chat_stream = ChatStream()
                self.chat_streams[chat_stream_id] = chat_stream
            return chat_stream
        
        # 创建新的聊天流
        chat_stream = ChatStream()
        self.chat_streams[chat_stream_id] = chat_stream
        self.logger.debug(f"已创建新的聊天流: {chat_stream_id}")
        return chat_stream
    
    def _clear_expired_chat_streams(self) -> None:
        """清理过期的聊天流"""
        expired_ids = []
        
        for chat_id, chat_stream in self.chat_streams.items():
            if chat_stream.is_expired():
                expired_ids.append(chat_id)
        
        for chat_id in expired_ids:
            del self.chat_streams[chat_id]
        
        if expired_ids:
            self.logger.debug(f"已清理 {len(expired_ids)} 个过期聊天流")
    
    def get_chat_stream(self, chat_stream_id: str) -> Optional[ChatStream]:
        """
        获取聊天流
        
        Args:
            chat_stream_id: 聊天流ID
            
        Returns:
            聊天流对象，如果不存在则返回None
        """
        return self.chat_streams.get(chat_stream_id) 