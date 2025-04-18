#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
模型路由提供商模块，用于在同一API供应商的不同模型之间路由请求。

该模块允许使用同一个API密钥访问不同的模型，并根据任务需求自动选择最合适的模型。
"""

import random
import time
from typing import Dict, List, Any, Optional, Tuple, Type, Union

from .base_provider import BaseProvider
from .openai_provider import OpenAIProvider
from .azure_provider import AzureProvider
from ...utils.logger import get_logger

logger = get_logger(__name__)

class ModelRouterProvider(BaseProvider):
    """
    模型路由提供商，在同一API提供商的不同模型之间进行路由。
    
    支持基于任务类型、成本和性能需求自动选择模型，可以设置默认模型和模型回退机制。
    """
    
    # 支持的提供商类型映射
    PROVIDER_TYPES = {
        "openai": OpenAIProvider,
        "azure": AzureProvider,
    }
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化模型路由提供商
        
        Args:
            config: 配置字典，包含模型路由配置信息
        """
        super().__init__(config)
        
        self.name = config.get("name", "ModelRouterProvider")
        self.provider_type = config.get("provider_type", "")  # 基础提供商类型
        self.default_model_id = config.get("default_model_id", "")  # 默认模型ID
        self.fallback_enabled = config.get("fallback_enabled", True)  # 是否启用回退
        
        # 共享配置（应用于所有模型）
        self.shared_config = config.get("shared_config", {})
        
        # 初始化模型实例字典 {model_id -> model_instance}
        self.models: Dict[str, BaseProvider] = {}
        
        # 模型状态跟踪
        self._failed_models = {}  # model_id -> 失败时间
        self._current_model_id = self.default_model_id  # 当前使用的模型ID
        
        # 任务路由配置
        self.task_routing = config.get("task_routing", {})
        
        # 模型路由规则
        self.model_rules = config.get("model_rules", [])
        
        # 初始化模型实例
        self._init_models(config.get("models", []))
        
        logger.info(f"模型路由提供商 {self.name} 初始化，基础提供商类型: {self.provider_type}，模型数量: {len(self.models)}")
    
    def _init_models(self, model_configs: List[Dict[str, Any]]) -> None:
        """
        初始化模型提供商实例
        
        Args:
            model_configs: 模型配置列表
        """
        if not self.provider_type or self.provider_type not in self.PROVIDER_TYPES:
            logger.error(f"无效的提供商类型: {self.provider_type}")
            return
        
        provider_class = self.PROVIDER_TYPES[self.provider_type]
        
        for model_config in model_configs:
            try:
                model_id = model_config.get("id")
                if not model_id:
                    logger.error("模型配置缺少ID，跳过")
                    continue
                
                # 合并共享配置和模型特定配置
                merged_config = {**self.shared_config, **model_config}
                
                # 创建提供商实例
                provider = provider_class(merged_config)
                self.models[model_id] = provider
                
                # 如果未设置默认模型ID，使用第一个模型
                if not self.default_model_id and len(self.models) == 1:
                    self.default_model_id = model_id
                    self._current_model_id = model_id
                
                logger.debug(f"添加模型: {model_id}")
            except Exception as e:
                logger.error(f"创建模型实例失败: {e}")
    
    async def initialize(self) -> bool:
        """
        初始化所有模型实例
        
        Returns:
            是否成功初始化至少一个模型
        """
        if not self.models:
            logger.error("没有可用的模型实例")
            return False
        
        success_count = 0
        
        for model_id, provider in self.models.items():
            try:
                if await provider.initialize():
                    success_count += 1
                    logger.info(f"模型 {model_id} 初始化成功")
                else:
                    logger.error(f"模型 {model_id} 初始化失败")
            except Exception as e:
                logger.error(f"初始化模型 {model_id} 失败: {e}")
        
        if success_count == 0:
            logger.error("所有模型初始化失败")
            return False
        
        # 确保默认模型可用，否则使用第一个可用的模型
        if self.default_model_id not in self.models or self.default_model_id in self._failed_models:
            for model_id in self.models.keys():
                if model_id not in self._failed_models:
                    self.default_model_id = model_id
                    self._current_model_id = model_id
                    logger.warning(f"默认模型不可用，切换到: {model_id}")
                    break
        
        logger.info(f"成功初始化 {success_count}/{len(self.models)} 个模型，默认模型: {self.default_model_id}")
        return True
    
    def _select_model(self, task: str = None, max_tokens: int = None, **kwargs) -> Optional[str]:
        """
        根据任务类型和参数选择合适的模型
        
        Args:
            task: 任务类型
            max_tokens: 最大生成token数
            **kwargs: 其他参数
            
        Returns:
            选中的模型ID
        """
        # 1. 检查是否直接指定了模型
        if "model_id" in kwargs:
            model_id = kwargs.get("model_id")
            if model_id in self.models and model_id not in self._failed_models:
                return model_id
        
        # 2. 根据任务类型路由
        if task and task in self.task_routing:
            model_id = self.task_routing[task]
            if model_id in self.models and model_id not in self._failed_models:
                return model_id
        
        # 3. 根据规则选择模型
        for rule in self.model_rules:
            condition = rule.get("condition", {})
            target_model = rule.get("model_id")
            
            # 检查规则是否匹配
            match = True
            for key, value in condition.items():
                if key == "min_tokens" and max_tokens is not None:
                    if max_tokens < value:
                        match = False
                        break
                elif key == "max_tokens" and max_tokens is not None:
                    if max_tokens > value:
                        match = False
                        break
                elif key == "task":
                    if task != value:
                        match = False
                        break
                elif key in kwargs:
                    if kwargs[key] != value:
                        match = False
                        break
            
            # 如果规则匹配且模型可用，返回该模型
            if match and target_model in self.models and target_model not in self._failed_models:
                return target_model
        
        # 4. 使用当前或默认模型
        if self._current_model_id in self.models and self._current_model_id not in self._failed_models:
            return self._current_model_id
        elif self.default_model_id in self.models and self.default_model_id not in self._failed_models:
            return self.default_model_id
        
        # 5. 使用任何可用模型
        for model_id in self.models.keys():
            if model_id not in self._failed_models:
                return model_id
        
        # 如果启用了回退，选择最近失败的模型
        if self.fallback_enabled and self._failed_models:
            oldest_failed = min(self._failed_models.items(), key=lambda x: x[1])
            return oldest_failed[0]
        
        return None
    
    def _mark_model_failed(self, model_id: str) -> None:
        """
        标记模型为失败状态
        
        Args:
            model_id: 失败的模型ID
        """
        self._failed_models[model_id] = time.time()
        logger.warning(f"模型 {model_id} 标记为失败状态")
    
    async def generate_text(
        self, 
        prompt: str, 
        max_tokens: int = 1000, 
        temperature: float = 0.7,
        stop: Optional[List[str]] = None,
        **kwargs
    ) -> Tuple[str, Dict[str, Any]]:
        """
        生成文本，自动选择合适的模型
        
        Args:
            prompt: 输入提示词
            max_tokens: 最大生成的token数
            temperature: 温度，控制输出的随机性
            stop: 停止生成的标志字符串列表
            **kwargs: 额外的参数，包括:
                      - model_id: 直接指定模型ID
                      - task: 任务类型，用于模型选择
                      - quality: 质量要求 (high, medium, low)
                      - priority: 优先级 (speed, balanced, quality)
            
        Returns:
            (生成的文本, 元数据字典)
            
        Raises:
            Exception: 所有模型都失败时抛出
        """
        # 获取任务类型
        task = kwargs.pop("task", None)
        
        # 从kwargs中提取和删除model_id，避免传递给模型API
        requested_model_id = kwargs.pop("model_id", None)
        
        # 选择模型
        model_id = requested_model_id if requested_model_id in self.models else self._select_model(
            task=task, max_tokens=max_tokens, **kwargs
        )
        
        if not model_id:
            self.failed_requests += 1
            error_msg = "没有可用的模型"
            logger.error(error_msg)
            raise Exception(error_msg)
        
        # 获取模型实例
        provider = self.models.get(model_id)
        
        # 记录当前模型
        self._current_model_id = model_id
        
        # 尝试生成文本
        errors = []
        tried_models = set()
        
        for _ in range(min(len(self.models), 3)):  # 最多尝试3次或所有模型
            if not model_id or model_id in tried_models:
                # 选择下一个模型
                model_id = self._select_model(task=task, max_tokens=max_tokens, **kwargs)
                if not model_id or model_id in tried_models:
                    break
            
            tried_models.add(model_id)
            provider = self.models.get(model_id)
            
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
                
                # 添加路由信息到元数据
                text, metadata = result
                metadata["router_info"] = {
                    "model_id": model_id,
                    "selected_by": "direct" if requested_model_id else "router",
                    "tried_models": list(tried_models)
                }
                
                return text, metadata
                
            except Exception as e:
                errors.append(f"{model_id}: {str(e)}")
                self._mark_model_failed(model_id)
                model_id = None  # 清空当前模型，让下一次迭代选择新模型
        
        # 所有尝试都失败
        self.failed_requests += 1
        error_msg = f"所有模型均失败: {'; '.join(errors)}"
        logger.error(error_msg)
        raise Exception(error_msg)
    
    async def generate_embedding(self, text: str) -> Tuple[List[float], Dict[str, Any]]:
        """
        生成文本嵌入向量，使用默认嵌入模型
        
        Args:
            text: 输入文本
            
        Returns:
            (嵌入向量, 元数据字典)
            
        Raises:
            Exception: 所有模型都失败时抛出
        """
        # 查找配置中指定的嵌入模型
        embedding_model_id = self.task_routing.get("embeddings", self.default_model_id)
        
        # 尝试生成嵌入
        errors = []
        tried_models = set()
        
        for _ in range(min(len(self.models), 3)):  # 最多尝试3次或所有模型
            if embedding_model_id in tried_models:
                # 选择下一个模型
                for model_id in self.models.keys():
                    if model_id not in tried_models:
                        embedding_model_id = model_id
                        break
                else:
                    break  # 所有模型都已尝试
            
            tried_models.add(embedding_model_id)
            provider = self.models.get(embedding_model_id)
            
            if not provider:
                embedding_model_id = None
                continue
            
            try:
                result = await provider.generate_embedding(text)
                
                # 更新统计数据
                self.total_requests += 1
                
                # 添加路由信息到元数据
                embedding, metadata = result
                metadata["router_info"] = {
                    "model_id": embedding_model_id,
                    "tried_models": list(tried_models)
                }
                
                return embedding, metadata
                
            except Exception as e:
                errors.append(f"{embedding_model_id}: {str(e)}")
                self._mark_model_failed(embedding_model_id)
                embedding_model_id = None
        
        # 所有尝试都失败
        self.failed_requests += 1
        error_msg = f"所有模型均失败: {'; '.join(errors)}"
        logger.error(error_msg)
        raise Exception(error_msg)
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取路由器性能统计信息
        
        Returns:
            性能统计字典
        """
        stats = super().get_stats()
        
        # 添加路由器特有统计信息
        stats.update({
            "provider_type": self.provider_type,
            "model_count": len(self.models),
            "available_models": len(self.models) - len(self._failed_models),
            "failed_models": list(self._failed_models.keys()),
            "default_model": self.default_model_id,
            "current_model": self._current_model_id
        })
        
        # 包含每个模型的统计
        model_stats = []
        for model_id, provider in self.models.items():
            if hasattr(provider, "get_stats"):
                model_stats.append({
                    "model_id": model_id,
                    "stats": provider.get_stats()
                })
        stats["models"] = model_stats
        
        return stats 