#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
林镜(LingJing) - Thought模型测试
"""

import unittest
import json
import time
from datetime import datetime

from linjing.models.thought import Thought


class TestThought(unittest.TestCase):
    """Thought模型测试类"""

    def setUp(self):
        """测试准备：创建一个测试用的Thought对象"""
        self.message_id = "test_message_123"
        self.timestamp = time.time()
        self.understanding = {
            "intent": "question",
            "topic": "技术",
            "is_question": True,
            "sentiment": "neutral",
            "keywords": ["Python", "编程"]
        }
        self.emotional_response = {
            "primary_emotion": "curiosity",
            "emotion_intensity": 0.7,
            "description": "这让我感到好奇",
            "causes": ["技术话题", "提问"]
        }
        self.response_plan = {
            "priority": "medium",
            "strategy": "informative",
            "description": "我应该提供信息性回应",
            "should_reference_memory": True,
            "tone": "helpful",
            "key_points": ["回答问题", "讨论技术"]
        }
        self.raw_content = "Python编程难学吗？"
        self.metadata = {
            "sender_id": "user_456",
            "message_type": "group",
            "group_id": "group_789"
        }

        # 创建测试对象
        self.thought = Thought(
            message_id=self.message_id,
            timestamp=self.timestamp,
            understanding=self.understanding,
            emotional_response=self.emotional_response,
            response_plan=self.response_plan,
            raw_content=self.raw_content,
            metadata=self.metadata
        )

    def test_init_and_properties(self):
        """测试初始化和属性访问"""
        self.assertEqual(self.thought.message_id, self.message_id)
        self.assertEqual(self.thought.timestamp, self.timestamp)
        self.assertEqual(self.thought.understanding, self.understanding)
        self.assertEqual(self.thought.emotional_response, self.emotional_response)
        self.assertEqual(self.thought.response_plan, self.response_plan)
        self.assertEqual(self.thought.raw_content, self.raw_content)
        self.assertEqual(self.thought.metadata, self.metadata)
        
        # 测试thought_id自动生成
        self.assertTrue(self.thought.thought_id.startswith(f"thought_{self.message_id}_"))

    def test_serialization(self):
        """测试序列化和反序列化"""
        # 序列化
        serialized = self.thought.serialize()
        self.assertIsInstance(serialized, str)
        
        # 确保可以解析为JSON
        json_data = json.loads(serialized)
        self.assertEqual(json_data["message_id"], self.message_id)
        
        # 反序列化
        deserialized = Thought.deserialize(serialized)
        self.assertEqual(deserialized.message_id, self.message_id)
        self.assertEqual(deserialized.understanding, self.understanding)
        self.assertEqual(deserialized.emotional_response, self.emotional_response)

    def test_to_from_dict(self):
        """测试to_dict和from_dict方法"""
        # 转换为字典
        thought_dict = self.thought.to_dict()
        self.assertIsInstance(thought_dict, dict)
        self.assertEqual(thought_dict["message_id"], self.message_id)
        
        # 从字典创建
        new_thought = Thought.from_dict(thought_dict)
        self.assertEqual(new_thought.message_id, self.message_id)
        self.assertEqual(new_thought.raw_content, self.raw_content)

    def test_get_methods(self):
        """测试各种get方法"""
        self.assertEqual(self.thought.get_sender_id(), "user_456")
        self.assertEqual(self.thought.get_message_type(), "group")
        self.assertTrue(self.thought.is_group_message())
        self.assertEqual(self.thought.get_group_id(), "group_789")
        self.assertEqual(self.thought.get_intent(), "question")
        self.assertTrue(self.thought.is_question())
        self.assertEqual(self.thought.get_topic(), "技术")
        self.assertEqual(self.thought.get_primary_emotion(), "curiosity")
        self.assertEqual(self.thought.get_emotion_intensity(), 0.7)
        self.assertEqual(self.thought.get_response_priority(), "medium")
        self.assertEqual(self.thought.get_response_strategy(), "informative")
        self.assertEqual(self.thought.get_response_tone(), "helpful")
        self.assertEqual(self.thought.get_key_points(), ["回答问题", "讨论技术"])
        self.assertTrue(self.thought.should_reference_memory())

    def test_get_formatted_timestamp(self):
        """测试格式化时间戳方法"""
        formatted = self.thought.get_formatted_timestamp()
        self.assertIsInstance(formatted, str)
        
        # 测试自定义格式
        custom_format = "%Y/%m/%d"
        formatted_custom = self.thought.get_formatted_timestamp(custom_format)
        expected = datetime.fromtimestamp(self.timestamp).strftime(custom_format)
        self.assertEqual(formatted_custom, expected)

    def test_summarize(self):
        """测试摘要生成方法"""
        summary = self.thought.summarize()
        self.assertIsInstance(summary, str)
        
        # 检查摘要中是否包含关键信息
        self.assertIn("question", summary)
        self.assertIn("技术", summary)
        self.assertIn("curiosity", summary)
        self.assertIn("informative", summary)
        self.assertIn("medium", summary)

    def test_empty_fields(self):
        """测试空字段处理"""
        empty_thought = Thought(message_id="empty_test")
        
        # 测试默认值和空值处理
        self.assertEqual(empty_thought.get_intent(), "unknown")
        self.assertEqual(empty_thought.get_topic(), "unknown")
        self.assertEqual(empty_thought.get_primary_emotion(), "neutral")
        self.assertEqual(empty_thought.get_response_strategy(), "conversational")
        self.assertEqual(empty_thought.get_key_points(), [])
        self.assertFalse(empty_thought.should_reference_memory())
        
        # 确保摘要方法仍能工作
        summary = empty_thought.summarize()
        self.assertIsInstance(summary, str)


if __name__ == "__main__":
    unittest.main() 