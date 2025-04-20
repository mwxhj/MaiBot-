#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
队列管理器测试脚本
"""

import asyncio
import sys
import os
import logging

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 正确导入路径
from linjing.concurrent.queue_manager import (
    RequestQueueManager,
    RequestQueueType,
    RequestStatus
)

# 设置日志级别
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


async def test_new_queue_manager():
    """测试新的队列管理器功能"""
    print("=== 测试新的队列管理器 ===")
    
    # 创建队列管理器
    manager = RequestQueueManager()
    
    # 启动管理器
    await manager.start()
    print("队列管理器已启动")
    
    try:
        # 测试处理函数
        async def process_data(data):
            print(f"处理数据: {data}")
            await asyncio.sleep(1)
            return {"success": True, "data": f"已处理 {data}"}
        
        # 添加请求
        print("添加请求...")
        task = await manager.add_request(
            queue_type=RequestQueueType.MESSAGE,
            data={"message": "测试消息"},
            processor=process_data
        )
        
        print(f"请求已添加: {task.request_id}, 状态: {task.status.name}")
        
        # 等待结果
        print("等待结果...")
        result = await task.future
        print(f"请求处理完成，结果: {result}")
        
        # 获取状态
        status = await manager.get_status()
        print(f"队列状态: {status}")
    finally:
        # 停止管理器
        await manager.stop()
        print("队列管理器已停止")


async def test_backward_compatibility():
    """测试向后兼容功能"""
    print("\n=== 测试向后兼容功能 ===")
    
    # 创建队列管理器
    manager = RequestQueueManager()
    
    # 启动管理器
    await manager.start()
    print("队列管理器已启动")
    
    try:
        # 测试处理函数(旧格式)
        async def process_message(message, context):
            print(f"处理消息: {message}, 上下文: {context}")
            await asyncio.sleep(1)
            return {"success": True, "message": "已处理"}
        
        # 使用旧的添加消息接口
        print("使用旧接口添加消息...")
        success = await manager.add_message(
            message={"content": "测试消息"},
            context={"session_id": "test_session"},
            processor=process_message
        )
        
        print(f"消息添加{'' if success else '失败'}")
        
        # 等待处理完成
        await asyncio.sleep(2)
        
        # 获取状态(旧格式)
        status = await manager.get_queue_status()
        print(f"旧格式队列状态: {status}")
    finally:
        # 停止管理器
        await manager.stop()
        print("队列管理器已停止")


async def main():
    """测试主函数"""
    # 测试新队列管理器
    await test_new_queue_manager()
    
    # 测试向后兼容性
    await test_backward_compatibility()


if __name__ == "__main__":
    asyncio.run(main()) 