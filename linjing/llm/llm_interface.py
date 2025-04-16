#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
林镜(LingJing) - LLM接口类

提供统一的接口来访问不同的LLM模型，包括OpenAI、Azure OpenAI等
"""

import json
import asyncio
import logging
from typing import Dict, Any, List, Union, Optional, Tuple
import time
import random
import re

from ..utils.logger import get_logger
from ..exceptions import (
    LLMError, LLMRequestError, LLMResponseError, 
    LLMTokenLimitError, LLMAuthenticationError
)
from ..constants import LLMProvider

# 单例实例
_llm_interface_instance = None

class LLMInterface:
    """LLM接口类，提供统一的接口访问各种LLM模型"""
    
    def __init__(self):
        """初始化LLM接口"""
        self.logger = get_logger('linjing.llm.interface')
        self.config = None
        self.client = None
        self.provider = None
        self.embedding_client = None
        self.embedding_model = None
        self.default_model = None
        self.default_temperature = 0.7
        self.default_max_tokens = 1000
        
        # 请求统计
        self.request_count = 0
        self.token_count = 0
        self.last_request_time = 0
        
        # 请求限制
        self.rate_limit = 60  # 每分钟最大请求数
        self.rate_window = 60  # 滑动窗口秒数
        self.request_timestamps = []  # 请求时间戳记录
    
    async def initialize(self) -> None:
        """初始化LLM接口"""
        self.logger.info("初始化LLM接口...")
        
        # 导入配置
        from ..config import async_get_config
        self.config = await async_get_config()
        
        if not self.config:
            raise LLMError("无法获取配置信息")
        
        # 获取LLM提供商
        provider_name = self.config.get('llm', {}).get('provider', LLMProvider.OPENAI)
        self.provider = provider_name
        
        # 根据提供商初始化客户端
        if provider_name == LLMProvider.OPENAI:
            await self._init_openai()
        elif provider_name == LLMProvider.AZURE:
            await self._init_azure()
        elif provider_name == LLMProvider.CUSTOM:
            await self._init_custom()
        else:
            raise LLMError(f"不支持的LLM提供商: {provider_name}")
        
        # 设置默认配置
        llm_config = self.config.get('llm', {})
        self.default_model = llm_config.get('default_model', 'gpt-3.5-turbo')
        self.default_temperature = llm_config.get('default_temperature', 0.7)
        self.default_max_tokens = llm_config.get('default_max_tokens', 1000)
        
        # 设置请求限制
        self.rate_limit = llm_config.get('rate_limit', 60)
        self.rate_window = llm_config.get('rate_window', 60)
        
        self.logger.info(f"LLM接口初始化完成，提供商: {provider_name}，默认模型: {self.default_model}")
    
    async def _init_openai(self) -> None:
        """初始化OpenAI客户端"""
        try:
            import openai
            
            # 获取API密钥
            openai_config = self.config.get('llm', {}).get('openai', {})
            api_key = openai_config.get('api_key')
            
            if not api_key:
                raise LLMAuthenticationError("未提供OpenAI API密钥")
            
            # 设置API密钥
            openai.api_key = api_key
            
            # 设置代理（如果有）
            proxy = openai_config.get('proxy')
            if proxy:
                openai.proxy = proxy
            
            # 设置基础URL（如果有）
            base_url = openai_config.get('base_url')
            if base_url:
                openai.base_url = base_url
            
            # 设置组织ID（如果有）
            org_id = openai_config.get('organization')
            if org_id:
                openai.organization = org_id
            
            self.client = openai.AsyncClient(
                api_key=api_key,
                base_url=base_url,
                organization=org_id
            )
            
            # 设置嵌入模型
            self.embedding_model = openai_config.get('embedding_model', 'text-embedding-ada-002')
            self.embedding_client = self.client
            
            self.logger.info("OpenAI客户端初始化成功")
        
        except ImportError:
            raise LLMError("未安装OpenAI包，请运行 'pip install openai'")
        except Exception as e:
            raise LLMError(f"初始化OpenAI客户端失败: {e}")
    
    async def _init_azure(self) -> None:
        """初始化Azure OpenAI客户端"""
        try:
            import openai
            
            # 获取Azure配置
            azure_config = self.config.get('llm', {}).get('azure', {})
            api_key = azure_config.get('api_key')
            api_version = azure_config.get('api_version', '2023-05-15')
            endpoint = azure_config.get('endpoint')
            
            if not api_key or not endpoint:
                raise LLMAuthenticationError("Azure OpenAI配置不完整，需要提供api_key和endpoint")
            
            # 设置Azure OpenAI客户端
            self.client = openai.AsyncAzureOpenAI(
                api_key=api_key,
                api_version=api_version,
                azure_endpoint=endpoint
            )
            
            # 设置嵌入模型
            self.embedding_model = azure_config.get('embedding_deployment')
            self.embedding_client = self.client
            
            # 模型名称映射
            self._model_name_map = azure_config.get('model_map', {})
            
            self.logger.info("Azure OpenAI客户端初始化成功")
        
        except ImportError:
            raise LLMError("未安装OpenAI包，请运行 'pip install openai'")
        except Exception as e:
            raise LLMError(f"初始化Azure OpenAI客户端失败: {e}")
    
    async def _init_custom(self) -> None:
        """初始化自定义LLM客户端"""
        try:
            # 获取自定义LLM配置
            custom_config = self.config.get('llm', {}).get('custom', {})
            adapter_module = custom_config.get('adapter_module')
            
            if not adapter_module:
                raise LLMError("未提供自定义LLM适配器模块")
            
            # 动态导入自定义适配器
            module_parts = adapter_module.split('.')
            module_name = '.'.join(module_parts[:-1])
            class_name = module_parts[-1]
            
            try:
                module = __import__(module_name, fromlist=[class_name])
                adapter_class = getattr(module, class_name)
            except (ImportError, AttributeError) as e:
                raise LLMError(f"导入自定义适配器失败: {e}")
            
            # 创建适配器实例
            self.client = adapter_class(custom_config)
            
            # 设置嵌入客户端
            if hasattr(self.client, 'get_embedding_client'):
                self.embedding_client = self.client.get_embedding_client()
            else:
                self.embedding_client = self.client
            
            # 设置嵌入模型
            self.embedding_model = custom_config.get('embedding_model', 'default')
            
            self.logger.info("自定义LLM客户端初始化成功")
        
        except Exception as e:
            raise LLMError(f"初始化自定义LLM客户端失败: {e}")
    
    async def chat_completion(self, prompt: Union[str, List[Dict[str, str]]], model: Optional[str] = None, 
                        temperature: Optional[float] = None, max_tokens: Optional[int] = None,
                        response_format: Optional[Dict[str, str]] = None) -> str:
        """
        获取聊天完成响应
        
        Args:
            prompt: 提示文本或消息列表
            model: 模型名称，默认使用配置中的默认模型
            temperature: 温度参数，控制随机性，默认使用配置中的默认温度
            max_tokens: 最大标记数，默认使用配置中的默认值
            response_format: 响应格式，如设置为 {"type": "json_object"} 则强制以JSON响应
            
        Returns:
            LLM响应文本
        """
        await self._check_rate_limit()
        
        try:
            # 默认参数
            model = model or self.default_model
            temperature = temperature if temperature is not None else self.default_temperature
            max_tokens = max_tokens or self.default_max_tokens
            
            # 如果是Azure，可能需要映射模型名
            if self.provider == LLMProvider.AZURE and hasattr(self, '_model_name_map'):
                model = self._model_name_map.get(model, model)
            
            # 准备消息
            messages = self._prepare_messages(prompt)
            
            # 构建请求参数
            params = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens
            }
            
            # 添加响应格式（如果指定）
            if response_format:
                params["response_format"] = response_format
            
            start_time = time.time()
            
            # 调用API
            if self.provider == LLMProvider.OPENAI or self.provider == LLMProvider.AZURE:
                response = await self.client.chat.completions.create(**params)
                result = response.choices[0].message.content or ""
            else:
                # 自定义提供商
                response = await self.client.chat_completion(**params)
                result = response.get('content', '')
            
            # 记录请求
            duration = time.time() - start_time
            self._record_request(duration)
            
            return result
        
        except Exception as e:
            error_msg = str(e)
            if "rate limit" in error_msg.lower():
                raise LLMRequestError(f"LLM请求超过速率限制: {e}")
            elif "token" in error_msg.lower() and ("exceed" in error_msg.lower() or "limit" in error_msg.lower()):
                raise LLMTokenLimitError(f"LLM令牌超出限制: {e}")
            elif "authenticate" in error_msg.lower() or "api key" in error_msg.lower():
                raise LLMAuthenticationError(f"LLM认证错误: {e}")
            else:
                raise LLMRequestError(f"LLM请求失败: {e}")
    
    async def create_embedding(self, text: Union[str, List[str]]) -> Union[List[float], List[List[float]]]:
        """
        创建文本嵌入
        
        Args:
            text: 输入文本或文本列表
            
        Returns:
            嵌入向量或嵌入向量列表
        """
        try:
            if self.provider == LLMProvider.OPENAI or self.provider == LLMProvider.AZURE:
                response = await self.embedding_client.embeddings.create(
                    model=self.embedding_model,
                    input=text
                )
                
                if isinstance(text, list):
                    return [item.embedding for item in response.data]
                else:
                    return response.data[0].embedding
            else:
                # 自定义提供商
                response = await self.client.create_embedding(
                    model=self.embedding_model,
                    input=text
                )
                
                if isinstance(text, list):
                    return response.get('embeddings', [])
                else:
                    return response.get('embedding', [])
        
        except Exception as e:
            raise LLMRequestError(f"获取嵌入向量失败: {e}")
    
    def _prepare_messages(self, prompt: Union[str, List[Dict[str, str]]]) -> List[Dict[str, str]]:
        """
        准备消息
        
        Args:
            prompt: 提示文本或消息列表
            
        Returns:
            格式化的消息列表
        """
        if isinstance(prompt, str):
            return [{"role": "user", "content": prompt}]
        
        # 验证消息格式
        for msg in prompt:
            if not isinstance(msg, dict) or "role" not in msg or "content" not in msg:
                raise ValueError("消息格式错误，每个消息必须包含 'role' 和 'content' 字段")
        
        return prompt
    
    def parse_json_response(self, response: str) -> Dict[str, Any]:
        """
        解析JSON响应
        
        Args:
            response: 响应文本
            
        Returns:
            解析后的JSON对象
        """
        # 尝试直接解析
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass
        
        # 尝试提取JSON部分
        try:
            # 使用正则表达式查找JSON对象
            json_match = re.search(r'({.*})', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
                return json.loads(json_str)
            
            # 尝试查找JSON数组
            json_array_match = re.search(r'(\[.*\])', response, re.DOTALL)
            if json_array_match:
                json_str = json_array_match.group(1)
                return json.loads(json_str)
        except json.JSONDecodeError:
            pass
        
        raise LLMResponseError(f"无法解析JSON响应: {response}")
    
    async def _check_rate_limit(self) -> None:
        """检查请求速率限制"""
        now = time.time()
        
        # 清理过期的时间戳
        self.request_timestamps = [ts for ts in self.request_timestamps if now - ts <= self.rate_window]
        
        # 检查是否超过限制
        if len(self.request_timestamps) >= self.rate_limit:
            oldest = self.request_timestamps[0]
            wait_time = self.rate_window - (now - oldest)
            
            if wait_time > 0:
                self.logger.warning(f"达到速率限制，等待 {wait_time:.2f} 秒")
                await asyncio.sleep(wait_time)
        
        # 记录当前请求时间戳
        self.request_timestamps.append(time.time())
    
    def _record_request(self, duration: float) -> None:
        """
        记录请求统计
        
        Args:
            duration: 请求持续时间
        """
        self.request_count += 1
        self.last_request_time = time.time()
        
        if self.request_count % 50 == 0:
            self.logger.info(f"LLM请求统计: 总请求数 {self.request_count}，上次请求耗时 {duration:.2f} 秒")
    
    async def health_check(self) -> Tuple[bool, str]:
        """
        健康检查
        
        Returns:
            (是否健康, 状态信息)
        """
        try:
            # 简单的测试请求
            response = await self.chat_completion(
                "Hello, are you working?",
                max_tokens=20
            )
            
            return True, "LLM接口正常工作"
        except Exception as e:
            return False, f"LLM接口异常: {e}"


async def get_llm_interface() -> LLMInterface:
    """
    获取LLM接口实例（单例模式）
    
    Returns:
        LLMInterface: LLM接口实例
    """
    global _llm_interface_instance
    
    if _llm_interface_instance is None:
        _llm_interface_instance = LLMInterface()
        await _llm_interface_instance.initialize()
    
    return _llm_interface_instance 