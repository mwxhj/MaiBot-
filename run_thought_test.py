#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
林镜(LingJing) - 思维生成器测试脚本
"""

import sys
import os
import asyncio
from typing import Dict, Any

# 确保项目根目录在Python路径中
project_dir = os.path.dirname(os.path.abspath(__file__))
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)

async def test_thought_generator():
    """测试思维生成器功能"""
    print("测试思维生成器...")
    
    try:
        # 导入思维生成器和相关模型
        from linjing.core.thought_generator import get_thought_generator
        from linjing.models.message_models import Message
        from linjing.models.chat_stream import ChatStream
        
        # 创建实例
        thought_generator = get_thought_generator()
        print("成功创建思维生成器实例")
        
        # 初始化
        await thought_generator.initialize()
        print("思维生成器初始化成功")
        
        # 创建测试消息
        message = Message(
            message_id="test_msg_001",
            message_type="private",
            sender_id="12345678",
            sender_name="测试用户",
            content="你好，今天天气真不错！",
            timestamp=1672565600.0,  # 2023-01-01 12:00:00
            is_at_me=False
        )
        
        # 创建聊天流
        chat_stream = ChatStream(stream_id="test_stream")
        chat_stream.add_message(message)
        
        # 测试思维生成
        print("测试思维生成...")
        thought = await thought_generator.generate_thought(
            chat_stream=chat_stream,
            current_message=message
        )
        print("思维生成成功")
        
        # 打印思维内容
        print("\n--- 生成的思维 ---")
        print(f"理解: {thought.understanding}")
        print(f"情感反应: {thought.emotional_response}")
        print(f"回应计划: {thought.response_plan}")
        
        return True
        
    except Exception as e:
        print(f"思维生成器测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """主函数"""
    print("林镜(LingJing)思维生成器测试")
    print("=" * 50)
    
    # 测试思维生成器
    thought_result = await test_thought_generator()
    
    print("=" * 50)
    print(f"思维生成器测试: {'成功' if thought_result else '失败'}")
    print("测试完成")

if __name__ == "__main__":
    asyncio.run(main()) 