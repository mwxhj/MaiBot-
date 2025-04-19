#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
OpenAI API 兼容的 LLM 提供商实现。
"""

import asyncio
from typing import Dict, List, Any, Optional, Union, Tuple

# 尝试导入 openai 库
try:
    import openai
    from openai import AsyncOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    AsyncOpenAI = None # 定义一个占位符以便类型提示

from .base_provider import BaseProvider
from ...utils.logger import get_logger

logger = get_logger(__name__)

class OpenAICompatibleProvider(BaseProvider):
    """
    与OpenAI API兼容的LLM提供商实现。

    可用于连接OpenAI官方服务或任何兼容OpenAI API规范的第三方服务（如本地模型服务）。
    需要安装 `openai` 库 (`pip install openai`)。
    """

    def __init__(self, config: Dict[str, Any]):
        """
        初始化 OpenAI 兼容提供商。

        Args:
            config: 配置字典，应包含:
                - id (str): 提供商的唯一标识符。
                - api_key (str): API 密钥。
                - api_base (str, optional): API 的基础 URL。如果为 None 或空，则使用 OpenAI 官方 URL。
                - timeout (int, optional): API 请求超时时间（秒），默认为 60。
        """
        super().__init__(config)
        if not OPENAI_AVAILABLE:
            logger.error("`openai` 库未安装。请运行 `pip install openai` 来安装。")
            # 可以在这里抛出异常或设置一个标志位阻止后续操作
            raise ImportError("`openai` 库未安装，无法使用 OpenAICompatibleProvider。")

        self.api_key = config.get("api_key")
        self.api_base = config.get("api_base") # OpenAI base URL or compatible endpoint
        self.timeout = config.get("timeout", 60) # Default timeout
        self.client: Optional[AsyncOpenAI] = None

    async def initialize(self) -> bool:
        """
        初始化 AsyncOpenAI 客户端。
        """
        if not self.api_key:
            logger.error(f"提供商 {self.provider_id}: 未配置 API key (api_key)")
            return False
        try:
            # 如果 api_base 未提供或为空字符串，则 AsyncOpenAI 会使用默认的 OpenAI URL
            effective_api_base = self.api_base if self.api_base else None
            self.client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=effective_api_base,
                timeout=self.timeout
            )
            # 可选：进行一个简单的测试调用来验证连接和认证
            # 例如，尝试列出模型（需要相应权限）
            # await self.client.models.list(timeout=10) # 使用较短超时进行测试
            logger.info(f"提供商 {self.provider_id}: OpenAI 兼容客户端初始化成功 (Base URL: {effective_api_base or 'Default OpenAI'})")
            return True
        except openai.AuthenticationError as e:
             logger.error(f"提供商 {self.provider_id}: OpenAI API 认证失败，请检查 API Key: {e}", exc_info=True)
             self.client = None
             return False
        except Exception as e:
            logger.error(f"提供商 {self.provider_id}: OpenAI 兼容客户端初始化失败: {e}", exc_info=True)
            self.client = None
            return False

    async def generate_text(
        self,
        model: str,
        prompt: Union[str, List[Dict[str, str]]], # 接受字符串或消息列表
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        stop: Optional[List[str]] = None,
        **kwargs
    ) -> Tuple[str, Dict[str, Any]]:
        """
        使用 OpenAI 兼容 API 生成文本。
        """
        if not self.client:
            raise RuntimeError(f"提供商 {self.provider_id} 未初始化或初始化失败。")

        request_params = {
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stop": stop,
            **kwargs # Pass any extra args
        }
        # Filter out None values from optional parameters
        request_params = {k: v for k, v in request_params.items() if v is not None}

        # --- 处理 prompt/messages ---
        if isinstance(prompt, str):
            # 如果是字符串，转换为 OpenAI Chat API 的消息格式
            request_params["messages"] = [{"role": "user", "content": prompt}]
        elif isinstance(prompt, list):
            # 如果已经是消息列表，直接使用
            request_params["messages"] = prompt
        else:
            raise ValueError("无效的 'prompt' 类型。应为字符串或消息字典列表。")
        # --- 结束处理 ---

        try:
            logger.debug(f"提供商 {self.provider_id}: 调用 chat.completions.create (模型: {model})，参数: {request_params}")
            start_time = asyncio.get_event_loop().time()

            response = await self.client.chat.completions.create(**request_params)

            end_time = asyncio.get_event_loop().time()
            latency = end_time - start_time

            # 提取文本和元数据
            generated_text = ""
            finish_reason = "unknown"
            if response.choices:
                message = response.choices[0].message
                generated_text = message.content or ""
                finish_reason = response.choices[0].finish_reason

            usage = response.usage
            metadata = {
                "latency_ms": latency * 1000,
                "finish_reason": finish_reason,
                "usage": {
                    "prompt_tokens": usage.prompt_tokens if usage else 0,
                    "completion_tokens": usage.completion_tokens if usage else 0,
                    "total_tokens": usage.total_tokens if usage else 0,
                } if usage else {},
                # "raw_response": response.model_dump() # 可选：包含原始响应
            }
            logger.debug(f"提供商 {self.provider_id}: generate_text 成功，耗时: {latency:.2f}s, Tokens: {metadata.get('usage')}")
            return generated_text, metadata

        except Exception as e:
            # 使用 logger.exception 自动处理异常信息和堆栈跟踪
            logger.exception(f"提供商 {self.provider_id}: 调用 generate_text (模型: {model}) 失败")
            # 根据策略 B，重新抛出异常
            raise e


    async def generate_embedding(
        self,
        model: str,
        text: Union[str, List[str]]
    ) -> Tuple[Union[List[float], List[List[float]]], Dict[str, Any]]:
        """
        使用 OpenAI 兼容 API 生成嵌入向量。
        """
        if not self.client:
            raise RuntimeError(f"提供商 {self.provider_id} 未初始化或初始化失败。")

        is_batch = isinstance(text, list)
        input_text = text if is_batch else [text]

        # OpenAI API v1.x 要求输入不能为空字符串列表
        if not input_text or any(not item for item in input_text):
             logger.warning(f"提供商 {self.provider_id}: generate_embedding 收到空输入，返回空结果。")
             return ([], {}) if is_batch else ([], {})


        try:
            logger.debug(f"提供商 {self.provider_id}: 调用 embeddings.create (模型: {model})，输入数量: {len(input_text)}")
            start_time = asyncio.get_event_loop().time()

            response = await self.client.embeddings.create(
                model=model,
                input=input_text
            )

            end_time = asyncio.get_event_loop().time()
            latency = end_time - start_time

            # 提取嵌入和元数据
            embeddings = [item.embedding for item in response.data]
            usage = response.usage
            metadata = {
                 "latency_ms": latency * 1000,
                 "usage": {
                     "prompt_tokens": usage.prompt_tokens if usage else 0,
                     "total_tokens": usage.total_tokens if usage else 0, # embedding API 通常只有 prompt tokens
                 } if usage else {},
                 # "raw_response": response.model_dump() # 可选
            }

            logger.debug(f"提供商 {self.provider_id}: generate_embedding 成功，耗时: {latency:.2f}s, Tokens: {metadata.get('usage')}")

            if is_batch:
                return embeddings, metadata
            else:
                # 确保即使API返回空列表（理论上不应发生），也不会索引错误
                return embeddings[0] if embeddings else [], metadata

        except Exception as e:
            logger.error(f"提供商 {self.provider_id}: 调用 generate_embedding (模型: {model}) 失败: {e}", exc_info=True)
            # 根据策略 B，重新抛出异常
            raise e

    async def close(self) -> None:
        """
        关闭 OpenAI 客户端（如果适用）。
        标准 openai >= v1.0 库似乎不需要显式关闭基于 httpx 的客户端，
        但如果未来使用其他底层库或需要清理资源，可以在这里实现。
        """
        if self.client and hasattr(self.client, 'close'):
             try:
                  # 检查是否有异步关闭方法
                  if asyncio.iscoroutinefunction(self.client.close):
                       await self.client.close()
                  else:
                       # 如果是同步方法（不太可能），则不调用
                       pass
                  logger.info(f"提供商 {self.provider_id}: OpenAI 兼容客户端已关闭。")
             except Exception as e:
                  logger.warning(f"提供商 {self.provider_id}: 关闭 OpenAI 客户端时出错: {e}", exc_info=True)
        self.client = None # 清理引用