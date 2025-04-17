#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ModelRouterProvider功能测试脚本。

测试在同一个OpenAI API密钥下使用不同模型的能力。
"""

import os
import sys
import asyncio
import logging
import random
import argparse
import json
from typing import Dict, Any, List, Tuple, Optional
from pathlib import Path

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

# 加载环境变量
try:
    from dotenv import load_dotenv
    # 先尝试从项目根目录加载.env文件
    env_path = os.path.join(project_root, '.env')
    if os.path.exists(env_path):
        load_dotenv(env_path)
        print(f"已从 {env_path} 加载环境变量")
    else:
        print("未找到.env文件，将使用系统环境变量或模拟模式")
except ImportError:
    print("python-dotenv 库未安装，将使用系统环境变量或模拟模式")

from linjing.llm.llm_manager import LLMManager
from linjing.config import Config  # 使用新创建的Config类

# 配置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def override_config_with_env(config: Config):
    """从环境变量覆盖配置项"""
    # 获取OpenAI API密钥
    openai_api_key = os.environ.get("OPENAI_API_KEY")
    if openai_api_key and not openai_api_key.startswith("sk-xxxxxxx"):
        logger.info("使用环境变量中的OpenAI API密钥")
        
        # 更新OpenAI提供商配置
        providers = config.get("llm.providers", [])
        for provider in providers:
            if provider.get("type") == "openai":
                provider["api_key"] = openai_api_key
                
                # 如果环境变量中有API基础URL，也一并更新
                api_base = os.environ.get("OPENAI_API_BASE")
                if api_base:
                    provider["api_base"] = api_base
                    
                # 如果环境变量中有组织ID，也一并更新
                org_id = os.environ.get("OPENAI_ORG_ID")
                if org_id:
                    provider["organization"] = org_id
            
            # 同时更新模型路由提供商中的共享配置
            if provider.get("type") == "model_router" and provider.get("provider_type") == "openai":
                if "shared_config" in provider:
                    provider["shared_config"]["api_key"] = openai_api_key
                    
                    # 更新API基础URL和组织ID
                    api_base = os.environ.get("OPENAI_API_BASE")
                    if api_base:
                        provider["shared_config"]["api_base"] = api_base
                        
                    org_id = os.environ.get("OPENAI_ORG_ID")
                    if org_id:
                        provider["shared_config"]["organization"] = org_id
    else:
        logger.warning("环境变量中未找到有效的OPENAI_API_KEY，请设置或在配置文件中提供有效密钥")
    
    # 获取Azure API密钥
    azure_api_key = os.environ.get("AZURE_OPENAI_API_KEY")
    if azure_api_key and not azure_api_key.startswith("xxxxxxx"):
        logger.info("使用环境变量中的Azure OpenAI API密钥")
        
        # 获取其他Azure配置
        resource_name = os.environ.get("AZURE_RESOURCE_NAME")
        api_base = os.environ.get("AZURE_API_BASE")
        deployment_name = os.environ.get("AZURE_DEPLOYMENT_NAME")
        embedding_deployment = os.environ.get("AZURE_EMBEDDING_DEPLOYMENT")
        api_version = os.environ.get("AZURE_API_VERSION")
        
        # 更新Azure提供商配置
        providers = config.get("llm.providers", [])
        for provider in providers:
            if provider.get("type") == "azure":
                provider["api_key"] = azure_api_key
                
                if resource_name and not resource_name.startswith("your-"):
                    provider["resource_name"] = resource_name
                
                if api_base and "{resource_name}" in api_base and resource_name:
                    # 替换API基础URL中的占位符
                    provider["api_base"] = api_base.replace("{resource_name}", resource_name)
                elif api_base:
                    provider["api_base"] = api_base
                
                if deployment_name and not deployment_name.startswith("your-"):
                    provider["deployment_name"] = deployment_name
                
                if embedding_deployment and not embedding_deployment.startswith("your-"):
                    provider["embedding_deployment"] = embedding_deployment
                
                if api_version:
                    provider["api_version"] = api_version
    
    return config

def setup_mock_providers(config: Config):
    """设置模拟提供商，用于测试而无需实际API调用"""
    logger.info("设置模拟提供商，将绕过实际API调用")
    
    # 添加模拟模式标记
    config.set("llm.mock_mode", True)
    
    # 更新模型路由提供商的设置
    providers = config.get("llm.providers", [])
    for i, provider in enumerate(providers):
        if provider.get("type") == "model_router" and provider.get("id") == "openai_models":
            # 启用该提供商
            provider["enabled"] = True
            provider["mock_mode"] = True
            
            # 确保共享配置存在
            if "shared_config" not in provider:
                provider["shared_config"] = {}
            
            # 设置模拟API密钥
            provider["shared_config"]["api_key"] = "mock-api-key"
            
            # 获取并确保模型列表完整
            models = provider.get("models", [])
            provider["default_model_id"] = models[0]["id"] if models else "gpt35"
    
    return config

# 模拟LLM提供商类
class MockLLMProvider:
    """模拟LLM提供商，用于测试模型路由器而无需实际API调用"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.model_id = config.get("id", "unknown")
        self.model_name = config.get("model", "unknown-model")
        logger.info(f"初始化模拟LLM提供商: {self.model_id} ({self.model_name})")
        
    async def initialize(self) -> bool:
        """模拟初始化过程"""
        # 模拟随机成功率
        success = random.random() > 0.1  # 90%成功率
        if success:
            logger.info(f"模拟提供商 {self.model_id} 初始化成功")
        else:
            logger.warning(f"模拟提供商 {self.model_id} 初始化失败")
        return success
    
    async def generate_text(self, prompt: str, **kwargs) -> Tuple[str, Dict[str, Any]]:
        """模拟文本生成"""
        # 根据模型类型生成不同风格的回复
        prefix = f"[{self.model_id}] "
        
        if "gpt4" in self.model_id:
            response = f"{prefix}这是GPT-4风格的回复，比较详细和精确。对于问题'{prompt[:30]}...'，我的回答是..."
        elif "gpt35" in self.model_id:
            response = f"{prefix}这是GPT-3.5风格的回复，简洁明了。回答问题'{prompt[:30]}...'，我认为..."
        else:
            response = f"{prefix}这是标准回复。针对'{prompt[:30]}...'，我的回应是..."
        
        # 根据任务调整回复
        task = kwargs.get("task", "")
        if task == "creative":
            response += "\n创造性的内容需要更强的想象力，这里有更多的创意表达..."
        elif task == "read_air":
            response += "\n读空气需要更敏锐的观察力，我注意到了隐含的情绪和意图..."
        
        # 模拟元数据
        metadata = {
            "model": self.model_name,
            "usage": {
                "prompt_tokens": len(prompt) // 4,
                "completion_tokens": len(response) // 4,
                "total_tokens": (len(prompt) + len(response)) // 4
            },
            "router_info": {
                "model_id": self.model_id,
                "selected_by": "direct" if kwargs.get("model_id") else "router",
                "tried_models": [self.model_id]
            }
        }
        
        return response, metadata
    
    async def generate_embedding(self, text: str) -> Tuple[List[float], Dict[str, Any]]:
        """模拟嵌入向量生成"""
        # 生成随机嵌入向量
        vector_size = 1536 if "text_embedding" in self.model_id else 768
        embedding = [random.random() for _ in range(vector_size)]
        
        # 模拟元数据
        metadata = {
            "model": self.model_name,
            "usage": {
                "prompt_tokens": len(text) // 4,
                "total_tokens": len(text) // 4
            },
            "router_info": {
                "model_id": self.model_id,
                "tried_models": [self.model_id]
            }
        }
        
        return embedding, metadata

