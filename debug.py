#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
林镜(LingJing) - 调试脚本
"""

import os
import sys
import importlib
import pkgutil

def print_separator():
    print("=" * 50)

def list_project_structure():
    """打印项目结构"""
    print_separator()
    print("项目结构:")
    for root, dirs, files in os.walk("linjing"):
        level = root.replace("linjing", "").count(os.sep)
        indent = " " * 4 * level
        print(f"{indent}{os.path.basename(root)}/")
        sub_indent = " " * 4 * (level + 1)
        for f in files:
            if f.endswith(".py"):
                print(f"{sub_indent}{f}")

def check_module_imports():
    """检查模块导入情况"""
    print_separator()
    print("检查模块导入:")
    
    try:
        import linjing
        print(f"成功导入根模块: {linjing.__file__}")
        
        # 测试导入主要模块
        modules_to_check = [
            "linjing.config",
            "linjing.utils.logger",
            "linjing.server.onebot_proxy",
            "linjing.core.message_processor",
            "linjing.models.message_models",
            "linjing.memory.memory_manager",
            "linjing.emotion.emotion_manager",
            "linjing.llm.llm_interface"
        ]
        
        for module_name in modules_to_check:
            try:
                module = importlib.import_module(module_name)
                print(f"✓ {module_name}: {module.__file__}")
            except Exception as e:
                print(f"✗ {module_name}: {str(e)}")
    
    except Exception as e:
        print(f"导入根模块失败: {str(e)}")

def check_python_path():
    """检查Python路径"""
    print_separator()
    print("Python路径:")
    for path in sys.path:
        print(f"- {path}")

def main():
    """主函数"""
    print("林镜(LingJing)项目调试信息")
    print(f"当前工作目录: {os.getcwd()}")
    print(f"Python版本: {sys.version}")
    
    # 将项目根目录添加到Python路径
    root_dir = os.getcwd()
    if root_dir not in sys.path:
        sys.path.insert(0, root_dir)
        print(f"已添加 {root_dir} 到Python路径")
    
    check_python_path()
    list_project_structure()
    check_module_imports()

if __name__ == "__main__":
    main() 