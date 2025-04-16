#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
简化版消息处理器，用于测试模拟器
"""

import asyncio
import random
from typing import Dict, Any, Optional
from datetime import datetime

class MessageProcessor:
    """
    简化版消息处理器，用于模拟消息处理流程
    """
    
    def __init__(self):
        """初始化消息处理器"""
        self.initialized = False
        print("创建简化版消息处理器")
    
    async def initialize(self):
        """初始化消息处理器及其依赖"""
        print("初始化简化版消息处理器")
        self.initialized = True
    
    async def process_message(self, message, chat_stream):
        """
        处理接收到的消息并返回回复
        
        Args:
            message: 接收到的消息对象
            chat_stream: 聊天流对象
            
        Returns:
            dict/str: 回复内容
        """
        if not self.initialized:
            await self.initialize()
        
        try:
            # 简单的消息处理逻辑
            content = message.content.raw_content if hasattr(message.content, 'raw_content') else str(message.content)
            sender_name = message.sender.nickname if hasattr(message.sender, 'nickname') else "用户"
            message_type = message.message_type
            
            # 添加消息到聊天流
            if hasattr(chat_stream, 'add_message'):
                chat_stream.add_message(message)
            
            # 构建简单回复
            now = datetime.now().strftime("%H:%M:%S")
            
            # 群聊消息，但没有@我
            if message_type == "group" and not message.is_at_me:
                # 提高群聊中的回复概率到70%
                if random.random() < 0.7:  # 原来是0.3，现在提高到0.7
                    return f"[群聊回复] 我看到{sender_name}说: {content[:20]}...\n我想参与这个讨论。"
                return None  # 只有30%的概率不回复
                
            # 关键词响应 - 更具体的匹配
            if "你好" in content or "hello" in content.lower():
                return f"你好，{sender_name}！现在是 {now}。很高兴见到你！"
                
            elif "时间" in content or "几点" in content:
                return f"现在的时间是 {now}。有什么我可以帮你的吗？"
                
            elif "名字" in content or "谁" in content:
                return "我是林镜，一个聊天机器人。很高兴为你服务！"
                
            elif "谢谢" in content or "感谢" in content:
                return "不客气，我很乐意帮助你！随时都可以找我聊天。"
                
            elif "回我" in content:
                return f"当然会回复你，{sender_name}！我不会忽视任何私聊消息。"
                
            # 默认回复 - 私聊消息和@我的群聊消息总是回复
            else:
                return f"我收到了你的消息: '{content}'\n有什么我可以帮你的吗？"
                
        except Exception as e:
            print(f"处理消息时出错: {e}")
            # 发生错误时也返回一个回复，而不是让整个处理失败
            return "抱歉，处理你的消息时出现了一些问题。能请你换个方式表达吗？" 