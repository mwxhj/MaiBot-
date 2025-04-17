#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
LLM管理器模块。

提供了对多个LLM提供商的统一管理。
"""

import time
import asyncio
from typing import Dict, List, Any, Optional, Union, Tuple, Type

from .token_counter import TokenCounter
from .providers import BaseProvider, OpenAIProvider, AzureProvider, ClusterProvider
from .providers.model_router_provider import ModelRouterProvider
from ..utils.logger import get_logger

logger = get_logger(__name__)


class LLMManager:
    """
    LLM管理器类，管理多个大型语言模型提供商。
    
    提供统一接口访问不同的LLM提供商，支持自动切换、负载均衡和任务路由。
    """
    
    # 提供商类型映射
    PROVIDER_TYPES = {
        "openai": OpenAIProvider,
        "azure": AzureProvider,
        "cluster": ClusterProvider,
        "model_router": ModelRouterProvider
    }
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化LLM管理器
        
        Args:
            config: 配置字典，包含LLM提供商配置
        """
        self.config = config
        self.llm_config = config.get("llm", {})
        
        # 创建令牌计数器
        token_counter_config = self.llm_config.get("token_counter", {})
        default_model = token_counter_config.get("default_model", "gpt-3.5-turbo")
        self.token_counter = TokenCounter(default_model)
        
        # 加载提供商
        self.providers: Dict[str, BaseProvider] = {}
        self.default_provider_id = self.llm_config.get("default_provider", "")
        self._current_provider_id = self.default_provider_id
        
        # 提供商状态追踪
        self.provider_status: Dict[str, Dict[str, Any]] = {}
        
        # 任务路由配置
        self.usage_strategy = self.llm_config.get("usage_strategy", {})
        self.auto_fallback = self.usage_strategy.get("auto_fallback", True)
        self.task_routing = self.usage_strategy.get("task_routing", {})
        
        logger.info(f"LLM管理器初始化，默认提供商: {self.default_provider_id}")
    
    async def initialize(self) -> bool:
        """
        初始化所有启用的LLM提供商
        
        Returns:
            是否成功初始化至少一个提供商
        """
        providers_config = self.llm_config.get("providers", [])
        
        for provider_config in providers_config:
            provider_id = provider_config.get("id")
            provider_type = provider_config.get("type")
            enabled = provider_config.get("enabled", True)
            
            if not enabled:
                logger.info(f"提供商 {provider_id} 已禁用，跳过初始化")
                continue
                
            if not provider_id or not provider_type:
                logger.warning(f"无效的提供商配置: 缺少ID或类型")
                continue
            
            provider_class = self.PROVIDER_TYPES.get(provider_type)
            if not provider_class:
                logger.warning(f"未知的提供商类型: {provider_type}")
                continue
            
            try:
                # 创建提供商实例
                provider = provider_class(provider_config)
                
                # 初始化提供商
                success = await provider.initialize()
                if success:
                    self.providers[provider_id] = provider
                    self.provider_status[provider_id] = {
                        "available": True,
                        "error_count": 0,
                        "last_error": None,
                        "last_used": 0,
                    }
                    logger.info(f"已成功初始化提供商: {provider_id}")
                else:
                    logger.error(f"提供商初始化失败: {provider_id}")
            except Exception as e:
                logger.error(f"提供商 {provider_id} 初始化出错: {e}")
        
        # 如果没有成功初始化默认提供商，尝试使用第一个可用的提供商
        if self.default_provider_id not in self.providers and self.providers:
            self.default_provider_id = next(iter(self.providers.keys()))
            self._current_provider_id = self.default_provider_id
            logger.warning(f"默认提供商不可用，切换到: {self.default_provider_id}")
        
        # 至少有一个可用的提供商
        return len(self.providers) > 0
    
    def get_provider(self, provider_id: Optional[str] = None) -> Optional[BaseProvider]:
        """
        获取指定ID的提供商实例
        
        Args:
            provider_id: 提供商ID，如未指定则使用当前提供商
            
        Returns:
            提供商实例，如不存在则返回None
        """
        provider_id = provider_id or self._current_provider_id
        return self.providers.get(provider_id)
    
    def set_current_provider(self, provider_id: str) -> bool:
        """
        设置当前使用的提供商
        
        Args:
            provider_id: 提供商ID
            
        Returns:
            是否成功设置
        """
        if provider_id in self.providers:
            self._current_provider_id = provider_id
            logger.info(f"已切换当前提供商为: {provider_id}")
            return True
        return False
    
    def get_provider_for_task(self, task: str) -> Optional[BaseProvider]:
        """
        根据任务类型获取推荐的提供商
        
        Args:
            task: 任务类型
            
        Returns:
            推荐的提供商实例
        """
        provider_id = self.task_routing.get(task, self._current_provider_id)
        provider = self.providers.get(provider_id)
        
        # 如果推荐的提供商不可用，使用当前提供商
        if not provider:
            provider = self.get_provider()
            
        return provider
    
    async def _handle_provider_error(self, provider_id: str, error: Exception) -> Optional[str]:
        """
        处理提供商错误，更新状态并在需要时切换提供商
        
        Args:
            provider_id: 出错的提供商ID
            error: 错误异常
            
        Returns:
            新的提供商ID，如无可用替代则返回None
        """
        # 更新提供商状态
        if provider_id in self.provider_status:
            status = self.provider_status[provider_id]
            status["error_count"] += 1
            status["last_error"] = str(error)
            
            # 从配置中获取错误阈值
            error_threshold = self.usage_strategy.get("error_threshold", 5)
            
            # 错误太多，标记为不可用
            if status["error_count"] >= error_threshold:
                status["available"] = False
                logger.warning(f"提供商 {provider_id} 错误次数过多，标记为不可用")
        
        # 如果开启自动切换且当前提供商是出错的提供商
        if self.auto_fallback and self._current_provider_id == provider_id:
            # 查找可用的替代提供商
            for pid, provider in self.providers.items():
                if pid != provider_id and self.provider_status.get(pid, {}).get("available", False):
                    self._current_provider_id = pid
                    logger.info(f"因错误自动切换提供商: {provider_id} -> {pid}")
                    return pid
            
            logger.error("所有提供商均不可用")
            return None
        
        return self._current_provider_id
    
    async def generate_text(
        self, 
        prompt: str, 
        provider_id: Optional[str] = None,
        max_tokens: int = 1000, 
        temperature: float = 0.7,
        stop: Optional[List[str]] = None,
        **kwargs
    ) -> Tuple[str, Dict[str, Any]]:
        """
        生成文本
        
        Args:
            prompt: 输入提示词
            provider_id: 提供商ID，如未指定则使用当前提供商
            max_tokens: 最大生成的token数
            temperature: 温度，控制输出的随机性
            stop: 停止生成的标志字符串列表
            **kwargs: 额外的模型特定参数
            
        Returns:
            (生成的文本, 元数据字典)
            
        Raises:
            ValueError: 如果没有可用的提供商
        """
        # 获取提供商
        provider_id = provider_id or self._current_provider_id
        provider = self.get_provider(provider_id)
        
        if not provider:
            raise ValueError(f"找不到提供商: {provider_id}")
        
        # 更新提供商使用状态
        if provider_id in self.provider_status:
            self.provider_status[provider_id]["last_used"] = time.time()
        
        try:
            # 调用提供商生成文本
            text, metadata = await provider.generate_text(
                prompt=prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                stop=stop,
                **kwargs
            )
            
            # 添加提供商信息到元数据
            metadata["provider_id"] = provider_id
            metadata["provider_name"] = provider.name
            
            return text, metadata
            
        except Exception as e:
            # 处理错误并尝试切换提供商
            new_provider_id = await self._handle_provider_error(provider_id, e)
            
            # 如果有新的提供商可用且不是之前的提供商，重试请求
            if new_provider_id and new_provider_id != provider_id:
                logger.info(f"使用替代提供商 {new_provider_id} 重试请求")
                return await self.generate_text(
                    prompt=prompt,
                    provider_id=new_provider_id,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    stop=stop,
                    **kwargs
                )
            else:
                # 没有可用的替代提供商，抛出异常
                raise ValueError(f"生成文本失败: {e}") from e
    
    async def generate_embedding(
        self, 
        text: str,
        provider_id: Optional[str] = None
    ) -> Tuple[List[float], Dict[str, Any]]:
        """
        生成文本嵌入向量
        
        Args:
            text: 输入文本
            provider_id: 提供商ID，如未指定则使用当前提供商
            
        Returns:
            (嵌入向量, 元数据字典)
            
        Raises:
            ValueError: 如果没有可用的提供商
        """
        # 优先使用embeddings任务指定的提供商
        if not provider_id:
            embeddings_provider_id = self.task_routing.get("embeddings")
            provider_id = embeddings_provider_id or self._current_provider_id
        
        # 获取提供商
        provider = self.get_provider(provider_id)
        
        if not provider:
            raise ValueError(f"找不到提供商: {provider_id}")
        
        # 更新提供商使用状态
        if provider_id in self.provider_status:
            self.provider_status[provider_id]["last_used"] = time.time()
        
        try:
            # 调用提供商生成嵌入
            embedding, metadata = await provider.generate_embedding(text)
            
            # 添加提供商信息到元数据
            metadata["provider_id"] = provider_id
            metadata["provider_name"] = provider.name
            
            return embedding, metadata
            
        except Exception as e:
            # 处理错误并尝试切换提供商
            new_provider_id = await self._handle_provider_error(provider_id, e)
            
            # 如果有新的提供商可用且不是之前的提供商，重试请求
            if new_provider_id and new_provider_id != provider_id:
                logger.info(f"使用替代提供商 {new_provider_id} 重试请求")
                return await self.generate_embedding(
                    text=text,
                    provider_id=new_provider_id
                )
            else:
                # 没有可用的替代提供商，抛出异常
                raise ValueError(f"生成嵌入向量失败: {e}") from e
    
    def get_token_counter(self) -> TokenCounter:
        """
        获取令牌计数器实例
        
        Returns:
            令牌计数器实例
        """
        return self.token_counter
    
    def get_providers_stats(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有提供商的状态和统计信息
        
        Returns:
            提供商统计信息字典
        """
        stats = {}
        for pid, provider in self.providers.items():
            # 获取提供商基本统计信息
            provider_stats = provider.get_stats()
            # 添加可用性状态
            provider_stats.update(self.provider_status.get(pid, {}))
            stats[pid] = provider_stats
        
        return stats
    
    def register_provider(self, provider_config: Dict[str, Any]) -> Optional[str]:
        """
        动态注册新的提供商
        
        Args:
            provider_config: 提供商配置字典
            
        Returns:
            注册的提供商ID，如注册失败则返回None
        """
        provider_id = provider_config.get("id")
        provider_type = provider_config.get("type")
        
        if not provider_id or not provider_type:
            logger.error("无效的提供商配置: 缺少ID或类型")
            return None
        
        if provider_id in self.providers:
            logger.warning(f"提供商 {provider_id} 已存在，将被覆盖")
        
        provider_class = self.PROVIDER_TYPES.get(provider_type)
        if not provider_class:
            logger.error(f"未知的提供商类型: {provider_type}")
            return None
        
        try:
            # 创建提供商实例
            provider = provider_class(provider_config)
            
            # 异步初始化提供商
            async def _init_provider():
                success = await provider.initialize()
                if success:
                    self.providers[provider_id] = provider
                    self.provider_status[provider_id] = {
                        "available": True,
                        "error_count": 0,
                        "last_error": None,
                        "last_used": 0,
                    }
                    logger.info(f"已成功注册并初始化提供商: {provider_id}")
                    return True
                else:
                    logger.error(f"提供商初始化失败: {provider_id}")
                    return False
            
            # 在事件循环中运行初始化
            loop = asyncio.get_event_loop()
            success = loop.run_until_complete(_init_provider())
            
            return provider_id if success else None
            
        except Exception as e:
            logger.error(f"注册提供商 {provider_id} 失败: {e}")
            return None
    
    async def close(self) -> None:
        """
        关闭所有提供商连接
        """
        for provider_id, provider in self.providers.items():
            try:
                if hasattr(provider, 'close') and callable(provider.close):
                    await provider.close()
                    logger.debug(f"已关闭提供商连接: {provider_id}")
            except Exception as e:
                logger.error(f"关闭提供商 {provider_id} 连接失败: {e}")
        
        self.providers = {} 