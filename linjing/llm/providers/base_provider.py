#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
LLM提供商基类。

定义了LLM提供商的通用接口，所有提供商实现必须继承此基类。
"""

import time
import logging
import asyncio
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union, Tuple

from ...utils.logger import get_logger

logger = get_logger(__name__)


class BaseProvider(ABC):
    """
    LLM提供商基类。
    
    提供大型语言模型的统一访问接口，定义了所有提供商必须实现的方法。
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化LLM提供商
        
        Args:
            config: 配置字典，包含API密钥等配置信息
        """
        self.config = config
        self.name = config.get("name", self.__class__.__name__)
        self.model = config.get("model", "")
        self.api_key = config.get("api_key", "")
        self.timeout = config.get("timeout", 30)
        self.max_retries = config.get("max_retries", 3)
        self.retry_delay = config.get("retry_delay", 1)
        
        # 性能统计
        self.total_tokens_used = 0
        self.total_requests = 0
        self.failed_requests = 0
        self.last_request_time = 0
        self.last_response_time = 0
        
        logger.info(f"初始化LLM提供商 {self.name}, 模型: {self.model}")
    
    @abstractmethod
    async def initialize(self) -> bool:
        """
        初始化提供商，验证API密钥等
        
        Returns:
            初始化是否成功
        """
        pass
    
    @abstractmethod
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
        pass
    
    @abstractmethod
    async def generate_embedding(self, text: str) -> Tuple[List[float], Dict[str, Any]]:
        """
        生成文本嵌入向量
        
        Args:
            text: 输入文本
            
        Returns:
            (嵌入向量, 元数据字典)
        """
        pass
    
    async def _retry_with_exponential_backoff(self, func, *args, **kwargs):
        """
        使用指数退避的重试机制
        
        Args:
            func: 要重试的异步函数
            *args: 函数参数
            **kwargs: 函数关键字参数
            
        Returns:
            函数返回值
            
        Raises:
            Exception: 重试次数用尽后仍然失败
        """
        retries = 0
        last_exception = None
        
        while retries <= self.max_retries:
            try:
                if retries > 0:
                    delay = self.retry_delay * (2 ** (retries - 1))
                    logger.warning(f"重试请求 ({retries}/{self.max_retries})，延迟 {delay} 秒")
                    await asyncio.sleep(delay)
                
                self.last_request_time = time.time()
                result = await func(*args, **kwargs)
                self.last_response_time = time.time()
                
                self.total_requests += 1
                return result
                
            except Exception as e:
                retries += 1
                last_exception = e
                self.failed_requests += 1
                
                if retries <= self.max_retries:
                    logger.warning(f"请求失败: {e}，准备重试")
                else:
                    logger.error(f"达到最大重试次数 ({self.max_retries})，放弃请求: {e}")
                    raise last_exception
    
    def update_token_usage(self, input_tokens: int, output_tokens: int) -> None:
        """
        更新token使用统计
        
        Args:
            input_tokens: 输入token数
            output_tokens: 输出token数
        """
        total = input_tokens + output_tokens
        self.total_tokens_used += total
        logger.debug(f"Token使用: 输入={input_tokens}, 输出={output_tokens}, 总计={total}")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取性能统计信息
        
        Returns:
            性能统计字典
        """
        return {
            "name": self.name,
            "model": self.model,
            "total_tokens_used": self.total_tokens_used,
            "total_requests": self.total_requests,
            "failed_requests": self.failed_requests,
            "success_rate": 1.0 - (self.failed_requests / max(1, self.total_requests)),
            "last_response_time": self.last_response_time,
            "last_request_latency": (self.last_response_time - self.last_request_time) if self.last_request_time > 0 else 0
        } 