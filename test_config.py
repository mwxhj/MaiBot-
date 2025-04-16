#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
林镜(LingJing) - 配置系统测试脚本
"""

import sys
import os
import json

# 添加项目根目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = current_dir
sys.path.append(root_dir)

def test_config():
    """测试配置系统的基本功能"""
    from linjing.config import load_config, get_config, update_config, save_config
    
    print("1. 测试配置加载...")
    # 加载默认配置
    config = load_config()
    if config:
        print("✓ 成功加载默认配置")
    else:
        print("✗ 加载默认配置失败")
        return
    
    # 检查关键配置项
    print("\n2. 检查关键配置项...")
    check_keys = ["server", "logging", "llm", "memory", "emotion", "plugins"]
    for key in check_keys:
        if key in config:
            print(f"✓ 找到配置项: {key}")
        else:
            print(f"✗ 未找到配置项: {key}")
    
    # 测试获取特定配置
    print("\n3. 测试获取特定配置...")
    server_host = get_config("server", {}).get("host")
    print(f"服务器主机: {server_host}")
    llm_provider = get_config("llm", {}).get("provider")
    print(f"LLM提供商: {llm_provider}")
    
    # 测试更新配置
    print("\n4. 测试更新配置...")
    original_port = get_config("server", {}).get("port")
    print(f"原服务器端口: {original_port}")
    
    # 更新服务器端口
    server_config = get_config("server", {})
    server_config["port"] = 9000
    update_config("server", server_config)
    
    # 验证更新
    new_port = get_config("server", {}).get("port")
    print(f"新服务器端口: {new_port}")
    print(f"配置更新{'成功' if new_port == 9000 else '失败'}")
    
    # 测试添加新配置项
    print("\n5. 测试添加新配置项...")
    test_config = {"test_key": "test_value"}
    update_config("test", test_config)
    
    # 验证添加
    test_value = get_config("test", {}).get("test_key")
    print(f"测试值: {test_value}")
    print(f"添加新配置项{'成功' if test_value == 'test_value' else '失败'}")
    
    # 测试保存配置
    print("\n6. 测试保存配置...")
    # 创建临时配置文件
    temp_config_path = os.path.join(current_dir, "temp_config.json")
    save_result = save_config(temp_config_path)
    
    if save_result:
        print(f"✓ 配置成功保存到: {temp_config_path}")
        
        # 验证保存的内容
        try:
            with open(temp_config_path, 'r', encoding='utf-8') as f:
                saved_config = json.load(f)
            
            if saved_config.get("server", {}).get("port") == 9000:
                print("✓ 保存的配置内容正确")
            else:
                print("✗ 保存的配置内容不符合预期")
        except Exception as e:
            print(f"✗ 读取保存的配置失败: {e}")
        
        # 清理临时文件
        try:
            os.remove(temp_config_path)
            print(f"✓ 清理临时配置文件")
        except:
            print(f"✗ 清理临时配置文件失败")
    else:
        print(f"✗ 保存配置失败")
    
    # 重新加载默认配置并还原修改
    print("\n7. 测试重新加载配置...")
    config = load_config()
    server_config = get_config("server", {})
    server_config["port"] = original_port
    update_config("server", server_config)
    print(f"✓ 还原服务器端口为: {original_port}")
    
    print("\n配置系统测试完成!")

if __name__ == "__main__":
    test_config() 