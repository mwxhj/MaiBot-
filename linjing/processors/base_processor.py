#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
处理器基类模块，定义所有处理器的基础接口。
"""

import inspect
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List, Type, ClassVar

from linjing.processors.message_context import MessageContext
from linjing.utils.logger import get_logger

# 获取日志记录器
logger = get_logger(__name__)


class BaseProcessor(ABC):
    """
    处理器基类，定义处理器的基本接口和行为。
    所有具体处理器都应继承此类。
    """
    
    # 处理器名称，子类应覆盖
    name: ClassVar[str] = "base_processor"
    
    # 处理器描述，子类应覆盖
    description: ClassVar[str] = "基础处理器"
    
    # 处理器版本，子类应覆盖
    version: ClassVar[str] = "1.0.0"
    
    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None, priority: Optional[int] = None): # 添加 name 参数
        """
        初始化处理器
        
        Args:
            name: 处理器名称 (从子类传递)
            config: 处理器配置
            priority: 处理器优先级，数值越小优先级越高
        """
        self.name = name # 设置实例 name, 覆盖类变量
        self.config = config or {}
        self.enabled = self.config.get("enabled", True)
        self.priority = priority
    
    @abstractmethod
    async def process(self, context: MessageContext) -> MessageContext:
        """
        处理消息上下文
        
        Args:
            context: 消息上下文
            
        Returns:
            处理后的消息上下文
        """
        raise NotImplementedError("处理器必须实现process方法")
    
    async def __call__(self, context: MessageContext) -> MessageContext:
        """
        使处理器可调用
        
        Args:
            context: 消息上下文
            
        Returns:
            处理后的消息上下文
        """
        if not self.enabled:
            # 处理器已禁用，直接返回上下文
            logger.debug(f"处理器 {self.name} 已禁用，跳过处理")
            return context
        
        if context.aborted:
            # 处理已中止，直接返回上下文
            logger.debug(f"处理已中止，处理器 {self.name} 跳过处理")
            return context
        
        # 记录处理开始
        start_time = time.time()
        processor_name = self.__class__.__name__
        logger.debug(f"处理器 {processor_name} 开始处理消息")
        
        try:
            # 调用实际的处理方法
            result = await self.process(context)
            
            # 记录处理日志
            context.log_processor(
                processor_name,
                f"处理完成，耗时 {(time.time() - start_time):.4f}s"
            )
            
            return result
        except Exception as e:
            # 记录错误
            error_msg = f"处理出错: {str(e)}"
            logger.error(f"处理器 {processor_name} {error_msg}", exc_info=True)
            
            # 记录到上下文
            context.log_processor(processor_name, error_msg)
            context.set_error(e)
            
            return context
    
    def enable(self) -> None:
        """启用处理器"""
        self.enabled = True
        logger.debug(f"处理器 {self.name} 已启用")
    
    def disable(self) -> None:
        """禁用处理器"""
        self.enabled = False
        logger.debug(f"处理器 {self.name} 已禁用")
    
    def is_enabled(self) -> bool:
        """
        检查处理器是否启用
        
        Returns:
            是否启用
        """
        return self.enabled
    
    def get_name(self) -> str:
        """
        获取处理器名称
        
        Returns:
            处理器名称
        """
        return self.name
    
    def get_description(self) -> str:
        """
        获取处理器描述
        
        Returns:
            处理器描述
        """
        return self.description
    
    def get_version(self) -> str:
        """
        获取处理器版本
        
        Returns:
            处理器版本
        """
        return self.version
    
    @classmethod
    def get_processor_info(cls) -> Dict[str, Any]:
        """
        获取处理器信息
        
        Returns:
            处理器信息字典
        """
        return {
            "name": cls.name,
            "description": cls.description,
            "version": cls.version,
            "class": cls.__name__
        }
    
    def update_config(self, config: Dict[str, Any]) -> None:
        """
        更新处理器配置
        
        Args:
            config: 新配置
        """
        self.config.update(config)
        # 更新启用状态
        if "enabled" in config:
            self.enabled = config["enabled"]
    
    def get_config(self) -> Dict[str, Any]:
        """
        获取处理器配置
        
        Returns:
            处理器配置
        """
        return self.config.copy()


# 处理器类型别名
Processor = BaseProcessor 