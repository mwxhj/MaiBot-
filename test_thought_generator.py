#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
林镜(LingJing) - 思维生成器测试脚本
"""

import sys
import os
import asyncio
from datetime import datetime

# 添加项目根目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = current_dir
sys.path.append(root_dir)

async def test_thought_generator():
    """测试思维生成器功能"""
    try:
        # 导入思维生成器和相关模型
        from linjing.core.thought_generator import get_thought_generator
        
        print("1. 获取思维生成器实例...")
        thought_generator = await get_thought_generator()
        print("✓ 成功获取思维生成器实例")
        
        # 初始化
        print("\n2. 初始化思维生成器...")
        await thought_generator.initialize()
        print("✓ 思维生成器初始化成功")
        
        # 准备聊天流和消息
        print("\n3. 准备测试数据...")
        # 导入消息模型
        from linjing.models.message_models import Message, MessageContent, Sender, MessageSegment
        from linjing.models.chat_stream import ChatStream
        
        # 创建发送者
        sender = Sender(
            user_id=12345678,
            nickname="测试用户"
        )
        
        # 创建消息内容
        content = MessageContent()
        content.add_text("你好，今天天气真不错！能跟我介绍一下你自己吗？")
        
        # 创建测试消息
        message = Message(
            id="test_msg_001",
            type="message",
            message_type="private",
            sender=sender,
            content=content,
            time=datetime.now(),
            self_id=10000
        )
        
        # 创建聊天流
        chat_stream = ChatStream()
        chat_stream.add_message(message)
        print("✓ 测试数据准备完成")
        
        # 测试思维生成
        print("\n4. 测试思维生成...")
        try:
            thought = await thought_generator.generate_thought(
                chat_stream=chat_stream,
                current_message=message
            )
            print("✓ 思维生成成功")
            
            # 打印思维内容
            print("\n--- 生成的思维 ---")
            print(f"理解: {thought.understanding}")
            print(f"情感反应: {thought.emotional_response}")
            print(f"回应计划: {thought.response_plan}")
            
        except Exception as e:
            print(f"✗ 思维生成失败: {e}")
            import traceback
            traceback.print_exc()
        
        print("\n思维生成器测试完成!")
        return True
        
    except ImportError as e:
        print(f"✗ 导入思维生成器模块失败: {e}")
        return False
    except Exception as e:
        print(f"✗ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    asyncio.run(test_thought_generator()) 