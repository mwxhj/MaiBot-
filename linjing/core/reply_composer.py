#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
林镜(LingJing) - 回复生成器
负责根据机器人的思考过程生成实际的回复内容
"""

import asyncio
import logging
import random
import time
from typing import Dict, List, Optional, Any, Union, Tuple
from ..utils.singleton import singleton
from ..utils.logger import get_logger

from linjing.models.chat_stream import ChatStream, Message
from linjing.models.thought import Thought
from linjing.utils.singleton import singleton
from linjing.llm.llm_interface import get_llm_interface
from linjing.emotion.emotion_manager import get_emotion_manager
from linjing.memory.memory_manager import get_memory_manager
from linjing.models.relationship_models import Relationship
from linjing.models.message_models import Message, MessageContent

logger = get_logger('linjing.core.reply_composer')

@singleton
class ReplyComposer:
    """
    回复生成器，负责根据机器人的思考过程生成实际的回复内容
    基于思考内容、情感状态和回应意愿，生成自然、人格化的回复
    """

    def __init__(self):
        """初始化回复生成器"""
        self.llm_interface = None
        self.emotion_manager = None
        self.memory_manager = None
        self.reply_templates = {
            "friendly": [
                "我觉得{}",
                "{}呢~",
                "{}哦！",
                "{}呀~",
                "{}啊，我很喜欢！"
            ],
            "neutral": [
                "{}。",
                "我想{}",
                "{}吧。",
                "{}。",
                "{}呢。"
            ],
            "reserved": [
                "可能{}吧...",
                "也许{}？",
                "{}，但我不太确定...",
                "{}，不过这只是我的看法...",
                "{}..."
            ]
        }
        self.lock = asyncio.Lock()
        logger.info("回复生成器初始化完成")

    async def initialize(self):
        """初始化回复生成器组件"""
        logger.info("正在初始化回复生成器...")
        self.llm_interface = get_llm_interface()
        self.emotion_manager = get_emotion_manager()
        self.memory_manager = get_memory_manager()
        logger.info("回复生成器初始化完成")

    async def compose_reply(
        self,
        thought: Thought,
        willingness_result: Dict[str, Any],
        chat_stream: ChatStream,
        original_message: Message
    ) -> Optional[str]:
        """
        根据思考内容生成回复
        
        Args:
            thought: 思考内容
            willingness_result: 意愿检查结果
            chat_stream: 聊天流对象
            original_message: 原始消息
            
        Returns:
            生成的回复文本，如果不回复则返回None
        """
        # 如果不愿意回复，直接返回None
        if not willingness_result.get("will_respond", True):
            logger.info("根据意愿检查结果，选择不回复")
            return None
        
        async with self.lock:
            # 获取回应态度
            attitude = willingness_result.get("attitude", "neutral")
            
            # 获取与发送者的关系
            relationship = await self._get_relationship(original_message.sender_id)
            
            # 获取当前情绪状态
            emotional_state = await self.emotion_manager.get_current_emotion()
            
            # 生成回复内容
            try:
                # 如果是简单回复，使用模板生成
                if self._is_simple_reply(thought, original_message):
                    reply_text = await self._generate_simple_reply(
                        thought, 
                        attitude, 
                        emotional_state
                    )
                else:
                    # 否则使用LLM生成更复杂的回复
                    reply_text = await self._generate_complex_reply(
                        thought, 
                        attitude, 
                        emotional_state, 
                        relationship,
                        chat_stream, 
                        original_message
                    )
                
                # 添加情绪表达（如表情符号）
                reply_text = await self._add_emotional_expression(
                    reply_text, 
                    emotional_state, 
                    attitude
                )
                
                # 记录回复到记忆系统
                await self._record_reply(reply_text, thought, original_message)
                
                return reply_text
            
            except Exception as e:
                logger.error(f"生成回复时出错: {e}")
                # 回退到简单回复
                return await self._generate_fallback_reply(attitude)

    async def _generate_simple_reply(
        self,
        thought: Thought,
        attitude: str,
        emotional_state: Dict[str, Any]
    ) -> str:
        """
        生成简单回复
        
        Args:
            thought: 思考内容
            attitude: 回应态度
            emotional_state: 情绪状态
            
        Returns:
            生成的简单回复文本
        """
        # 获取回应计划
        response_plan = thought.response_plan
        
        # 选择对应态度的模板
        templates = self.reply_templates.get(attitude, self.reply_templates["neutral"])
        template = random.choice(templates)
        
        # 根据回应计划获取回复内容
        content = ""
        
        if "key_points" in response_plan and response_plan["key_points"]:
            key_point = random.choice(response_plan["key_points"])
            content = key_point
        else:
            # 根据意图生成简单回复
            intent = thought.understanding.get("intent", "statement")
            
            if intent == "greeting":
                greetings = ["你好", "嗨", "你好啊", "哈喽", "嘿"]
                content = random.choice(greetings)
            elif intent == "question":
                content = "我需要思考一下这个问题"
            elif intent == "gratitude":
                content = "不客气，很高兴能帮到你"
            else:
                content = "我明白了"
        
        # 应用模板
        try:
            reply = template.format(content)
        except Exception:
            # 如果格式化失败，直接返回内容
            reply = content
        
        return reply

    async def _generate_complex_reply(
        self,
        thought: Thought,
        attitude: str,
        emotional_state: Dict[str, Any],
        relationship: Optional[Relationship],
        chat_stream: ChatStream,
        original_message: Message
    ) -> str:
        """
        生成复杂回复
        
        Args:
            thought: 思考内容
            attitude: 回应态度
            emotional_state: 情绪状态
            relationship: 与发送者的关系
            chat_stream: 聊天流对象
            original_message: 原始消息
            
        Returns:
            生成的复杂回复文本
        """
        # 构建回复生成提示
        context = self._extract_context(chat_stream, original_message)
        prompt = self._build_reply_prompt(
            thought, 
            attitude, 
            emotional_state, 
            relationship,
            context
        )
        
        # 生成回复
        reply_text = await self.llm_interface.generate_reply(prompt)
        
        # 如果回复为空或过长，回退到简单回复
        if not reply_text or len(reply_text) > 500:
            logger.warning(f"生成的回复无效或过长: {reply_text[:50]}...")
            return await self._generate_simple_reply(thought, attitude, emotional_state)
        
        return reply_text

    async def _add_emotional_expression(
        self,
        reply_text: str,
        emotional_state: Dict[str, Any],
        attitude: str
    ) -> str:
        """
        向回复添加情绪表达（如表情符号）
        
        Args:
            reply_text: 回复文本
            emotional_state: 情绪状态
            attitude: 回应态度
            
        Returns:
            添加情绪表达后的回复文本
        """
        # 获取当前主导情绪和强度
        emotion = emotional_state.get("emotion", "neutral")
        intensity = emotional_state.get("intensity", 0.5)
        
        # 根据情绪和态度选择是否添加表情
        should_add_emoji = random.random() < 0.7  # 70%的概率添加表情
        
        if attitude == "friendly":
            should_add_emoji = random.random() < 0.9  # 友好态度更可能添加表情
        elif attitude == "reserved":
            should_add_emoji = random.random() < 0.3  # 保守态度较少添加表情
        
        # 如果情绪强度较低，减少表情使用
        if intensity < 0.3:
            should_add_emoji = should_add_emoji and random.random() < 0.5
        
        if not should_add_emoji:
            return reply_text
        
        # 情绪对应的表情映射
        emotion_emojis = {
            "joy": ["😊", "😄", "😁", "🥰", "😍"],
            "sadness": ["😔", "😢", "🥺", "😞", "😟"],
            "anger": ["😠", "😡", "😤", "😒", "🙄"],
            "fear": ["😨", "😰", "😱", "😳", "🤭"],
            "surprise": ["😮", "😲", "😯", "🤔", "🙀"],
            "disgust": ["😖", "🤢", "😫", "😣", "😑"],
            "trust": ["👍", "🤝", "🥰", "☺️", "🌟"],
            "anticipation": ["🤩", "🌈", "✨", "🌻", "🎵"],
            "neutral": ["😐", "🙂", "🤔", "👋", "💭"]
        }
        
        # 根据情绪选择表情
        emojis = emotion_emojis.get(emotion, emotion_emojis["neutral"])
        
        # 选择1-2个表情
        num_emojis = 1 if random.random() < 0.7 else 2
        selected_emojis = random.sample(emojis, min(num_emojis, len(emojis)))
        
        # 将表情添加到回复末尾
        emoji_str = " " + "".join(selected_emojis)
        
        # 检查回复是否已有标点符号结尾
        if reply_text and reply_text[-1] in "。，！？,.!?":
            return reply_text + emoji_str
        else:
            return reply_text + "。" + emoji_str

    async def _record_reply(
        self,
        reply_text: str,
        thought: Thought,
        original_message: Message
    ) -> None:
        """
        记录回复到记忆系统
        
        Args:
            reply_text: 回复文本
            thought: 思考内容
            original_message: 原始消息
        """
        try:
            if self.memory_manager:
                # 创建回复记录
                reply_record = {
                    "timestamp": time.time(),
                    "original_message_id": original_message.message_id,
                    "reply_content": reply_text,
                    "thought_id": thought.message_id if hasattr(thought, 'message_id') else None,
                    "sender_id": original_message.sender_id
                }
                
                # 存储到记忆系统
                await self.memory_manager.record_reply(reply_record)
                
                # 更新关系（如果有发送者ID）
                if hasattr(original_message, 'sender_id') and original_message.sender_id:
                    # 更新与用户的关系
                    interaction_data = {
                        "timestamp": time.time(),
                        "type": "reply",
                        "sentiment": "positive" if "😊" in reply_text or "😄" in reply_text else "neutral",
                        "content": reply_text,
                        "metadata": {
                            "original_message": original_message.content if hasattr(original_message, 'content') else ""
                        }
                    }
                    
                    await self.memory_manager.add_interaction(
                        "bot", 
                        original_message.sender_id,
                        interaction_data
                    )
        except Exception as e:
            logger.error(f"记录回复到记忆系统时出错: {e}")

    def _is_simple_reply(self, thought: Thought, message: Message) -> bool:
        """
        判断是否使用简单回复模板
        
        Args:
            thought: 思考内容
            message: 原始消息
            
        Returns:
            是否使用简单回复
        """
        # 内容较短的消息使用简单回复
        if hasattr(message, 'content') and len(message.content) < 15:
            return True
        
        # 简单意图使用简单回复
        intent = thought.understanding.get("intent", "")
        simple_intents = ["greeting", "gratitude", "farewell"]
        if intent in simple_intents:
            return True
        
        # 低优先级消息使用简单回复
        priority = thought.response_plan.get("priority", "low")
        if priority == "low":
            return True
        
        # 否则使用复杂回复
        return False

    async def _generate_fallback_reply(self, attitude: str) -> str:
        """
        生成后备回复
        
        Args:
            attitude: 回应态度
            
        Returns:
            后备回复文本
        """
        fallback_replies = {
            "friendly": [
                "我明白你的意思啦~",
                "好的，我记住了哦！",
                "嗯嗯，继续聊吧~",
                "这个很有意思呢！"
            ],
            "neutral": [
                "好的，我明白了。",
                "我理解了你的意思。",
                "嗯，我记住了。",
                "继续吧。"
            ],
            "reserved": [
                "嗯...",
                "我需要思考一下...",
                "这个问题有点复杂...",
                "可能是这样吧..."
            ]
        }
        
        replies = fallback_replies.get(attitude, fallback_replies["neutral"])
        return random.choice(replies)

    async def _get_relationship(self, sender_id: str) -> Optional[Relationship]:
        """获取与发送者的关系"""
        try:
            # 从记忆管理器获取关系数据
            return await self.memory_manager.get_relationship("bot", sender_id)
        except Exception as e:
            logger.error(f"获取关系数据时出错: {e}")
            return None

    def _extract_context(self, chat_stream: ChatStream, current_message: Message) -> List[Dict]:
        """提取聊天上下文"""
        context = []
        recent_messages = chat_stream.get_recent_messages(5)  # 获取最近5条消息
        
        for msg in recent_messages:
            if msg.message_id != current_message.message_id:  # 排除当前消息
                context.append({
                    "sender": msg.sender_id,
                    "content": msg.content,
                    "timestamp": msg.timestamp
                })
                
        return context

    def _build_reply_prompt(
        self,
        thought: Thought,
        attitude: str,
        emotional_state: Dict[str, Any],
        relationship: Optional[Relationship],
        context: List[Dict]
    ) -> str:
        """
        构建回复生成提示
        
        Args:
            thought: 思考内容
            attitude: 回应态度
            emotional_state: 情绪状态
            relationship: 与发送者的关系
            context: 对话上下文
            
        Returns:
            提示文本
        """
        # 获取信息
        message_content = thought.raw_content
        understanding = thought.understanding
        emotion = emotional_state.get("emotion", "neutral")
        intensity = emotional_state.get("intensity", 0.5)
        
        # 构建提示
        prompt = f"生成回复，原始消息: '{message_content}'\n\n"
        
        # 添加我的理解
        prompt += f"我的理解: {understanding.get('intent', '一般对话')}, 主题: {understanding.get('topic', '未知')}\n"
        
        # 添加情绪状态
        prompt += f"我当前的情绪: {emotion}, 强度: {intensity}\n"
        
        # 添加回应态度
        prompt += f"回应态度: {attitude}\n"
        
        # 添加回应计划
        response_plan = thought.response_plan
        if response_plan:
            prompt += f"回应策略: {response_plan.get('strategy', 'conversational')}\n"
            prompt += f"回应重点: {', '.join(response_plan.get('key_points', ['简单回应']))}\n"
            prompt += f"语气: {response_plan.get('tone', 'neutral')}\n"
        
        # 添加关系信息
        if relationship:
            familiarity = relationship.source_impression.familiarity
            likability = relationship.source_impression.likability
            prompt += f"与对方关系: 熟悉度 {familiarity}, 好感度 {likability}\n"
        
        # 添加上下文
        if context:
            prompt += "\n最近的对话:\n"
            for ctx in context[-3:]:  # 只使用最近3条
                prompt += f"- {ctx['sender']}: {ctx['content']}\n"
        
        # 生成要求
        prompt += f"""
请根据以上信息生成一个自然、符合我情绪和态度的回复。回复应该:
1. 简洁自然，不超过两句话
2. 反映我当前的情绪状态和回应态度
3. 保持语气一致性
4. 没有解释或元描述
5. 直接给出回复内容，不要添加引号

回复:"""
        
        return prompt

def get_reply_composer() -> ReplyComposer:
    """获取回复生成器单例"""
    return ReplyComposer() 