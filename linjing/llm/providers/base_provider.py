#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
LLM提供商基类。

定义了LLM提供商的通用接口，所有提供商实现必须继承此基类。
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Union, Tuple

from ...utils.logger import get_logger

logger = get_logger(__name__)


class BaseProvider(ABC):
    """
    LLM提供商抽象基类。

    提供大型语言模型的统一访问接口，定义了所有提供商必须实现的方法。
    子类需要实现具体的API调用逻辑。
    """

    def __init__(self, config: Dict[str, Any]):
        """
        初始化LLM提供商

        Args:
            config: 配置字典，至少应包含 'id' 和 'type'。
                    子类可以从中读取所需的特定配置，如 api_key, api_base 等。
        """
        self.config = config
        self.provider_id = config.get("id", "unknown_provider") # 使用 id 作为标识符
        self.name = config.get("name", self.__class__.__name__) # 可选的显示名称
        logger.info(f"初始化LLM提供商: {self.provider_id} (类型: {self.__class__.__name__})")

    @abstractmethod
    async def initialize(self) -> bool:
        """
        异步初始化提供商。

        例如，可以在这里进行API连接测试或加载必要资源。

        Returns:
            初始化是否成功。
        """
        pass

    @abstractmethod
    async def generate_text(
        self,
        model: str, # 模型名称现在是必需参数
        prompt: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        stop: Optional[List[str]] = None,
        **kwargs
    ) -> Tuple[str, Dict[str, Any]]:
        """
        生成文本。

        Args:
            model: 要使用的模型名称。
            prompt: 输入提示词。
            max_tokens: 最大生成的token数 (可选, Provider可有默认值)。
            temperature: 温度 (可选, Provider可有默认值)。
            stop: 停止生成的标志字符串列表 (可选)。
            **kwargs: 传递给底层API的其他特定参数。

        Returns:
            一个元组，包含：
            - 生成的文本 (str)
            - 元数据字典 (Dict[str, Any])，例如 token 使用情况、完成原因等。

        Raises:
            Exception: 如果API调用失败或发生其他错误。
        """
        pass

    @abstractmethod
    async def generate_embedding(
        self,
        model: str, # 模型名称现在是必需参数
        text: Union[str, List[str]] # 支持单个文本或列表以进行批量处理
    ) -> Tuple[Union[List[float], List[List[float]]], Dict[str, Any]]:
        """
        生成文本嵌入向量。

        Args:
            model: 要使用的嵌入模型名称。
            text: 输入文本或文本列表。

        Returns:
            一个元组，包含：
            - 嵌入向量 (List[float]) 或向量列表 (List[List[float]])
            - 元数据字典 (Dict[str, Any])，例如 token 使用情况。

        Raises:
            Exception: 如果API调用失败或发生其他错误。
        """
        pass

    async def close(self) -> None:
        """
        可选的关闭方法。

        用于释放资源，例如关闭HTTP客户端会话。
        默认实现为空。
        """
        pass