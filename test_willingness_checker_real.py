#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
使用实际代码测试林镜(LingJing)中回应意愿检查器（WillingnessChecker）的功能
"""

import asyncio
from datetime import datetime

from linjing.core.willingness_checker import WillingnessChecker, get_willingness_checker
from linjing.models.message_models import Message, Sender, MessageContent
from linjing.models import ChatStream


async def test_willingness_checker():
    """测试回应意愿检查器的功能"""
    
    print("开始测试WillingnessChecker(使用实际代码)...")
    
    # 获取单例实例
    willingness_checker = await get_willingness_checker()
    
    # 创建测试消息
    def create_test_message(content="你好", message_type="private", at_me=False):
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
    
    # 创建思维内容
    def create_thought_content(intent_type="statements", emotional_type="neutral"):
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
    
    # 测试私聊消息
    print("\n测试私聊消息...")
    message = create_test_message(content="你好", message_type="private")
    thought_content = create_thought_content(intent_type="greetings")
    chat_stream = ChatStream()
    
    will_respond, response_info = await willingness_checker.check_willingness(
        message, thought_content, chat_stream
    )
    
    print(f"是否回应: {will_respond}")
    print(f"回应态度: {response_info['attitude']}")
    print(f"回应原因: {response_info['reason']}")
    
    # 测试包含关键词的消息
    print("\n测试包含关键词的消息...")
    message = create_test_message(content="林镜你好", message_type="private")
    thought_content = create_thought_content(intent_type="greetings")
    
    will_respond, response_info = await willingness_checker.check_willingness(
        message, thought_content, chat_stream
    )
    
    print(f"是否回应: {will_respond}")
    print(f"回应态度: {response_info['attitude']}")
    print(f"关键词加分: {response_info['reason']['keyword_bonus']}")
    
    # 测试群聊消息
    print("\n测试群聊消息...")
    message = create_test_message(content="大家好", message_type="group")
    thought_content = create_thought_content(intent_type="greetings")
    
    will_respond, response_info = await willingness_checker.check_willingness(
        message, thought_content, chat_stream
    )
    
    print(f"是否回应: {will_respond}")
    print(f"回应态度: {response_info['attitude']}")
    
    # 测试@我的群聊消息
    print("\n测试@我的群聊消息...")
    message = create_test_message(content="@林镜 你好", message_type="group", at_me=True)
    thought_content = create_thought_content(intent_type="greetings")
    
    will_respond, response_info = await willingness_checker.check_willingness(
        message, thought_content, chat_stream
    )
    
    print(f"是否回应: {will_respond}")
    print(f"回应态度: {response_info['attitude']}")
    
    print("\nWillingnessChecker测试完成")


if __name__ == "__main__":
    # 运行测试
    asyncio.run(test_willingness_checker()) 