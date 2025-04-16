#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
林镜(LingJing) - 关系管理器
"""

import asyncio
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from ..utils.logger import get_logger
from ..config import async_get_config
from ..models.relationship_models import Relationship, Impression, Interaction

class RelationshipManager:
    """
    关系管理器，负责管理机器人与各实体之间的关系
    
    处理关系的建立、查询、更新和持久化等操作。
    """
    
    def __init__(self):
        """初始化关系管理器"""
        self.logger = get_logger('linjing.relationship.relationship_manager')
        self.config = None
        self.relationships = {}  # 关系字典，键为 (source_id, target_id)
        self.initialized = False
    
    async def initialize(self) -> None:
        """初始化关系管理器"""
        self.logger.info("初始化关系管理器...")
        
        # 导入配置
        self.config = await async_get_config()
        
        # 加载关系数据
        # 这里可以添加从数据库或文件加载已有关系的代码
        
        self.initialized = True
        self.logger.info("关系管理器初始化完成")
    
    async def get_relationship(self, source_id: str, target_id: str) -> Optional[Relationship]:
        """
        获取关系对象
        
        Args:
            source_id: 源实体ID
            target_id: 目标实体ID
            
        Returns:
            关系对象，如果不存在则返回None
        """
        if not self.initialized:
            await self.initialize()
            
        relationship_key = (source_id, target_id)
        
        # 如果关系不存在，创建一个新的关系
        if relationship_key not in self.relationships:
            relationship = Relationship(
                source_id=source_id,
                target_id=target_id,
                relationship_type="general"
            )
            self.relationships[relationship_key] = relationship
            self.logger.debug(f"创建新的关系: {source_id} -> {target_id}")
            
        return self.relationships.get(relationship_key)
    
    async def update_relationship(self, relationship: Relationship) -> bool:
        """
        更新关系
        
        Args:
            relationship: 关系对象
            
        Returns:
            bool: 是否成功更新
        """
        if not self.initialized:
            await self.initialize()
            
        relationship_key = (relationship.source_id, relationship.target_id)
        self.relationships[relationship_key] = relationship
        relationship.updated_at = datetime.now()
        
        # 这里可以添加持久化关系数据的代码
        
        self.logger.debug(f"更新关系: {relationship.source_id} -> {relationship.target_id}")
        return True
    
    async def add_interaction(self, source_id: str, target_id: str, 
                           interaction_type: str, content: str, 
                           sentiment: float = 0.0,
                           metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        添加互动记录
        
        Args:
            source_id: 源实体ID
            target_id: 目标实体ID
            interaction_type: 互动类型
            content: 互动内容
            sentiment: 情感值，-1.0到1.0
            metadata: 元数据
            
        Returns:
            bool: 是否成功添加
        """
        if not self.initialized:
            await self.initialize()
            
        relationship = await self.get_relationship(source_id, target_id)
        if not relationship:
            return False
        
        interaction = Interaction(
            timestamp=datetime.now(),
            interaction_type=interaction_type,
            sentiment=sentiment,
            content=content,
            metadata=metadata or {}
        )
        
        relationship.add_interaction(interaction)
        await self.update_relationship(relationship)
        
        self.logger.debug(f"添加互动记录: {source_id} -> {target_id}, 类型: {interaction_type}")
        return True
    
    async def get_all_relationships(self, source_id: Optional[str] = None) -> List[Relationship]:
        """
        获取所有关系
        
        Args:
            source_id: 源实体ID，如果提供则只返回该实体的关系
            
        Returns:
            关系列表
        """
        if not self.initialized:
            await self.initialize()
            
        if source_id:
            return [
                relationship for (src, _), relationship in self.relationships.items()
                if src == source_id
            ]
        else:
            return list(self.relationships.values())
    
    async def save_all_relationships(self) -> bool:
        """
        保存所有关系数据
        
        Returns:
            bool: 是否成功保存
        """
        if not self.initialized:
            await self.initialize()
            
        # 这里可以添加将关系数据保存到数据库或文件的代码
        
        self.logger.info(f"保存所有关系数据，共 {len(self.relationships)} 个关系")
        return True

# 单例实例
_relationship_manager = None

async def get_relationship_manager() -> RelationshipManager:
    """
    获取关系管理器单例实例
    
    Returns:
        RelationshipManager: 关系管理器实例
    """
    global _relationship_manager
    
    if _relationship_manager is None:
        _relationship_manager = RelationshipManager()
        await _relationship_manager.initialize()
    
    return _relationship_manager 