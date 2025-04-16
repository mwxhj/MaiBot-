#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
林镜(LingJing) - 情绪管理器测试脚本
"""

import sys
import os
import asyncio
from typing import Dict, Any

# 确保项目根目录在Python路径中
project_dir = os.path.dirname(os.path.abspath(__file__))
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)

async def test_emotion_manager():
    """测试情绪管理器功能"""
    print("测试情绪管理器...")
    
    try:
        # 导入情绪管理器
        from linjing.emotion.emotion_manager import EmotionManager
        
        # 创建实例
        emotion_manager = EmotionManager()
        print("成功创建情绪管理器实例")
        
        # 初始化
        await emotion_manager.initialize()
        print("情绪管理器初始化成功")
        
        # 获取当前情绪
        current_emotion = await emotion_manager.get_current_emotion()
        print(f"当前情绪: {current_emotion['emotion']}, 强度: {current_emotion['intensity']}")
        
        # 测试更新情绪
        updated_emotion = await emotion_manager.update_emotion(
            emotion_type="joy",
            intensity_change=0.3,
            reason="测试情绪更新"
        )
        print(f"更新后情绪: {updated_emotion['emotion']}, 强度: {updated_emotion['intensity']}")
        
        # 测试事件影响
        event_emotion = await emotion_manager.apply_event_impact(
            event_type="greeting",
            impact_level=0.5,
            description="测试事件影响"
        )
        print(f"事件后情绪: {event_emotion['emotion']}, 强度: {event_emotion['intensity']}")
        
        # 获取情绪历史
        history = await emotion_manager.get_emotion_history(limit=3)
        print(f"情绪历史记录: {len(history)} 条")
        
        # 测试模拟消息处理
        try:
            from linjing.models.message_models import Message, MessageContent
            
            # 创建测试消息
            content = MessageContent()
            content.add_text("这是一条让人开心的消息！")
            
            message = Message(
                id="test_msg_002",
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
            
            # 处理消息
            message_emotion = await emotion_manager.process_message(message)
            if message_emotion:
                print(f"消息处理后情绪: {message_emotion['emotion']}, 强度: {message_emotion['intensity']}")
            else:
                print("消息处理未产生情绪变化")
        
        except Exception as e:
            print(f"消息处理测试失败: {e}")
        
        # 测试重置情绪
        reset_emotion = await emotion_manager.reset_emotion()
        print(f"重置后情绪: {reset_emotion['emotion']}, 强度: {reset_emotion['intensity']}")
        
        return True
        
    except Exception as e:
        print(f"情绪管理器测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """主函数"""
    print("林镜(LingJing)情绪管理器测试")
    print("=" * 50)
    
    # 测试情绪管理器
    emotion_result = await test_emotion_manager()
    
    print("=" * 50)
    print(f"情绪管理器测试: {'成功' if emotion_result else '失败'}")
    print("测试完成")

if __name__ == "__main__":
    asyncio.run(main()) 