#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
OpenAI提供商实现。

提供对OpenAI API的访问，支持文本生成和嵌入向量生成。
"""

import time
import json
import logging
import aiohttp
from typing import Dict, List, Any, Optional, Union, Tuple

from .base_provider import BaseProvider
from ...utils.logger import get_logger

logger = get_logger(__name__)


class OpenAIProvider(BaseProvider):
    """
    OpenAI API提供商。
    
    支持OpenAI的文本生成、嵌入生成等功能。
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化OpenAI提供商
        
        Args:
            config: 配置字典，包含API密钥等配置信息
        """
        super().__init__(config)
        
        # OpenAI特定配置
        self.api_base = config.get("api_base", "https://api.openai.com/v1")
        self.organization = config.get("organization", "")
        
        # 嵌入模型
        self.embedding_model = config.get("embedding_model", "text-embedding-3-small")
        
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
                logger.error("OpenAI API密钥未提供")
                return False
            
            # 创建HTTP会话
            self._session = aiohttp.ClientSession()
            
            # 验证API密钥
            headers = self._get_headers()
            async with self._session.get(
                f"{self.api_base}/models", 
                headers=headers
            ) as response:
                if response.status == 200:
                    self._initialized = True
                    logger.info(f"OpenAI提供商初始化成功，API基础URL: {self.api_base}")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"OpenAI API密钥验证失败: {error_text}")
                    return False
                
        except Exception as e:
            logger.error(f"OpenAI提供商初始化失败: {e}")
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
        url = f"{self.api_base}/chat/completions"
        headers = self._get_headers()
        
        # 准备消息
        messages = kwargs.get("messages", None)
        if messages is None:
            messages = [{"role": "user", "content": prompt}]
        
        # 准备请求体
        data = {
            "model": self.model,
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
                    logger.error(f"OpenAI API请求失败 ({response.status}): {error_text}")
                    raise Exception(f"OpenAI API请求失败: {error_text}")
                
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
                "model": result.get("model", self.model),
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
        
        # 构建请求
        url = f"{self.api_base}/embeddings"
        headers = self._get_headers()
        
        # 准备请求体
        data = {
            "model": self.embedding_model,
            "input": text
        }
        
        # 执行请求
        async def _make_request():
            async with self._session.post(url, headers=headers, json=data) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"OpenAI嵌入API请求失败 ({response.status}): {error_text}")
                    raise Exception(f"OpenAI嵌入API请求失败: {error_text}")
                
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
                "model": result.get("model", self.embedding_model),
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
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        if self.organization:
            headers["OpenAI-Organization"] = self.organization
            
        return headers
    
    async def close(self) -> None:
        """
        关闭会话
        """
        if self._session:
            await self._session.close()
            self._session = None
            self._initialized = False 