#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
向量数据库管理器工厂模块。

提供创建和管理向量数据库实例的接口，专注于增强版VectorDBManagerEnhanced实现，
提供连接池、重试和更多高级功能。
"""

import logging
import os
from typing import Dict, Any, Optional

# 导入增强版向量数据库管理器实现
from linjing.storage.vector_db_enhanced import VectorDBManagerEnhanced

logger = logging.getLogger(__name__)

class VectorDBManagerFactory:
    """
    向量数据库管理器工厂类
    
    负责创建、缓存和管理向量数据库管理器实例。
    """
    
    # 缓存已创建的实例，按配置哈希存储
    _instances: Dict[str, VectorDBManagerEnhanced] = {}
    
    @classmethod
    def create(cls, config: Dict[str, Any]) -> VectorDBManagerEnhanced:
        """
        创建或获取向量数据库管理器实例
        
        Args:
            config: 数据库配置字典
            
        Returns:
            向量数据库管理器实例
        """
        # 创建缓存键
        cache_key = cls._get_cache_key(config)
        
        # 检查是否已存在实例
        if cache_key in cls._instances:
            logger.debug(f"复用已有向量数据库实例: {cache_key}")
            return cls._instances[cache_key]
        
        # 创建新实例
        logger.info("创建新的向量数据库实例")
        instance = VectorDBManagerEnhanced(config)
        
        # 缓存实例
        cls._instances[cache_key] = instance
        return instance
    
    @classmethod
    def _get_cache_key(cls, config: Dict[str, Any]) -> str:
        """
        生成缓存键
        
        Args:
            config: 配置字典
            
        Returns:
            缓存键字符串
        """
        # 排序配置项以确保相同配置生成相同的键
        config_str = str(sorted([(k, v) for k, v in config.items()]))
        return f"enhanced:{config_str}" 