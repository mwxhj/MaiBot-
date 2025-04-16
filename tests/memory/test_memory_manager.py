#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
林镜(LingJing) - 记忆管理器测试
"""

import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import asyncio
import json
import time

from linjing.memory.memory_manager import MemoryManager
from linjing.models.chat_stream import Message
from linjing.models.thought import Thought


class TestMemoryManager(unittest.TestCase):
    """MemoryManager测试类"""

    def setUp(self):
        """测试准备"""
        # 创建MemoryManager实例
        self.memory_manager = MemoryManager()
        
        # 模拟依赖组件
        self.memory_manager.config = MagicMock()
        self.memory_manager.llm_client = AsyncMock()
        self.memory_manager.short_term_storage = MagicMock()
        self.memory_manager.long_term_storage = MagicMock()
        self.memory_manager.vector_storage = MagicMock()
        
        # 设置模拟返回值
        self.memory_manager.config.get.return_value = {
            "memory": {
                "short_term_limit": 100,
                "summarization_threshold": 20,
                "max_interactions_per_user": 50,
                "importance_threshold": 0.6
            }
        }
        
        # 模拟LLM返回值
        self.memory_manager.llm_client.evaluate_memory_importance.return_value = {
            "importance_score": 0.75,
            "reasoning": "包含重要的个人偏好信息",
            "extracted_facts": ["用户喜欢编程", "用户对AI感兴趣"],
            "categories": ["兴趣爱好", "技术偏好"]
        }
        
        self.memory_manager.llm_client.summarize_interactions.return_value = {
            "summary": "用户经常讨论技术话题，尤其是编程和AI。对新技术持积极态度，交流风格友好。",
            "key_topics": ["编程", "AI", "技术"],
            "interaction_style": "友好",
            "insights": ["用户是技术爱好者", "喜欢学习新事物"]
        }
        
        # 模拟存储返回值
        self.memory_manager.short_term_storage.get_all.return_value = [
            {
                "timestamp": time.time() - 3600,
                "content": "用户: 你好，林镜！",
                "message_id": "msg_1",
                "sender_id": "user_1",
                "type": "message"
            },
            {
                "timestamp": time.time() - 3500,
                "content": "林镜: 你好！很高兴见到你。有什么我能帮助你的吗？",
                "message_id": "msg_2",
                "sender_id": "bot_id",
                "type": "message"
            }
        ]
        
        self.memory_manager.long_term_storage.get.return_value = {
            "user_id": "user_1",
            "user_summary": {
                "common_topics": ["技术", "编程", "AI"],
                "interaction_style": "友好",
                "preferences": ["喜欢详细解释", "偏好技术讨论"],
                "notable_facts": ["是一名程序员", "对AI有研究"]
            },
            "first_interaction": time.time() - 86400,
            "last_interaction": time.time() - 3600,
            "interaction_count": 15
        }
        
        # 创建测试消息
        self.message = Message(
            message_id="msg_test",
            sender_id="user_1",
            content="我最近在学习Python，你有什么学习建议吗？",
            message_type="group",
            group_id="group_1",
            timestamp=time.time(),
            is_at_me=True
        )
        
        # 创建测试思考
        self.thought = Thought(
            message_id="msg_test",
            understanding="用户在询问Python学习建议",
            emotional_response={
                "primary": "interest",
                "secondary": "desire_to_help",
                "intensity": 0.8
            },
            reasoning="用户对编程学习有兴趣，需要专业指导",
            social_context={
                "is_direct_interaction": True,
                "requires_response": True,
                "conversation_topic": "programming",
                "topic_relevance": "high"
            },
            response_considerations={
                "should_respond": True,
                "response_type": "advice",
                "priority": "high",
                "key_points": ["学习资源", "学习方法", "实践建议"]
            }
        )
        
        # 运行初始化
        self.loop = asyncio.get_event_loop()
        self.loop.run_until_complete(self.memory_manager.initialize())

    def test_init(self):
        """测试初始化"""
        self.assertIsNotNone(self.memory_manager.config)
        self.assertIsNotNone(self.memory_manager.llm_client)
        self.assertIsNotNone(self.memory_manager.short_term_storage)
        self.assertIsNotNone(self.memory_manager.long_term_storage)
        self.assertIsNotNone(self.memory_manager.vector_storage)
        self.assertEqual(self.memory_manager.short_term_limit, 100)
        self.assertEqual(self.memory_manager.summarization_threshold, 20)

    def test_add_message(self):
        """测试添加消息"""
        # 执行测试
        result = self.loop.run_until_complete(
            self.memory_manager.add_message(self.message)
        )
        
        # 验证结果
        self.assertEqual(result, True)
        
        # 验证存储调用
        self.memory_manager.short_term_storage.add.assert_called_once()
        
        # 模拟短期记忆达到阈值的情况
        self.memory_manager.short_term_storage.count.return_value = self.memory_manager.summarization_threshold + 1
        
        # 执行测试
        result = self.loop.run_until_complete(
            self.memory_manager.add_message(self.message)
        )
        
        # 验证结果 - 应该触发总结和清理
        self.assertEqual(result, True)
        self.memory_manager.llm_client.summarize_interactions.assert_called_once()
        self.memory_manager.short_term_storage.clear.assert_called_once()

    def test_add_thought(self):
        """测试添加思考"""
        # 执行测试
        result = self.loop.run_until_complete(
            self.memory_manager.add_thought(self.thought)
        )
        
        # 验证结果
        self.assertEqual(result, True)
        
        # 验证存储调用
        self.memory_manager.short_term_storage.add.assert_called_once()

    def test_add_interaction(self):
        """测试添加交互"""
        # 准备测试数据
        interaction = {
            "timestamp": time.time(),
            "message": self.message,
            "thought": self.thought,
            "response": "这是一个回复",
            "metadata": {"sentiment": "positive"}
        }
        
        # 执行测试
        result = self.loop.run_until_complete(
            self.memory_manager.add_interaction(interaction)
        )
        
        # 验证结果
        self.assertEqual(result, True)
        
        # 验证重要性评估调用
        self.memory_manager.llm_client.evaluate_memory_importance.assert_called_once()
        
        # 验证存储调用 - 重要性超过阈值，应该存储
        self.memory_manager.long_term_storage.add.assert_called_once()
        self.memory_manager.vector_storage.add.assert_called_once()

    def test_get_user_interaction_summary(self):
        """测试获取用户交互摘要"""
        # 执行测试
        summary = self.loop.run_until_complete(
            self.memory_manager.get_user_interaction_summary("user_1")
        )
        
        # 验证结果
        self.assertIsInstance(summary, dict)
        self.assertIn("common_topics", summary)
        self.assertIn("interaction_style", summary)
        self.assertIn("preferences", summary)
        self.assertEqual(summary["common_topics"][0], "技术")
        self.assertEqual(summary["interaction_style"], "友好")
        
        # 验证存储调用
        self.memory_manager.long_term_storage.get.assert_called_once()

    def test_get_recent_interactions(self):
        """测试获取最近交互"""
        # 执行测试
        interactions = self.loop.run_until_complete(
            self.memory_manager.get_recent_interactions("user_1", 5)
        )
        
        # 验证结果
        self.assertIsInstance(interactions, list)
        
        # 验证存储调用
        self.memory_manager.short_term_storage.get_by_user.assert_called_once()

    def test_search_memories(self):
        """测试搜索记忆"""
        # 模拟向量存储搜索结果
        self.memory_manager.vector_storage.search.return_value = [
            {
                "content": "用户提到喜欢Python编程",
                "metadata": {
                    "timestamp": time.time() - 7200,
                    "user_id": "user_1",
                    "categories": ["编程语言", "兴趣爱好"]
                },
                "score": 0.85
            },
            {
                "content": "用户讨论了Python学习资源",
                "metadata": {
                    "timestamp": time.time() - 3600,
                    "user_id": "user_1",
                    "categories": ["学习资源", "编程语言"]
                },
                "score": 0.75
            }
        ]
        
        # 执行测试
        results = self.loop.run_until_complete(
            self.memory_manager.search_memories("Python学习", 5)
        )
        
        # 验证结果
        self.assertIsInstance(results, list)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["score"], 0.85)
        self.assertEqual(results[1]["score"], 0.75)
        
        # 验证存储调用
        self.memory_manager.vector_storage.search.assert_called_once()

    def test_get_user_interaction_stats(self):
        """测试获取用户交互统计"""
        # 执行测试
        stats = self.loop.run_until_complete(
            self.memory_manager.get_user_interaction_stats("user_1")
        )
        
        # 验证结果
        self.assertIsInstance(stats, dict)
        self.assertIn("total_interactions", stats)
        self.assertIn("first_interaction", stats)
        self.assertIn("last_interaction", stats)
        self.assertEqual(stats["total_interactions"], 15)
        
        # 验证存储调用
        self.memory_manager.long_term_storage.get.assert_called_once()

    def test_summarize_interactions(self):
        """测试总结交互"""
        # 模拟短期记忆中的交互
        interactions = [
            {
                "timestamp": time.time() - 3600,
                "content": "用户: 你好，我是一名Python开发者",
                "message_id": "msg_a",
                "sender_id": "user_1",
                "type": "message"
            },
            {
                "timestamp": time.time() - 3500,
                "content": "林镜: 你好！很高兴认识你。Python是一门很棒的语言。",
                "message_id": "msg_b",
                "sender_id": "bot_id",
                "type": "message"
            },
            {
                "timestamp": time.time() - 3400,
                "content": "用户: 我最近在学习机器学习，你有什么建议吗？",
                "message_id": "msg_c",
                "sender_id": "user_1",
                "type": "message"
            }
        ]
        
        # 执行测试
        summary = self.loop.run_until_complete(
            self.memory_manager._summarize_interactions(interactions, "user_1")
        )
        
        # 验证结果
        self.assertIsInstance(summary, dict)
        self.assertIn("summary", summary)
        self.assertIn("key_topics", summary)
        self.assertIn("interaction_style", summary)
        
        # 验证LLM调用
        self.memory_manager.llm_client.summarize_interactions.assert_called_once()

    def test_evaluate_importance(self):
        """测试评估重要性"""
        # 准备测试数据
        interaction = {
            "message": self.message,
            "thought": self.thought,
            "response": "这是一个回复",
            "metadata": {"sentiment": "positive"}
        }
        
        # 执行测试
        importance = self.loop.run_until_complete(
            self.memory_manager._evaluate_importance(interaction)
        )
        
        # 验证结果
        self.assertIsInstance(importance, dict)
        self.assertIn("importance_score", importance)
        self.assertIn("reasoning", importance)
        self.assertIn("extracted_facts", importance)
        self.assertEqual(importance["importance_score"], 0.75)
        
        # 验证LLM调用
        self.memory_manager.llm_client.evaluate_memory_importance.assert_called_once()

    def test_update_user_summary(self):
        """测试更新用户摘要"""
        # 准备测试数据
        new_summary = {
            "summary": "用户是Python开发者，对机器学习感兴趣。交流风格直接，经常问具体问题。",
            "key_topics": ["Python", "机器学习", "开发"],
            "interaction_style": "直接",
            "insights": ["技术专业人士", "学习进取"]
        }
        
        existing_summary = {
            "user_id": "user_1",
            "user_summary": {
                "common_topics": ["编程", "技术"],
                "interaction_style": "友好",
                "preferences": ["喜欢详细解释"],
                "notable_facts": ["是一名程序员"]
            },
            "first_interaction": time.time() - 86400,
            "last_interaction": time.time() - 3600,
            "interaction_count": 10
        }
        
        self.memory_manager.long_term_storage.get.return_value = existing_summary
        
        # 执行测试
        result = self.loop.run_until_complete(
            self.memory_manager._update_user_summary("user_1", new_summary)
        )
        
        # 验证结果
        self.assertEqual(result, True)
        
        # 验证存储调用
        self.memory_manager.long_term_storage.update.assert_called_once()
        
        # 验证更新的内容
        call_args = self.memory_manager.long_term_storage.update.call_args[0][0]
        self.assertEqual(call_args["user_id"], "user_1")
        self.assertIn("Python", call_args["user_summary"]["common_topics"])
        self.assertEqual(call_args["user_summary"]["interaction_style"], "直接")
        self.assertEqual(call_args["interaction_count"], 10)  # 应该保留原有值

    def test_prune_memory(self):
        """测试记忆修剪"""
        # 执行测试
        result = self.loop.run_until_complete(
            self.memory_manager.prune_memory("user_1")
        )
        
        # 验证结果
        self.assertEqual(result, True)
        
        # 验证存储调用
        self.memory_manager.short_term_storage.prune.assert_called_once()
        self.memory_manager.long_term_storage.prune.assert_called_once()

    def test_clear_memory(self):
        """测试清除记忆"""
        # 执行测试 - 清除特定用户的记忆
        result_user = self.loop.run_until_complete(
            self.memory_manager.clear_memory("user_1")
        )
        
        # 验证结果
        self.assertEqual(result_user, True)
        
        # 验证存储调用
        self.memory_manager.short_term_storage.clear_by_user.assert_called_once_with("user_1")
        self.memory_manager.long_term_storage.remove.assert_called_once_with("user_1")
        self.memory_manager.vector_storage.delete_by_filter.assert_called_once()
        
        # 重置mock
        self.memory_manager.short_term_storage.reset_mock()
        self.memory_manager.long_term_storage.reset_mock()
        self.memory_manager.vector_storage.reset_mock()
        
        # 执行测试 - 清除所有记忆
        result_all = self.loop.run_until_complete(
            self.memory_manager.clear_memory()
        )
        
        # 验证结果
        self.assertEqual(result_all, True)
        
        # 验证存储调用
        self.memory_manager.short_term_storage.clear.assert_called_once()
        self.memory_manager.long_term_storage.clear.assert_called_once()
        self.memory_manager.vector_storage.clear.assert_called_once()

    def test_error_handling(self):
        """测试错误处理"""
        # 设置LLM抛出异常
        self.memory_manager.llm_client.evaluate_memory_importance.side_effect = Exception("模型调用失败")
        
        # 准备测试数据
        interaction = {
            "timestamp": time.time(),
            "message": self.message,
            "thought": self.thought,
            "response": "这是一个回复",
            "metadata": {"sentiment": "positive"}
        }
        
        # 执行测试
        result = self.loop.run_until_complete(
            self.memory_manager.add_interaction(interaction)
        )
        
        # 验证结果 - 即使LLM失败也应该成功添加
        self.assertEqual(result, True)
        
        # 验证LLM被调用
        self.memory_manager.llm_client.evaluate_memory_importance.assert_called_once()
        
        # 验证存储调用 - 应该使用默认重要性值
        self.memory_manager.long_term_storage.add.assert_called_once()


if __name__ == "__main__":
    unittest.main() 