#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
测试林镜(LingJing)中回应意愿检查器（WillingnessChecker）的功能
"""

import asyncio
import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch, AsyncMock
import sys

from linjing.core.willingness_checker import WillingnessChecker, get_willingness_checker
from linjing.models.message_models import Message, Sender, MessageContent
from linjing.models import ChatStream
from linjing.models.relationship_models import Relationship, Impression


class TestWillingnessChecker(unittest.TestCase):
    """测试WillingnessChecker类的功能"""

    def setUp(self):
        """测试前的设置"""
        self.willingness_checker = WillingnessChecker()
        
        # 模拟配置
        self.mock_config = {
            'willingness': {
                'base_level': 0.8,
                'mood_influence': 0.3,
                'personality_weight': 0.4,
                'response_bias': {
                    'questions': 0.9
                },
                'trigger_keywords': {
                    '林镜': 0.9
                }
            }
        }
        
        # 模拟情感管理器
        self.mock_emotion_manager = MagicMock()
        self.mock_emotion_manager.get_current_emotion.return_value = {
            "emotion": "joy",
            "intensity": 0.7
        }
        
        # 模拟关系管理器
        self.mock_relationship_manager = MagicMock()
        self.mock_relationship_manager.get_relationship.return_value = self._create_mock_relationship()
        
        # 创建一个模拟的关系模型
    def _create_mock_relationship(self):
        """创建模拟的关系对象"""
        impression = Impression(
            familiarity=0.6,
            trust=0.7,
            likability=0.8,
            respect=0.5
        )
        relationship = MagicMock(spec=Relationship)
        relationship.calculate_relationship_strength.return_value = 0.7
        relationship.impressions = {"self": impression}
        return relationship

    def create_test_message(self, content="你好", message_type="private", at_me=False):
        """创建测试消息"""
        sender = Sender(user_id=123456, nickname="测试用户")
        
        # 创建MessageContent对象并设置raw_content
        message_content = MessageContent()
        message_content.raw_content = content
        
        # 添加文本消息段
        message_content.add_text(content)
        
        message = Message(
            id="test_msg_id",
            type="message",
            message_type=message_type,
            sender=sender,
            content=message_content,
            time=datetime.now(),
            self_id=654321
        )
        
        # 添加@我的属性
        message.is_at_me = at_me
        
        if message_type == "group":
            message.group_id = 789012
        
        return message

    def create_thought_content(self, intent_type="statements", emotional_type="neutral"):
        """创建思维内容"""
        return {
            "intent": {
                "type": intent_type,
                "confidence": 0.9
            },
            "emotional_response": {
                "type": emotional_type,
                "intensity": 0.6
            }
        }
    
    def mock_imports(self):
        """模拟导入"""
        # 创建模拟的get_relationship_manager函数
        async def mock_get_relationship_manager():
            return self.mock_relationship_manager
            
        # 创建模拟的get_emotion_manager函数
        async def mock_get_emotion_manager():
            return self.mock_emotion_manager
            
        # 创建模拟的get_config函数
        async def mock_get_config():
            return self.mock_config
            
        # 替换模块和函数
        sys.modules['linjing.relationship'] = MagicMock()
        sys.modules['linjing.relationship'].get_relationship_manager = mock_get_relationship_manager
        
        sys.modules['linjing.emotion'] = MagicMock()
        sys.modules['linjing.emotion'].get_emotion_manager = mock_get_emotion_manager
        
        sys.modules['linjing.config'] = MagicMock()
        sys.modules['linjing.config'].get_config = mock_get_config
        
        # 替换_check_keywords方法，使其能处理MessageContent对象
        original_check_keywords = self.willingness_checker._check_keywords
        
        async def mock_check_keywords(content):
            if isinstance(content, MessageContent):
                # 使用raw_content或get_plain_text()方法获取文本内容
                return await original_check_keywords(content.raw_content or content.get_plain_text())
            return await original_check_keywords(content)
            
        self.willingness_checker._check_keywords = mock_check_keywords
        
    async def async_test_initialize(self):
        """测试初始化方法"""
        # 模拟导入
        self.mock_imports()
        
        # 初始化
        await self.willingness_checker.initialize()
        
        # 验证配置是否正确加载
        self.assertEqual(self.willingness_checker.base_willingness, 0.8)
        self.assertEqual(self.willingness_checker.mood_influence, 0.3)
        self.assertEqual(self.willingness_checker.personality_weight, 0.4)
        self.assertEqual(self.willingness_checker.response_bias["questions"], 0.9)
        self.assertEqual(self.willingness_checker.trigger_keywords["林镜"], 0.9)
    
    async def async_test_check_willingness_private(self):
        """测试私聊消息的回应意愿检查"""
        # 模拟导入
        self.mock_imports()
        
        # 初始化
        await self.willingness_checker.initialize()
        
        # 测试普通私聊消息
        message = self.create_test_message(content="你好", message_type="private")
        thought_content = self.create_thought_content(intent_type="greetings")
        chat_stream = ChatStream()
        
        will_respond, response_info = await self.willingness_checker.check_willingness(
            message, thought_content, chat_stream
        )
        
        # 验证结果
        self.assertIsInstance(will_respond, bool)
        self.assertIn("attitude", response_info)
        self.assertIn("reason", response_info)
        
        # 测试包含关键词的消息
        message = self.create_test_message(content="林镜你好", message_type="private")
        will_respond, response_info = await self.willingness_checker.check_willingness(
            message, thought_content, chat_stream
        )
        
        # 应该有更高的回应意愿
        self.assertTrue(will_respond)
    
    async def async_test_check_willingness_group(self):
        """测试群聊消息的回应意愿检查"""
        # 模拟导入
        self.mock_imports()
        
        # 初始化
        await self.willingness_checker.initialize()
        
        # 测试普通群聊消息
        message = self.create_test_message(content="大家好", message_type="group")
        thought_content = self.create_thought_content(intent_type="greetings")
        chat_stream = ChatStream()
        
        will_respond, response_info = await self.willingness_checker.check_willingness(
            message, thought_content, chat_stream
        )
        
        # 验证结果（群聊中普通消息可能不回应）
        self.assertIsInstance(will_respond, bool)
        
        # 测试@我的群聊消息
        message = self.create_test_message(content="@林镜 你好", message_type="group", at_me=True)
        will_respond, response_info = await self.willingness_checker.check_willingness(
            message, thought_content, chat_stream
        )
        
        # 应该会回应@我的消息
        self.assertTrue(will_respond)
    
    async def async_test_determine_attitude(self):
        """测试态度确定方法"""
        # 模拟导入
        self.mock_imports()
        
        # 初始化
        await self.willingness_checker.initialize()
        
        # 测试高意愿状态
        thought_content = self.create_thought_content(emotional_type="joy")
        attitude = await self.willingness_checker._determine_attitude(0.9, thought_content)
        self.assertIn(attitude, ["friendly", "neutral", "reserved"])
        
        # 测试低意愿状态
        thought_content = self.create_thought_content(emotional_type="anger")
        attitude = await self.willingness_checker._determine_attitude(0.4, thought_content)
        self.assertIn(attitude, ["friendly", "neutral", "reserved"])
    
    async def async_test_singleton(self):
        """测试单例实例获取"""
        # 模拟导入
        self.mock_imports()
        
        # 测试单例
        instance1 = await get_willingness_checker()
        instance2 = await get_willingness_checker()
        
        self.assertIs(instance1, instance2)

    def test_all(self):
        """运行所有异步测试"""
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.async_test_initialize())
        loop.run_until_complete(self.async_test_check_willingness_private())
        loop.run_until_complete(self.async_test_check_willingness_group())
        loop.run_until_complete(self.async_test_determine_attitude())
        loop.run_until_complete(self.async_test_singleton())


if __name__ == "__main__":
    print("开始测试WillingnessChecker...")
    unittest.main() 