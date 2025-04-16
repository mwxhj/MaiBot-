#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
林镜(LingJing) - 情绪管理器测试
"""

import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import asyncio
import json
import time

from linjing.emotion.emotion_manager import EmotionManager
from linjing.models.chat_stream import Message


class TestEmotionManager(unittest.TestCase):
    """EmotionManager测试类"""

    def setUp(self):
        """测试准备"""
        # 创建EmotionManager实例
        self.emotion_manager = EmotionManager()
        
        # 模拟依赖组件
        self.emotion_manager.config = MagicMock()
        self.emotion_manager.llm_client = AsyncMock()
        self.emotion_manager.storage = MagicMock()
        
        # 设置模拟返回值
        self.emotion_manager.config.get.return_value = {
            "emotion": {
                "base_state": "平静",
                "base_valence": 0.6,
                "base_arousal": 0.4,
                "base_dominance": 0.5,
                "base_social_openness": 0.7,
                "decay_rate": 0.05,
                "intensity_bounds": {
                    "min": 0.0,
                    "max": 1.0
                },
                "valid_emotions": [
                    "平静", "愉悦", "兴奋", "好奇", "惊讶",
                    "困惑", "焦虑", "沮丧", "失落", "不满"
                ]
            }
        }
        
        # 模拟LLM分析情绪影响
        self.emotion_manager.llm_client.analyze_emotional_impact.return_value = {
            "state_change": "愉悦",
            "valence_change": 0.2,
            "arousal_change": 0.1,
            "dominance_change": 0.0,
            "social_openness_change": 0.1,
            "intensity": 0.7,
            "triggers": ["表达善意", "亲切问候"],
            "reasoning": "用户友好的问候增加了愉悦感和社交开放度"
        }
        
        # 模拟存储的当前情绪状态
        self.emotion_manager.storage.get.return_value = {
            "state": "平静",
            "valence": 0.6,
            "arousal": 0.4,
            "dominance": 0.5,
            "social_openness": 0.7,
            "updated_at": time.time() - 3600
        }
        
        # 创建测试消息
        self.message = Message(
            message_id="msg_123",
            sender_id="user_456",
            content="你好，林镜！最近怎么样？",
            message_type="group",
            group_id="group_789",
            timestamp=time.time(),
            is_at_me=True
        )
        
        # 运行初始化
        self.loop = asyncio.get_event_loop()
        self.loop.run_until_complete(self.emotion_manager.initialize())

    def test_init(self):
        """测试初始化"""
        self.assertIsNotNone(self.emotion_manager.config)
        self.assertIsNotNone(self.emotion_manager.llm_client)
        self.assertIsNotNone(self.emotion_manager.storage)
        self.assertEqual(self.emotion_manager.base_state, "平静")
        self.assertEqual(self.emotion_manager.base_valence, 0.6)
        self.assertEqual(self.emotion_manager.base_arousal, 0.4)
        self.assertEqual(self.emotion_manager.base_dominance, 0.5)
        self.assertEqual(self.emotion_manager.base_social_openness, 0.7)
        self.assertEqual(self.emotion_manager.decay_rate, 0.05)
        self.assertEqual(len(self.emotion_manager.valid_emotions), 10)

    def test_get_current_emotion(self):
        """测试获取当前情绪"""
        # 执行测试
        emotion = self.loop.run_until_complete(
            self.emotion_manager.get_current_emotion()
        )
        
        # 验证结果
        self.assertIsInstance(emotion, dict)
        self.assertEqual(emotion["state"], "平静")
        self.assertEqual(emotion["valence"], 0.6)
        self.assertEqual(emotion["arousal"], 0.4)
        self.assertEqual(emotion["dominance"], 0.5)
        self.assertEqual(emotion["social_openness"], 0.7)
        
        # 验证存储调用
        self.emotion_manager.storage.get.assert_called_once()

    def test_update_emotion(self):
        """测试更新情绪"""
        # 执行测试
        result = self.loop.run_until_complete(
            self.emotion_manager.update_emotion(self.message)
        )
        
        # 验证结果
        self.assertIsInstance(result, dict)
        self.assertEqual(result["state"], "愉悦")  # 从"平静"变为"愉悦"
        self.assertEqual(result["valence"], 0.8)  # 0.6 + 0.2
        self.assertEqual(result["arousal"], 0.5)  # 0.4 + 0.1
        self.assertEqual(result["dominance"], 0.5)  # 0.5 + 0.0
        self.assertEqual(result["social_openness"], 0.8)  # 0.7 + 0.1
        
        # 验证LLM调用
        self.emotion_manager.llm_client.analyze_emotional_impact.assert_called_once()
        
        # 验证存储调用
        self.emotion_manager.storage.set.assert_called_once()

    def test_apply_decay(self):
        """测试情绪衰减"""
        # 设置最后更新时间为6小时前
        old_state = {
            "state": "愉悦",
            "valence": 0.9,
            "arousal": 0.8,
            "dominance": 0.7,
            "social_openness": 0.9,
            "updated_at": time.time() - 21600  # 6小时前
        }
        self.emotion_manager.storage.get.return_value = old_state
        
        # 执行测试
        emotion = self.loop.run_until_complete(
            self.emotion_manager.get_current_emotion()
        )
        
        # 验证结果 - 应该向基础状态衰减
        self.assertIsInstance(emotion, dict)
        # 预期衰减：6小时 * 0.05 = 0.3 的距离
        # 新valence = 0.9 - (0.9 - 0.6) * 0.3 = 0.9 - 0.09 = 0.81
        self.assertAlmostEqual(emotion["valence"], 0.81, places=2)
        # 新arousal = 0.8 - (0.8 - 0.4) * 0.3 = 0.8 - 0.12 = 0.68
        self.assertAlmostEqual(emotion["arousal"], 0.68, places=2)
        # 新dominance = 0.7 - (0.7 - 0.5) * 0.3 = 0.7 - 0.06 = 0.64
        self.assertAlmostEqual(emotion["dominance"], 0.64, places=2)
        # 新social_openness = 0.9 - (0.9 - 0.7) * 0.3 = 0.9 - 0.06 = 0.84
        self.assertAlmostEqual(emotion["social_openness"], 0.84, places=2)

    def test_set_emotion(self):
        """测试设置情绪"""
        # 执行测试
        new_emotion = {
            "state": "好奇",
            "valence": 0.7,
            "arousal": 0.6,
            "dominance": 0.5,
            "social_openness": 0.8
        }
        
        result = self.loop.run_until_complete(
            self.emotion_manager.set_emotion(new_emotion)
        )
        
        # 验证结果
        self.assertIsInstance(result, dict)
        self.assertEqual(result["state"], "好奇")
        self.assertEqual(result["valence"], 0.7)
        self.assertEqual(result["arousal"], 0.6)
        self.assertEqual(result["dominance"], 0.5)
        self.assertEqual(result["social_openness"], 0.8)
        
        # 验证存储调用
        self.emotion_manager.storage.set.assert_called_once()

    def test_reset_emotion(self):
        """测试重置情绪"""
        # 执行测试
        result = self.loop.run_until_complete(
            self.emotion_manager.reset_emotion()
        )
        
        # 验证结果
        self.assertIsInstance(result, dict)
        self.assertEqual(result["state"], self.emotion_manager.base_state)
        self.assertEqual(result["valence"], self.emotion_manager.base_valence)
        self.assertEqual(result["arousal"], self.emotion_manager.base_arousal)
        self.assertEqual(result["dominance"], self.emotion_manager.base_dominance)
        self.assertEqual(result["social_openness"], self.emotion_manager.base_social_openness)
        
        # 验证存储调用
        self.emotion_manager.storage.set.assert_called_once()

    def test_analyze_emotional_impact(self):
        """测试分析情绪影响"""
        # 执行测试
        impact = self.loop.run_until_complete(
            self.emotion_manager._analyze_emotional_impact(self.message)
        )
        
        # 验证结果
        self.assertIsInstance(impact, dict)
        self.assertEqual(impact["state_change"], "愉悦")
        self.assertEqual(impact["valence_change"], 0.2)
        self.assertEqual(impact["arousal_change"], 0.1)
        self.assertEqual(impact["dominance_change"], 0.0)
        self.assertEqual(impact["social_openness_change"], 0.1)
        self.assertEqual(impact["intensity"], 0.7)
        
        # 验证LLM调用
        self.emotion_manager.llm_client.analyze_emotional_impact.assert_called_once()

    def test_apply_emotional_changes(self):
        """测试应用情绪变化"""
        # 准备测试数据
        current_emotion = {
            "state": "平静",
            "valence": 0.6,
            "arousal": 0.4,
            "dominance": 0.5,
            "social_openness": 0.7
        }
        
        impact = {
            "state_change": "愉悦",
            "valence_change": 0.2,
            "arousal_change": 0.1,
            "dominance_change": 0.0,
            "social_openness_change": 0.1,
            "intensity": 0.7
        }
        
        # 执行测试
        new_emotion = self.emotion_manager._apply_emotional_changes(current_emotion, impact)
        
        # 验证结果
        self.assertIsInstance(new_emotion, dict)
        self.assertEqual(new_emotion["state"], "愉悦")
        self.assertEqual(new_emotion["valence"], 0.8)  # 0.6 + 0.2
        self.assertEqual(new_emotion["arousal"], 0.5)  # 0.4 + 0.1
        self.assertEqual(new_emotion["dominance"], 0.5)  # 0.5 + 0.0
        self.assertEqual(new_emotion["social_openness"], 0.8)  # 0.7 + 0.1

    def test_clamp_values(self):
        """测试值范围限制"""
        # 准备超出范围的情绪值
        emotion = {
            "state": "极度兴奋",
            "valence": 1.2,
            "arousal": -0.3,
            "dominance": 1.5,
            "social_openness": -0.2
        }
        
        # 执行测试
        clamped = self.emotion_manager._clamp_values(emotion)
        
        # 验证结果
        self.assertIsInstance(clamped, dict)
        self.assertEqual(clamped["valence"], 1.0)  # 最大值为1.0
        self.assertEqual(clamped["arousal"], 0.0)  # 最小值为0.0
        self.assertEqual(clamped["dominance"], 1.0)  # 最大值为1.0
        self.assertEqual(clamped["social_openness"], 0.0)  # 最小值为0.0

    def test_invalid_emotion_state(self):
        """测试无效情绪状态处理"""
        # 准备包含无效情绪状态的测试数据
        emotion = {
            "state": "不存在的情绪",
            "valence": 0.7,
            "arousal": 0.5,
            "dominance": 0.6,
            "social_openness": 0.8
        }
        
        # 执行测试 - 设置无效情绪
        result = self.loop.run_until_complete(
            self.emotion_manager.set_emotion(emotion)
        )
        
        # 验证结果 - 应该使用有效情绪替代
        self.assertIsInstance(result, dict)
        self.assertIn(result["state"], self.emotion_manager.valid_emotions)
        self.assertNotEqual(result["state"], "不存在的情绪")

    def test_get_emotion_history(self):
        """测试获取情绪历史"""
        # 模拟情绪历史数据
        emotion_history = [
            {
                "state": "平静",
                "valence": 0.6,
                "arousal": 0.4,
                "dominance": 0.5,
                "social_openness": 0.7,
                "timestamp": time.time() - 7200
            },
            {
                "state": "好奇",
                "valence": 0.7,
                "arousal": 0.6,
                "dominance": 0.5,
                "social_openness": 0.8,
                "timestamp": time.time() - 3600
            },
            {
                "state": "愉悦",
                "valence": 0.8,
                "arousal": 0.7,
                "dominance": 0.6,
                "social_openness": 0.9,
                "timestamp": time.time()
            }
        ]
        
        self.emotion_manager.storage.get_all.return_value = emotion_history
        
        # 执行测试
        history = self.loop.run_until_complete(
            self.emotion_manager.get_emotion_history()
        )
        
        # 验证结果
        self.assertIsInstance(history, list)
        self.assertEqual(len(history), 3)
        self.assertEqual(history[0]["state"], "平静")
        self.assertEqual(history[1]["state"], "好奇")
        self.assertEqual(history[2]["state"], "愉悦")
        
        # 验证存储调用
        self.emotion_manager.storage.get_all.assert_called_once()

    def test_error_handling(self):
        """测试错误处理"""
        # 设置LLM抛出异常
        self.emotion_manager.llm_client.analyze_emotional_impact.side_effect = Exception("模型调用失败")
        
        # 执行测试
        result = self.loop.run_until_complete(
            self.emotion_manager.update_emotion(self.message)
        )
        
        # 验证结果 - 应该返回当前情绪而不是崩溃
        self.assertIsInstance(result, dict)
        self.assertEqual(result["state"], "平静")  # 维持当前状态
        
        # 验证LLM被调用
        self.emotion_manager.llm_client.analyze_emotional_impact.assert_called_once()
        
        # 验证存储没有被更新
        self.emotion_manager.storage.set.assert_not_called()


if __name__ == "__main__":
    unittest.main() 