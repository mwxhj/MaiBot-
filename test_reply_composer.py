#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
林镜(LingJing) - 回复生成器测试脚本
"""

import sys
import os
import asyncio
from datetime import datetime

# 添加项目根目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = current_dir
sys.path.append(root_dir)

async def test_reply_composer():
    """测试回复生成器功能"""
    try:
        # 导入回复生成器和相关模型
        from linjing.core.reply_composer import ReplyComposer, get_reply_composer
        from linjing.models.message_models import Message, MessageContent, Sender
        from linjing.models.chat_stream import ChatStream
        from linjing.models.thought import Thought
        
        print("1. 获取回复生成器实例...")
        reply_composer = get_reply_composer()
        print("✓ 成功获取回复生成器实例")
        
        # 初始化
        print("\n2. 初始化回复生成器...")
        await reply_composer.initialize()
        print("✓ 回复生成器初始化成功")
        
        # 创建测试数据
        print("\n3. 准备测试数据...")
        
        # 创建发送者
        sender = Sender(
            user_id="12345678",
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
            self_id="10000"
        )
        
        # 创建聊天流
        chat_stream = ChatStream()
        chat_stream.add_message(message)
        
        # 创建简单思维
        thought = Thought(
            message_id="test_msg_001",
            timestamp=datetime.now().timestamp(),
            understanding={
                "intent": "greeting",
                "topic": "自我介绍",
                "sentiment": "positive",
                "is_question": True,
                "keywords": ["你好", "天气", "介绍"]
            },
            emotional_response={
                "primary_emotion": "joy",
                "emotion_intensity": 0.7,
                "description": "这让我感到开心",
                "relationship_influence": 1.0,
                "causes": ["greeting", "自我介绍"]
            },
            response_plan={
                "priority": "high",
                "strategy": "informative",
                "description": "我应该友好地回应并做自我介绍",
                "should_reference_memory": False,
                "tone": "friendly",
                "key_points": ["回应问候", "自我介绍"]
            },
            raw_content="你好，今天天气真不错！能跟我介绍一下你自己吗？",
            metadata={
                "sender_id": "12345678",
                "message_type": "private",
                "group_id": None
            }
        )
        
        # 创建模拟意愿检查结果
        willingness_result = {
            "will_respond": True,
            "attitude": "friendly",
            "response_type": "normal",
            "delay": 0
        }
        
        print("✓ 测试数据准备完成")
        
        # 测试生成回复
        print("\n4. 测试生成回复...")
        try:
            # 模拟回复生成
            reply = await reply_composer.compose_reply(
                thought=thought,
                willingness_result=willingness_result,
                chat_stream=chat_stream,
                original_message=message
            )
            
            if reply:
                print("✓ 成功生成回复")
                print(f"\n--- 生成的回复 ---\n{reply}")
            else:
                print("✗ 回复生成返回了None")
                
        except Exception as e:
            print(f"✗ 回复生成失败: {e}")
            import traceback
            traceback.print_exc()
        
        # 测试不同态度的回复
        print("\n5. 测试不同态度的回复...")
        attitudes = ["neutral", "reserved"]
        
        for attitude in attitudes:
            try:
                willingness_result["attitude"] = attitude
                
                reply = await reply_composer.compose_reply(
                    thought=thought,
                    willingness_result=willingness_result,
                    chat_stream=chat_stream,
                    original_message=message
                )
                
                if reply:
                    print(f"✓ 成功生成 {attitude} 态度的回复")
                    print(f"\n--- {attitude} 态度的回复 ---\n{reply}")
                else:
                    print(f"✗ {attitude} 态度的回复生成返回了None")
                    
            except Exception as e:
                print(f"✗ {attitude} 态度的回复生成失败: {e}")
        
        # 测试不回复的情况
        print("\n6. 测试不回复的情况...")
        willingness_result["will_respond"] = False
        
        try:
            reply = await reply_composer.compose_reply(
                thought=thought,
                willingness_result=willingness_result,
                chat_stream=chat_stream,
                original_message=message
            )
            
            if reply is None:
                print("✓ 正确处理了不回复的情况")
            else:
                print(f"✗ 应该不回复但生成了回复: {reply}")
                
        except Exception as e:
            print(f"✗ 测试不回复情况时出错: {e}")
        
        print("\n回复生成器测试完成!")
        return True
        
    except ImportError as e:
        print(f"✗ 导入回复生成器模块失败: {e}")
        return False
    except Exception as e:
        print(f"✗ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    asyncio.run(test_reply_composer()) 