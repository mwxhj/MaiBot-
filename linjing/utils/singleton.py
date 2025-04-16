#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
林镜(LingJing) - 单例模式工具
"""

from typing import Any, Dict, Type, TypeVar

T = TypeVar('T')
_INSTANCES: Dict[Type, Any] = {}

def singleton(cls: Type[T]) -> Type[T]:
    """
    单例模式装饰器，确保一个类只有一个实例
    
    Args:
        cls: 需要实现单例模式的类
        
    Returns:
        装饰后的类，保证只有一个实例
    """
    def get_instance(*args, **kwargs) -> T:
        if cls not in _INSTANCES:
            _INSTANCES[cls] = cls(*args, **kwargs)
        return _INSTANCES[cls]
    
    # 创建一个新类，包装原始类
    class Singleton(cls):
        def __new__(cls, *args, **kwargs):
            return get_instance(*args, **kwargs)
        
        @classmethod
        def get_instance(cls, *args, **kwargs) -> T:
            """获取单例实例"""
            return get_instance(*args, **kwargs)
        
        @classmethod
        def clear_instance(cls):
            """清除单例实例（主要用于测试）"""
            if cls in _INSTANCES:
                del _INSTANCES[cls]
    
    Singleton.__name__ = cls.__name__
    Singleton.__qualname__ = cls.__qualname__
    Singleton.__module__ = cls.__module__
    
    return Singleton 