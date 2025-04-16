#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
林镜(LingJing) - 思维生成器
负责分析消息内容并生成机器人的内部思考过程
"""

import asyncio
import logging
import time
import random
from typing import Dict, List, Optional, Any, Tuple

from ..models.chat_stream import ChatStream
from ..models.message_models import Message, MessageContent
from ..models.thought import Thought
from ..utils.logger import get_logger
from ..llm.llm_interface import get_llm_interface
from ..emotion.emotion_manager import get_emotion_manager
from ..memory.memory_manager import get_memory_manager
from ..models.relationship_models import Relationship, Impression
from ..utils.singleton import singleton

logger = get_logger('linjing.core.thought_generator')

@singleton
class ThoughtGenerator:
    """
    思维生成器，负责分析消息并生成机器人的内部思考过程
    生成的思考将包含对消息的理解、情感反应和可能的回应计划
    """

    def __init__(self):
        """初始化思维生成器"""
        self.llm_interface = None
        self.emotion_manager = None
        self.memory_manager = None
        self.thinking_templates = {
            "理解": [
                "这条消息是在说{}",
                "用户似乎在讨论{}",
                "这是关于{}的问题",
                "这条消息表达了对{}的看法"
            ],
            "情感": [
                "这让我感到{}",
                "对此我的情绪是{}",
                "这种情况让我{}",
                "我对此的反应是{}"
            ],
            "计划": [
                "我应该{}回应",
                "最好的回应方式是{}",
                "我可以{}",
                "合适的反应是{}"
            ]
        }
        self.lock = asyncio.Lock()
        logger.info("思维生成器初始化完成")

    async def initialize(self):
        """初始化思维生成器组件"""
        logger.info("正在初始化思维生成器...")
        self.llm_interface = await get_llm_interface()
        self.emotion_manager = await get_emotion_manager()
        self.memory_manager = await get_memory_manager()
        logger.info("思维生成器初始化完成")

    async def generate_thought(self, chat_stream: ChatStream, current_message: Message) -> Thought:
        """
        为当前消息生成思考
        
        Args:
            chat_stream: 聊天流对象，包含聊天历史
            current_message: 当前消息
            
        Returns:
            生成的思考对象
        """
        async with self.lock:
            # 提取消息上下文
            context = self._extract_context(chat_stream, current_message)
            
            # 获取发送者与机器人的关系
            relationship = await self._get_relationship(current_message.sender.user_id)
            
            # 分析消息内容
            understanding = await self._analyze_message_content(current_message, context)
            
            # 生成情感反应
            emotional_response = await self._generate_emotional_response(
                current_message, 
                understanding, 
                relationship
            )
            
            # 形成回应计划
            response_plan = await self._form_response_plan(
                current_message, 
                understanding, 
                emotional_response, 
                relationship
            )
            
            # 构建完整思考
            thought = Thought(
                message_id=current_message.id,
                timestamp=time.time(),
                understanding=understanding,
                emotional_response=emotional_response,
                response_plan=response_plan,
                raw_content=current_message.content.get_plain_text(),
                metadata={
                    "sender_id": current_message.sender.user_id,
                    "message_type": current_message.message_type,
                    "group_id": current_message.group_id if current_message.message_type == "group" else None
                }
            )
            
            # 记录思考到记忆系统
            await self._store_thought(thought)
            
            return thought

    async def _analyze_message_content(self, message: Message, context: List[Dict]) -> Dict[str, Any]:
        """
        分析消息内容，理解其意图和主题
        
        Args:
            message: 当前消息
            context: 消息上下文
            
        Returns:
            包含消息理解的字典
        """
        try:
            # 直接使用简单方法分析消息
            return {
                "intent": self._detect_basic_intent(message.content),
                "topic": self._extract_basic_topic(message.content),
                "sentiment": "neutral",
                "is_question": "?" in message.content.get_plain_text() or "？" in message.content.get_plain_text(),
                "keywords": self._extract_keywords(message.content)
            }
        except Exception as e:
            logger.error(f"分析消息内容时出错: {e}")
            # 回退到简单分析
            return {
                "intent": "statement",
                "topic": "未知",
                "sentiment": "neutral",
                "is_question": False,
                "keywords": []
            }

    async def _generate_emotional_response(
        self, 
        message: Message, 
        understanding: Dict[str, Any], 
        relationship: Optional[Relationship]
    ) -> Dict[str, Any]:
        """
        生成对消息的情感反应
        
        Args:
            message: 当前消息
            understanding: 消息理解
            relationship: 与发送者的关系
            
        Returns:
            情感反应字典
        """
        # 获取当前情绪状态
        current_emotion = await self.emotion_manager.get_current_emotion()
        
        # 根据关系调整情感反应
        relationship_factor = 1.0
        if relationship:
            familiarity = relationship.impression.familiarity
            likability = relationship.impression.likability
            relationship_factor = 0.5 + (familiarity + likability) / 4
        
        # 生成情感反应
        template = random.choice(self.thinking_templates["情感"])
        emotion_description = template.format(current_emotion["emotion"])
        
        return {
            "primary_emotion": current_emotion["emotion"],
            "emotion_intensity": current_emotion["intensity"],
            "description": emotion_description,
            "relationship_influence": relationship_factor,
            "causes": [understanding.get("intent", ""), understanding.get("topic", "")]
        }

    async def _form_response_plan(
        self, 
        message: Message, 
        understanding: Dict[str, Any], 
        emotional_response: Dict[str, Any], 
        relationship: Optional[Relationship]
    ) -> Dict[str, Any]:
        """
        形成回应计划
        
        Args:
            message: 当前消息
            understanding: 消息理解
            emotional_response: 情感反应
            relationship: 与发送者的关系
            
        Returns:
            回应计划字典
        """
        # 确定回应优先级
        priority = self._determine_response_priority(message, understanding)
        
        # 选择回应策略
        strategy = self._select_response_strategy(
            understanding, 
            emotional_response, 
            relationship
        )
        
        # 生成回应计划描述
        template = random.choice(self.thinking_templates["计划"])
        plan_description = template.format(strategy["description"])
        
        return {
            "priority": priority,
            "strategy": strategy["name"],
            "description": plan_description,
            "should_reference_memory": random.random() < 0.3,  # 30%概率引用记忆
            "tone": strategy["tone"],
            "key_points": self._extract_key_points_to_address(understanding)
        }

    def _determine_response_priority(self, message: Message, understanding: Dict[str, Any]) -> str:
        """确定回应优先级"""
        if message.message_type == "private" or message.content.contains_at(message.self_id):
            return "high"
        elif understanding.get("is_question", False):
            return "medium"
        else:
            return "low"

    def _select_response_strategy(
        self, 
        understanding: Dict[str, Any], 
        emotional_response: Dict[str, Any], 
        relationship: Optional[Relationship]
    ) -> Dict[str, str]:
        """选择回应策略"""
        intent = understanding.get("intent", "")
        emotion = emotional_response.get("primary_emotion", "neutral")
        
        # 基于意图和情绪选择策略
        if "question" in intent or understanding.get("is_question", False):
            return {
                "name": "informative",
                "description": "提供信息性回应",
                "tone": "helpful"
            }
        elif "greeting" in intent or "chat" in intent:
            return {
                "name": "conversational",
                "description": "进行友好对话",
                "tone": "friendly" if emotion in ["happy", "excited"] else "casual"
            }
        elif "negative" in understanding.get("sentiment", ""):
            return {
                "name": "supportive",
                "description": "提供支持或转移话题",
                "tone": "empathetic"
            }
        else:
            return {
                "name": "reflective",
                "description": "反思性回应",
                "tone": "thoughtful"
            }

    def _extract_key_points_to_address(self, understanding: Dict[str, Any]) -> List[str]:
        """提取需要在回应中处理的关键点"""
        key_points = []
        
        if understanding.get("is_question", False):
            key_points.append("回答问题")
        
        if understanding.get("topic"):
            key_points.append(f"讨论{understanding.get('topic')}")
        
        if understanding.get("intent") == "greeting":
            key_points.append("回应问候")
            
        # 确保至少有一个关键点
        if not key_points:
            key_points.append("简单回应")
            
        return key_points

    def _extract_context(self, chat_stream: ChatStream, current_message: Message) -> List[Dict]:
        """提取聊天上下文"""
        context = []
        recent_messages = chat_stream.get_messages(5)  # 获取最近5条消息
        
        for msg in recent_messages:
            if msg.id != current_message.id:  # 排除当前消息
                context.append({
                    "sender": msg.sender.user_id,
                    "content": msg.content.get_plain_text(),
                    "timestamp": msg.time
                })
                
        return context

    async def _get_relationship(self, sender_id: Any) -> Optional[Relationship]:
        """获取与发送者的关系"""
        try:
            # 模拟一个基本关系
            from ..models.relationship_models import Relationship, Impression
            
            impression = Impression(
                familiarity=0.5,
                likability=0.7,
                trust=0.6,
                respect=0.5
            )
            
            return Relationship(
                source_id="bot",
                target_id=str(sender_id),
                relationship_type="user",
                impression=impression
            )
        except Exception as e:
            logger.error(f"获取关系数据时出错: {e}")
            return None

    def _build_analysis_prompt(self, message: Message, context: List[Dict]) -> str:
        """构建消息分析提示"""
        prompt = f"分析以下消息:\n{message.content}\n\n"
        
        if context:
            prompt += "上下文:\n"
            for ctx in context:
                prompt += f"- {ctx['sender']}: {ctx['content']}\n"
        
        prompt += "\n分析消息的意图、主题、情感和是否包含问题。"
        return prompt

    def _detect_basic_intent(self, content: MessageContent) -> str:
        """检测基本意图"""
        content_text = content.get_plain_text().lower()
        
        if any(word in content_text for word in ["你好", "早上好", "晚上好", "嗨", "hi", "hello"]):
            return "greeting"
        elif "?" in content_text or "？" in content_text or any(word in content_text for word in ["什么", "怎么", "如何", "为什么"]):
            return "question"
        elif any(word in content_text for word in ["谢谢", "感谢"]):
            return "gratitude"
        else:
            return "statement"

    def _extract_basic_topic(self, content: MessageContent) -> str:
        """提取基本主题"""
        # 简化实现，实际应使用NLP技术
        content_text = content.get_plain_text()
        if len(content_text) < 10:
            return "短消息"
        
        topics = {
            "技术": ["代码", "编程", "python", "开发", "bug", "问题"],
            "情感": ["喜欢", "讨厌", "开心", "难过", "生气", "感觉"],
            "日常": ["天气", "吃饭", "睡觉", "工作", "学习"]
        }
        
        for topic, keywords in topics.items():
            if any(keyword in content_text for keyword in keywords):
                return topic
                
        return "一般对话"

    def _extract_keywords(self, content: MessageContent) -> List[str]:
        """提取关键词"""
        # 简化实现，返回分词结果中长度大于1的词
        # 实际应使用专业NLP库
        content_text = content.get_plain_text()
        words = content_text.split()
        return [word for word in words if len(word) > 1]

    async def _store_thought(self, thought: Thought) -> None:
        """将思考存储到记忆系统"""
        try:
            await self.memory_manager.store_thought(thought)
        except Exception as e:
            logger.error(f"存储思考到记忆系统时出错: {e}")

async def get_thought_generator() -> ThoughtGenerator:
    """
    获取思维生成器实例
    
    Returns:
        ThoughtGenerator实例
    """
    generator = ThoughtGenerator()
    return generator 