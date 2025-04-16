#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
林镜(LingJing) - 读空气处理器
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional, Tuple, Union
from datetime import datetime, timedelta

from ..constants import SocialIntent
from ..models.message_models import Message
from ..models.chat_stream import ChatStream
from ..utils.logger import get_logger
from ..llm.llm_interface import LLMInterface

class ReadAirProcessor:
    """读空气处理器，分析社交语境，决定是否回复"""
    
    def __init__(self):
        """初始化读空气处理器"""
        self.logger = get_logger('linjing.core.read_air')
        self.llm_interface = None
        self.context_window = 10  # 上下文窗口大小
        self.cooldown_period = 60  # 冷却时间（秒）
        self.default_reply_threshold = 0.6  # 默认回复阈值
        self.at_reply_threshold = 0.3  # 被@时的回复阈值
        self.last_reply_time = {}  # 记录最后回复时间，格式: {chat_stream_id: timestamp}
    
    async def initialize(self) -> None:
        """初始化处理器"""
        self.logger.info("初始化读空气处理器...")
        # 导入LLM接口
        from ..llm.llm_interface import get_llm_interface
        self.llm_interface = await get_llm_interface()
        self.logger.info("读空气处理器初始化完成")
    
    async def process(self, message: Message, chat_stream: ChatStream) -> bool:
        """
        处理消息并判断是否需要回复
        
        Args:
            message: 消息对象
            chat_stream: 聊天流
            
        Returns:
            是否应该回复
        """
        # 如果消息是机器人自己发的，不回复
        if message.sender.user_id == message.self_id:
            return False
        
        # 检查冷却时间
        chat_id = f"{message.message_type}_{message.group_id if message.is_group_message() else message.sender.user_id}"
        if not self._check_cooldown(chat_id):
            self.logger.debug(f"冷却期内，暂不回复: {chat_id}")
            return False
        
        # 私聊消息总是回复
        if message.is_private_message():
            self._update_last_reply_time(chat_id)
            return True
        
        # 如果被@，几乎总是回复
        if message.contains_at_me():
            social_intent = await self._analyze_social_intent(message, chat_stream)
            should_reply = self._should_reply_when_at(social_intent)
            if should_reply:
                self._update_last_reply_time(chat_id)
            return should_reply
        
        # 构建社交上下文
        context = await self._build_context(message, chat_stream)
        
        # 分析社交意图
        social_intent = await self._analyze_social_intent(message, chat_stream, context)
        
        # 决定是否应该回复
        should_reply = await self._should_reply(social_intent, message, chat_stream)
        
        if should_reply:
            self._update_last_reply_time(chat_id)
        
        return should_reply
    
    async def _build_context(self, message: Message, chat_stream: ChatStream) -> Dict[str, Any]:
        """
        构建社交上下文
        
        Args:
            message: 当前消息
            chat_stream: 聊天流
            
        Returns:
            社交上下文字典
        """
        # 获取最近的消息
        recent_messages = chat_stream.get_messages(self.context_window)
        
        # 提取消息内容、发送者和时间
        context_messages = []
        for msg in recent_messages:
            context_messages.append({
                'id': msg.id,
                'sender_id': msg.sender.user_id,
                'sender_name': msg.sender.nickname or f"User{msg.sender.user_id}",
                'content': msg.get_plain_text(),
                'timestamp': msg.time.isoformat(),
                'is_bot': msg.sender.user_id == message.self_id
            })
        
        # 构建上下文
        context = {
            'messages': context_messages,
            'current_message': {
                'id': message.id,
                'content': message.get_plain_text(),
                'sender_id': message.sender.user_id,
                'sender_name': message.sender.nickname or f"User{message.sender.user_id}",
                'timestamp': message.time.isoformat()
            },
            'chat_type': message.message_type,
            'bot_id': message.self_id,
            'contains_at_me': message.contains_at_me(),
            'group_id': message.group_id if message.is_group_message() else None
        }
        
        return context
    
    async def _analyze_social_intent(self, message: Message, chat_stream: ChatStream, 
                               context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        分析社交意图
        
        Args:
            message: 消息对象
            chat_stream: 聊天流
            context: 社交上下文，如果为None则自动构建
            
        Returns:
            社交意图分析结果
        """
        if context is None:
            context = await self._build_context(message, chat_stream)
        
        # 检查缓存
        cached_intent = chat_stream.get_context(f"social_intent_{message.id}")
        if cached_intent:
            return cached_intent
        
        # 构建提示词
        prompt = self._build_social_intent_prompt(context)
        
        # 调用LLM
        try:
            response = await self.llm_interface.chat_completion(
                prompt=prompt,
                model="gpt-3.5-turbo",  # 可从配置中获取
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            # 解析结果
            intent_analysis = self.llm_interface.parse_json_response(response)
            
            # 缓存结果
            chat_stream.set_context(f"social_intent_{message.id}", intent_analysis)
            
            return intent_analysis
        except Exception as e:
            self.logger.error(f"分析社交意图时发生错误: {e}", exc_info=True)
            # 返回默认值
            return {
                "intent_type": SocialIntent.IRRELEVANT,
                "is_target_bot": False,
                "should_reply": False,
                "confidence": 0.2,
                "reasoning": "发生错误，无法分析社交意图"
            }
    
    def _build_social_intent_prompt(self, context: Dict[str, Any]) -> str:
        """
        构建社交意图分析提示词
        
        Args:
            context: 社交上下文
            
        Returns:
            提示词
        """
        messages = []
        
        # 系统提示词
        system_prompt = """
你是一个社交意图分析专家，你的任务是分析一段对话中最新消息的社交意图。
请分析最新消息：
1. 属于哪种社交意图类型（问题、陈述、指令、表达情感、承诺、问候、感谢、道歉、告别、提及机器人、@机器人或无关信息）
2. 这条消息是否针对机器人
3. 机器人是否应该回复这条消息
4. 你对分析结果的置信度（0-1之间的数字）
5. 简短解释你的分析理由

请严格按照以下JSON格式输出：
{
  "intent_type": "question|statement|directive|expressives|commissives|greetings|thanks|apology|farewell|mention|at|irrelevant",
  "is_target_bot": true|false,
  "should_reply": true|false,
  "confidence": 0.0-1.0,
  "reasoning": "简短解释"
}
        """
        messages.append({"role": "system", "content": system_prompt})
        
        # 用户提示词
        user_prompt = "以下是一段聊天上下文，请分析最新消息：\n\n"
        
        # 添加聊天上下文
        if context['messages']:
            user_prompt += "聊天历史：\n"
            for msg in context['messages']:
                sender = f"机器人(ID:{msg['sender_id']})" if msg['is_bot'] else f"{msg['sender_name']}(ID:{msg['sender_id']})"
                user_prompt += f"{sender}: {msg['content']}\n"
            user_prompt += "\n"
        
        # 添加当前消息
        sender = f"{context['current_message']['sender_name']}(ID:{context['current_message']['sender_id']})"
        user_prompt += f"最新消息 -> {sender}: {context['current_message']['content']}\n\n"
        
        # 添加其他上下文信息
        user_prompt += f"聊天类型: {'私聊' if context['chat_type'] == 'private' else '群聊'}\n"
        user_prompt += f"机器人ID: {context['bot_id']}\n"
        if context['chat_type'] == 'group':
            user_prompt += f"群ID: {context['group_id']}\n"
        user_prompt += f"是否@了机器人: {'是' if context['contains_at_me'] else '否'}\n"
        
        user_prompt += "\n请根据以上信息分析最新消息的社交意图，并按指定JSON格式输出。"
        
        messages.append({"role": "user", "content": user_prompt})
        
        return messages
    
    async def _should_reply(self, social_intent: Dict[str, Any], message: Message, 
                     chat_stream: ChatStream) -> bool:
        """
        决定是否应该回复
        
        Args:
            social_intent: 社交意图分析结果
            message: 消息对象
            chat_stream: 聊天流
            
        Returns:
            是否应该回复
        """
        # 如果LLM明确建议回复
        if social_intent.get("should_reply", False) and social_intent.get("confidence", 0) >= self.default_reply_threshold:
            return True
        
        # 如果是针对机器人的消息
        if social_intent.get("is_target_bot", False) and social_intent.get("confidence", 0) >= 0.5:
            return True
        
        # 以下社交意图类型更可能需要回复
        high_response_intents = [
            SocialIntent.QUESTION,
            SocialIntent.GREETINGS,
            SocialIntent.THANKS,
            SocialIntent.APOLOGY,
            SocialIntent.FAREWELL,
            SocialIntent.MENTION,
            SocialIntent.AT
        ]
        
        intent_type = social_intent.get("intent_type", SocialIntent.IRRELEVANT)
        if intent_type in high_response_intents and social_intent.get("confidence", 0) >= 0.4:
            return True
        
        # 私聊中的指令类型消息
        if message.is_private_message() and intent_type == SocialIntent.DIRECTIVE:
            return True
        
        # 根据上下文判断是否是对话延续
        is_conversation_continuation = await self._is_conversation_continuation(message, chat_stream)
        if is_conversation_continuation:
            return True
        
        # 默认不回复
        return False
    
    def _should_reply_when_at(self, social_intent: Dict[str, Any]) -> bool:
        """
        当被@时决定是否应该回复
        
        Args:
            social_intent: 社交意图分析结果
            
        Returns:
            是否应该回复
        """
        # 被@时，几乎总是回复，除非:
        # 1. 分析结果明确表示不应该回复
        # 2. 置信度高
        # 3. 意图类型是无关信息
        if (not social_intent.get("should_reply", True) and 
            social_intent.get("confidence", 0) > 0.8 and 
            social_intent.get("intent_type") == SocialIntent.IRRELEVANT):
            return False
        
        # 大多数情况下回复
        return True
    
    async def _is_conversation_continuation(self, message: Message, chat_stream: ChatStream) -> bool:
        """
        判断当前消息是否是对话的延续
        
        Args:
            message: 消息对象
            chat_stream: 聊天流
            
        Returns:
            是否是对话延续
        """
        # 获取最近的消息
        recent_messages = chat_stream.get_messages(5)  # 只看最近5条
        
        # 如果不足2条消息，不算是延续
        if len(recent_messages) < 2:
            return False
        
        # 检查是否有机器人最近的发言
        bot_messages = [msg for msg in recent_messages if msg.sender.user_id == message.self_id]
        if not bot_messages:
            return False
        
        # 最近的机器人消息
        last_bot_message = bot_messages[-1]
        
        # 如果机器人最后一次发言是最新的第二条消息，当前消息可能是对话延续
        if recent_messages[-2].id == last_bot_message.id:
            # 时间间隔不超过5分钟
            time_diff = (message.time - last_bot_message.time).total_seconds()
            if time_diff <= 300:  # 5分钟内
                return True
        
        return False
    
    def _check_cooldown(self, chat_id: str) -> bool:
        """
        检查冷却时间
        
        Args:
            chat_id: 聊天ID
            
        Returns:
            是否已过冷却期
        """
        if chat_id not in self.last_reply_time:
            return True
        
        last_time = self.last_reply_time[chat_id]
        now = datetime.now()
        
        # 检查是否已过冷却期
        return (now - last_time).total_seconds() >= self.cooldown_period
    
    def _update_last_reply_time(self, chat_id: str) -> None:
        """
        更新最后回复时间
        
        Args:
            chat_id: 聊天ID
        """
        self.last_reply_time[chat_id] = datetime.now() 
# -*- coding: utf-8 -*-

"""
林镜(LingJing) - 读空气处理器
"""



class ReadAirProcessor:
    """读空气处理器，分析社交语境，决定是否回复"""
    
    def __init__(self):
        """初始化读空气处理器"""
        self.logger = get_logger('linjing.core.read_air')
        self.llm_interface = None
        self.context_window = 10  # 上下文窗口大小
        self.cooldown_period = 60  # 冷却时间（秒）
        self.default_reply_threshold = 0.6  # 默认回复阈值
        self.at_reply_threshold = 0.3  # 被@时的回复阈值
        self.last_reply_time = {}  # 记录最后回复时间，格式: {chat_stream_id: timestamp}
    
    async def initialize(self) -> None:
        """初始化处理器"""
        self.logger.info("初始化读空气处理器...")
        # 导入LLM接口
        from ..llm.llm_interface import get_llm_interface
        self.llm_interface = await get_llm_interface()
        self.logger.info("读空气处理器初始化完成")
    
    async def process(self, message: Message, chat_stream: ChatStream) -> bool:
        """
        处理消息并判断是否需要回复
        
        Args:
            message: 消息对象
            chat_stream: 聊天流
            
        Returns:
            是否应该回复
        """
        # 如果消息是机器人自己发的，不回复
        if message.sender.user_id == message.self_id:
            return False
        
        # 检查冷却时间
        chat_id = f"{message.message_type}_{message.group_id if message.is_group_message() else message.sender.user_id}"
        if not self._check_cooldown(chat_id):
            self.logger.debug(f"冷却期内，暂不回复: {chat_id}")
            return False
        
        # 私聊消息总是回复
        if message.is_private_message():
            self._update_last_reply_time(chat_id)
            return True
        
        # 如果被@，几乎总是回复
        if message.contains_at_me():
            social_intent = await self._analyze_social_intent(message, chat_stream)
            should_reply = self._should_reply_when_at(social_intent)
            if should_reply:
                self._update_last_reply_time(chat_id)
            return should_reply
        
        # 构建社交上下文
        context = await self._build_context(message, chat_stream)
        
        # 分析社交意图
        social_intent = await self._analyze_social_intent(message, chat_stream, context)
        
        # 决定是否应该回复
        should_reply = await self._should_reply(social_intent, message, chat_stream)
        
        if should_reply:
            self._update_last_reply_time(chat_id)
        
        return should_reply
    
    async def _build_context(self, message: Message, chat_stream: ChatStream) -> Dict[str, Any]:
        """
        构建社交上下文
        
        Args:
            message: 当前消息
            chat_stream: 聊天流
            
        Returns:
            社交上下文字典
        """
        # 获取最近的消息
        recent_messages = chat_stream.get_messages(self.context_window)
        
        # 提取消息内容、发送者和时间
        context_messages = []
        for msg in recent_messages:
            context_messages.append({
                'id': msg.id,
                'sender_id': msg.sender.user_id,
                'sender_name': msg.sender.nickname or f"User{msg.sender.user_id}",
                'content': msg.get_plain_text(),
                'timestamp': msg.time.isoformat(),
                'is_bot': msg.sender.user_id == message.self_id
            })
        
        # 构建上下文
        context = {
            'messages': context_messages,
            'current_message': {
                'id': message.id,
                'content': message.get_plain_text(),
                'sender_id': message.sender.user_id,
                'sender_name': message.sender.nickname or f"User{message.sender.user_id}",
                'timestamp': message.time.isoformat()
            },
            'chat_type': message.message_type,
            'bot_id': message.self_id,
            'contains_at_me': message.contains_at_me(),
            'group_id': message.group_id if message.is_group_message() else None
        }
        
        return context
    
    async def _analyze_social_intent(self, message: Message, chat_stream: ChatStream, 
                               context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        分析社交意图
        
        Args:
            message: 消息对象
            chat_stream: 聊天流
            context: 社交上下文，如果为None则自动构建
            
        Returns:
            社交意图分析结果
        """
        if context is None:
            context = await self._build_context(message, chat_stream)
        
        # 检查缓存
        cached_intent = chat_stream.get_context(f"social_intent_{message.id}")
        if cached_intent:
            return cached_intent
        
        # 构建提示词
        prompt = self._build_social_intent_prompt(context)
        
        # 调用LLM
        try:
            response = await self.llm_interface.chat_completion(
                prompt=prompt,
                model="gpt-3.5-turbo",  # 可从配置中获取
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            # 解析结果
            intent_analysis = self.llm_interface.parse_json_response(response)
            
            # 缓存结果
            chat_stream.set_context(f"social_intent_{message.id}", intent_analysis)
            
            return intent_analysis
        except Exception as e:
            self.logger.error(f"分析社交意图时发生错误: {e}", exc_info=True)
            # 返回默认值
            return {
                "intent_type": SocialIntent.IRRELEVANT,
                "is_target_bot": False,
                "should_reply": False,
                "confidence": 0.2,
                "reasoning": "发生错误，无法分析社交意图"
            }
    
    def _build_social_intent_prompt(self, context: Dict[str, Any]) -> str:
        """
        构建社交意图分析提示词
        
        Args:
            context: 社交上下文
            
        Returns:
            提示词
        """
        messages = []
        
        # 系统提示词
        system_prompt = """
你是一个社交意图分析专家，你的任务是分析一段对话中最新消息的社交意图。
请分析最新消息：
1. 属于哪种社交意图类型（问题、陈述、指令、表达情感、承诺、问候、感谢、道歉、告别、提及机器人、@机器人或无关信息）
2. 这条消息是否针对机器人
3. 机器人是否应该回复这条消息
4. 你对分析结果的置信度（0-1之间的数字）
5. 简短解释你的分析理由

请严格按照以下JSON格式输出：
{
  "intent_type": "question|statement|directive|expressives|commissives|greetings|thanks|apology|farewell|mention|at|irrelevant",
  "is_target_bot": true|false,
  "should_reply": true|false,
  "confidence": 0.0-1.0,
  "reasoning": "简短解释"
}
        """
        messages.append({"role": "system", "content": system_prompt})
        
        # 用户提示词
        user_prompt = "以下是一段聊天上下文，请分析最新消息：\n\n"
        
        # 添加聊天上下文
        if context['messages']:
            user_prompt += "聊天历史：\n"
            for msg in context['messages']:
                sender = f"机器人(ID:{msg['sender_id']})" if msg['is_bot'] else f"{msg['sender_name']}(ID:{msg['sender_id']})"
                user_prompt += f"{sender}: {msg['content']}\n"
            user_prompt += "\n"
        
        # 添加当前消息
        sender = f"{context['current_message']['sender_name']}(ID:{context['current_message']['sender_id']})"
        user_prompt += f"最新消息 -> {sender}: {context['current_message']['content']}\n\n"
        
        # 添加其他上下文信息
        user_prompt += f"聊天类型: {'私聊' if context['chat_type'] == 'private' else '群聊'}\n"
        user_prompt += f"机器人ID: {context['bot_id']}\n"
        if context['chat_type'] == 'group':
            user_prompt += f"群ID: {context['group_id']}\n"
        user_prompt += f"是否@了机器人: {'是' if context['contains_at_me'] else '否'}\n"
        
        user_prompt += "\n请根据以上信息分析最新消息的社交意图，并按指定JSON格式输出。"
        
        messages.append({"role": "user", "content": user_prompt})
        
        return messages
    
    async def _should_reply(self, social_intent: Dict[str, Any], message: Message, 
                     chat_stream: ChatStream) -> bool:
        """
        决定是否应该回复
        
        Args:
            social_intent: 社交意图分析结果
            message: 消息对象
            chat_stream: 聊天流
            
        Returns:
            是否应该回复
        """
        # 如果LLM明确建议回复
        if social_intent.get("should_reply", False) and social_intent.get("confidence", 0) >= self.default_reply_threshold:
            return True
        
        # 如果是针对机器人的消息
        if social_intent.get("is_target_bot", False) and social_intent.get("confidence", 0) >= 0.5:
            return True
        
        # 以下社交意图类型更可能需要回复
        high_response_intents = [
            SocialIntent.QUESTION,
            SocialIntent.GREETINGS,
            SocialIntent.THANKS,
            SocialIntent.APOLOGY,
            SocialIntent.FAREWELL,
            SocialIntent.MENTION,
            SocialIntent.AT
        ]
        
        intent_type = social_intent.get("intent_type", SocialIntent.IRRELEVANT)
        if intent_type in high_response_intents and social_intent.get("confidence", 0) >= 0.4:
            return True
        
        # 私聊中的指令类型消息
        if message.is_private_message() and intent_type == SocialIntent.DIRECTIVE:
            return True
        
        # 根据上下文判断是否是对话延续
        is_conversation_continuation = await self._is_conversation_continuation(message, chat_stream)
        if is_conversation_continuation:
            return True
        
        # 默认不回复
        return False
    
    def _should_reply_when_at(self, social_intent: Dict[str, Any]) -> bool:
        """
        当被@时决定是否应该回复
        
        Args:
            social_intent: 社交意图分析结果
            
        Returns:
            是否应该回复
        """
        # 被@时，几乎总是回复，除非:
        # 1. 分析结果明确表示不应该回复
        # 2. 置信度高
        # 3. 意图类型是无关信息
        if (not social_intent.get("should_reply", True) and 
            social_intent.get("confidence", 0) > 0.8 and 
            social_intent.get("intent_type") == SocialIntent.IRRELEVANT):
            return False
        
        # 大多数情况下回复
        return True
    
    async def _is_conversation_continuation(self, message: Message, chat_stream: ChatStream) -> bool:
        """
        判断当前消息是否是对话的延续
        
        Args:
            message: 消息对象
            chat_stream: 聊天流
            
        Returns:
            是否是对话延续
        """
        # 获取最近的消息
        recent_messages = chat_stream.get_messages(5)  # 只看最近5条
        
        # 如果不足2条消息，不算是延续
        if len(recent_messages) < 2:
            return False
        
        # 检查是否有机器人最近的发言
        bot_messages = [msg for msg in recent_messages if msg.sender.user_id == message.self_id]
        if not bot_messages:
            return False
        
        # 最近的机器人消息
        last_bot_message = bot_messages[-1]
        
        # 如果机器人最后一次发言是最新的第二条消息，当前消息可能是对话延续
        if recent_messages[-2].id == last_bot_message.id:
            # 时间间隔不超过5分钟
            time_diff = (message.time - last_bot_message.time).total_seconds()
            if time_diff <= 300:  # 5分钟内
                return True
        
        return False
    
    def _check_cooldown(self, chat_id: str) -> bool:
        """
        检查冷却时间
        
        Args:
            chat_id: 聊天ID
            
        Returns:
            是否已过冷却期
        """
        if chat_id not in self.last_reply_time:
            return True
        
        last_time = self.last_reply_time[chat_id]
        now = datetime.now()
        
        # 检查是否已过冷却期
        return (now - last_time).total_seconds() >= self.cooldown_period
    
    def _update_last_reply_time(self, chat_id: str) -> None:
        """
        更新最后回复时间
        
        Args:
            chat_id: 聊天ID
        """
        self.last_reply_time[chat_id] = datetime.now() 