# 修补LLM管理器以支持模拟模式
def patch_llm_manager(mock_mode: bool = False):
    """修补LLM管理器以支持模拟模式"""
    if not mock_mode:
        return
    
    logger.info("应用模拟模式补丁到LLM管理器")
    
    # 保存原始方法
    original_register_provider = LLMManager.register_provider
    
    # 创建补丁方法
    def patched_register_provider(self, provider_config: Dict[str, Any]) -> Optional[str]:
        """修补后的注册提供商方法，支持模拟模式"""
        # 检查是否为模型路由提供商
        if provider_config.get("type") == "model_router" and provider_config.get("mock_mode", False):
            provider_id = provider_config.get("id")
            logger.info(f"注册模拟模型路由提供商: {provider_id}")
            
            # 创建模拟提供商并注册
            from linjing.llm.providers.model_router_provider import ModelRouterProvider
            
            # 修改ModelRouterProvider的_init_models方法
            original_init_models = ModelRouterProvider._init_models
            
            def patched_init_models(self, model_configs: List[Dict[str, Any]]) -> None:
                """修补后的初始化模型方法，使用模拟提供商"""
                logger.info(f"初始化模拟模型，数量: {len(model_configs)}")
                
                for model_config in model_configs:
                    try:
                        model_id = model_config.get("id")
                        if not model_id:
                            logger.error("模型配置缺少ID，跳过")
                            continue
                        
                        # 合并共享配置和模型特定配置
                        merged_config = {**self.shared_config, **model_config}
                        
                        # 创建模拟提供商实例
                        provider = MockLLMProvider(merged_config)
                        self.models[model_id] = provider
                        
                        # 如果未设置默认模型ID，使用第一个模型
                        if not self.default_model_id and len(self.models) == 1:
                            self.default_model_id = model_id
                            self._current_model_id = model_id
                        
                        logger.debug(f"添加模拟模型: {model_id}")
                    except Exception as e:
                        logger.error(f"创建模拟模型实例失败: {e}")
            
            # 应用补丁
            ModelRouterProvider._init_models = patched_init_models
            
            # 创建提供商实例并注册
            provider = ModelRouterProvider(provider_config)
            self.providers[provider_id] = provider
            
            # 如果没有默认提供商，设置为当前提供商
            if not self.default_provider_id:
                self.default_provider_id = provider_id
                self.current_provider_id = provider_id
            
            return provider_id
        
        # 否则使用原始方法
        return original_register_provider(self, provider_config)
    
    # 应用补丁
    LLMManager.register_provider = patched_register_provider

