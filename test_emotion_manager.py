#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
林镜(LingJing) - 情绪管理器测试脚本
"""

import sys
import os
import asyncio

# 添加项目根目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = current_dir
sys.path.append(root_dir)

async def test_emotion_manager():
    """测试情绪管理器功能"""
    try:
        # 导入情绪管理器
        from linjing.emotion.emotion_manager import EmotionManager
        
        print("1. 创建情绪管理器实例...")
        # 创建实例
        emotion_manager = EmotionManager()
        print("✓ 成功创建情绪管理器实例")
        
        # 初始化
        print("\n2. 初始化情绪管理器...")
        await emotion_manager.initialize()
        print("✓ 情绪管理器初始化成功")
        
        # 获取当前情绪
        print("\n3. 测试获取当前情绪...")
        current_emotion = await emotion_manager.get_current_emotion()
        print(f"当前情绪: {current_emotion['emotion']}, 强度: {current_emotion['intensity']}")
        
        # 测试更新情绪
        print("\n4. 测试更新情绪...")
        updated_emotion = await emotion_manager.update_emotion(
            emotion_type="joy",
            intensity_change=0.3,
            reason="收到用户的友好消息"
        )
        print(f"更新后情绪: {updated_emotion['emotion']}, 强度: {updated_emotion['intensity']}")
        
        # 测试事件影响
        print("\n5. 测试事件影响...")
        event_emotion = await emotion_manager.apply_event_impact(
            event_type="greeting",
            impact_level=0.5,
            description="用户打招呼"
        )
        print(f"事件后情绪: {event_emotion['emotion']}, 强度: {event_emotion['intensity']}")
        
        # 获取情绪历史
        print("\n6. 测试获取情绪历史...")
        history = await emotion_manager.get_emotion_history(limit=3)
        print(f"情绪历史记录: {len(history)} 条")
        for i, record in enumerate(history):
            print(f"  [{i+1}] {record['timestamp']}: {record['emotion']} ({record['intensity']})")
        
        # 测试重置情绪
        print("\n7. 测试重置情绪...")
        reset_emotion = await emotion_manager.reset_emotion()
        print(f"重置后情绪: {reset_emotion['emotion']}, 强度: {reset_emotion['intensity']}")
        
        print("\n情绪管理器测试完成!")
        return True
        
    except ImportError as e:
        print(f"✗ 导入情绪管理器模块失败: {e}")
        return False
    except Exception as e:
        print(f"✗ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    asyncio.run(test_emotion_manager()) 