#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
林镜(LingJing) - 最简版演示脚本
"""

import sys
import os

# 确保项目根目录在Python路径中
project_dir = os.path.dirname(os.path.abspath(__file__))
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)

def try_import(module_name):
    """尝试导入模块并报告结果"""
    try:
        exec(f"import {module_name}")
        print(f"✓ 成功导入: {module_name}")
        return True
    except Exception as e:
        print(f"✗ 导入失败: {module_name} - {str(e)}")
        return False

def main():
    """主函数"""
    print("林镜(LingJing)最简版演示")
    print("=" * 50)
    
    # 尝试导入各个模块
    modules = [
        "linjing",
        "linjing.models",
        "linjing.models.message_models",
        "linjing.models.chat_stream",
        "linjing.server",
        "linjing.server.onebot_proxy",
        "linjing.utils",
        "linjing.utils.logger",
        "linjing.exceptions"
    ]
    
    success = 0
    for module in modules:
        if try_import(module):
            success += 1
    
    print(f"成功导入 {success}/{len(modules)} 个模块")
    
    # 创建简单的消息实例
    try:
        from linjing.models.message_models import Message, MessageContent, MessageSegment
        
        content = MessageContent()
        content.add_text("这是一条测试消息")
        
        message = Message(
            id="test_msg_001",
            type="message",
            message_type="private",
            sender={
                "user_id": 12345678,
                "nickname": "测试用户"
            },
            content=content,
            time="2023-01-01 12:00:00",
            self_id=87654321
        )
        
        print(f"成功创建消息对象: {message.id}")
        print(f"消息内容: {message.content.get_plain_text()}")
        
        # 测试ChatStream
        try:
            from linjing.models.chat_stream import ChatStream
            
            # 创建聊天流
            chat_stream = ChatStream()
            print(f"成功创建聊天流对象: {chat_stream}")
            
            # 添加消息到聊天流
            chat_stream.add_message(message)
            print(f"成功添加消息到聊天流，当前消息数: {len(chat_stream)}")
            
            # 获取最近消息
            recent_messages = chat_stream.get_messages(limit=5)
            print(f"获取最近消息: {len(recent_messages)} 条")
            
            # 测试聊天上下文
            chat_stream.set_context("user_name", "测试用户")
            chat_stream.set_temporary_context("greeting", "你好", ttl=60)
            
            print(f"聊天上下文 - 用户名: {chat_stream.get_context('user_name')}")
            print(f"临时上下文 - 问候: {chat_stream.get_context('greeting')}")
            
            print("聊天流测试成功")
        except Exception as e:
            print(f"聊天流测试失败: {e}")
    except Exception as e:
        print(f"创建消息对象失败: {e}")
    
    print("=" * 50)
    print("演示完成")

if __name__ == "__main__":
    main() 