async def test_model_router(mock_mode: bool = False):
    """测试ModelRouterProvider的功能"""
    # 应用模拟模式补丁
    if mock_mode:
        patch_llm_manager(mock_mode)
    
    # 加载配置
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.yaml")
    
    print(f"尝试加载配置文件: {config_path}")
    
    config = Config()
    if not config.load_from_file(config_path):
        logger.error("加载配置文件失败")
        return
    
    logger.info("成功加载配置文件")
    
    # 从环境变量覆盖API密钥
    if not mock_mode:
        config = override_config_with_env(config)
    else:
        # 设置模拟提供商
        config = setup_mock_providers(config)
    
    # 确保配置中有ModelRouterProvider
    llm_config = config.get("llm", {})
    if not any(p.get("type") == "model_router" for p in llm_config.get("providers", [])):
        logger.error("配置中没有找到type为model_router的提供商，请先配置")
        return
    
    logger.info("找到ModelRouterProvider配置")
    
    # 初始化LLM管理器
    llm_manager = LLMManager({"llm": llm_config})
    await llm_manager.initialize()
    
    # 显示所有提供商状态
    print("\n=== 初始化的提供商 ===")
    stats = llm_manager.get_providers_stats()
    for provider_id, provider_stats in stats.items():
        print(f"提供商: {provider_id}, 可用: {provider_stats.get('available', False)}")
        if provider_id == "openai_models":
            models = provider_stats.get("models", [])
            print(f"  模型数量: {len(models)}")
            for model in models:
                print(f"  - {model.get('model_id')}")
    
    # 测试不同任务类型的路由
    tasks = ["chat", "read_air", "creative"]
    prompts = {
        "chat": "你好，给我讲个笑话。",
        "read_air": "我今天感觉很累，不想说话。",
        "creative": "写一首关于人工智能的短诗。"
    }
    
    print("\n=== 测试不同任务类型路由 ===")
    for task in tasks:
        print(f"\n--- 任务类型: {task} ---")
        prompt = prompts.get(task, "测试内容。")
        
        try:
            # 1. 使用任务路由
            text, metadata = await llm_manager.generate_text(
                prompt, 
                max_tokens=100,
                task=task
            )
            
            router_info = metadata.get("router_info", {})
            model_id = router_info.get("model_id", "未知")
            
            print(f"路由到模型: {model_id}")
            print(f"生成内容前30字符: {text[:30]}...")
            
        except Exception as e:
            logger.error(f"测试任务 {task} 失败: {e}")
    
    # 测试直接指定模型ID
    print("\n=== 测试直接指定模型ID ===")
    try:
        model_id = "gpt4"  # 使用配置中定义的模型ID
        text, metadata = await llm_manager.generate_text(
            "这个问题很复杂，需要深入思考。", 
            max_tokens=100,
            provider_id="openai_models",  # 指定提供商
            model_id=model_id  # 直接指定模型ID
        )
        
        router_info = metadata.get("router_info", {})
        actual_model = router_info.get("model_id", "未知")
        
        print(f"请求模型: {model_id}, 实际使用: {actual_model}")
        print(f"生成内容前30字符: {text[:30]}...")
    except Exception as e:
        logger.error(f"测试直接指定模型失败: {e}")
    
    # 测试条件路由规则
    print("\n=== 测试条件路由规则 ===")
    try:
        # 测试token数量条件路由
        text, metadata = await llm_manager.generate_text(
            "生成一个长回答需要更强大的模型。", 
            max_tokens=3000,  # 大于规则中的min_tokens阈值
            provider_id="openai_models"
        )
        
        router_info = metadata.get("router_info", {})
        model_id = router_info.get("model_id", "未知")
        
        print(f"大token数量路由到模型: {model_id}")
        print(f"生成内容前30字符: {text[:30]}...")
        
        # 测试优先级条件路由
        text, metadata = await llm_manager.generate_text(
            "这是一个需要高质量回答的问题。", 
            max_tokens=100,
            provider_id="openai_models",
            priority="quality"  # 匹配规则中的优先级条件
        )
        
        router_info = metadata.get("router_info", {})
        model_id = router_info.get("model_id", "未知")
        
        print(f"高质量优先级路由到模型: {model_id}")
        print(f"生成内容前30字符: {text[:30]}...")
        
    except Exception as e:
        logger.error(f"测试条件路由规则失败: {e}")
    
    # 关闭LLM管理器
    await llm_manager.close()

if __name__ == "__main__":
    # 添加命令行参数
    parser = argparse.ArgumentParser(description="测试模型路由器")
    parser.add_argument("--mock", action="store_true", help="使用模拟模式，无需实际API调用")
    parser.add_argument("--real", action="store_true", help="使用真实API调用，需要有效的API密钥")
    args = parser.parse_args()
    
    # 检查OpenAI API密钥是否有效，决定是否默认使用模拟模式
    has_valid_key = os.environ.get("OPENAI_API_KEY") and not os.environ.get("OPENAI_API_KEY").startswith("sk-xxxxx")
    
    # 使用命令行参数决定是否使用模拟模式
    # 如果--real被指定，且有有效密钥，则不使用模拟模式
    # 如果--mock被指定，或没有有效密钥，则使用模拟模式
    mock_mode = True  # 默认使用模拟模式
    if args.real and has_valid_key:
        mock_mode = False
        print("使用真实API模式，将进行实际API调用")
    elif args.mock or not has_valid_key:
        mock_mode = True
        if args.mock:
            print("启用模拟模式，将不进行实际API调用")
        else:
            print("未检测到有效的API密钥，默认启用模拟模式")
    
    asyncio.run(test_model_router(mock_mode=mock_mode)) 