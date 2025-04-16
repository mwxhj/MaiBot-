#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
林镜(LingJing) - WillingnessChecker组件测试
"""

import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import asyncio
import time
import json

from linjing.models.chat_stream import ChatStream, Message
from linjing.models.thought import Thought
from linjing.core.willingness_checker import WillingnessChecker


class TestWillingnessChecker(unittest.TestCase):
    """WillingnessChecker测试类"""

    def setUp(self):
        """测试准备"""
        # 创建WillingnessChecker实例
        self.checker = WillingnessChecker(
            base_willingness=0.5,
            mention_bonus=0.3,
            keyword_bonus=0.2,
            relationship_factor=0.15,
            emotion_factor=0.15,
            cooldown_minutes=5,
            daily_message_quota=100,
            message_interval_seconds=10
        )
        
        # 模拟依赖组件
        self.checker.config = MagicMock()
        self.checker.relationship_manager = AsyncMock()
        self.checker.emotion_manager = AsyncMock()
        self.checker.memory_manager = AsyncMock()
        
        # 设置模拟返回值
        self.checker.config.get.return_value = {
            "bot_name": "林镜",
            "keywords": ["林镜", "小镜", "机器人", "你好", "问题"]
        }
        
        self.checker.relationship_manager.get_relationship.return_value = {
            "strength": 0.6,
            "familiarity": 0.5,
            "trust": 0.7,
            "likability": 0.6
        }
        
        self.checker.emotion_manager.get_current_emotion.return_value = {
            "state": "平静",
            "valence": 0.5,  # 情绪效价
            "arousal": 0.3,  # 情绪唤醒度
            "dominance": 0.6,  # 情绪支配度
            "social_openness": 0.7,  # 社交开放度
        }
        
        self.checker.memory_manager.get_user_interaction_stats.return_value = {
            "total_interactions": 50,
            "recent_interactions": 5,
            "last_interaction_time": time.time() - 3600,
            "interaction_frequency": 0.6
        }
        
        # 创建测试消息对象
        self.group_message = Message(
            message_id="msg_123",
            sender_id="user_456",
            content="这是一条群聊测试消息",
            message_type="group",
            group_id="group_789",
            timestamp=time.time(),
            is_at_me=False
        )
        
        self.at_message = Message(
            message_id="msg_124",
            sender_id="user_456",
            content="@林镜 这是一条@消息",
            message_type="group",
            group_id="group_789",
            timestamp=time.time(),
            is_at_me=True
        )
        
        self.private_message = Message(
            message_id="msg_125",
            sender_id="user_456",
            content="这是一条私聊消息",
            message_type="private",
            timestamp=time.time(),
            is_at_me=False
        )
        
        self.keyword_message = Message(
            message_id="msg_126",
            sender_id="user_456",
            content="林镜，你能回答我一个问题吗？",
            message_type="group",
            group_id="group_789",
            timestamp=time.time(),
            is_at_me=False
        )
        
        # 创建测试思考对象
        self.thought = Thought(
            message_id="msg_123",
            understanding="这是用户发送的普通群聊消息",
            emotional_response={
                "primary": "neutral",
                "secondary": "interest",
                "intensity": 0.3
            },
            reasoning="用户只是在群里发言，没有特别需要回应的内容",
            social_context={
                "is_direct_interaction": False,
                "requires_response": False,
                "conversation_topic": "general",
                "topic_relevance": "low"
            },
            response_considerations={
                "should_respond": False,
                "response_type": None,
                "priority": "low",
                "key_points": []
            }
        )
        
        self.direct_thought = Thought(
            message_id="msg_124",
            understanding="用户@了机器人并询问问题",
            emotional_response={
                "primary": "interest",
                "secondary": "desire_to_help",
                "intensity": 0.7
            },
            reasoning="用户直接询问机器人，需要给予回应",
            social_context={
                "is_direct_interaction": True,
                "requires_response": True,
                "conversation_topic": "question",
                "topic_relevance": "high"
            },
            response_considerations={
                "should_respond": True,
                "response_type": "answer",
                "priority": "high",
                "key_points": ["提供帮助", "回答问题"]
            }
        )
        
        # 创建测试聊天流
        self.chat_stream = ChatStream(
            stream_id="test_stream",
            messages=[
                Message(
                    message_id="msg_121",
                    sender_id="user_789",
                    content="之前的一条消息",
                    message_type="group",
                    group_id="group_789",
                    timestamp=time.time() - 300,
                    is_at_me=False
                ),
                self.group_message
            ]
        )
        
        # 运行初始化
        self.loop = asyncio.get_event_loop()
        self.loop.run_until_complete(self.checker.initialize())

    def test_init(self):
        """测试初始化"""
        self.assertIsNotNone(self.checker.config)
        self.assertIsNotNone(self.checker.relationship_manager)
        self.assertIsNotNone(self.checker.emotion_manager)
        self.assertIsNotNone(self.checker.memory_manager)
        self.assertEqual(self.checker.base_willingness, 0.5)
        self.assertEqual(self.checker.mention_bonus, 0.3)
        self.assertEqual(self.checker.keyword_bonus, 0.2)
        self.assertEqual(self.checker.relationship_factor, 0.15)
        self.assertEqual(self.checker.emotion_factor, 0.15)
        self.assertEqual(self.checker.cooldown_minutes, 5)
        self.assertEqual(self.checker.daily_message_quota, 100)
        self.assertEqual(self.checker.message_interval_seconds, 10)
        self.assertIsInstance(self.checker._last_response_time, dict)
        self.assertIsInstance(self.checker._daily_message_count, dict)
        self.assertIsInstance(self.checker._last_message_time, dict)

    def test_check_at_message(self):
        """测试检查@消息"""
        # 执行测试
        result = self.loop.run_until_complete(
            self.checker.check(self.chat_stream, self.at_message, self.direct_thought)
        )
        
        # 验证结果
        self.assertIsInstance(result, dict)
        self.assertTrue(result["should_express"])
        self.assertGreaterEqual(result["willingness"], 0.9)  # @消息应有较高的意愿分数
        self.assertEqual(result["attitude"], "friendly")  # @消息应该使用友好态度
        
        # 验证依赖组件调用
        self.checker.relationship_manager.get_relationship.assert_called_once()
        self.checker.emotion_manager.get_current_emotion.assert_called_once()

    def test_check_private_message(self):
        """测试检查私聊消息"""
        # 执行测试
        result = self.loop.run_until_complete(
            self.checker.check(self.chat_stream, self.private_message, self.direct_thought)
        )
        
        # 验证结果
        self.assertIsInstance(result, dict)
        self.assertTrue(result["should_express"])
        self.assertGreaterEqual(result["willingness"], 0.7)  # 私聊消息应有较高的意愿分数
        
        # 验证依赖组件调用
        self.checker.relationship_manager.get_relationship.assert_called_once()
        self.checker.emotion_manager.get_current_emotion.assert_called_once()

    def test_check_keyword_message(self):
        """测试检查包含关键词的消息"""
        # 执行测试
        result = self.loop.run_until_complete(
            self.checker.check(self.chat_stream, self.keyword_message, self.thought)
        )
        
        # 验证结果
        self.assertIsInstance(result, dict)
        self.assertTrue(result["should_express"])
        self.assertGreaterEqual(result["willingness"], 0.7)  # 包含关键词应提高意愿分数
        
        # 验证关键词检测逻辑
        # 重置思考对象认为不需要回应
        thought = Thought(
            message_id="msg_126",
            understanding="用户在群聊中提到了机器人的名字",
            emotional_response={
                "primary": "neutral",
                "secondary": "interest",
                "intensity": 0.4
            },
            reasoning="用户提到了机器人，但没有直接互动",
            social_context={
                "is_direct_interaction": False,
                "requires_response": False,
                "conversation_topic": "general",
                "topic_relevance": "medium"
            },
            response_considerations={
                "should_respond": False,  # 思考认为不需要回应
                "response_type": None,
                "priority": "low",
                "key_points": []
            }
        )
        
        # 再次执行测试
        result = self.loop.run_until_complete(
            self.checker.check(self.chat_stream, self.keyword_message, thought)
        )
        
        # 验证结果 - 即使思考认为不需要回应，但因为关键词会提高意愿
        self.assertTrue(result["should_express"])

    def test_check_regular_message(self):
        """测试检查普通消息"""
        # 执行测试
        result = self.loop.run_until_complete(
            self.checker.check(self.chat_stream, self.group_message, self.thought)
        )
        
        # 验证结果
        self.assertIsInstance(result, dict)
        # 普通消息且思考不建议回应，应该不表达
        self.assertFalse(result["should_express"])
        
        # 修改思考对象让它认为需要回应
        thought = Thought(
            message_id="msg_123",
            understanding="用户在群聊中发言，内容可能需要回应",
            emotional_response={
                "primary": "interest",
                "secondary": "desire_to_help",
                "intensity": 0.5
            },
            reasoning="用户在讨论一个与机器人相关的话题",
            social_context={
                "is_direct_interaction": False,
                "requires_response": True,
                "conversation_topic": "technology",
                "topic_relevance": "high"
            },
            response_considerations={
                "should_respond": True,  # 思考认为需要回应
                "response_type": "opinion",
                "priority": "medium",
                "key_points": ["提供见解"]
            }
        )
        
        # 再次执行测试
        result = self.loop.run_until_complete(
            self.checker.check(self.chat_stream, self.group_message, thought)
        )
        
        # 验证结果 - 思考认为需要回应，应该表达
        self.assertTrue(result["should_express"])

    def test_cooldown_mechanism(self):
        """测试冷却机制"""
        # 设置上次回复时间
        group_id = self.group_message.group_id
        self.checker._last_response_time[group_id] = time.time() - 60  # 1分钟前回复过
        
        # 执行测试
        result = self.loop.run_until_complete(
            self.checker.check(self.chat_stream, self.group_message, self.direct_thought)
        )
        
        # 验证结果
        self.assertIsInstance(result, dict)
        self.assertFalse(result["should_express"])  # 冷却期间不应表达
        self.assertIn("cooldown", result["reason"].lower())
        
        # 设置@消息，应该无视冷却
        result = self.loop.run_until_complete(
            self.checker.check(self.chat_stream, self.at_message, self.direct_thought)
        )
        
        # 验证结果
        self.assertTrue(result["should_express"])  # @消息无视冷却
        
        # 测试冷却时间过后
        self.checker._last_response_time[group_id] = time.time() - 360  # 6分钟前，超出冷却时间
        
        # 再次执行测试
        result = self.loop.run_until_complete(
            self.checker.check(self.chat_stream, self.group_message, self.direct_thought)
        )
        
        # 验证结果
        self.assertTrue(result["should_express"])  # 冷却时间过后可以表达

    def test_message_quota(self):
        """测试消息配额机制"""
        # 设置今日消息数量已达上限
        today = time.strftime("%Y-%m-%d")
        self.checker._daily_message_count[today] = self.checker.daily_message_quota
        
        # 执行测试（非@消息）
        result = self.loop.run_until_complete(
            self.checker.check(self.chat_stream, self.group_message, self.direct_thought)
        )
        
        # 验证结果
        self.assertIsInstance(result, dict)
        self.assertFalse(result["should_express"])  # 配额用尽不应表达
        self.assertIn("配额", result["reason"])
        
        # 测试@消息，应该无视配额限制
        result = self.loop.run_until_complete(
            self.checker.check(self.chat_stream, self.at_message, self.direct_thought)
        )
        
        # 验证结果
        self.assertTrue(result["should_express"])  # @消息无视配额限制
        
        # 重置配额
        self.checker._daily_message_count[today] = 0
        
        # 再次执行测试
        result = self.loop.run_until_complete(
            self.checker.check(self.chat_stream, self.group_message, self.direct_thought)
        )
        
        # 验证结果
        self.assertTrue(result["should_express"])  # 配额充足可以表达

    def test_message_interval(self):
        """测试消息间隔机制"""
        # 设置上次消息时间
        group_id = self.group_message.group_id
        self.checker._last_message_time[group_id] = time.time() - 5  # 5秒前发过消息
        
        # 执行测试（非@消息）
        result = self.loop.run_until_complete(
            self.checker.check(self.chat_stream, self.group_message, self.direct_thought)
        )
        
        # 验证结果
        self.assertIsInstance(result, dict)
        self.assertFalse(result["should_express"])  # 间隔不足不应表达
        self.assertIn("间隔", result["reason"])
        
        # 测试@消息，应该无视间隔限制
        result = self.loop.run_until_complete(
            self.checker.check(self.chat_stream, self.at_message, self.direct_thought)
        )
        
        # 验证结果
        self.assertTrue(result["should_express"])  # @消息无视间隔限制
        
        # 设置足够的间隔
        self.checker._last_message_time[group_id] = time.time() - 15  # 15秒前，大于间隔
        
        # 再次执行测试
        result = self.loop.run_until_complete(
            self.checker.check(self.chat_stream, self.group_message, self.direct_thought)
        )
        
        # 验证结果
        self.assertTrue(result["should_express"])  # 间隔足够可以表达

    def test_relationship_impact(self):
        """测试关系对意愿的影响"""
        # 设置亲密关系
        close_relationship = {
            "strength": 0.9,
            "familiarity": 0.9,
            "trust": 0.9,
            "likability": 0.9
        }
        self.checker.relationship_manager.get_relationship.return_value = close_relationship
        
        # 执行测试
        result = self.loop.run_until_complete(
            self.checker.check(self.chat_stream, self.group_message, self.thought)
        )
        
        # 记录意愿分数
        high_willingness = result["willingness"]
        
        # 设置疏远关系
        distant_relationship = {
            "strength": 0.1,
            "familiarity": 0.1,
            "trust": 0.1,
            "likability": 0.1
        }
        self.checker.relationship_manager.get_relationship.return_value = distant_relationship
        
        # 再次执行测试
        result = self.loop.run_until_complete(
            self.checker.check(self.chat_stream, self.group_message, self.thought)
        )
        
        # 验证结果
        self.assertLess(result["willingness"], high_willingness)  # 关系疏远应降低意愿

    def test_emotion_impact(self):
        """测试情绪对意愿的影响"""
        # 设置积极情绪
        positive_emotion = {
            "state": "愉悦",
            "valence": 0.9,  # 高效价（积极）
            "arousal": 0.7,  # 高唤醒度
            "dominance": 0.8,  # 高支配度
            "social_openness": 0.9,  # 高社交开放度
        }
        self.checker.emotion_manager.get_current_emotion.return_value = positive_emotion
        
        # 执行测试
        result = self.loop.run_until_complete(
            self.checker.check(self.chat_stream, self.group_message, self.thought)
        )
        
        # 记录意愿分数
        high_willingness = result["willingness"]
        
        # 设置消极情绪
        negative_emotion = {
            "state": "沮丧",
            "valence": 0.1,  # 低效价（消极）
            "arousal": 0.2,  # 低唤醒度
            "dominance": 0.2,  # 低支配度
            "social_openness": 0.1,  # 低社交开放度
        }
        self.checker.emotion_manager.get_current_emotion.return_value = negative_emotion
        
        # 再次执行测试
        result = self.loop.run_until_complete(
            self.checker.check(self.chat_stream, self.group_message, self.thought)
        )
        
        # 验证结果
        self.assertLess(result["willingness"], high_willingness)  # 消极情绪应降低意愿

    def test_attitude_selection(self):
        """测试态度选择"""
        # 测试不同意愿分数对应的态度
        test_cases = [
            # 高意愿，应选择友好态度
            {"emotion": {"valence": 0.8, "social_openness": 0.8}, "expected_attitude": "friendly"},
            # 中等意愿，应选择中立态度
            {"emotion": {"valence": 0.5, "social_openness": 0.5}, "expected_attitude": "neutral"},
            # 低意愿，应选择保留态度
            {"emotion": {"valence": 0.2, "social_openness": 0.2}, "expected_attitude": "reserved"}
        ]
        
        for case in test_cases:
            # 设置情绪
            self.checker.emotion_manager.get_current_emotion.return_value = {
                "state": "测试",
                "valence": case["emotion"]["valence"],
                "arousal": 0.5,
                "dominance": 0.5,
                "social_openness": case["emotion"]["social_openness"]
            }
            
            # 执行测试
            result = self.loop.run_until_complete(
                self.checker.check(self.chat_stream, self.group_message, self.direct_thought)
            )
            
            # 验证结果
            self.assertEqual(result["attitude"], case["expected_attitude"])

    def test_error_handling(self):
        """测试错误处理"""
        # 设置关系管理器抛出异常
        self.checker.relationship_manager.get_relationship.side_effect = Exception("关系获取失败")
        
        # 执行测试
        result = self.loop.run_until_complete(
            self.checker.check(self.chat_stream, self.group_message, self.thought)
        )
        
        # 验证结果
        self.assertIsInstance(result, dict)
        self.assertIn("willingness", result)  # 即使出错也应返回意愿分数
        self.assertIn("should_express", result)
        self.assertIn("attitude", result)
        
        # 清除异常设置
        self.checker.relationship_manager.get_relationship.side_effect = None
        
        # 设置情绪管理器抛出异常
        self.checker.emotion_manager.get_current_emotion.side_effect = Exception("情绪获取失败")
        
        # 执行测试
        result = self.loop.run_until_complete(
            self.checker.check(self.chat_stream, self.group_message, self.thought)
        )
        
        # 验证结果
        self.assertIsInstance(result, dict)
        self.assertIn("willingness", result)  # 即使出错也应返回意愿分数
        self.assertIn("should_express", result)
        self.assertIn("attitude", result)


if __name__ == "__main__":
    unittest.main() 