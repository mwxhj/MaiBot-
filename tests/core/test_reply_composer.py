#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
林镜(LingJing) - ReplyComposer组件测试
"""

import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import asyncio
import json
import time

from linjing.models.chat_stream import ChatStream, Message
from linjing.models.thought import Thought
from linjing.core.reply_composer import ReplyComposer


class TestReplyComposer(unittest.TestCase):
    """ReplyComposer测试类"""

    def setUp(self):
        """测试准备"""
        # 创建ReplyComposer实例
        self.composer = ReplyComposer()
        
        # 模拟依赖组件
        self.composer.config = MagicMock()
        self.composer.llm_client = AsyncMock()
        self.composer.personality_manager = AsyncMock()
        self.composer.emotion_manager = AsyncMock()
        self.composer.relationship_manager = AsyncMock()
        self.composer.memory_manager = AsyncMock()
        
        # 设置模拟返回值
        self.composer.config.get.return_value = {
            "name": "林镜",
            "personality": {
                "traits": ["友善", "好奇", "有耐心"],
                "voice": "温和",
                "speaking_style": "亲切而简洁"
            },
            "response_styles": {
                "friendly": {
                    "tone": "温暖",
                    "formality": "随和",
                    "verbosity": "适中",
                    "emoji_usage": "适量"
                },
                "neutral": {
                    "tone": "平和",
                    "formality": "标准",
                    "verbosity": "简洁",
                    "emoji_usage": "极少"
                },
                "reserved": {
                    "tone": "冷静",
                    "formality": "正式",
                    "verbosity": "精简",
                    "emoji_usage": "无"
                }
            }
        }
        
        self.composer.personality_manager.get_current_personality.return_value = {
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
        
        self.composer.emotion_manager.get_current_emotion.return_value = {
            "state": "平静",
            "valence": 0.6,  # 情绪效价
            "arousal": 0.4,  # 情绪唤醒度
            "dominance": 0.5,  # 情绪支配度
            "social_openness": 0.7  # 社交开放度
        }
        
        self.composer.relationship_manager.get_relationship.return_value = {
            "strength": 0.6,
            "familiarity": 0.5,
            "trust": 0.7,
            "likability": 0.6
        }
        
        self.composer.memory_manager.get_user_interaction_summary.return_value = {
            "common_topics": ["问候", "技术", "日常生活"],
            "interaction_style": "友好",
            "previous_discussions": ["上次讨论了编程语言", "之前聊过音乐"]
        }
        
        self.composer.memory_manager.get_recent_interactions.return_value = [
            {
                "timestamp": time.time() - 3600,
                "content": "你好，林镜！",
                "sentiment": "positive"
            },
            {
                "timestamp": time.time() - 3500,
                "content": "你能告诉我今天的天气吗？",
                "sentiment": "neutral"
            }
        ]
        
        # 模拟LLM返回
        self.composer.llm_client.chat_completion.return_value = {
            "message": "你好！很高兴再次与你交流。今天我感觉不错，希望你也一样。有什么我能帮助你的吗？",
            "finish_reason": "stop"
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
        
        # 创建测试思考对象
        self.thought = Thought(
            message_id="msg_123",
            understanding="用户在问候机器人并询问近况",
            emotional_response={
                "primary": "joy",
                "secondary": "interest",
                "intensity": 0.7
            },
            reasoning="用户表现出友好，想要与机器人闲聊",
            social_context={
                "is_direct_interaction": True,
                "requires_response": True,
                "conversation_topic": "greeting",
                "topic_relevance": "high"
            },
            response_considerations={
                "should_respond": True,
                "response_type": "greeting",
                "priority": "high",
                "key_points": ["回应问候", "简述近况", "表达友好"]
            }
        )
        
        # 创建表达意愿检查结果
        self.willingness_result = {
            "should_express": True,
            "willingness": 0.85,
            "attitude": "friendly",
            "reason": "用户直接问候，情绪积极"
        }
        
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
        self.loop.run_until_complete(self.composer.initialize())

    def test_init(self):
        """测试初始化"""
        self.assertIsNotNone(self.composer.config)
        self.assertIsNotNone(self.composer.llm_client)
        self.assertIsNotNone(self.composer.personality_manager)
        self.assertIsNotNone(self.composer.emotion_manager)
        self.assertIsNotNone(self.composer.relationship_manager)
        self.assertIsNotNone(self.composer.memory_manager)

    def test_compose_reply(self):
        """测试生成回复"""
        # 执行测试
        result = self.loop.run_until_complete(
            self.composer.compose(
                self.chat_stream,
                self.message,
                self.thought,
                self.willingness_result
            )
        )
        
        # 验证结果
        self.assertIsInstance(result, dict)
        self.assertIn("reply", result)
        self.assertIn("messages", result)
        self.assertTrue(len(result["reply"]) > 0)
        
        # 验证调用LLM
        self.composer.llm_client.chat_completion.assert_called_once()

    def test_compose_with_friendly_attitude(self):
        """测试使用友好态度生成回复"""
        # 设置友好态度
        willingness_result = {
            "should_express": True,
            "willingness": 0.9,
            "attitude": "friendly",
            "reason": "用户直接问候，关系亲密"
        }
        
        # 执行测试
        result = self.loop.run_until_complete(
            self.composer.compose(
                self.chat_stream,
                self.message,
                self.thought,
                willingness_result
            )
        )
        
        # 验证结果
        self.assertIsInstance(result, dict)
        self.assertIn("reply", result)
        
        # 验证LLM调用参数包含友好态度相关指示
        call_args = self.composer.llm_client.chat_completion.call_args[0][0]
        messages = call_args.get("messages", [])
        system_message = next((m for m in messages if m.get("role") == "system"), {})
        self.assertIn("friendly", str(system_message).lower())

    def test_compose_with_neutral_attitude(self):
        """测试使用中立态度生成回复"""
        # 设置中立态度
        willingness_result = {
            "should_express": True,
            "willingness": 0.65,
            "attitude": "neutral",
            "reason": "普通互动"
        }
        
        # 执行测试
        result = self.loop.run_until_complete(
            self.composer.compose(
                self.chat_stream,
                self.message,
                self.thought,
                willingness_result
            )
        )
        
        # 验证结果
        self.assertIsInstance(result, dict)
        self.assertIn("reply", result)
        
        # 验证LLM调用参数包含中立态度相关指示
        call_args = self.composer.llm_client.chat_completion.call_args[0][0]
        messages = call_args.get("messages", [])
        system_message = next((m for m in messages if m.get("role") == "system"), {})
        self.assertIn("neutral", str(system_message).lower())

    def test_compose_with_reserved_attitude(self):
        """测试使用保留态度生成回复"""
        # 设置保留态度
        willingness_result = {
            "should_express": True,
            "willingness": 0.4,
            "attitude": "reserved",
            "reason": "关系较疏远"
        }
        
        # 执行测试
        result = self.loop.run_until_complete(
            self.composer.compose(
                self.chat_stream,
                self.message,
                self.thought,
                willingness_result
            )
        )
        
        # 验证结果
        self.assertIsInstance(result, dict)
        self.assertIn("reply", result)
        
        # 验证LLM调用参数包含保留态度相关指示
        call_args = self.composer.llm_client.chat_completion.call_args[0][0]
        messages = call_args.get("messages", [])
        system_message = next((m for m in messages if m.get("role") == "system"), {})
        self.assertIn("reserved", str(system_message).lower())

    def test_compose_with_emotion_influence(self):
        """测试情绪对回复的影响"""
        # 设置不同情绪
        emotions = [
            {
                "state": "愉悦",
                "valence": 0.9,  # 高正面情绪
                "arousal": 0.7,
                "dominance": 0.6,
                "social_openness": 0.8
            },
            {
                "state": "沮丧",
                "valence": 0.2,  # 低正面情绪
                "arousal": 0.3,
                "dominance": 0.4,
                "social_openness": 0.3
            }
        ]
        
        replies = []
        for emotion in emotions:
            # 设置情绪
            self.composer.emotion_manager.get_current_emotion.return_value = emotion
            
            # 执行测试
            result = self.loop.run_until_complete(
                self.composer.compose(
                    self.chat_stream,
                    self.message,
                    self.thought,
                    self.willingness_result
                )
            )
            
            # 收集回复
            replies.append(result["reply"])
            
            # 验证LLM调用参数包含情绪相关信息
            call_args = self.composer.llm_client.chat_completion.call_args[0][0]
            messages = call_args.get("messages", [])
            system_message = next((m for m in messages if m.get("role") == "system"), {})
            self.assertIn(emotion["state"], str(system_message))
        
        # 重置情绪
        self.composer.emotion_manager.get_current_emotion.return_value = {
            "state": "平静",
            "valence": 0.6,
            "arousal": 0.4,
            "dominance": 0.5,
            "social_openness": 0.7
        }

    def test_compose_with_relationship_influence(self):
        """测试关系对回复的影响"""
        # 设置不同关系
        relationships = [
            {
                "strength": 0.9,
                "familiarity": 0.9,
                "trust": 0.9,
                "likability": 0.9
            },
            {
                "strength": 0.1,
                "familiarity": 0.1,
                "trust": 0.1,
                "likability": 0.1
            }
        ]
        
        for relationship in relationships:
            # 设置关系
            self.composer.relationship_manager.get_relationship.return_value = relationship
            
            # 执行测试
            result = self.loop.run_until_complete(
                self.composer.compose(
                    self.chat_stream,
                    self.message,
                    self.thought,
                    self.willingness_result
                )
            )
            
            # 验证结果
            self.assertIsInstance(result, dict)
            self.assertIn("reply", result)
            
            # 验证LLM调用参数包含关系相关信息
            call_args = self.composer.llm_client.chat_completion.call_args[0][0]
            messages = call_args.get("messages", [])
            system_message = next((m for m in messages if m.get("role") == "system"), {})
            self.assertIn("relationship", str(system_message).lower())
        
        # 重置关系
        self.composer.relationship_manager.get_relationship.return_value = {
            "strength": 0.6,
            "familiarity": 0.5,
            "trust": 0.7,
            "likability": 0.6
        }

    def test_compose_with_memory_influence(self):
        """测试记忆对回复的影响"""
        # 设置记忆内容
        self.composer.memory_manager.get_user_interaction_summary.return_value = {
            "common_topics": ["编程", "人工智能", "音乐"],
            "interaction_style": "学术性",
            "previous_discussions": ["上次讨论了深度学习", "之前聊过编程语言的优缺点"]
        }
        
        # 执行测试
        result = self.loop.run_until_complete(
            self.composer.compose(
                self.chat_stream,
                self.message,
                self.thought,
                self.willingness_result
            )
        )
        
        # 验证结果
        self.assertIsInstance(result, dict)
        self.assertIn("reply", result)
        
        # 验证LLM调用参数包含记忆相关信息
        call_args = self.composer.llm_client.chat_completion.call_args[0][0]
        messages = call_args.get("messages", [])
        system_message = next((m for m in messages if m.get("role") == "system"), {})
        self.assertIn("previous", str(system_message).lower())

    def test_compose_with_context_influence(self):
        """测试上下文对回复的影响"""
        # 创建更长的聊天上下文
        extended_chat_stream = ChatStream(
            stream_id="test_stream",
            messages=[
                Message(
                    message_id="msg_121",
                    sender_id="user_456",
                    content="大家好啊！",
                    message_type="group",
                    group_id="group_789",
                    timestamp=time.time() - 600,
                    is_at_me=False
                ),
                Message(
                    message_id="msg_122",
                    sender_id="other_user",
                    content="林镜，你觉得人工智能发展得怎么样了？",
                    message_type="group",
                    group_id="group_789",
                    timestamp=time.time() - 500,
                    is_at_me=True
                ),
                Message(
                    message_id="msg_bot_1",
                    sender_id="bot_id",
                    content="我认为人工智能正在快速发展，已经在很多领域展现出惊人的能力。",
                    message_type="group",
                    group_id="group_789",
                    timestamp=time.time() - 450,
                    is_at_me=False,
                    is_from_self=True
                ),
                self.message  # 当前待回复消息
            ]
        )
        
        # 执行测试
        result = self.loop.run_until_complete(
            self.composer.compose(
                extended_chat_stream,
                self.message,
                self.thought,
                self.willingness_result
            )
        )
        
        # 验证结果
        self.assertIsInstance(result, dict)
        self.assertIn("reply", result)
        
        # 验证LLM调用参数包含上下文信息
        call_args = self.composer.llm_client.chat_completion.call_args[0][0]
        messages = call_args.get("messages", [])
        self.assertTrue(len(messages) > 2)  # 应该包含多条消息作为上下文

    def test_compose_with_retry(self):
        """测试生成回复失败后重试"""
        # 设置LLM首次调用失败
        self.composer.llm_client.chat_completion.side_effect = [
            Exception("模型调用失败"),  # 第一次失败
            {"message": "重试后的回复内容", "finish_reason": "stop"}  # 第二次成功
        ]
        
        # 执行测试
        result = self.loop.run_until_complete(
            self.composer.compose(
                self.chat_stream,
                self.message,
                self.thought,
                self.willingness_result
            )
        )
        
        # 验证结果
        self.assertIsInstance(result, dict)
        self.assertIn("reply", result)
        self.assertEqual(result["reply"], "重试后的回复内容")
        
        # 验证调用次数
        self.assertEqual(self.composer.llm_client.chat_completion.call_count, 2)
        
        # 重置side_effect
        self.composer.llm_client.chat_completion.side_effect = None
        self.composer.llm_client.chat_completion.return_value = {
            "message": "你好！很高兴再次与你交流。今天我感觉不错，希望你也一样。有什么我能帮助你的吗？",
            "finish_reason": "stop"
        }

    def test_compose_with_fallback(self):
        """测试多次重试失败后使用备用回复"""
        # 设置LLM始终调用失败
        self.composer.llm_client.chat_completion.side_effect = Exception("模型调用失败")
        
        # 执行测试
        result = self.loop.run_until_complete(
            self.composer.compose(
                self.chat_stream,
                self.message,
                self.thought,
                self.willingness_result
            )
        )
        
        # 验证结果
        self.assertIsInstance(result, dict)
        self.assertIn("reply", result)
        self.assertGreater(len(result["reply"]), 0)  # 应该有备用回复
        
        # 验证调用次数应该达到最大重试次数
        # 假设最大重试次数为3
        self.assertGreaterEqual(self.composer.llm_client.chat_completion.call_count, 1)
        
        # 重置side_effect
        self.composer.llm_client.chat_completion.side_effect = None
        self.composer.llm_client.chat_completion.return_value = {
            "message": "你好！很高兴再次与你交流。今天我感觉不错，希望你也一样。有什么我能帮助你的吗？",
            "finish_reason": "stop"
        }

    def test_message_formatting(self):
        """测试消息格式化"""
        # 执行测试
        result = self.loop.run_until_complete(
            self.composer.compose(
                self.chat_stream,
                self.message,
                self.thought,
                self.willingness_result
            )
        )
        
        # 验证结果
        self.assertIsInstance(result, dict)
        self.assertIn("reply", result)
        self.assertIn("messages", result)
        
        # 检查消息格式
        message_format = result.get("messages", {})
        self.assertIsInstance(message_format, dict)
        
        # 确保返回了必要的消息格式信息
        reply_types = ["text"]  # 至少应该有文本类型
        for reply_type in reply_types:
            if reply_type in message_format:
                self.assertIn("content", message_format[reply_type])

    def test_error_handling(self):
        """测试错误处理"""
        # 模拟各种依赖组件异常
        
        # 1. 情绪管理器异常
        self.composer.emotion_manager.get_current_emotion.side_effect = Exception("情绪获取失败")
        
        # 执行测试
        result = self.loop.run_until_complete(
            self.composer.compose(
                self.chat_stream,
                self.message,
                self.thought,
                self.willingness_result
            )
        )
        
        # 验证结果 - 即使出错也应该返回有效回复
        self.assertIsInstance(result, dict)
        self.assertIn("reply", result)
        self.assertGreater(len(result["reply"]), 0)
        
        # 清除异常设置
        self.composer.emotion_manager.get_current_emotion.side_effect = None
        
        # 2. 关系管理器异常
        self.composer.relationship_manager.get_relationship.side_effect = Exception("关系获取失败")
        
        # 执行测试
        result = self.loop.run_until_complete(
            self.composer.compose(
                self.chat_stream,
                self.message,
                self.thought,
                self.willingness_result
            )
        )
        
        # 验证结果 - 即使出错也应该返回有效回复
        self.assertIsInstance(result, dict)
        self.assertIn("reply", result)
        self.assertGreater(len(result["reply"]), 0)
        
        # 清除异常设置
        self.composer.relationship_manager.get_relationship.side_effect = None
        
        # 3. 记忆管理器异常
        self.composer.memory_manager.get_user_interaction_summary.side_effect = Exception("记忆获取失败")
        
        # 执行测试
        result = self.loop.run_until_complete(
            self.composer.compose(
                self.chat_stream,
                self.message,
                self.thought,
                self.willingness_result
            )
        )
        
        # 验证结果 - 即使出错也应该返回有效回复
        self.assertIsInstance(result, dict)
        self.assertIn("reply", result)
        self.assertGreater(len(result["reply"]), 0)


if __name__ == "__main__":
    unittest.main() 