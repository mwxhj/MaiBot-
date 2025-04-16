#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
林镜(LingJing) - LLM接口测试脚本
"""

import sys
import os
import asyncio

# 添加项目根目录到Python路径
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = current_dir
sys.path.append(root_dir)

async def test_llm_interface():
    """测试LLM接口基本功能"""
    try:
        from linjing.llm.llm_interface import get_llm_interface
        from linjing.exceptions import LLMError, LLMAuthenticationError
        
        print("1. 初始化LLM接口...")
        try:
            llm = await get_llm_interface()
            print(f"✓ 成功初始化LLM接口")
            print(f"  - 使用模型: {llm.default_model}")
            print(f"  - 提供商: {llm.provider}")
        except LLMAuthenticationError as e:
            print(f"✗ LLM认证错误: {e}")
            print("  请在配置文件中设置有效的API密钥")
            return
        except LLMError as e:
            print(f"✗ LLM初始化错误: {e}")
            return
        
        # 测试健康检查
        print("\n2. 测试LLM健康检查...")
        try:
            health_status, message = await llm.health_check()
            if health_status:
                print(f"✓ 健康检查通过: {message}")
            else:
                print(f"✗ 健康检查失败: {message}")
        except Exception as e:
            print(f"✗ 健康检查出错: {e}")
        
        # 测试文本生成
        print("\n3. 测试文本生成...")
        try:
            prompt = "你好，请给我讲个故事"
            print(f"  发送提示: '{prompt}'")
            response = await llm.chat_completion(prompt)
            print(f"  响应: '{response[:100]}...'")
        except Exception as e:
            print(f"✗ 文本生成失败: {e}")
        
        # 测试结构化输出
        print("\n4. 测试结构化输出...")
        try:
            schema_prompt = [
                {"role": "system", "content": "你需要生成一个JSON结构，包含以下字段：mood、topic、suggestions"},
                {"role": "user", "content": prompt}
            ]
            print(f"  发送结构化提示")
            response_format = {"type": "json_object"}
            structured_response = await llm.chat_completion(schema_prompt, response_format=response_format)
            
            try:
                structured_output = llm.parse_json_response(structured_response)
                print(f"  解析后的结构化输出: {structured_output}")
            except Exception as e:
                print(f"✗ 解析结构化输出失败: {e}")
                print(f"  原始响应: '{structured_response[:100]}...'")
        except Exception as e:
            print(f"✗ 结构化输出生成失败: {e}")
        
        print("\nLLM接口测试完成!")
        
    except ImportError as e:
        print(f"✗ 导入LLM接口模块失败: {e}")
    except Exception as e:
        print(f"✗ 测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_llm_interface()) 