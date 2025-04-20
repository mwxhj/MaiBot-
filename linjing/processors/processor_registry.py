#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
处理器注册中心模块，用于管理和注册所有可用的处理器。
"""

import inspect
import pkgutil
import importlib
from typing import Any, Dict, List, Optional, Type, Set, Callable, TypeVar

from linjing.processors.base_processor import BaseProcessor
from linjing.utils.logger import get_logger

# 获取日志记录器
logger = get_logger(__name__)

# 类型变量
T = TypeVar('T', bound=BaseProcessor)


class ProcessorRegistry:
    """
    处理器注册中心，用于管理所有可用的处理器。
    提供注册、查找、列出处理器的功能。
    """
    
    # 注册的处理器类字典，键为处理器名称，值为处理器类
    _processor_classes: Dict[str, Type[BaseProcessor]] = {}
    
    # 处理器实例缓存，键为处理器名称，值为处理器实例
    _processor_instances: Dict[str, BaseProcessor] = {}
    
    @classmethod
    def register(cls, name: Optional[str] = None):
        """
        注册处理器的装饰器
        
        Args:
            name: 处理器名称，如果为None则使用类的name属性
            
        Returns:
            装饰器函数
        """
        def decorator(processor_class: Type[BaseProcessor]) -> Type[BaseProcessor]:
            # 确定处理器名称
            processor_name = name or processor_class.name
            
            # 注册处理器类
            cls._processor_classes[processor_name] = processor_class
            logger.debug(f"注册处理器: {processor_name} -> {processor_class.__name__}")
            
            return processor_class
            
        return decorator
    
    @classmethod
    def get_processor_class(cls, name: str) -> Optional[Type[BaseProcessor]]:
        """
        获取处理器类
        
        Args:
            name: 处理器名称
            
        Returns:
            处理器类或None
        """
        return cls._processor_classes.get(name)
    
    @classmethod
    def create_processor(
        cls, name: str, config: Optional[Dict[str, Any]] = None
    ) -> Optional[BaseProcessor]:
        """
        创建处理器实例
        
        Args:
            name: 处理器名称
            config: 处理器配置
            
        Returns:
            处理器实例或None
        """
        processor_class = cls.get_processor_class(name)
        if not processor_class:
            logger.error(f"找不到处理器: {name}")
            return None
        
        try:
            # 传递 name 和 config 给构造函数
            processor = processor_class(name=name, config=config)
            return processor
        except Exception as e:
            logger.error(f"创建处理器 {name} 失败: {str(e)}", exc_info=True)
            return None
    
    @classmethod
    def get_processor(
        cls, name: str, config: Optional[Dict[str, Any]] = None
    ) -> Optional[BaseProcessor]:
        """
        获取处理器实例，如果不存在则创建
        
        Args:
            name: 处理器名称
            config: 处理器配置
            
        Returns:
            处理器实例或None
        """
        # 检查缓存中是否存在
        if name in cls._processor_instances:
            # 如果提供了配置，则更新处理器配置
            if config:
                cls._processor_instances[name].update_config(config)
            return cls._processor_instances[name]
        
        # 创建新的处理器实例
        processor = cls.create_processor(name, config)
        if processor:
            # 缓存处理器实例
            cls._processor_instances[name] = processor
        
        return processor
    
    @classmethod
    def list_processors(cls) -> Dict[str, Dict[str, Any]]:
        """
        列出所有已注册的处理器
        
        Returns:
            处理器信息字典，键为处理器名称，值为处理器信息
        """
        processors_info = {}
        for name, processor_class in cls._processor_classes.items():
            processors_info[name] = processor_class.get_processor_info()
        return processors_info
    
    @classmethod
    def clear(cls) -> None:
        """
        清除所有注册的处理器
        """
        cls._processor_classes.clear()
        cls._processor_instances.clear()
        logger.debug("处理器注册中心已清空")
    
    @classmethod
    def scan_processors(cls, package_name: str) -> None:
        """
        扫描并自动注册指定包中的所有处理器
        
        Args:
            package_name: 包名
        """
        package = importlib.import_module(package_name)
        for _, name, is_pkg in pkgutil.iter_modules(package.__path__, package.__name__ + '.'):
            try:
                module = importlib.import_module(name)
                # 查找模块中的处理器类
                for item_name in dir(module):
                    item = getattr(module, item_name)
                    if (inspect.isclass(item) and 
                        issubclass(item, BaseProcessor) and 
                        item is not BaseProcessor):
                        # 自动注册处理器
                        cls._processor_classes[item.name] = item
                        logger.debug(f"自动注册处理器: {item.name} -> {item.__name__}")
            except Exception as e:
                logger.error(f"加载处理器模块 {name} 失败: {str(e)}", exc_info=True)
    
    @classmethod
    def register_bulk(cls, processors: Dict[str, Type[BaseProcessor]]) -> None:
        """
        批量注册处理器
        
        Args:
            processors: 处理器名称到类的映射
        """
        for name, processor_class in processors.items():
            cls._processor_classes[name] = processor_class
            logger.debug(f"批量注册处理器: {name} -> {processor_class.__name__}")
    
    @classmethod
    def instantiate_all(cls, config: Dict[str, Dict[str, Any]]) -> Dict[str, BaseProcessor]:
        """
        根据配置实例化所有处理器
        
        Args:
            config: 处理器配置，键为处理器名称，值为处理器配置
            
        Returns:
            处理器实例字典，键为处理器名称，值为处理器实例
        """
        processors = {}
        for name, processor_config in config.items():
            processor = cls.get_processor(name, processor_config)
            if processor:
                processors[name] = processor
        
        return processors

    @classmethod
    def register_processor(cls, processor_cls: Type[BaseProcessor]) -> None:
        """
        注册处理器类
        
        Args:
            processor_cls: 要注册的处理器类
            
        Raises:
            ValueError: 处理器已注册或缺少处理器名称
        """
        try:
            # 获取处理器名称 (从类属性)
            processor_name = getattr(processor_cls, 'processor_name', None)
            if not processor_name:
                raise ValueError(f"处理器类 {processor_cls.__name__} 缺少 processor_name 属性")
            
            # 检查是否已注册
            if processor_name in cls._processor_classes:
                logger.warning(f"处理器 {processor_name} 已经注册，将被覆盖")
            
            # 添加到注册表
            cls._processor_classes[processor_name] = processor_cls
            logger.info(f"成功注册处理器: {processor_name} ({processor_cls.__name__})")
        except Exception as e:
            logger.error(f"注册处理器 {processor_cls.__name__} 时出错: {e}", exc_info=True)
            raise

    @classmethod
    def create_processor(cls, processor_name: str, config: Optional[Dict[str, Any]] = None) -> BaseProcessor:
        """
        创建处理器实例
        
        Args:
            processor_name: 处理器名称
            config: 配置字典（可选）
            
        Returns:
            处理器实例
            
        Raises:
            ValueError: 处理器未注册
        """
        # 检查处理器是否已注册
        if processor_name not in cls._processor_classes:
            registered = ", ".join(cls._processor_classes.keys())
            raise ValueError(f"处理器 {processor_name} 未注册。已注册的处理器: {registered}")
        
        # 获取处理器类并创建实例
        processor_cls = cls._processor_classes[processor_name]
        try:
            # 使用配置创建处理器实例
            processor = processor_cls(name=processor_name, config=config)
            logger.debug(f"已创建处理器实例: {processor_name}")
            return processor
        except Exception as e:
            logger.error(f"创建处理器 {processor_name} 实例时出错: {e}", exc_info=True)
            raise 