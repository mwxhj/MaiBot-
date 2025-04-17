#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
集群提供商模块，用于管理多个同类型的LLM提供商实例。

该模块提供了负载均衡和故障转移功能，允许使用多个相同类型的LLM服务。
"""

import random
import time
from typing import Dict, List, Any, Optional, Tuple, Type, Union

from .base_provider import BaseProvider
from .openai_provider import OpenAIProvider
from .azure_provider import AzureProvider
from ...utils.logger import get_logger

logger = get_logger(__name__)

class ClusterProvider(BaseProvider):
    """
    集群提供商，管理多个同类型的LLM提供商实例。
    
    支持负载均衡和故障自动转移功能，可以统一管理多个API密钥或区域端点。
    """
    
    # 支持的提供商类型映射
    PROVIDER_TYPES = {
        "openai": OpenAIProvider,
        "azure": AzureProvider,
    }
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化集群提供商
        
        Args:
            config: 配置字典，包含集群配置信息
        """
        super().__init__(config)
        
        self.name = config.get("name", "ClusterProvider")
        self.member_type = config.get("member_type", "")  # 成员提供商类型
        self.strategy = config.get("strategy", "round_robin")  # 负载均衡策略
        self.failover = config.get("failover", True)  # 是否启用故障转移
        self.members: List[BaseProvider] = []  # 成员提供商列表
        self.retry_interval = config.get("retry_interval", 300)  # 失败提供商重试间隔（秒）
        
        # 负载均衡状态
        self._current_index = 0
        self._last_used_time = {}  # provider_id -> 上次使用时间
        self._failed_providers = {}  # provider_id -> 失败时间
        
        # 初始化成员提供商列表
        self._init_members(config.get("members", []))
        
        logger.info(f"集群提供商 {self.name} 初始化，成员类型: {self.member_type}，成员数量: {len(self.members)}")
    
    def _init_members(self, member_configs: List[Dict[str, Any]]) -> None:
        """
        初始化成员提供商列表
        
        Args:
            member_configs: 成员提供商配置列表
        """
        if not self.member_type or self.member_type not in self.PROVIDER_TYPES:
            logger.error(f"无效的成员提供商类型: {self.member_type}")
            return
        
        provider_class = self.PROVIDER_TYPES[self.member_type]
        
        for i, member_config in enumerate(member_configs):
            try:
                # 确保每个成员有唯一ID
                if "id" not in member_config:
                    member_config["id"] = f"{self.member_type}_{i+1}"
                
                # 创建提供商实例
                provider = provider_class(member_config)
                self.members.append(provider)
                
                logger.debug(f"添加集群成员: {member_config.get('id')}")
            except Exception as e:
                logger.error(f"创建成员提供商失败: {e}")
    
    async def initialize(self) -> bool:
        """
        初始化所有成员提供商
        
        Returns:
            是否成功初始化至少一个成员提供商
        """
        if not self.members:
            logger.error("没有可用的成员提供商")
            return False
        
        success_count = 0
        
        for provider in self.members:
            try:
                if await provider.initialize():
                    success_count += 1
            except Exception as e:
                logger.error(f"初始化成员提供商 {provider.name} 失败: {e}")
        
        if success_count == 0:
            logger.error("所有成员提供商初始化失败")
            return False
        
        logger.info(f"成功初始化 {success_count}/{len(self.members)} 个成员提供商")
        return True
    
    def _select_provider(self) -> Optional[BaseProvider]:
        """
        根据负载均衡策略选择一个提供商
        
        Returns:
            选中的提供商实例
        """
        # 过滤掉失败的提供商
        available_providers = []
        for provider in self.members:
            provider_id = getattr(provider, "id", str(id(provider)))
            # 如果在失败列表中且未达到重试时间，则跳过
            if provider_id in self._failed_providers:
                failed_time = self._failed_providers[provider_id]
                if time.time() - failed_time < self.retry_interval:
                    continue
                # 已达到重试时间，从失败列表移除
                del self._failed_providers[provider_id]
            available_providers.append(provider)
        
        if not available_providers:
            if self.failover and self._failed_providers:
                # 如果启用了故障转移，则从失败列表中选择最早失败的
                oldest_failed = min(self._failed_providers.items(), key=lambda x: x[1])
                for provider in self.members:
                    if getattr(provider, "id", str(id(provider))) == oldest_failed[0]:
                        return provider
            logger.error("没有可用的提供商")
            return None
        
        # 根据策略选择提供商
        if self.strategy == "random":
            provider = random.choice(available_providers)
        elif self.strategy == "least_used":
            # 选择使用次数最少的
            provider = min(
                available_providers,
                key=lambda p: getattr(p, "total_requests", 0)
            )
        else:  # round_robin或未知策略
            provider = available_providers[self._current_index % len(available_providers)]
            self._current_index += 1
        
        # 记录使用时间
        provider_id = getattr(provider, "id", str(id(provider)))
        self._last_used_time[provider_id] = time.time()
        
        return provider
    
    def _mark_provider_failed(self, provider: BaseProvider) -> None:
        """
        标记提供商为失败状态
        
        Args:
            provider: 失败的提供商实例
        """
        provider_id = getattr(provider, "id", str(id(provider)))
        self._failed_providers[provider_id] = time.time()
        logger.warning(f"提供商 {provider.name} 标记为失败状态")
    
    async def generate_text(
        self, 
        prompt: str, 
        max_tokens: int = 1000, 
        temperature: float = 0.7,
        stop: Optional[List[str]] = None,
        **kwargs
    ) -> Tuple[str, Dict[str, Any]]:
        """
        生成文本，自动选择一个成员提供商
        
        Args:
            prompt: 输入提示词
            max_tokens: 最大生成的token数
            temperature: 温度，控制输出的随机性
            stop: 停止生成的标志字符串列表
            **kwargs: 额外的模型特定参数
            
        Returns:
            (生成的文本, 元数据字典)
            
        Raises:
            Exception: 所有提供商都失败时抛出
        """
        # 遍历所有提供商尝试生成文本
        errors = []
        tried_providers = set()
        
        for _ in range(min(len(self.members), 3)):  # 最多尝试3次或所有提供商
            provider = self._select_provider()
            if not provider:
                break
                
            provider_id = getattr(provider, "id", str(id(provider)))
            if provider_id in tried_providers:
                continue
            tried_providers.add(provider_id)
            
            try:
                result = await provider.generate_text(
                    prompt=prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    stop=stop,
                    **kwargs
                )
                # 更新统计数据
                self.total_requests += 1
                if hasattr(provider, "total_tokens_used"):
                    self.total_tokens_used += getattr(provider, "total_tokens_used", 0)
                return result
            except Exception as e:
                errors.append(f"{provider.name}: {str(e)}")
                self._mark_provider_failed(provider)
        
        # 所有提供商都失败
        self.failed_requests += 1
        error_msg = f"所有提供商均失败: {'; '.join(errors)}"
        logger.error(error_msg)
        raise Exception(error_msg)
    
    async def generate_embedding(self, text: str) -> Tuple[List[float], Dict[str, Any]]:
        """
        生成文本嵌入向量，自动选择一个成员提供商
        
        Args:
            text: 输入文本
            
        Returns:
            (嵌入向量, 元数据字典)
            
        Raises:
            Exception: 所有提供商都失败时抛出
        """
        # 遍历所有提供商尝试生成嵌入
        errors = []
        tried_providers = set()
        
        for _ in range(min(len(self.members), 3)):  # 最多尝试3次或所有提供商
            provider = self._select_provider()
            if not provider:
                break
                
            provider_id = getattr(provider, "id", str(id(provider)))
            if provider_id in tried_providers:
                continue
            tried_providers.add(provider_id)
            
            try:
                result = await provider.generate_embedding(text)
                # 更新统计数据
                self.total_requests += 1
                return result
            except Exception as e:
                errors.append(f"{provider.name}: {str(e)}")
                self._mark_provider_failed(provider)
        
        # 所有提供商都失败
        self.failed_requests += 1
        error_msg = f"所有提供商均失败: {'; '.join(errors)}"
        logger.error(error_msg)
        raise Exception(error_msg)
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取集群性能统计信息
        
        Returns:
            性能统计字典
        """
        stats = super().get_stats()
        
        # 添加集群特有统计信息
        stats.update({
            "strategy": self.strategy,
            "member_count": len(self.members),
            "available_members": len(self.members) - len(self._failed_providers),
            "failed_members": list(self._failed_providers.keys()),
        })
        
        # 包含每个成员的统计
        member_stats = []
        for provider in self.members:
            if hasattr(provider, "get_stats"):
                member_stats.append(provider.get_stats())
        stats["members"] = member_stats
        
        return stats 