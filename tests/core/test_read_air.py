#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
林镜(LingJing) - ReadAirProcessor组件测试
"""

import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import asyncio
import json
import time

from linjing.models.chat_stream import ChatStream, Message
from linjing.core.read_air import ReadAirProcessor


class TestReadAirProcessor(unittest.TestCase):
    """ReadAirProcessor测试类"""

    def setUp(self):
        """测试准备"""
        # 创建ReadAirProcessor实例
        self.processor = ReadAirProcessor()
        
        # 模拟依赖组件
        self.processor.config = MagicMock()
        self.processor.llm_client = AsyncMock()
        self.processor.relationship_manager = AsyncMock()
        
        # 设置模拟返回值
        self.processor.config.get.return_value = {
            "name": "林镜",
            "bot_id": "bot_12345678",
            "read_air": {
                "context_window": 10,
                "cooldown_seconds": 60,
                "group_reply_threshold": 0.6,
                "private_reply_threshold": 0.4
            }
        }
        
        # 模拟LLM分析结果
        self.processor.llm_client.analyze_social_intent.return_value = {
            "is_direct_interaction": True,
            "requires_response": True,
            "intent": "greeting",
            "confidence": 0.9
        }
        
        # 创建测试聊天流
        self.chat_stream = ChatStream()
        self.chat_stream.set_context("stream_id", "test_stream")
        
        # 添加历史消息
        current_time = time.time()
        for i in range(5):
            self.chat_stream.add_message(
                Message(
                    message_id=f"msg_{i}",
                    sender_id=f"user_{i % 3}",  # 3个用户轮流发言
                    content=f"测试消息 {i}",
                    message_type="group",
                    group_id="group_123456",
                    timestamp=current_time - (5 - i) * 60,  # 消息间隔1分钟
                    is_at_me=False
                )
            )
        
        # 创建测试消息
        self.test_message = Message(
            message_id="test_msg_id",
            sender_id="user_1",
            content="你好，林镜！",
            message_type="group",
            group_id="group_123456",
            timestamp=current_time,
            is_at_me=False
        )
        
        self.at_message = Message(
            message_id="at_msg_id",
            sender_id="user_1",
            content="[CQ:at,qq=bot_12345678] 你好，林镜！",
            message_type="group",
            group_id="group_123456",
            timestamp=current_time,
            is_at_me=True
        )
        
        self.private_message = Message(
            message_id="private_msg_id",
            sender_id="user_1",
            content="你好，林镜！",
            message_type="private",
            group_id=None,
            timestamp=current_time,
            is_at_me=False
        )
        
        self.mention_message = Message(
            message_id="mention_msg_id",
            sender_id="user_1",
            content="林镜你好！",
            message_type="group",
            group_id="group_123456",
            timestamp=current_time,
            is_at_me=False
        )
        
        # 运行初始化
        self.loop = asyncio.get_event_loop()
        self.loop.run_until_complete(self.processor.initialize())

    def test_init(self):
        """测试初始化"""
        self.assertIsNotNone(self.processor.config)
        self.assertIsNotNone(self.processor.llm_client)
        self.assertEqual(self.processor.context_window, 10)
        self.assertEqual(self.processor.cooldown_seconds, 60)
        self.assertEqual(self.processor.group_reply_threshold, 0.6)
        self.assertEqual(self.processor.private_reply_threshold, 0.4)
        self.assertIsInstance(self.processor.last_reply_time, dict)

    def test_process_group_message(self):
        """测试处理群消息"""
        # 执行测试
        result = self.loop.run_until_complete(
            self.processor.process(self.test_message, self.chat_stream)
        )
        
        # 验证结果
        self.assertIsInstance(result, dict)
        self.assertIn("should_reply", result)
        self.assertIn("social_intent", result)
        self.assertIn("relevant_context", result)
        
        # 验证LLM被调用
        self.processor.llm_client.analyze_social_intent.assert_called_once()

    def test_process_at_message(self):
        """测试处理@消息"""
        # 执行测试
        result = self.loop.run_until_complete(
            self.processor.process(self.at_message, self.chat_stream)
        )
        
        # 验证结果 - @消息应该直接回复
        self.assertIsInstance(result, dict)
        self.assertTrue(result["should_reply"])
        self.assertIn("social_intent", result)
        self.assertIn("relevant_context", result)

    def test_process_private_message(self):
        """测试处理私聊消息"""
        # 执行测试
        result = self.loop.run_until_complete(
            self.processor.process(self.private_message, self.chat_stream)
        )
        
        # 验证结果 - 私聊消息应该有更低的回复阈值
        self.assertIsInstance(result, dict)
        self.assertIn("should_reply", result)
        self.assertIn("social_intent", result)
        self.assertIn("relevant_context", result)
        
        # 验证使用了私聊阈值
        # 注意：这里我们不能直接验证阈值比较的结果，因为它发生在内部方法中
        # 但我们可以确认正确的LLM调用发生了
        self.processor.llm_client.analyze_social_intent.assert_called_once()

    def test_process_mention_message(self):
        """测试处理提及机器人名字的消息"""
        # 设置LLM分析结果，确保提及被正确识别
        self.processor.llm_client.analyze_social_intent.return_value = {
            "is_direct_interaction": True,
            "requires_response": True,
            "intent": "greeting",
            "confidence": 0.85,
            "contains_name_mention": True
        }
        
        # 执行测试
        result = self.loop.run_until_complete(
            self.processor.process(self.mention_message, self.chat_stream)
        )
        
        # 验证结果 - 提及机器人名字的消息应该有更高的回复概率
        self.assertIsInstance(result, dict)
        self.assertTrue(result["should_reply"])
        self.assertIn("social_intent", result)
        self.assertIn("relevant_context", result)
        self.assertTrue(result["social_intent"]["contains_name_mention"])

    def test_cooldown_period(self):
        """测试冷却期功能"""
        # 记录当前组的最后回复时间
        group_id = self.test_message.group_id
        self.processor.last_reply_time[group_id] = time.time()
        
        # 执行测试
        result = self.loop.run_until_complete(
            self.processor.process(self.test_message, self.chat_stream)
        )
        
        # 验证结果 - 在冷却期内应该不回复
        self.assertFalse(result["should_reply"])
        self.assertEqual(result.get("reason"), "cooldown")
        
        # 重置冷却期为已过期
        self.processor.last_reply_time[group_id] = time.time() - self.processor.cooldown_seconds - 10
        
        # 重新执行测试
        result = self.loop.run_until_complete(
            self.processor.process(self.test_message, self.chat_stream)
        )
        
        # 验证结果 - 冷却期过后应该可以回复
        self.assertNotEqual(result.get("reason"), "cooldown")
        self.processor.llm_client.analyze_social_intent.assert_called()

    def test_build_context(self):
        """测试构建上下文"""
        # 执行测试
        context = self.processor._build_context(self.test_message, self.chat_stream)
        
        # 验证结果
        self.assertIsInstance(context, list)
        self.assertLessEqual(len(context), self.processor.context_window)
        
        # 验证上下文中包含了历史消息
        found_history = False
        for msg in context:
            if msg["message_id"] != self.test_message.message_id:
                found_history = True
                break
        self.assertTrue(found_history)
        
        # 验证当前消息在上下文中
        found_current = False
        for msg in context:
            if msg["message_id"] == self.test_message.message_id:
                found_current = True
                break
        self.assertTrue(found_current)

    def test_analyze_social_intent(self):
        """测试社交意图分析"""
        # 构建上下文
        context = self.processor._build_context(self.test_message, self.chat_stream)
        
        # 执行测试
        intent = self.loop.run_until_complete(
            self.processor._analyze_social_intent(self.test_message, context)
        )
        
        # 验证结果
        self.assertIsInstance(intent, dict)
        self.assertIn("is_direct_interaction", intent)
        self.assertIn("requires_response", intent)
        self.assertIn("intent", intent)
        self.assertIn("confidence", intent)
        
        # 验证LLM被调用
        self.processor.llm_client.analyze_social_intent.assert_called_once()

    def test_should_reply_logic(self):
        """测试回复决策逻辑"""
        # 测试@消息
        self.assertTrue(
            self.processor._should_reply({
                "is_direct_interaction": True,
                "requires_response": True,
                "intent": "greeting",
                "confidence": 0.5
            }, self.at_message)
        )
        
        # 测试高置信度消息
        self.assertTrue(
            self.processor._should_reply({
                "is_direct_interaction": True,
                "requires_response": True,
                "intent": "greeting",
                "confidence": 0.9
            }, self.test_message)
        )
        
        # 测试低置信度消息
        self.assertFalse(
            self.processor._should_reply({
                "is_direct_interaction": False,
                "requires_response": False,
                "intent": "chatting",
                "confidence": 0.3
            }, self.test_message)
        )
        
        # 测试私聊消息
        self.assertTrue(
            self.processor._should_reply({
                "is_direct_interaction": True,
                "requires_response": True,
                "intent": "greeting",
                "confidence": 0.5
            }, self.private_message)
        )
        
        # 测试名字提及
        self.assertTrue(
            self.processor._should_reply({
                "is_direct_interaction": True,
                "requires_response": True,
                "intent": "greeting",
                "confidence": 0.5,
                "contains_name_mention": True
            }, self.test_message)
        )

    def test_relationship_influence(self):
        """测试关系影响"""
        # 设置关系管理器返回值
        self.processor.relationship_manager.get_relationship.return_value = {
            "familiarity": 0.8,
            "trust": 0.7,
            "likability": 0.9
        }
        
        # 将关系影响配置设为可用
        self.processor.config.get.return_value = {
            "name": "林镜",
            "bot_id": "bot_12345678",
            "read_air": {
                "context_window": 10,
                "cooldown_seconds": 60,
                "group_reply_threshold": 0.6,
                "private_reply_threshold": 0.4,
                "use_relationship_bias": True
            }
        }
        
        # 执行测试
        result = self.loop.run_until_complete(
            self.processor.process(self.test_message, self.chat_stream)
        )
        
        # 验证结果 - 因为关系很好，所以应该更倾向于回复
        self.assertTrue(result["should_reply"])
        
        # 验证关系管理器被调用
        self.processor.relationship_manager.get_relationship.assert_called_once()

    def test_error_handling(self):
        """测试错误处理"""
        # 设置LLM抛出异常
        self.processor.llm_client.analyze_social_intent.side_effect = Exception("测试异常")
        
        # 执行测试
        result = self.loop.run_until_complete(
            self.processor.process(self.test_message, self.chat_stream)
        )
        
        # 验证结果 - 应该返回安全的默认值
        self.assertIsInstance(result, dict)
        self.assertIn("should_reply", result)
        self.assertFalse(result["should_reply"])  # 出错时默认不回复
        self.assertIn("social_intent", result)
        self.assertIn("error", result)  # 应该包含错误信息

    def test_bot_self_message(self):
        """测试机器人自己的消息"""
        # 创建机器人自己的消息
        bot_message = Message(
            message_id="bot_msg_id",
            sender_id=self.processor.config.get()["bot_id"],  # 使用机器人ID作为发送者
            content="我是机器人发的消息",
            message_type="group",
            group_id="group_123456",
            timestamp=time.time(),
            is_at_me=False
        )
        
        # 执行测试
        result = self.loop.run_until_complete(
            self.processor.process(bot_message, self.chat_stream)
        )
        
        # 验证结果 - 不应该回复自己的消息
        self.assertFalse(result["should_reply"])
        self.assertEqual(result.get("reason"), "self_message")
        
        # 验证LLM没有被调用
        self.processor.llm_client.analyze_social_intent.assert_not_called()


if __name__ == "__main__":
    unittest.main() 