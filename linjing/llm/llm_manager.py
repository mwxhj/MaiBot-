#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
LLM管理器模块 (Refactored)。

提供了对多个LLM提供商的统一管理，支持基于配置的任务路由。
采用更简洁的架构，允许用户定义兼容OpenAI API的提供商。
"""

import os
import re
import asyncio
from typing import Dict, List, Any, Optional, Union, Tuple, Type

from .token_counter import TokenCounter
from .providers.base_provider import BaseProvider
from .providers.openai_compatible_provider import OpenAICompatibleProvider # Use the new provider
from ..utils.logger import get_logger

logger = get_logger(__name__)


class LLMManager:
    """
    LLM管理器类 (Refactored)。

    管理多个大型语言模型提供商，主要支持兼容OpenAI API的提供商。
    提供统一接口访问，并根据任务类型路由请求。
    错误处理简化为直接向上抛出异常。
    """

    # 提供商类型映射 (简化，只支持 openai_compatible)
    PROVIDER_TYPES: Dict[str, Type[BaseProvider]] = {
        "openai_compatible": OpenAICompatibleProvider,
        # 可以扩展其他 Provider 类型
    }

    def __init__(self, config: Dict[str, Any]):
        """
        初始化LLM管理器

        Args:
            config: 配置字典，包含LLM提供商配置 (llm.providers) 和路由策略 (llm.usage_strategy)
        """
        self.config = config
        self.llm_config = config.get("llm", {})

        # 创建令牌计数器 (保留)
        token_counter_config = self.llm_config.get("token_counter", {})
        default_model_for_counter = token_counter_config.get("default_model", "gpt-3.5-turbo")
        self.token_counter = TokenCounter(default_model_for_counter)

        # 加载提供商
        self.providers: Dict[str, BaseProvider] = {} # 存储实例化的 Provider 对象，键为 provider_id
        self.provider_configs: Dict[str, Dict[str, Any]] = {} # 存储原始配置，键为 provider_id
        self.provider_models: Dict[str, List[str]] = {} # 存储每个provider支持的模型列表

        # 任务路由配置
        self.usage_strategy = self.llm_config.get("usage_strategy", {})
        self.task_routing = self.usage_strategy.get("task_routing", {}) # 任务到 {provider_id, model} 的映射

        logger.info("LLM管理器初始化，加载配置：")
        logger.info(f"提供商数量: {len(self.llm_config.get('providers', []))}")
        logger.info(f"加载的任务路由数量: {len(self.task_routing)}")
        for task, route in self.task_routing.items():
            logger.info(f"任务 '{task}' 路由到: {route}")
        logger.info(f"支持的提供商类型: {list(self.PROVIDER_TYPES.keys())}")

    async def initialize(self) -> bool:
        """
        初始化所有启用的LLM提供商

        Returns:
            是否成功初始化至少一个提供商
        """
        providers_config_list = self.llm_config.get("providers", [])
        if not isinstance(providers_config_list, list):
             logger.error("LLM 配置中的 'providers' 必须是一个列表")
             return False

        # 环境变量展开函数 (保留)
        def expand_env_vars(value: Any) -> Any:
            if isinstance(value, str):
                match = re.match(r"\$\{(.+?)(?::-([^}]+))?\}", value)
                if match:
                    var_name, default_value = match.groups()
                    env_value = os.environ.get(var_name)
                    if env_value is not None:
                        return env_value
                    elif default_value is not None:
                        return default_value
                    else:
                        logger.warning(f"环境变量 {var_name} 未设置，且没有提供默认值")
                        return ""
                else:
                    return value
            elif isinstance(value, dict):
                return {k: expand_env_vars(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [expand_env_vars(item) for item in value]
            else:
                return value

        initialization_tasks = []
        provider_details = [] # Store (id, type, config) for later processing

        for provider_config_raw in providers_config_list:
            if not isinstance(provider_config_raw, dict):
                 logger.warning(f"提供商配置项不是字典格式，已跳过: {provider_config_raw}")
                 continue

            provider_id = provider_config_raw.get("id")
            provider_type = provider_config_raw.get("type") # e.g., "openai_compatible"
            enabled = provider_config_raw.get("enabled", True)

            if not enabled:
                logger.info(f"提供商 {provider_id} 已禁用，跳过初始化")
                continue

            if not provider_id or not provider_type:
                logger.warning(f"无效的提供商配置: 缺少ID或类型。配置: {provider_config_raw}")
                continue

            provider_class = self.PROVIDER_TYPES.get(provider_type)
            if not provider_class:
                logger.warning(f"未知的提供商类型: {provider_type} (ID: {provider_id})。支持的类型: {list(self.PROVIDER_TYPES.keys())}")
                continue

            try:
                # 展开配置中的环境变量
                provider_config = expand_env_vars(provider_config_raw)
                logger.debug(f"准备初始化提供商 {provider_id} (类型: {provider_type})")

                # 创建提供商实例
                provider = provider_class(provider_config)

                # 添加初始化任务和详情
                initialization_tasks.append(provider.initialize())
                provider_details.append({"id": provider_id, "type": provider_type, "config": provider_config, "instance": provider})

            except ImportError as e:
                 logger.error(f"提供商 {provider_id} (类型: {provider_type}) 依赖库未安装: {e}")
            except Exception as e:
                logger.error(f"创建提供商 {provider_id} 实例时出错: {e}", exc_info=True)

        # 并发执行所有初始化任务
        results = await asyncio.gather(*initialization_tasks, return_exceptions=True)

        # 处理初始化结果
        successful_providers = 0
        for i, result in enumerate(results):
            detail = provider_details[i]
            provider_id = detail["id"]
            provider_type = detail["type"]
            provider_instance = detail["instance"]
            provider_config = detail["config"]

            if isinstance(result, Exception):
                logger.error(f"提供商 {provider_id} (类型: {provider_type}) 初始化失败: {result}", exc_info=isinstance(result, Exception))
            elif result is True:
                self.providers[provider_id] = provider_instance
                self.provider_configs[provider_id] = provider_config # Store expanded config
                # 从配置中提取并存储模型列表
                self.provider_models[provider_id] = provider_config.get("models", [])
                logger.info(f"已成功初始化提供商: {provider_id} (类型: {provider_type})")
                successful_providers += 1
            else: # result is False
                 logger.error(f"提供商 {provider_id} (类型: {provider_type}) 初始化方法返回 False。")


        # 验证任务路由配置
        for task, routing_info in self.task_routing.items():
            if not isinstance(routing_info, dict) or "provider_id" not in routing_info or "model" not in routing_info:
                logger.error(f"任务 '{task}' 的路由配置无效，必须包含 provider_id 和 model 字段")
                continue
            
            provider_id = routing_info["provider_id"]
            model = routing_info["model"]
            
            if provider_id not in self.providers:
                logger.error(f"任务 '{task}' 配置的提供商 '{provider_id}' 不可用或未初始化")
            elif model not in self.provider_models.get(provider_id, []):
                logger.warning(f"任务 '{task}' 配置的模型 '{model}' 不在提供商 '{provider_id}' 的支持列表中")

        if not self.providers:
            logger.error("没有可用的 LLM 提供商！管理器初始化失败。")
            return False

        return successful_providers > 0

    def get_provider(self, provider_id: str) -> Optional[BaseProvider]:
        """
        获取指定ID的提供商实例。
        """
        return self.providers.get(provider_id)

    def _get_provider_and_model_for_task(self, task: str) -> Tuple[BaseProvider, str, str]:
        """
        根据任务类型获取提供商实例、提供商ID和模型名称。

        Args:
            task: 任务类型 (例如 'chat', 'embeddings')

        Returns:
            (提供商实例, 提供商ID, 模型名称)

        Raises:
            ValueError: 如果找不到任务对应的可用提供商或模型。
        """
        # 1. 查找任务路由配置
        # === 添加调试日志 ===
        logger.debug(f"查找任务 '{task}' 的路由。当前路由表: {self.task_routing}")
        routing_info = self.task_routing.get(task)
        if not routing_info or not isinstance(routing_info, dict):
            # 在抛出错误前再记录一次详细信息
            logger.error(f"无法为任务 '{task}' 找到有效的路由信息。路由表内容: {self.task_routing}")
            raise ValueError(f"任务 '{task}' 未配置有效的路由信息")

        provider_id = routing_info.get("provider_id")
        model = routing_info.get("model")
        
        if not provider_id or not model:
            raise ValueError(f"任务 '{task}' 的路由配置缺少 provider_id 或 model 字段")

        # 2. 获取提供商实例
        provider = self.get_provider(provider_id)
        if not provider:
            raise ValueError(f"任务 '{task}' 配置的提供商 '{provider_id}' 未找到或未成功初始化")

        # 3. 检查模型是否在提供商支持列表中
        if model not in self.provider_models.get(provider_id, []):
            logger.warning(f"任务 '{task}' 配置的模型 '{model}' 不在提供商 '{provider_id}' 的支持列表中")

        logger.debug(f"任务 '{task}' 路由到提供商 '{provider_id}' 的模型 '{model}'")
        return provider, provider_id, model


    async def generate_text(
        self,
        prompt: Union[str, List[Dict[str, str]]], # 支持字符串或消息列表
        task: str = "chat", # 任务类型，用于路由
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        stop: Optional[List[str]] = None,
        model_override: Optional[str] = None, # 允许临时覆盖模型
        **kwargs
    ) -> Tuple[str, Dict[str, Any]]:
        """
        生成文本。根据任务路由选择提供商和模型。

        Args:
            prompt: 输入提示词 (str) 或消息列表 (List[Dict[str, str]])。
            task: 任务类型，用于路由 (默认 'chat')。
            max_tokens: 最大生成 token 数。
            temperature: 温度。
            stop: 停止序列。
            model_override: 临时指定要使用的模型名称，覆盖配置中的模型。
            **kwargs: 其他传递给 provider 的参数。

        Returns:
            (生成的文本, 元数据字典)。

        Raises:
            ValueError: 如果找不到任务对应的可用提供商或模型。
            Exception: 如果底层 Provider 调用失败。
        """
        provider, provider_id, model_name = self._get_provider_and_model_for_task(task)
        
        # 允许调用时覆盖模型
        if model_override:
            model_name = model_override
            logger.debug(f"使用调用时覆盖的模型 '{model_name}' 替代配置的模型")

        logger.debug(f"使用提供商 '{provider_id}' (模型: {model_name}) 为任务 '{task}' 生成文本")

        try:
            # 直接调用 Provider，让异常向上冒泡
            text, metadata = await provider.generate_text(
                model=model_name,
                prompt=prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                stop=stop,
                **kwargs
            )

            # 添加额外元数据
            metadata["provider_id"] = provider_id
            metadata["provider_name"] = provider.name
            metadata["model_used"] = model_name
            metadata["task"] = task

            return text, metadata

        except Exception as e:
            logger.error(f"提供商 '{provider_id}' (模型: {model_name}) 在任务 '{task}' 中生成文本失败: {e}", exc_info=True)
            # 按策略 B，直接抛出异常
            raise e


    async def generate_embedding(
        self,
        text: Union[str, List[str]],
        task: str = "embeddings", # 任务类型固定为 embeddings
        model_override: Optional[str] = None # 允许临时覆盖模型
    ) -> Tuple[Union[List[float], List[List[float]]], Dict[str, Any]]:
        """
        生成文本嵌入向量。根据任务路由选择提供商和模型。

        Args:
            text: 输入文本或文本列表。
            task: 任务类型 (默认 'embeddings')。
            model_override: 临时指定要使用的嵌入模型名称，覆盖配置中的模型。

        Returns:
            (嵌入向量或向量列表, 元数据字典)。

        Raises:
            ValueError: 如果找不到任务对应的可用提供商或模型。
            Exception: 如果底层 Provider 调用失败。
        """
        provider, provider_id, model_name = self._get_provider_and_model_for_task(task)
        
        # 允许调用时覆盖模型
        if model_override:
            model_name = model_override
            logger.debug(f"使用调用时覆盖的模型 '{model_name}' 替代配置的模型")

        logger.debug(f"使用提供商 '{provider_id}' (模型: {model_name}) 为任务 '{task}' 生成嵌入")

        try:
            # 直接调用 Provider，让异常向上冒泡
            embedding, metadata = await provider.generate_embedding(
                 model=model_name,
                 text=text
            )

            # 添加额外元数据
            metadata["provider_id"] = provider_id
            metadata["provider_name"] = provider.name
            metadata["model_used"] = model_name
            metadata["task"] = task

            return embedding, metadata

        except Exception as e:
            logger.error(f"提供商 '{provider_id}' (模型: {model_name}) 在任务 '{task}' 中生成嵌入失败: {e}", exc_info=True)
            # 按策略 B，直接抛出异常
            raise e

    def get_token_counter(self) -> TokenCounter:
        """获取令牌计数器实例"""
        return self.token_counter

    async def close(self) -> None:
        """
        关闭所有已初始化的提供商。
        """
        logger.info("正在关闭 LLM 管理器中的所有提供商...")
        close_tasks = []
        for provider_id, provider in self.providers.items():
            logger.debug(f"请求关闭提供商: {provider_id}")
            close_tasks.append(provider.close()) # BaseProvider.close is async

        results = await asyncio.gather(*close_tasks, return_exceptions=True)

        for i, result in enumerate(results):
             provider_id = list(self.providers.keys())[i]
             if isinstance(result, Exception):
                  logger.error(f"关闭提供商 {provider_id} 时出错: {result}", exc_info=True)
             else:
                  logger.debug(f"提供商 {provider_id} 已成功关闭。")
        logger.info("所有 LLM 提供商关闭完成。")
        self.providers.clear()
        self.provider_configs.clear()
