#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
林镜(LingJing) - LLM客户端测试
"""

import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import asyncio
import json
import time

from linjing.llm.llm_client import LLMClient


class TestLLMClient(unittest.TestCase):
    """LLMClient测试类"""

    def setUp(self):
        """测试准备"""
        # 创建LLMClient实例
        self.llm_client = LLMClient()
        
        # 模拟依赖组件
        self.llm_client.config = MagicMock()
        self.llm_client.azure_client = AsyncMock()
        self.llm_client.openai_client = AsyncMock()
        self.llm_client.rate_limiter = MagicMock()
        
        # 设置模拟返回值
        self.llm_client.config.get.return_value = {
            "llm": {
                "provider": "azure",
                "default_model": "gpt-4",
                "chat_model": "gpt-4",
                "embedding_model": "text-embedding-ada-002",
                "temperature": 0.7,
                "max_tokens": 1000,
                "timeout_seconds": 30,
                "retry_attempts": 3,
                "retry_delay": 2
            }
        }
        
        # 设置模拟Azure响应
        self.llm_client.azure_client.chat_completion.return_value = {
            "id": "chatcmpl-123456789",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": "gpt-4",
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "这是模型的回复内容"
                    },
                    "finish_reason": "stop",
                    "index": 0
                }
            ],
            "usage": {
                "prompt_tokens": 50,
                "completion_tokens": 30,
                "total_tokens": 80
            }
        }
        
        self.llm_client.azure_client.embedding.return_value = {
            "data": [
                {
                    "embedding": [0.1, 0.2, 0.3, 0.4, 0.5],  # 简化的嵌入向量
                    "index": 0,
                    "object": "embedding"
                }
            ],
            "model": "text-embedding-ada-002",
            "object": "list",
            "usage": {
                "prompt_tokens": 10,
                "total_tokens": 10
            }
        }
        
        # 运行初始化
        self.loop = asyncio.get_event_loop()
        self.loop.run_until_complete(self.llm_client.initialize())

    def test_init(self):
        """测试初始化"""
        self.assertIsNotNone(self.llm_client.config)
        self.assertIsNotNone(self.llm_client.azure_client)
        self.assertIsNotNone(self.llm_client.openai_client)
        self.assertIsNotNone(self.llm_client.rate_limiter)
        self.assertEqual(self.llm_client.provider, "azure")
        self.assertEqual(self.llm_client.default_model, "gpt-4")
        self.assertEqual(self.llm_client.chat_model, "gpt-4")
        self.assertEqual(self.llm_client.embedding_model, "text-embedding-ada-002")
        self.assertEqual(self.llm_client.temperature, 0.7)
        self.assertEqual(self.llm_client.max_tokens, 1000)
        self.assertEqual(self.llm_client.timeout, 30)
        self.assertEqual(self.llm_client.retry_attempts, 3)
        self.assertEqual(self.llm_client.retry_delay, 2)

    def test_chat_completion(self):
        """测试聊天补全"""
        # 准备测试数据
        messages = [
            {"role": "system", "content": "你是林镜，一个友好的助手。"},
            {"role": "user", "content": "你好，请介绍一下自己。"}
        ]
        
        # 执行测试
        response = self.loop.run_until_complete(
            self.llm_client.chat_completion({"messages": messages})
        )
        
        # 验证结果
        self.assertIsInstance(response, dict)
        self.assertIn("message", response)
        self.assertEqual(response["message"], "这是模型的回复内容")
        self.assertIn("finish_reason", response)
        self.assertEqual(response["finish_reason"], "stop")
        
        # 验证Azure客户端调用
        self.llm_client.azure_client.chat_completion.assert_called_once()
        
        # 验证Azure客户端调用参数
        call_args = self.llm_client.azure_client.chat_completion.call_args[0][0]
        self.assertEqual(call_args["messages"], messages)
        self.assertEqual(call_args["model"], "gpt-4")
        self.assertEqual(call_args["temperature"], 0.7)
        self.assertEqual(call_args["max_tokens"], 1000)

    def test_embedding(self):
        """测试嵌入向量生成"""
        # 准备测试数据
        text = "这是一段测试文本，用于生成嵌入向量。"
        
        # 执行测试
        response = self.loop.run_until_complete(
            self.llm_client.embedding(text)
        )
        
        # 验证结果
        self.assertIsInstance(response, list)
        self.assertEqual(len(response), 5)  # 简化的嵌入向量长度为5
        self.assertEqual(response[0], 0.1)
        self.assertEqual(response[4], 0.5)
        
        # 验证Azure客户端调用
        self.llm_client.azure_client.embedding.assert_called_once()
        
        # 验证Azure客户端调用参数
        call_args = self.llm_client.azure_client.embedding.call_args[0][0]
        self.assertEqual(call_args["text"], text)
        self.assertEqual(call_args["model"], "text-embedding-ada-002")

    def test_generate_thought(self):
        """测试生成思考"""
        # 设置模拟返回值
        self.llm_client.azure_client.chat_completion.return_value = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps({
                            "understanding": "用户在问候机器人",
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
                                "key_points": ["回应问候", "表达友好"]
                            }
                        })
                    },
                    "finish_reason": "stop"
                }
            ]
        }
        
        # 准备测试数据
        context = {
            "current_message": {
                "content": "你好，林镜！",
                "sender_id": "user_1",
                "is_at_me": True
            },
            "chat_history": [
                {"content": "大家好啊！", "sender_id": "user_2", "is_at_me": False}
            ],
            "relationship": {
                "familiarity": 0.5,
                "trust": 0.6
            },
            "current_emotion": {
                "state": "平静",
                "valence": 0.6
            }
        }
        
        # 执行测试
        response = self.loop.run_until_complete(
            self.llm_client.generate_thought(context)
        )
        
        # 验证结果
        self.assertIsInstance(response, dict)
        self.assertIn("understanding", response)
        self.assertIn("emotional_response", response)
        self.assertIn("reasoning", response)
        self.assertIn("social_context", response)
        self.assertIn("response_considerations", response)
        self.assertEqual(response["understanding"], "用户在问候机器人")
        self.assertEqual(response["emotional_response"]["primary"], "joy")
        
        # 验证Azure客户端调用
        self.llm_client.azure_client.chat_completion.assert_called_once()

    def test_analyze_emotional_impact(self):
        """测试分析情绪影响"""
        # 设置模拟返回值
        self.llm_client.azure_client.chat_completion.return_value = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps({
                            "state_change": "愉悦",
                            "valence_change": 0.2,
                            "arousal_change": 0.1,
                            "dominance_change": 0.0,
                            "social_openness_change": 0.1,
                            "intensity": 0.7,
                            "triggers": ["表达善意", "亲切问候"],
                            "reasoning": "用户友好的问候增加了愉悦感"
                        })
                    },
                    "finish_reason": "stop"
                }
            ]
        }
        
        # 准备测试数据
        message = {
            "content": "你好，林镜！最近怎么样？",
            "sender_id": "user_1",
            "is_at_me": True
        }
        
        current_emotion = {
            "state": "平静",
            "valence": 0.6,
            "arousal": 0.4,
            "dominance": 0.5,
            "social_openness": 0.7
        }
        
        # 执行测试
        response = self.loop.run_until_complete(
            self.llm_client.analyze_emotional_impact(message, current_emotion)
        )
        
        # 验证结果
        self.assertIsInstance(response, dict)
        self.assertIn("state_change", response)
        self.assertIn("valence_change", response)
        self.assertIn("arousal_change", response)
        self.assertIn("intensity", response)
        self.assertEqual(response["state_change"], "愉悦")
        self.assertEqual(response["valence_change"], 0.2)
        
        # 验证Azure客户端调用
        self.llm_client.azure_client.chat_completion.assert_called_once()

    def test_evaluate_memory_importance(self):
        """测试评估记忆重要性"""
        # 设置模拟返回值
        self.llm_client.azure_client.chat_completion.return_value = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps({
                            "importance_score": 0.75,
                            "reasoning": "包含重要的个人偏好信息",
                            "extracted_facts": ["用户喜欢编程", "用户对AI感兴趣"],
                            "categories": ["兴趣爱好", "技术偏好"]
                        })
                    },
                    "finish_reason": "stop"
                }
            ]
        }
        
        # 准备测试数据
        interaction = {
            "message": {
                "content": "我最近在学习Python，你有什么学习建议吗？",
                "sender_id": "user_1"
            },
            "response": "我建议你从基础开始，然后尝试做一些小项目来巩固知识。",
            "thought": {
                "understanding": "用户在询问Python学习建议",
                "reasoning": "用户对编程学习有兴趣，需要专业指导"
            }
        }
        
        # 执行测试
        response = self.loop.run_until_complete(
            self.llm_client.evaluate_memory_importance(interaction)
        )
        
        # 验证结果
        self.assertIsInstance(response, dict)
        self.assertIn("importance_score", response)
        self.assertIn("reasoning", response)
        self.assertIn("extracted_facts", response)
        self.assertEqual(response["importance_score"], 0.75)
        self.assertEqual(len(response["extracted_facts"]), 2)
        
        # 验证Azure客户端调用
        self.llm_client.azure_client.chat_completion.assert_called_once()

    def test_summarize_interactions(self):
        """测试总结交互"""
        # 设置模拟返回值
        self.llm_client.azure_client.chat_completion.return_value = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps({
                            "summary": "用户经常讨论技术话题，尤其是编程和AI。对新技术持积极态度，交流风格友好。",
                            "key_topics": ["编程", "AI", "技术"],
                            "interaction_style": "友好",
                            "insights": ["用户是技术爱好者", "喜欢学习新事物"]
                        })
                    },
                    "finish_reason": "stop"
                }
            ]
        }
        
        # 准备测试数据
        interactions = [
            {
                "timestamp": time.time() - 3600,
                "content": "用户: 你好，我是一名Python开发者",
                "sender_id": "user_1"
            },
            {
                "timestamp": time.time() - 3500,
                "content": "林镜: 你好！很高兴认识你。Python是一门很棒的语言。",
                "sender_id": "bot_id"
            },
            {
                "timestamp": time.time() - 3400,
                "content": "用户: 我最近在学习机器学习，你有什么建议吗？",
                "sender_id": "user_1"
            }
        ]
        
        # 执行测试
        response = self.loop.run_until_complete(
            self.llm_client.summarize_interactions(interactions)
        )
        
        # 验证结果
        self.assertIsInstance(response, dict)
        self.assertIn("summary", response)
        self.assertIn("key_topics", response)
        self.assertIn("interaction_style", response)
        self.assertEqual(response["interaction_style"], "友好")
        self.assertEqual(len(response["key_topics"]), 3)
        
        # 验证Azure客户端调用
        self.llm_client.azure_client.chat_completion.assert_called_once()

    def test_analyze_social_intent(self):
        """测试分析社交意图"""
        # 设置模拟返回值
        self.llm_client.azure_client.chat_completion.return_value = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps({
                            "is_direct_interaction": True,
                            "requires_response": True,
                            "intent": "greeting",
                            "confidence": 0.9,
                            "contains_name_mention": True
                        })
                    },
                    "finish_reason": "stop"
                }
            ]
        }
        
        # 准备测试数据
        message = {
            "content": "林镜，你好！",
            "sender_id": "user_1",
            "is_at_me": False
        }
        
        context = [
            {"content": "大家好啊！", "sender_id": "user_2"}
        ]
        
        # 执行测试
        response = self.loop.run_until_complete(
            self.llm_client.analyze_social_intent(message, context)
        )
        
        # 验证结果
        self.assertIsInstance(response, dict)
        self.assertIn("is_direct_interaction", response)
        self.assertIn("requires_response", response)
        self.assertIn("intent", response)
        self.assertIn("confidence", response)
        self.assertTrue(response["is_direct_interaction"])
        self.assertTrue(response["requires_response"])
        self.assertEqual(response["intent"], "greeting")
        self.assertEqual(response["confidence"], 0.9)
        
        # 验证Azure客户端调用
        self.llm_client.azure_client.chat_completion.assert_called_once()

    def test_provider_switching(self):
        """测试提供商切换"""
        # 更改配置为OpenAI
        self.llm_client.provider = "openai"
        
        # 准备测试数据
        messages = [
            {"role": "system", "content": "你是林镜，一个友好的助手。"},
            {"role": "user", "content": "你好，请介绍一下自己。"}
        ]
        
        # 设置OpenAI模拟返回值
        self.llm_client.openai_client.chat_completion.return_value = {
            "id": "chatcmpl-987654321",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": "gpt-4",
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "这是OpenAI的回复内容"
                    },
                    "finish_reason": "stop",
                    "index": 0
                }
            ],
            "usage": {
                "prompt_tokens": 50,
                "completion_tokens": 30,
                "total_tokens": 80
            }
        }
        
        # 执行测试
        response = self.loop.run_until_complete(
            self.llm_client.chat_completion({"messages": messages})
        )
        
        # 验证结果
        self.assertIsInstance(response, dict)
        self.assertIn("message", response)
        self.assertEqual(response["message"], "这是OpenAI的回复内容")
        
        # 验证OpenAI客户端调用
        self.llm_client.openai_client.chat_completion.assert_called_once()
        # 验证Azure客户端没有被调用
        self.llm_client.azure_client.chat_completion.assert_not_called()

    def test_retry_mechanism(self):
        """测试重试机制"""
        # 设置Azure客户端首次调用失败，第二次成功
        self.llm_client.azure_client.chat_completion.side_effect = [
            Exception("模型调用失败"),
            {
                "choices": [
                    {
                        "message": {
                            "content": "重试成功后的回复"
                        },
                        "finish_reason": "stop"
                    }
                ]
            }
        ]
        
        # 准备测试数据
        messages = [
            {"role": "system", "content": "你是林镜，一个友好的助手。"},
            {"role": "user", "content": "你好，请介绍一下自己。"}
        ]
        
        # 执行测试
        response = self.loop.run_until_complete(
            self.llm_client.chat_completion({"messages": messages})
        )
        
        # 验证结果
        self.assertIsInstance(response, dict)
        self.assertIn("message", response)
        self.assertEqual(response["message"], "重试成功后的回复")
        
        # 验证Azure客户端被调用两次
        self.assertEqual(self.llm_client.azure_client.chat_completion.call_count, 2)

    def test_error_handling(self):
        """测试错误处理"""
        # 设置Azure客户端始终调用失败
        self.llm_client.azure_client.chat_completion.side_effect = Exception("模型调用失败")
        
        # 设置重试次数为1次，加速测试
        self.llm_client.retry_attempts = 1
        
        # 准备测试数据
        messages = [
            {"role": "system", "content": "你是林镜，一个友好的助手。"},
            {"role": "user", "content": "你好，请介绍一下自己。"}
        ]
        
        # 执行测试，应该抛出异常
        with self.assertRaises(Exception):
            self.loop.run_until_complete(
                self.llm_client.chat_completion({"messages": messages})
            )
        
        # 验证Azure客户端被调用次数等于重试次数+1
        self.assertEqual(self.llm_client.azure_client.chat_completion.call_count, 2)


if __name__ == "__main__":
    unittest.main() 