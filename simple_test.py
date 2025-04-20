#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
简单测试脚本，用于验证模块导入
"""

import sys
import os

# 添加项目根目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

print(f"当前目录: {current_dir}")
print(f"Python路径: {sys.path}")

try:
    # 使用相对导入尝试导入模块
    import linjing.concurrent
    print("成功导入 linjing.concurrent 模块")
    print(f"模块路径: {linjing.concurrent.__file__}")
    
    # 导入 RequestQueueManager
    from linjing.concurrent import RequestQueueManager
    print("成功导入 RequestQueueManager")
    
    # 创建实例
    manager = RequestQueueManager()
    print(f"成功创建 RequestQueueManager 实例: {manager}")
    
except ImportError as e:
    print(f"导入错误: {e}")
    
    # 尝试直接导入
    try:
        sys.path.insert(0, os.path.join(current_dir, "MaiBot-"))
        from concurrent import queue_manager
        print("使用直接路径成功导入")
    except ImportError as e2:
        print(f"二次导入错误: {e2}")
        
        # 列出当前目录结构
        print("\n当前目录结构:")
        for root, dirs, files in os.walk(current_dir):
            level = root.replace(current_dir, '').count(os.sep)
            indent = ' ' * 4 * level
            print(f"{indent}{os.path.basename(root)}/")
            sub_indent = ' ' * 4 * (level + 1)
            for f in files:
                print(f"{sub_indent}{f}")

if __name__ == "__main__":
    print("测试完成") 