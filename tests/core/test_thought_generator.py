#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
林镜(LingJing) - ThoughtGenerator组件测试
"""

import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import asyncio
import json
import time

from linjing.models.chat_stream import ChatStream, Message
from linjing.models.thought import Thought
from linjing.core.thought_generator import ThoughtGenerator


class TestThoughtGenerator(unittest.TestCase):
    """ThoughtGenerator测试类"""

    def setUp(self):
        """测试准备"""
        # 创建ThoughtGenerator实例
        self.generator = ThoughtGenerator()
        
        # 模拟依赖组件
        self.generator.config = MagicMock()
        self.generator.llm_client = AsyncMock()
        self.generator.relationship_manager = AsyncMock()
        self.generator.emotion_manager = AsyncMock()
        self.generator.memory_manager = AsyncMock()
        self.generator.personality_manager = AsyncMock()
        
        # 设置模拟返回值
        self.generator.config.get.return_value = {
            "name": "林镜",
            "personality": {
                "traits": ["友善", "好奇", "有耐心"],
                "voice": "温和",
                "speaking_style": "亲切而简洁"
            }
        }
        
        # 模拟LLM返回的思考结果
        self.generator.llm_client.generate_thought.return_value = {
            "understanding": "用户在问候机器人并询问近况",
            "emotional_response": {
                "primary": "joy",
                "secondary": "interest",
                "intensity": 0.7
            },
            "reasoning": "用户表现出友好，想要与机器人闲聊",
            "social_context": {
                "is_direct_interaction": True,
                "requires_response": True,
                "conversation_topic": "greeting",
                "topic_relevance": "high"
            },
            "response_considerations": {
                "should_respond": True,
                "response_type": "greeting",
                "priority": "high",
                "key_points": ["回应问候", "简述近况", "表达友好"]
            }
        }
        
        # 模拟关系管理器返回值
        self.generator.relationship_manager.get_relationship.return_value = {
            "strength": 0.6,
            "familiarity": 0.5,
            "trust": 0.7,
            "likability": 0.6,
            "tags": ["群友", "积极互动"],
            "notes": ["经常在群里讨论技术话题", "对AI感兴趣"]
        }
        
        # 模拟情绪管理器返回值
        self.generator.emotion_manager.get_current_emotion.return_value = {
            "state": "平静",
            "valence": 0.6,  # 情绪效价
            "arousal": 0.4,  # 情绪唤醒度
            "dominance": 0.5,  # 情绪支配度
            "social_openness": 0.7  # 社交开放度
        }
        
        # 模拟记忆管理器返回值
        self.generator.memory_manager.get_recent_interactions.return_value = [
            {"timestamp": time.time() - 3600, "content": "用户: 你好，林镜！", "sentiment": "positive"},
            {"timestamp": time.time() - 3500, "content": "林镜: 你好！很高兴见到你。", "sentiment": "positive"}
        ]
        
        self.generator.memory_manager.get_user_interaction_summary.return_value = {
            "common_topics": ["问候", "技术", "日常生活"],
            "interaction_style": "友好",
            "previous_discussions": ["上次讨论了编程语言", "之前聊过音乐"]
        }
        
        # 模拟性格管理器返回值
        self.generator.personality_manager.get_current_personality.return_value = {
            "traits": ["友善", "好奇", "有耐心"],
            "voice": "温和",
            "speaking_style": "亲切而简洁",
            "communication_preferences": {
                "directness": 0.7,
                "formality": 0.5,
                "humor": 0.6,
                "empathy": 0.8
            }
        }
        
        # 创建测试消息对象
        self.message = Message(
            message_id="msg_123",
            sender_id="user_456",
            content="你好，林镜！最近怎么样？",
            message_type="group",
            group_id="group_789",
            timestamp=time.time(),
            is_at_me=True
        )
        
        # 创建测试聊天流
        self.chat_stream = ChatStream(
            stream_id="test_stream",
            messages=[
                Message(
                    message_id="msg_121",
                    sender_id="user_456",
                    content="大家好啊！",
                    message_type="group",
                    group_id="group_789",
                    timestamp=time.time() - 300,
                    is_at_me=False
                ),
                self.message
            ]
        )
        
        # 运行初始化
        self.loop = asyncio.get_event_loop()
        self.loop.run_until_complete(self.generator.initialize())

    def test_init(self):
        """测试初始化"""
        self.assertIsNotNone(self.generator.config)
        self.assertIsNotNone(self.generator.llm_client)
        self.assertIsNotNone(self.generator.relationship_manager)
        self.assertIsNotNone(self.generator.emotion_manager)
        self.assertIsNotNone(self.generator.memory_manager)
        self.assertIsNotNone(self.generator.personality_manager)

    def test_generate_thought(self):
        """测试生成思考"""
        # 执行测试
        result = self.loop.run_until_complete(
            self.generator.generate(self.chat_stream, self.message)
        )
        
        # 验证结果
        self.assertIsInstance(result, Thought)
        self.assertEqual(result.message_id, self.message.message_id)
        self.assertIn("用户在问候", result.understanding)
        self.assertIsInstance(result.emotional_response, dict)
        self.assertIn("primary", result.emotional_response)
        self.assertIn("secondary", result.emotional_response)
        self.assertIn("intensity", result.emotional_response)
        self.assertIsInstance(result.social_context, dict)
        self.assertIn("is_direct_interaction", result.social_context)
        self.assertIn("requires_response", result.social_context)
        self.assertIsInstance(result.response_considerations, dict)
        self.assertIn("should_respond", result.response_considerations)
        self.assertIn("response_type", result.response_considerations)
        
        # 验证LLM被调用
        self.generator.llm_client.generate_thought.assert_called_once()

    def test_generate_thought_with_at(self):
        """测试生成@消息的思考"""
        # 创建@消息
        at_message = Message(
            message_id="msg_at",
            sender_id="user_456",
            content="@林镜 你能介绍一下自己吗？",
            message_type="group",
            group_id="group_789",
            timestamp=time.time(),
            is_at_me=True
        )
        
        # 执行测试
        result = self.loop.run_until_complete(
            self.generator.generate(self.chat_stream, at_message)
        )
        
        # 验证结果
        self.assertIsInstance(result, Thought)
        
        # 验证LLM调用参数中包含@信息
        call_args = self.generator.llm_client.generate_thought.call_args[0][0]
        self.assertIn("@", str(call_args))

    def test_generate_thought_with_private(self):
        """测试生成私聊消息的思考"""
        # 创建私聊消息
        private_message = Message(
            message_id="msg_private",
            sender_id="user_456",
            content="你好，林镜！",
            message_type="private",
            timestamp=time.time(),
            is_at_me=False
        )
        
        # 创建私聊聊天流
        private_chat_stream = ChatStream(
            stream_id="private_user_456",
            messages=[private_message]
        )
        
        # 执行测试
        result = self.loop.run_until_complete(
            self.generator.generate(private_chat_stream, private_message)
        )
        
        # 验证结果
        self.assertIsInstance(result, Thought)
        
        # 验证LLM调用参数中包含私聊信息
        call_args = self.generator.llm_client.generate_thought.call_args[0][0]
        self.assertIn("私聊", str(call_args))

    def test_build_context(self):
        """测试构建上下文"""
        # 执行测试
        context = self.generator._build_context(self.chat_stream, self.message)
        
        # 验证结果
        self.assertIsInstance(context, dict)
        self.assertIn("current_message", context)
        self.assertIn("chat_history", context)
        self.assertIn("relationship", context)
        self.assertIn("current_emotion", context)
        self.assertIn("recent_interactions", context)
        self.assertIn("user_summary", context)
        self.assertIn("personality", context)
        
        # 验证上下文中包含了历史消息
        self.assertGreaterEqual(len(context["chat_history"]), 1)
        
        # 验证当前消息在上下文中
        self.assertEqual(context["current_message"]["content"], self.message.content)

    def test_thought_for_different_message_types(self):
        """测试不同类型消息的思考生成"""
        # 测试不同类型的消息
        message_types = [
            # 问候消息
            Message(
                message_id="msg_greeting",
                sender_id="user_456",
                content="你好，林镜！",
                message_type="group",
                group_id="group_789",
                timestamp=time.time(),
                is_at_me=False
            ),
            # 问题消息
            Message(
                message_id="msg_question",
                sender_id="user_456",
                content="林镜，你觉得人工智能会取代人类工作吗？",
                message_type="group",
                group_id="group_789",
                timestamp=time.time(),
                is_at_me=False
            ),
            # 命令消息
            Message(
                message_id="msg_command",
                sender_id="user_456",
                content="/help",
                message_type="group",
                group_id="group_789",
                timestamp=time.time(),
                is_at_me=False
            )
        ]
        
        # 为不同消息类型设置不同的LLM返回值
        llm_responses = [
            # 问候消息的思考
            {
                "understanding": "用户在群聊中问候大家",
                "emotional_response": {"primary": "joy", "secondary": "interest", "intensity": 0.5},
                "reasoning": "用户只是在群里打招呼，没有特别针对机器人",
                "social_context": {"is_direct_interaction": False, "requires_response": False},
                "response_considerations": {"should_respond": False, "priority": "low"}
            },
            # 问题消息的思考
            {
                "understanding": "用户询问关于AI取代人类工作的问题",
                "emotional_response": {"primary": "curiosity", "secondary": "thoughtfulness", "intensity": 0.7},
                "reasoning": "用户提出了一个关于AI社会影响的深度问题",
                "social_context": {"is_direct_interaction": True, "requires_response": True},
                "response_considerations": {"should_respond": True, "response_type": "opinion", "priority": "high"}
            },
            # 命令消息的思考
            {
                "understanding": "用户发送了一个命令请求帮助",
                "emotional_response": {"primary": "desire_to_help", "secondary": "focus", "intensity": 0.6},
                "reasoning": "用户需要了解机器人的功能和使用方法",
                "social_context": {"is_direct_interaction": True, "requires_response": True},
                "response_considerations": {"should_respond": True, "response_type": "command", "priority": "high"}
            }
        ]
        
        thoughts = []
        for i, message in enumerate(message_types):
            # 设置对应的LLM返回值
            self.generator.llm_client.generate_thought.return_value = llm_responses[i]
            
            # 执行测试
            result = self.loop.run_until_complete(
                self.generator.generate(self.chat_stream, message)
            )
            
            # 收集结果
            thoughts.append(result)
        
        # 验证结果 - 每种消息类型都应该生成对应的思考
        self.assertEqual(len(thoughts), len(message_types))
        for i, thought in enumerate(thoughts):
            self.assertIsInstance(thought, Thought)
            # 验证理解部分与LLM返回值一致
            self.assertEqual(thought.understanding, llm_responses[i]["understanding"])

    def test_with_complex_context(self):
        """测试复杂上下文的思考生成"""
        # 创建更复杂的聊天上下文
        complex_chat_stream = ChatStream(
            stream_id="complex_stream",
            messages=[
                Message(
                    message_id="msg_1",
                    sender_id="user_1",
                    content="大家好，今天天气真好！",
                    message_type="group",
                    group_id="group_789",
                    timestamp=time.time() - 600,
                    is_at_me=False
                ),
                Message(
                    message_id="msg_2",
                    sender_id="user_2",
                    content="确实很好，适合出去玩。",
                    message_type="group",
                    group_id="group_789",
                    timestamp=time.time() - 550,
                    is_at_me=False
                ),
                Message(
                    message_id="msg_3",
                    sender_id="user_3",
                    content="林镜，你喜欢什么天气？",
                    message_type="group",
                    group_id="group_789",
                    timestamp=time.time() - 500,
                    is_at_me=True
                ),
                Message(
                    message_id="msg_4",
                    sender_id="bot_id",
                    content="我喜欢晴朗的天气，阳光明媚但不太热的那种。",
                    message_type="group",
                    group_id="group_789",
                    timestamp=time.time() - 450,
                    is_at_me=False,
                    is_from_self=True
                ),
                Message(
                    message_id="msg_5",
                    sender_id="user_1",
                    content="林镜，你觉得今天适合做什么活动？",
                    message_type="group",
                    group_id="group_789",
                    timestamp=time.time() - 300,
                    is_at_me=True
                )
            ]
        )
        
        # 当前要回复的消息
        current_message = Message(
            message_id="msg_6",
            sender_id="user_2",
            content="我也想知道林镜的建议。",
            message_type="group",
            group_id="group_789",
            timestamp=time.time(),
            is_at_me=False
        )
        
        # 设置LLM返回值
        self.generator.llm_client.generate_thought.return_value = {
            "understanding": "用户想知道机器人关于今天适合活动的建议",
            "emotional_response": {"primary": "interest", "secondary": "desire_to_help", "intensity": 0.6},
            "reasoning": "用户在延续之前的话题，也想获取机器人的看法",
            "social_context": {"is_direct_interaction": True, "requires_response": True, "conversation_topic": "leisure"},
            "response_considerations": {"should_respond": True, "response_type": "suggestion", "priority": "medium"}
        }
        
        # 执行测试
        result = self.loop.run_until_complete(
            self.generator.generate(complex_chat_stream, current_message)
        )
        
        # 验证结果
        self.assertIsInstance(result, Thought)
        
        # 验证LLM调用参数包含足够的上下文信息
        call_args = self.generator.llm_client.generate_thought.call_args[0][0]
        context_dict = call_args
        self.assertGreaterEqual(len(context_dict.get("chat_history", [])), 4)  # 应包含足够的历史消息

    def test_with_emotion_influence(self):
        """测试情绪对思考的影响"""
        # 设置不同情绪状态
        emotions = [
            # 积极情绪
            {
                "state": "愉悦",
                "valence": 0.9,  # 高正面情绪
                "arousal": 0.7,
                "dominance": 0.6,
                "social_openness": 0.8
            },
            # 消极情绪
            {
                "state": "沮丧",
                "valence": 0.2,  # 低正面情绪
                "arousal": 0.3,
                "dominance": 0.4,
                "social_openness": 0.3
            }
        ]
        
        thoughts = []
        for emotion in emotions:
            # 设置情绪
            self.generator.emotion_manager.get_current_emotion.return_value = emotion
            
            # 执行测试
            result = self.loop.run_until_complete(
                self.generator.generate(self.chat_stream, self.message)
            )
            
            # 收集思考
            thoughts.append(result)
            
            # 验证LLM调用参数包含情绪信息
            call_args = self.generator.llm_client.generate_thought.call_args[0][0]
            self.assertEqual(call_args["current_emotion"]["state"], emotion["state"])
        
        # 重置情绪
        self.generator.emotion_manager.get_current_emotion.return_value = {
            "state": "平静",
            "valence": 0.6,
            "arousal": 0.4,
            "dominance": 0.5,
            "social_openness": 0.7
        }

    def test_with_relationship_influence(self):
        """测试关系对思考的影响"""
        # 设置不同关系
        relationships = [
            # 亲密关系
            {
                "strength": 0.9,
                "familiarity": 0.9,
                "trust": 0.9,
                "likability": 0.9,
                "tags": ["好友", "亲密互动"],
                "notes": ["经常深入交流", "互相信任"]
            },
            # 疏远关系
            {
                "strength": 0.1,
                "familiarity": 0.1,
                "trust": 0.1,
                "likability": 0.1,
                "tags": ["新用户", "首次互动"],
                "notes": ["刚刚认识", "关系待建立"]
            }
        ]
        
        thoughts = []
        for relationship in relationships:
            # 设置关系
            self.generator.relationship_manager.get_relationship.return_value = relationship
            
            # 执行测试
            result = self.loop.run_until_complete(
                self.generator.generate(self.chat_stream, self.message)
            )
            
            # 收集思考
            thoughts.append(result)
            
            # 验证LLM调用参数包含关系信息
            call_args = self.generator.llm_client.generate_thought.call_args[0][0]
            self.assertEqual(call_args["relationship"]["strength"], relationship["strength"])
        
        # 重置关系
        self.generator.relationship_manager.get_relationship.return_value = {
            "strength": 0.6,
            "familiarity": 0.5,
            "trust": 0.7,
            "likability": 0.6,
            "tags": ["群友", "积极互动"],
            "notes": ["经常在群里讨论技术话题", "对AI感兴趣"]
        }

    def test_error_handling(self):
        """测试错误处理"""
        # 设置LLM抛出异常
        self.generator.llm_client.generate_thought.side_effect = Exception("模型调用失败")
        
        # 执行测试
        result = self.loop.run_until_complete(
            self.generator.generate(self.chat_stream, self.message)
        )
        
        # 验证结果 - 应该返回一个基本的思考对象
        self.assertIsInstance(result, Thought)
        self.assertEqual(result.message_id, self.message.message_id)
        # 检查是否包含错误信息
        self.assertIn("错误", result.understanding.lower())
        
        # 重置side_effect
        self.generator.llm_client.generate_thought.side_effect = None

    def test_retry_mechanism(self):
        """测试重试机制"""
        # 设置LLM首次调用失败后恢复
        self.generator.llm_client.generate_thought.side_effect = [
            Exception("首次调用失败"),
            {
                "understanding": "重试成功后的理解",
                "emotional_response": {"primary": "relief", "secondary": "joy", "intensity": 0.5},
                "reasoning": "重试成功后的推理",
                "social_context": {"is_direct_interaction": True, "requires_response": True},
                "response_considerations": {"should_respond": True, "priority": "medium"}
            }
        ]
        
        # 执行测试
        result = self.loop.run_until_complete(
            self.generator.generate(self.chat_stream, self.message)
        )
        
        # 验证结果
        self.assertIsInstance(result, Thought)
        self.assertEqual(result.understanding, "重试成功后的理解")
        
        # 验证调用次数
        self.assertEqual(self.generator.llm_client.generate_thought.call_count, 2)
        
        # 重置side_effect
        self.generator.llm_client.generate_thought.side_effect = None

    def test_with_different_personality(self):
        """测试不同性格对思考的影响"""
        # 设置不同性格
        personalities = [
            # 外向性格
            {
                "traits": ["外向", "活跃", "热情"],
                "voice": "活力充沛",
                "speaking_style": "热情洋溢",
                "communication_preferences": {
                    "directness": 0.8,
                    "formality": 0.3,
                    "humor": 0.8,
                    "empathy": 0.7
                }
            },
            # 内向性格
            {
                "traits": ["内向", "沉思", "谨慎"],
                "voice": "温和平静",
                "speaking_style": "深思熟虑",
                "communication_preferences": {
                    "directness": 0.5,
                    "formality": 0.7,
                    "humor": 0.3,
                    "empathy": 0.8
                }
            }
        ]
        
        thoughts = []
        for personality in personalities:
            # 设置性格
            self.generator.personality_manager.get_current_personality.return_value = personality
            
            # 执行测试
            result = self.loop.run_until_complete(
                self.generator.generate(self.chat_stream, self.message)
            )
            
            # 收集思考
            thoughts.append(result)
            
            # 验证LLM调用参数包含性格信息
            call_args = self.generator.llm_client.generate_thought.call_args[0][0]
            self.assertEqual(call_args["personality"]["traits"], personality["traits"])
        
        # 重置性格
        self.generator.personality_manager.get_current_personality.return_value = {
            "traits": ["友善", "好奇", "有耐心"],
            "voice": "温和",
            "speaking_style": "亲切而简洁",
            "communication_preferences": {
                "directness": 0.7,
                "formality": 0.5,
                "humor": 0.6,
                "empathy": 0.8
            }
        }


if __name__ == "__main__":
    unittest.main() 