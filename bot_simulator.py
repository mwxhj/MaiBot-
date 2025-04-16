#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
林镜(LingJing) - 机器人消息模拟工具
用于在开发和测试环境中模拟向机器人发送消息，无需依赖外部消息源
"""

import asyncio
import json
import uuid
import time
import os
import sys
from datetime import datetime
from typing import Dict, Any, Optional

# 确保林镜项目在Python路径中
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

# 从林镜项目导入实际组件
try:
    from linjing.models.message_models import Message, Sender, MessageContent
    from linjing.core.message_processor import MessageProcessor
    from linjing.models.chat_stream import ChatStream
    from linjing.core.thought_generator import get_thought_generator
    from linjing.core.willingness_checker import get_willingness_checker
    from linjing.emotion import get_emotion_manager
    from linjing.relationship import get_relationship_manager
    from linjing.services.llm_interface import get_llm_interface
    from linjing.utils.logger import get_logger
    
    # 设置日志器
    logger = get_logger("bot_simulator")
    logger.info("成功导入林镜项目组件")
    USING_REAL_COMPONENTS = True
except ImportError as e:
    # 导入失败时回退到简化版
    print(f"导入林镜项目组件失败: {e}")
    print("回退到简化版模拟器...")
    USING_REAL_COMPONENTS = False
    
    # 简化版消息类实现
    class Sender:
        def __init__(self, user_id, nickname):
            self.user_id = user_id
            self.nickname = nickname
            self.is_self = False

    class MessageContent:
        def __init__(self):
            self.raw_content = ""
            self.segments = []
        
        def add_text(self, text):
            self.segments.append({"type": "text", "content": text})
        
        def __str__(self):
            return self.raw_content

    class Message:
        def __init__(self, id, type, message_type, sender, content, time, self_id):
            self.id = id
            self.type = type
            self.message_type = message_type
            self.sender = sender
            self.content = content
            self.time = time
            self.self_id = self_id
            self.is_at_me = False
            self.group_id = None

    class ChatStream:
        def __init__(self):
            self.messages = []
        
        def add_message(self, message):
            self.messages.append(message)
        
        def get_messages(self):
            return self.messages

    # 简化版消息处理器
    from simple_message_processor import MessageProcessor
    logger = None


class BotSimulator:
    """机器人消息模拟器，用于测试消息处理和回复功能"""
    
    def __init__(self):
        """初始化模拟器"""
        self.message_processor = None
        self.chat_stream = ChatStream()
        self.self_id = "12345678"  # 机器人自己的ID
        self.user_id = "98765432"  # 模拟用户ID
        self.user_nickname = "测试用户"  # 模拟用户昵称
        self.group_id = "11223344"  # 模拟群组ID
        self.initialized = False
        
    async def initialize(self):
        """初始化消息处理器"""
        if self.initialized:
            return
            
        if USING_REAL_COMPONENTS:
            print("正在初始化林镜实际组件...")
            
            try:
                # 初始化LLM接口
                print("初始化LLM接口...")
                llm_interface = await get_llm_interface()
                
                # 初始化情绪管理器
                print("初始化情绪管理器...")
                emotion_manager = await get_emotion_manager()
                
                # 初始化关系管理器
                print("初始化关系管理器...")
                relationship_manager = await get_relationship_manager()
                
                # 初始化意愿检查器
                print("初始化意愿检查器...")
                willingness_checker = await get_willingness_checker()
                
                # 初始化思考生成器
                print("初始化思考生成器...")
                thought_generator = await get_thought_generator()
                
                # 创建和初始化消息处理器
                print("初始化消息处理器...")
                self.message_processor = MessageProcessor()
                await self.message_processor.initialize()
                
                print("所有组件初始化完成，使用实际的林镜项目组件")
            
            except Exception as e:
                print(f"初始化林镜组件失败: {e}")
                import traceback
                traceback.print_exc()
                print("回退到简化版模拟器...")
                USING_REAL_COMPONENTS = False
                self.message_processor = MessageProcessor()
                await self.message_processor.initialize()
        else:
            print("使用简化版消息处理器...")
            self.message_processor = MessageProcessor()
            await self.message_processor.initialize()
        
        self.initialized = True
        print("消息处理器初始化完成，可以开始发送消息了！")
        
    async def send_message(self, content: str, message_type: str = "private", is_at_me: bool = False):
        """
        向机器人发送模拟消息
        
        Args:
            content: 消息内容
            message_type: 消息类型，"private"或"group"
            is_at_me: 是否@机器人（群聊中有效）
        """
        if not self.initialized:
            await self.initialize()
            
        # 创建发送者
        sender = Sender(user_id=self.user_id, nickname=self.user_nickname)
        
        # 创建消息内容
        message_content = MessageContent()
        message_content.raw_content = content
        message_content.add_text(content)
        
        # 创建消息
        message = Message(
            id=f"sim_{uuid.uuid4().hex[:8]}",
            type="message",
            message_type=message_type,
            sender=sender,
            content=message_content,
            time=datetime.now(),
            self_id=self.self_id
        )
        
        # 如果是群组消息，添加群组ID
        if message_type == "group":
            message.group_id = self.group_id
            
        # 设置@我的属性
        message.is_at_me = is_at_me
        
        # 处理消息
        print(f"\n[用户消息] {content}")
        try:
            print("正在处理消息...")
            if USING_REAL_COMPONENTS:
                print("使用实际的林镜消息处理流程")
            else:
                print("使用简化版消息处理流程")
                
            response = await self.message_processor.process_message(message, self.chat_stream)
            
            # 模拟消息处理延迟
            time.sleep(0.5)
            
            # 显示处理结果
            if response:
                if isinstance(response, dict) and "content" in response:
                    print(f"\n[机器人回复] {response['content']}")
                else:
                    print(f"\n[机器人回复] {response}")
            else:
                print("\n[机器人选择不回复]")
                
        except Exception as e:
            print(f"\n[错误] 消息处理失败: {e}")
            import traceback
            traceback.print_exc()
            
    async def interactive_mode(self):
        """交互模式，通过命令行接收用户输入并发送消息"""
        print("欢迎使用林镜机器人模拟器！输入 'exit' 退出，'help' 查看帮助。")
        print("默认为私聊模式，输入 'mode group' 切换到群聊模式，'mode private' 切换回私聊模式。")
        print("在群聊模式下，输入 '@林镜 你好' 可以模拟@机器人。")
        
        if USING_REAL_COMPONENTS:
            print("当前使用林镜实际组件进行对话")
        else:
            print("当前使用简化版模拟器进行对话")
        
        current_mode = "private"
        
        while True:
            try:
                user_input = input("\n请输入消息 > ")
                
                if user_input.lower() == 'exit':
                    print("退出模拟器...")
                    break
                    
                elif user_input.lower() == 'help':
                    print("\n帮助信息:")
                    print("- 输入消息内容直接发送消息")
                    print("- 'mode group' - 切换到群聊模式")
                    print("- 'mode private' - 切换到私聊模式")
                    print("- 群聊模式下，@ 开头的消息将被视为@机器人")
                    print("- 'reload' - 重新加载模拟器")
                    print("- 'exit' - 退出模拟器")
                    continue
                    
                elif user_input.lower() == 'reload':
                    print("重新加载模拟器...")
                    self.initialized = False
                    await self.initialize()
                    continue
                    
                elif user_input.lower().startswith('mode '):
                    mode = user_input.lower().split(' ')[1]
                    if mode in ['private', 'group']:
                        current_mode = mode
                        print(f"已切换到{current_mode}模式")
                    else:
                        print("无效的模式，有效选项: private, group")
                    continue
                
                # 检查是否是@机器人
                is_at_me = False
                if current_mode == "group" and user_input.startswith("@"):
                    is_at_me = True
                
                # 发送消息
                await self.send_message(user_input, current_mode, is_at_me)
                
            except KeyboardInterrupt:
                print("\n接收到退出信号，退出模拟器...")
                break
            except Exception as e:
                print(f"发生错误: {e}")
                import traceback
                traceback.print_exc()


async def main():
    """主函数"""
    simulator = BotSimulator()
    await simulator.initialize()
    await simulator.interactive_mode()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n程序已终止")
    except Exception as e:
        print(f"程序运行出错: {e}")
        import traceback
        traceback.print_exc() 