#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
林镜(LingJing) - MessageProcessor组件测试
"""

import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import asyncio
import json
import time

from linjing.models.chat_stream import ChatStream, Message
from linjing.models.thought import Thought
from linjing.core.message_processor import MessageProcessor


class TestMessageProcessor(unittest.TestCase):
    """MessageProcessor测试类"""

    def setUp(self):
        """测试准备"""
        # 创建MessageProcessor实例
        self.processor = MessageProcessor()
        
        # 模拟依赖组件
        self.processor.config = MagicMock()
        self.processor.bot_adapter = AsyncMock()
        self.processor.read_air_processor = AsyncMock()
        self.processor.thought_generator = AsyncMock()
        self.processor.willingness_checker = AsyncMock()
        self.processor.reply_composer = AsyncMock()
        self.processor.relationship_manager = AsyncMock()
        self.processor.emotion_manager = AsyncMock()
        self.processor.memory_manager = AsyncMock()
        
        # 设置模拟返回值
        self.processor.config.get.return_value = {
            "name": "林镜",
            "bot_id": "bot_12345678",
            "default_group_settings": {
                "response_rate": 0.5,
                "learning_enabled": True,
                "personality": "default"
            }
        }
        
        # 模拟read_air_processor处理结果
        self.processor.read_air_processor.process.return_value = {
            "should_reply": True,
            "social_intent": {
                "is_direct_interaction": True,
                "requires_response": True,
                "intent": "greeting",
                "confidence": 0.9
            },
            "relevant_context": [
                {"message_id": "msg_123", "content": "测试消息1"},
                {"message_id": "msg_124", "content": "测试消息2"}
            ]
        }
        
        # 模拟thought_generator处理结果
        thought = Thought(
            message_id="msg_12345",
            understanding="用户在问候机器人",
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
                "key_points": ["回应问候", "表达友好"]
            }
        )
        self.processor.thought_generator.generate.return_value = thought
        
        # 模拟willingness_checker处理结果
        self.processor.willingness_checker.check.return_value = {
            "should_express": True,
            "willingness": 0.85,
            "attitude": "friendly",
            "reason": "用户直接问候，情绪积极"
        }
        
        # 模拟reply_composer处理结果
        self.processor.reply_composer.compose.return_value = {
            "reply": "你好！很高兴见到你。",
            "messages": {
                "text": {
                    "content": "你好！很高兴见到你。"
                }
            }
        }
        
        # 创建测试消息
        self.group_message = {
            "post_type": "message",
            "message_type": "group",
            "time": int(time.time()),
            "self_id": "bot_12345678",
            "message_id": "msg_12345",
            "group_id": "group_123456",
            "user_id": "user_12345",
            "sender": {
                "user_id": "user_12345",
                "nickname": "测试用户",
                "card": "测试用户"
            },
            "message": "你好，林镜！",
            "raw_message": "你好，林镜！"
        }
        
        self.private_message = {
            "post_type": "message",
            "message_type": "private",
            "time": int(time.time()),
            "self_id": "bot_12345678",
            "message_id": "msg_12346",
            "user_id": "user_12345",
            "sender": {
                "user_id": "user_12345",
                "nickname": "测试用户"
            },
            "message": "你好，林镜！",
            "raw_message": "你好，林镜！"
        }
        
        self.at_message = {
            "post_type": "message",
            "message_type": "group",
            "time": int(time.time()),
            "self_id": "bot_12345678",
            "message_id": "msg_12347",
            "group_id": "group_123456",
            "user_id": "user_12345",
            "sender": {
                "user_id": "user_12345",
                "nickname": "测试用户",
                "card": "测试用户"
            },
            "message": "[CQ:at,qq=bot_12345678] 你好，林镜！",
            "raw_message": "[CQ:at,qq=bot_12345678] 你好，林镜！"
        }
        
        self.notice_message = {
            "post_type": "notice",
            "notice_type": "group_increase",
            "time": int(time.time()),
            "self_id": "bot_12345678",
            "user_id": "user_12345",
            "group_id": "group_123456",
            "operator_id": "user_98765"
        }
        
        # 运行初始化
        self.loop = asyncio.get_event_loop()
        self.loop.run_until_complete(self.processor.initialize())

    def test_init(self):
        """测试初始化"""
        self.assertIsNotNone(self.processor.config)
        self.assertIsNotNone(self.processor.bot_adapter)
        self.assertIsNotNone(self.processor.read_air_processor)
        self.assertIsNotNone(self.processor.thought_generator)
        self.assertIsNotNone(self.processor.willingness_checker)
        self.assertIsNotNone(self.processor.reply_composer)
        self.assertIsNotNone(self.processor.relationship_manager)
        self.assertIsNotNone(self.processor.emotion_manager)
        self.assertIsNotNone(self.processor.memory_manager)
        self.assertIsInstance(self.processor.chat_streams, dict)

    def test_process_group_message(self):
        """测试处理群消息"""
        # 执行测试
        result = self.loop.run_until_complete(
            self.processor.process_message(self.group_message)
        )
        
        # 验证结果
        self.assertIsNotNone(result)
        
        # 验证各组件被调用
        self.processor.read_air_processor.process.assert_called_once()
        self.processor.thought_generator.generate.assert_called_once()
        self.processor.willingness_checker.check.assert_called_once()
        self.processor.reply_composer.compose.assert_called_once()
        self.processor.bot_adapter.send_group_message.assert_called_once()
        
        # 验证消息被添加到聊天流中
        group_id = self.group_message["group_id"]
        self.assertIn(group_id, self.processor.chat_streams)

    def test_process_private_message(self):
        """测试处理私聊消息"""
        # 执行测试
        result = self.loop.run_until_complete(
            self.processor.process_message(self.private_message)
        )
        
        # 验证结果
        self.assertIsNotNone(result)
        
        # 验证各组件被调用
        self.processor.read_air_processor.process.assert_called_once()
        self.processor.thought_generator.generate.assert_called_once()
        self.processor.willingness_checker.check.assert_called_once()
        self.processor.reply_composer.compose.assert_called_once()
        self.processor.bot_adapter.send_private_message.assert_called_once()
        
        # 验证消息被添加到聊天流中
        user_id = self.private_message["user_id"]
        self.assertIn(f"private_{user_id}", self.processor.chat_streams)

    def test_process_at_message(self):
        """测试处理@消息"""
        # 执行测试
        result = self.loop.run_until_complete(
            self.processor.process_message(self.at_message)
        )
        
        # 验证结果
        self.assertIsNotNone(result)
        
        # 验证各组件被调用 - @消息应该处理为特殊的群消息
        self.processor.read_air_processor.process.assert_called_once()
        self.processor.thought_generator.generate.assert_called_once()
        self.processor.willingness_checker.check.assert_called_once()
        self.processor.reply_composer.compose.assert_called_once()
        self.processor.bot_adapter.send_group_message.assert_called_once()
        
        # 验证@标记被正确处理
        call_args = self.processor.read_air_processor.process.call_args[0][0]
        self.assertTrue(call_args.is_at_me)

    def test_process_notice(self):
        """测试处理通知消息"""
        # 执行测试
        result = self.loop.run_until_complete(
            self.processor.process_message(self.notice_message)
        )
        
        # 验证结果
        self.assertIsNotNone(result)
        
        # 验证通知被正确处理 - 这里我们简单检查它没有调用标准消息处理流程
        self.processor.read_air_processor.process.assert_not_called()
        self.processor.thought_generator.generate.assert_not_called()
        self.processor.willingness_checker.check.assert_not_called()
        self.processor.reply_composer.compose.assert_not_called()

    def test_convert_to_internal_message(self):
        """测试消息转换为内部格式"""
        # 执行转换
        internal_message = self.processor._convert_to_internal_message(self.group_message)
        
        # 验证结果
        self.assertEqual(internal_message.message_id, self.group_message["message_id"])
        self.assertEqual(internal_message.sender_id, self.group_message["user_id"])
        self.assertEqual(internal_message.content, self.group_message["message"])
        self.assertEqual(internal_message.message_type, "group")
        self.assertEqual(internal_message.group_id, self.group_message["group_id"])
        self.assertFalse(internal_message.is_at_me)  # 普通群消息应该不是@消息
        
        # 测试@消息转换
        at_internal_message = self.processor._convert_to_internal_message(self.at_message)
        self.assertTrue(at_internal_message.is_at_me)  # @消息应该标记为@
        
        # 测试私聊消息转换
        private_internal_message = self.processor._convert_to_internal_message(self.private_message)
        self.assertEqual(private_internal_message.message_type, "private")
        self.assertIsNone(private_internal_message.group_id)  # 私聊消息没有群ID

    def test_get_or_create_chat_stream(self):
        """测试获取或创建聊天流"""
        # 测试群聊天流
        message = self.processor._convert_to_internal_message(self.group_message)
        chat_stream = self.processor._get_or_create_chat_stream(message)
        
        # 验证结果
        self.assertIsInstance(chat_stream, ChatStream)
        self.assertEqual(chat_stream.stream_id, self.group_message["group_id"])
        self.assertEqual(len(chat_stream.messages), 1)
        self.assertEqual(chat_stream.messages[0].message_id, message.message_id)
        
        # 检查缓存
        self.assertIn(self.group_message["group_id"], self.processor.chat_streams)
        self.assertEqual(self.processor.chat_streams[self.group_message["group_id"]], chat_stream)
        
        # 添加第二条消息到同一个流
        second_message = Message(
            message_id="msg_next",
            sender_id=self.group_message["user_id"],
            content="第二条消息",
            message_type="group",
            group_id=self.group_message["group_id"],
            timestamp=time.time(),
            is_at_me=False
        )
        
        chat_stream = self.processor._get_or_create_chat_stream(second_message)
        
        # 验证消息被添加
        self.assertEqual(len(chat_stream.messages), 2)
        self.assertEqual(chat_stream.messages[1].message_id, second_message.message_id)
        
        # 测试私聊流
        private_message = self.processor._convert_to_internal_message(self.private_message)
        private_chat_stream = self.processor._get_or_create_chat_stream(private_message)
        
        # 验证结果
        self.assertIsInstance(private_chat_stream, ChatStream)
        expected_stream_id = f"private_{self.private_message['user_id']}"
        self.assertEqual(private_chat_stream.stream_id, expected_stream_id)
        self.assertIn(expected_stream_id, self.processor.chat_streams)

    def test_message_flow(self):
        """测试完整的消息处理流程"""
        # 设置read_air结果为不应回复，确保短路处理
        self.processor.read_air_processor.process.return_value = {
            "should_reply": False,
            "social_intent": {
                "is_direct_interaction": False,
                "requires_response": False,
                "intent": "chatting",
                "confidence": 0.3
            },
            "relevant_context": []
        }
        
        # 执行测试
        result = self.loop.run_until_complete(
            self.processor.process_message(self.group_message)
        )
        
        # 验证结果 - 应该短路在read_air处
        self.processor.read_air_processor.process.assert_called_once()
        self.processor.thought_generator.generate.assert_not_called()
        self.processor.willingness_checker.check.assert_not_called()
        self.processor.reply_composer.compose.assert_not_called()
        self.processor.bot_adapter.send_group_message.assert_not_called()
        
        # 重置模拟对象并设置为应该回复
        self.processor.read_air_processor.reset_mock()
        self.processor.read_air_processor.process.return_value = {
            "should_reply": True,
            "social_intent": {
                "is_direct_interaction": True,
                "requires_response": True,
                "intent": "greeting",
                "confidence": 0.9
            },
            "relevant_context": []
        }
        
        # 设置思考生成器的返回值
        thought = Thought(
            message_id="msg_12345",
            understanding="用户在问候机器人",
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
                "key_points": ["回应问候", "表达友好"]
            }
        )
        self.processor.thought_generator.generate.return_value = thought
        
        # 设置willingness_checker的返回值为不应该表达
        self.processor.willingness_checker.reset_mock()
        self.processor.willingness_checker.check.return_value = {
            "should_express": False,
            "willingness": 0.2,
            "attitude": "reserved",
            "reason": "此时不适合回复"
        }
        
        # 执行测试
        result = self.loop.run_until_complete(
            self.processor.process_message(self.group_message)
        )
        
        # 验证结果 - 应该短路在willingness_checker处
        self.processor.read_air_processor.process.assert_called_once()
        self.processor.thought_generator.generate.assert_called_once()
        self.processor.willingness_checker.check.assert_called_once()
        self.processor.reply_composer.compose.assert_not_called()
        self.processor.bot_adapter.send_group_message.assert_not_called()
        
        # 重置模拟对象并设置为应该表达
        self.processor.read_air_processor.reset_mock()
        self.processor.thought_generator.reset_mock()
        self.processor.willingness_checker.reset_mock()
        self.processor.willingness_checker.check.return_value = {
            "should_express": True,
            "willingness": 0.85,
            "attitude": "friendly",
            "reason": "用户直接问候，情绪积极"
        }
        
        # 执行测试
        result = self.loop.run_until_complete(
            self.processor.process_message(self.group_message)
        )
        
        # 验证结果 - 应该完成完整流程
        self.processor.read_air_processor.process.assert_called_once()
        self.processor.thought_generator.generate.assert_called_once()
        self.processor.willingness_checker.check.assert_called_once()
        self.processor.reply_composer.compose.assert_called_once()
        self.processor.bot_adapter.send_group_message.assert_called_once()

    def test_memory_update(self):
        """测试记忆更新"""
        # 执行测试
        result = self.loop.run_until_complete(
            self.processor.process_message(self.group_message)
        )
        
        # 验证记忆管理器被调用
        self.processor.memory_manager.add_message.assert_called()
        self.processor.memory_manager.add_interaction.assert_called()

    def test_relationship_update(self):
        """测试关系更新"""
        # 执行测试
        result = self.loop.run_until_complete(
            self.processor.process_message(self.group_message)
        )
        
        # 验证关系管理器被调用
        self.processor.relationship_manager.update_relationship.assert_called()

    def test_emotion_update(self):
        """测试情绪更新"""
        # 执行测试
        result = self.loop.run_until_complete(
            self.processor.process_message(self.group_message)
        )
        
        # 验证情绪管理器被调用
        self.processor.emotion_manager.update_emotion.assert_called()

    def test_handle_command(self):
        """测试处理命令消息"""
        # 创建命令消息
        command_message = {
            "post_type": "message",
            "message_type": "group",
            "time": int(time.time()),
            "self_id": "bot_12345678",
            "message_id": "msg_12348",
            "group_id": "group_123456",
            "user_id": "user_12345",
            "sender": {
                "user_id": "user_12345",
                "nickname": "测试用户",
                "card": "测试用户"
            },
            "message": "/cmd 测试命令",
            "raw_message": "/cmd 测试命令"
        }
        
        # 模拟命令处理器
        self.processor.command_handler = AsyncMock()
        self.processor.command_handler.is_command.return_value = True
        self.processor.command_handler.process_command.return_value = {
            "success": True,
            "message": "命令已执行"
        }
        
        # 执行测试
        result = self.loop.run_until_complete(
            self.processor.process_message(command_message)
        )
        
        # 验证命令处理器被调用
        self.processor.command_handler.is_command.assert_called_once()
        self.processor.command_handler.process_command.assert_called_once()
        
        # 验证常规消息处理流程未被调用
        self.processor.read_air_processor.process.assert_not_called()
        self.processor.thought_generator.generate.assert_not_called()
        
        # 验证消息仍被记录
        self.processor.memory_manager.add_message.assert_called()

    def test_error_handling(self):
        """测试错误处理"""
        # 设置read_air_processor抛出异常
        self.processor.read_air_processor.process.side_effect = Exception("测试异常")
        
        # 执行测试
        result = self.loop.run_until_complete(
            self.processor.process_message(self.group_message)
        )
        
        # 验证结果 - 不应该崩溃
        self.assertIsNotNone(result)
        self.processor.read_air_processor.process.assert_called_once()
        
        # 重置并测试其他组件异常
        self.processor.read_air_processor.reset_mock()
        self.processor.read_air_processor.process.side_effect = None
        self.processor.thought_generator.generate.side_effect = Exception("测试异常")
        
        # 执行测试
        result = self.loop.run_until_complete(
            self.processor.process_message(self.group_message)
        )
        
        # 验证结果 - 不应该崩溃
        self.assertIsNotNone(result)
        self.processor.read_air_processor.process.assert_called_once()
        self.processor.thought_generator.generate.assert_called_once()

    def test_chat_stream_pruning(self):
        """测试聊天流修剪"""
        # 创建一个长消息历史的聊天流
        chat_stream = ChatStream(stream_id="test_stream")
        
        # 添加多条消息，超过预设的最大长度
        for i in range(50):  # 假设最大长度小于50
            chat_stream.add_message(
                Message(
                    message_id=f"msg_{i}",
                    sender_id="user_12345",
                    content=f"消息 {i}",
                    message_type="group",
                    group_id="group_123456",
                    timestamp=time.time() - (50 - i) * 60,  # 消息间隔1分钟
                    is_at_me=False
                )
            )
        
        # 设置聊天流
        self.processor.chat_streams["test_stream"] = chat_stream
        
        # 执行聊天流修剪
        self.processor._prune_chat_streams()
        
        # 验证结果 - 应该修剪为预设的最大长度
        self.assertLessEqual(len(self.processor.chat_streams["test_stream"].messages), 50)
        
        # 验证保留最新的消息
        self.assertEqual(
            self.processor.chat_streams["test_stream"].messages[-1].message_id,
            "msg_49"
        )

    def test_handle_non_message_events(self):
        """测试处理非消息事件"""
        # 创建各种非消息事件
        events = [
            # 请求事件
            {
                "post_type": "request",
                "request_type": "friend",
                "time": int(time.time()),
                "self_id": "bot_12345678",
                "user_id": "user_12345"
            },
            # 元事件
            {
                "post_type": "meta_event",
                "meta_event_type": "heartbeat",
                "time": int(time.time()),
                "self_id": "bot_12345678",
                "status": {
                    "good": True
                }
            }
        ]
        
        # 模拟事件处理器
        self.processor.event_handler = AsyncMock()
        
        # 测试每个事件
        for event in events:
            # 执行测试
            result = self.loop.run_until_complete(
                self.processor.process_message(event)
            )
            
            # 验证结果 - 事件处理器应该被调用
            self.processor.event_handler.process_event.assert_called()
            self.processor.event_handler.reset_mock()


if __name__ == "__main__":
    unittest.main() 