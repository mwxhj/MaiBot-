#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Azure OpenAI提供商实现。

提供对Azure OpenAI服务的访问，支持文本生成和嵌入向量生成。
"""

import time
import json
import logging
import aiohttp
from typing import Dict, List, Any, Optional, Union, Tuple

from .base_provider import BaseProvider
from ...utils.logger import get_logger

logger = get_logger(__name__)


class AzureProvider(BaseProvider):
    """
    Azure OpenAI API提供商。
    
    支持Azure OpenAI服务的文本生成、嵌入生成等功能。
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化Azure OpenAI提供商
        
        Args:
            config: 配置字典，包含API密钥等配置信息
        """
        super().__init__(config)
        
        # Azure特定配置
        self.resource_name = config.get("resource_name", "")
        self.deployment_name = config.get("deployment_name", "")
        self.api_version = config.get("api_version", "2023-05-15")
        
        # 嵌入模型部署名称
        self.embedding_deployment = config.get("embedding_deployment", "")
        
        # 构建API基础URL
        if self.resource_name:
            self.api_base = f"https://{self.resource_name}.openai.azure.com/openai/deployments"
        else:
            self.api_base = config.get("api_base", "")
        
        # 会话
        self._session = None
        self._initialized = False
    
    async def initialize(self) -> bool:
        """
        初始化提供商，验证API密钥等
        
        Returns:
            初始化是否成功
        """
        if self._initialized:
            return True
        
        try:
            if not self.api_key:
                logger.error("Azure OpenAI API密钥未提供")
                return False
            
            if not self.api_base:
                logger.error("Azure OpenAI资源名称或API基础URL未提供")
                return False
                
            if not self.deployment_name:
                logger.error("Azure OpenAI部署名称未提供")
                return False
            
            # 创建HTTP会话
            self._session = aiohttp.ClientSession()
            
            # 验证API密钥
            url = f"{self.api_base}/{self.deployment_name}/chat/completions?api-version={self.api_version}"
            headers = self._get_headers()
            data = {
                "messages": [
                    {"role": "user", "content": "Hello"}
                ],
                "max_tokens": 1
            }
            
            try:
                async with self._session.post(url, headers=headers, json=data, timeout=10) as response:
                    if response.status == 200:
                        self._initialized = True
                        logger.info(f"Azure OpenAI提供商初始化成功，API基础URL: {self.api_base}")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(f"Azure OpenAI API密钥验证失败: {error_text}")
                        return False
            except Exception as e:
                logger.error(f"Azure OpenAI API连接失败: {e}")
                return False
                
        except Exception as e:
            logger.error(f"Azure OpenAI提供商初始化失败: {e}")
            return False
    
    async def generate_text(
        self, 
        prompt: str, 
        max_tokens: int = 1000, 
        temperature: float = 0.7,
        stop: Optional[List[str]] = None,
        **kwargs
    ) -> Tuple[str, Dict[str, Any]]:
        """
        生成文本
        
        Args:
            prompt: 输入提示词
            max_tokens: 最大生成的token数
            temperature: 温度，控制输出的随机性
            stop: 停止生成的标志字符串列表
            **kwargs: 额外的模型特定参数
            
        Returns:
            (生成的文本, 元数据字典)
        """
        if not self._initialized:
            await self.initialize()
        
        # 构建请求
        url = f"{self.api_base}/{self.deployment_name}/chat/completions?api-version={self.api_version}"
        headers = self._get_headers()
        
        # 准备消息
        messages = kwargs.get("messages", None)
        if messages is None:
            messages = [{"role": "user", "content": prompt}]
        
        # 准备请求体
        data = {
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        
        if stop:
            data["stop"] = stop
        
        # 附加其他参数
        for key, value in kwargs.items():
            if key not in ["messages"]:  # 排除已处理的参数
                data[key] = value
        
        # 执行请求
        async def _make_request():
            async with self._session.post(url, headers=headers, json=data) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Azure OpenAI API请求失败 ({response.status}): {error_text}")
                    raise Exception(f"Azure OpenAI API请求失败: {error_text}")
                
                result = await response.json()
                return result
        
        try:
            result = await self._retry_with_exponential_backoff(_make_request)
            
            # 提取生成的文本
            text = result["choices"][0]["message"]["content"]
            
            # 统计token使用
            if "usage" in result:
                self.update_token_usage(
                    result["usage"]["prompt_tokens"],
                    result["usage"]["completion_tokens"]
                )
            
            # 准备元数据
            metadata = {
                "model": self.deployment_name,
                "usage": result.get("usage", {}),
                "id": result.get("id", ""),
                "finish_reason": result["choices"][0].get("finish_reason", "")
            }
            
            return text, metadata
            
        except Exception as e:
            logger.error(f"文本生成失败: {e}")
            raise
    
    async def generate_embedding(self, text: str) -> Tuple[List[float], Dict[str, Any]]:
        """
        生成文本嵌入向量
        
        Args:
            text: 输入文本
            
        Returns:
            (嵌入向量, 元数据字典)
        """
        if not self._initialized:
            await self.initialize()
        
        # 获取嵌入部署名称
        deployment = self.embedding_deployment or self.deployment_name
        
        # 构建请求
        url = f"{self.api_base}/{deployment}/embeddings?api-version={self.api_version}"
        headers = self._get_headers()
        
        # 准备请求体
        data = {
            "input": text
        }
        
        # 执行请求
        async def _make_request():
            async with self._session.post(url, headers=headers, json=data) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Azure OpenAI嵌入API请求失败 ({response.status}): {error_text}")
                    raise Exception(f"Azure OpenAI嵌入API请求失败: {error_text}")
                
                result = await response.json()
                return result
        
        try:
            result = await self._retry_with_exponential_backoff(_make_request)
            
            # 提取嵌入向量
            embedding = result["data"][0]["embedding"]
            
            # 统计token使用
            if "usage" in result:
                self.update_token_usage(
                    result["usage"]["prompt_tokens"],
                    0  # 嵌入生成没有输出tokens
                )
            
            # 准备元数据
            metadata = {
                "model": deployment,
                "usage": result.get("usage", {}),
                "dimensions": len(embedding)
            }
            
            return embedding, metadata
            
        except Exception as e:
            logger.error(f"嵌入生成失败: {e}")
            raise
    
    def _get_headers(self) -> Dict[str, str]:
        """
        获取API请求头
        
        Returns:
            请求头字典
        """
        return {
            "Content-Type": "application/json",
            "api-key": self.api_key
        }
    
    async def close(self) -> None:
        """
        关闭会话
        """
        if self._session:
            await self._session.close()
            self._session = None
            self._initialized = False 