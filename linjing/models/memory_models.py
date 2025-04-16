#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
林镜(LingJing) - 记忆数据模型
"""

from typing import Dict, Any, List, Optional, Union, Set
from datetime import datetime
from dataclasses import dataclass, field
import json

from ..constants import MemoryType, MemoryPriority

@dataclass
class Memory:
    """记忆模型"""
    id: str
    content: str
    memory_type: str = MemoryType.EPISODIC
    priority: int = MemoryPriority.MEDIUM
    created_at: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)
    access_count: int = 0
    importance_score: float = 0.0
    relevance_score: float = 0.0
    emotion_tags: List[str] = field(default_factory=list)
    related_entities: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    vector: Optional[List[float]] = None
    source_ids: List[str] = field(default_factory=list)
    is_core_memory: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典
        
        Returns:
            记忆字典表示
        """
        return {
            'id': self.id,
            'content': self.content,
            'memory_type': self.memory_type,
            'priority': self.priority,
            'created_at': self.created_at.isoformat(),
            'last_accessed': self.last_accessed.isoformat(),
            'access_count': self.access_count,
            'importance_score': self.importance_score,
            'relevance_score': self.relevance_score,
            'emotion_tags': self.emotion_tags,
            'related_entities': self.related_entities,
            'metadata': self.metadata,
            'vector': self.vector,
            'source_ids': self.source_ids,
            'is_core_memory': self.is_core_memory,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Memory':
        """
        从字典创建记忆
        
        Args:
            data: 记忆字典数据
            
        Returns:
            记忆对象
        """
        memory = cls(
            id=data.get('id', ''),
            content=data.get('content', ''),
            memory_type=data.get('memory_type', MemoryType.EPISODIC),
            priority=data.get('priority', MemoryPriority.MEDIUM),
            access_count=data.get('access_count', 0),
            importance_score=data.get('importance_score', 0.0),
            relevance_score=data.get('relevance_score', 0.0),
            emotion_tags=data.get('emotion_tags', []),
            related_entities=data.get('related_entities', []),
            metadata=data.get('metadata', {}),
            vector=data.get('vector'),
            source_ids=data.get('source_ids', []),
            is_core_memory=data.get('is_core_memory', False),
        )
        
        # 解析日期时间
        created_at = data.get('created_at')
        if created_at:
            memory.created_at = datetime.fromisoformat(created_at)
        
        last_accessed = data.get('last_accessed')
        if last_accessed:
            memory.last_accessed = datetime.fromisoformat(last_accessed)
        
        return memory
    
    def serialize(self) -> str:
        """
        序列化为JSON字符串
        
        Returns:
            JSON字符串
        """
        return json.dumps(self.to_dict(), ensure_ascii=False)
    
    @classmethod
    def deserialize(cls, data: str) -> 'Memory':
        """
        从JSON字符串反序列化
        
        Args:
            data: JSON字符串
            
        Returns:
            记忆对象
        """
        return cls.from_dict(json.loads(data))
    
    def update_access(self) -> None:
        """更新访问信息"""
        self.last_accessed = datetime.now()
        self.access_count += 1
    
    def update_importance(self, score: float) -> None:
        """
        更新重要性评分
        
        Args:
            score: 重要性评分
        """
        self.importance_score = score
    
    def update_relevance(self, score: float) -> None:
        """
        更新相关性评分
        
        Args:
            score: 相关性评分
        """
        self.relevance_score = score
    
    def add_emotion_tag(self, tag: str) -> None:
        """
        添加情绪标签
        
        Args:
            tag: 情绪标签
        """
        if tag not in self.emotion_tags:
            self.emotion_tags.append(tag)
    
    def remove_emotion_tag(self, tag: str) -> None:
        """
        移除情绪标签
        
        Args:
            tag: 情绪标签
        """
        if tag in self.emotion_tags:
            self.emotion_tags.remove(tag)
    
    def add_related_entity(self, entity_type: str, entity_id: str, relationship: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        添加相关实体
        
        Args:
            entity_type: 实体类型
            entity_id: 实体ID
            relationship: 关系类型
            metadata: 元数据
        """
        entity = {
            'type': entity_type,
            'id': entity_id,
            'relationship': relationship
        }
        
        if metadata:
            entity['metadata'] = metadata
        
        # 检查是否已存在相同实体
        for existing in self.related_entities:
            if existing.get('type') == entity_type and existing.get('id') == entity_id:
                # 更新现有实体
                existing.update(entity)
                return
        
        # 添加新实体
        self.related_entities.append(entity)
    
    def remove_related_entity(self, entity_type: str, entity_id: str) -> None:
        """
        移除相关实体
        
        Args:
            entity_type: 实体类型
            entity_id: 实体ID
        """
        self.related_entities = [
            entity for entity in self.related_entities
            if not (entity.get('type') == entity_type and entity.get('id') == entity_id)
        ]
    
    def get_related_entities_by_type(self, entity_type: str) -> List[Dict[str, Any]]:
        """
        获取指定类型的相关实体
        
        Args:
            entity_type: 实体类型
            
        Returns:
            相关实体列表
        """
        return [
            entity for entity in self.related_entities
            if entity.get('type') == entity_type
        ]
    
    def get_metadata(self, key: str, default: Any = None) -> Any:
        """
        获取元数据
        
        Args:
            key: 键
            default: 默认值
            
        Returns:
            元数据值
        """
        return self.metadata.get(key, default)
    
    def set_metadata(self, key: str, value: Any) -> None:
        """
        设置元数据
        
        Args:
            key: 键
            value: 值
        """
        self.metadata[key] = value
    
    def remove_metadata(self, key: str) -> None:
        """
        移除元数据
        
        Args:
            key: 键
        """
        if key in self.metadata:
            del self.metadata[key]
    
    def set_as_core_memory(self, is_core: bool = True) -> None:
        """
        设置为核心记忆
        
        Args:
            is_core: 是否为核心记忆
        """
        self.is_core_memory = is_core
    
    def add_source(self, source_id: str) -> None:
        """
        添加源记忆ID
        
        Args:
            source_id: 源记忆ID
        """
        if source_id not in self.source_ids:
            self.source_ids.append(source_id)
    
    def remove_source(self, source_id: str) -> None:
        """
        移除源记忆ID
        
        Args:
            source_id: 源记忆ID
        """
        if source_id in self.source_ids:
            self.source_ids.remove(source_id)
    
    def calculate_decay_score(self, current_time: Optional[datetime] = None, base_decay_rate: float = 0.1) -> float:
        """
        计算记忆衰减评分
        
        Args:
            current_time: 当前时间，如果为None则使用当前时间
            base_decay_rate: 基础衰减率
            
        Returns:
            衰减后的评分（0-1之间，0表示完全衰减，1表示无衰减）
        """
        if current_time is None:
            current_time = datetime.now()
        
        # 计算时间差（天）
        days_since_access = (current_time - self.last_accessed).total_seconds() / (24 * 3600)
        
        # 应用基于优先级的衰减率
        decay_rate = base_decay_rate / (self.priority + 1)
        
        # 计算衰减评分（指数衰减）
        decay_score = 1.0 * (1.0 - decay_rate) ** days_since_access
        
        # 考虑访问频率的影响
        frequency_boost = min(0.2, 0.01 * self.access_count)
        
        # 考虑重要性评分的影响
        importance_boost = 0.3 * self.importance_score
        
        # 核心记忆额外加成
        core_boost = 0.3 if self.is_core_memory else 0.0
        
        # 合并所有因素
        final_score = min(1.0, decay_score + frequency_boost + importance_boost + core_boost)
        
        return final_score 
# -*- coding: utf-8 -*-

"""
林镜(LingJing) - 记忆数据模型
"""



@dataclass
class Memory:
    """记忆模型"""
    id: str
    content: str
    memory_type: str = MemoryType.EPISODIC
    priority: int = MemoryPriority.MEDIUM
    created_at: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)
    access_count: int = 0
    importance_score: float = 0.0
    relevance_score: float = 0.0
    emotion_tags: List[str] = field(default_factory=list)
    related_entities: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    vector: Optional[List[float]] = None
    source_ids: List[str] = field(default_factory=list)
    is_core_memory: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典
        
        Returns:
            记忆字典表示
        """
        return {
            'id': self.id,
            'content': self.content,
            'memory_type': self.memory_type,
            'priority': self.priority,
            'created_at': self.created_at.isoformat(),
            'last_accessed': self.last_accessed.isoformat(),
            'access_count': self.access_count,
            'importance_score': self.importance_score,
            'relevance_score': self.relevance_score,
            'emotion_tags': self.emotion_tags,
            'related_entities': self.related_entities,
            'metadata': self.metadata,
            'vector': self.vector,
            'source_ids': self.source_ids,
            'is_core_memory': self.is_core_memory,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Memory':
        """
        从字典创建记忆
        
        Args:
            data: 记忆字典数据
            
        Returns:
            记忆对象
        """
        memory = cls(
            id=data.get('id', ''),
            content=data.get('content', ''),
            memory_type=data.get('memory_type', MemoryType.EPISODIC),
            priority=data.get('priority', MemoryPriority.MEDIUM),
            access_count=data.get('access_count', 0),
            importance_score=data.get('importance_score', 0.0),
            relevance_score=data.get('relevance_score', 0.0),
            emotion_tags=data.get('emotion_tags', []),
            related_entities=data.get('related_entities', []),
            metadata=data.get('metadata', {}),
            vector=data.get('vector'),
            source_ids=data.get('source_ids', []),
            is_core_memory=data.get('is_core_memory', False),
        )
        
        # 解析日期时间
        created_at = data.get('created_at')
        if created_at:
            memory.created_at = datetime.fromisoformat(created_at)
        
        last_accessed = data.get('last_accessed')
        if last_accessed:
            memory.last_accessed = datetime.fromisoformat(last_accessed)
        
        return memory
    
    def serialize(self) -> str:
        """
        序列化为JSON字符串
        
        Returns:
            JSON字符串
        """
        return json.dumps(self.to_dict(), ensure_ascii=False)
    
    @classmethod
    def deserialize(cls, data: str) -> 'Memory':
        """
        从JSON字符串反序列化
        
        Args:
            data: JSON字符串
            
        Returns:
            记忆对象
        """
        return cls.from_dict(json.loads(data))
    
    def update_access(self) -> None:
        """更新访问信息"""
        self.last_accessed = datetime.now()
        self.access_count += 1
    
    def update_importance(self, score: float) -> None:
        """
        更新重要性评分
        
        Args:
            score: 重要性评分
        """
        self.importance_score = score
    
    def update_relevance(self, score: float) -> None:
        """
        更新相关性评分
        
        Args:
            score: 相关性评分
        """
        self.relevance_score = score
    
    def add_emotion_tag(self, tag: str) -> None:
        """
        添加情绪标签
        
        Args:
            tag: 情绪标签
        """
        if tag not in self.emotion_tags:
            self.emotion_tags.append(tag)
    
    def remove_emotion_tag(self, tag: str) -> None:
        """
        移除情绪标签
        
        Args:
            tag: 情绪标签
        """
        if tag in self.emotion_tags:
            self.emotion_tags.remove(tag)
    
    def add_related_entity(self, entity_type: str, entity_id: str, relationship: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        添加相关实体
        
        Args:
            entity_type: 实体类型
            entity_id: 实体ID
            relationship: 关系类型
            metadata: 元数据
        """
        entity = {
            'type': entity_type,
            'id': entity_id,
            'relationship': relationship
        }
        
        if metadata:
            entity['metadata'] = metadata
        
        # 检查是否已存在相同实体
        for existing in self.related_entities:
            if existing.get('type') == entity_type and existing.get('id') == entity_id:
                # 更新现有实体
                existing.update(entity)
                return
        
        # 添加新实体
        self.related_entities.append(entity)
    
    def remove_related_entity(self, entity_type: str, entity_id: str) -> None:
        """
        移除相关实体
        
        Args:
            entity_type: 实体类型
            entity_id: 实体ID
        """
        self.related_entities = [
            entity for entity in self.related_entities
            if not (entity.get('type') == entity_type and entity.get('id') == entity_id)
        ]
    
    def get_related_entities_by_type(self, entity_type: str) -> List[Dict[str, Any]]:
        """
        获取指定类型的相关实体
        
        Args:
            entity_type: 实体类型
            
        Returns:
            相关实体列表
        """
        return [
            entity for entity in self.related_entities
            if entity.get('type') == entity_type
        ]
    
    def get_metadata(self, key: str, default: Any = None) -> Any:
        """
        获取元数据
        
        Args:
            key: 键
            default: 默认值
            
        Returns:
            元数据值
        """
        return self.metadata.get(key, default)
    
    def set_metadata(self, key: str, value: Any) -> None:
        """
        设置元数据
        
        Args:
            key: 键
            value: 值
        """
        self.metadata[key] = value
    
    def remove_metadata(self, key: str) -> None:
        """
        移除元数据
        
        Args:
            key: 键
        """
        if key in self.metadata:
            del self.metadata[key]
    
    def set_as_core_memory(self, is_core: bool = True) -> None:
        """
        设置为核心记忆
        
        Args:
            is_core: 是否为核心记忆
        """
        self.is_core_memory = is_core
    
    def add_source(self, source_id: str) -> None:
        """
        添加源记忆ID
        
        Args:
            source_id: 源记忆ID
        """
        if source_id not in self.source_ids:
            self.source_ids.append(source_id)
    
    def remove_source(self, source_id: str) -> None:
        """
        移除源记忆ID
        
        Args:
            source_id: 源记忆ID
        """
        if source_id in self.source_ids:
            self.source_ids.remove(source_id)
    
    def calculate_decay_score(self, current_time: Optional[datetime] = None, base_decay_rate: float = 0.1) -> float:
        """
        计算记忆衰减评分
        
        Args:
            current_time: 当前时间，如果为None则使用当前时间
            base_decay_rate: 基础衰减率
            
        Returns:
            衰减后的评分（0-1之间，0表示完全衰减，1表示无衰减）
        """
        if current_time is None:
            current_time = datetime.now()
        
        # 计算时间差（天）
        days_since_access = (current_time - self.last_accessed).total_seconds() / (24 * 3600)
        
        # 应用基于优先级的衰减率
        decay_rate = base_decay_rate / (self.priority + 1)
        
        # 计算衰减评分（指数衰减）
        decay_score = 1.0 * (1.0 - decay_rate) ** days_since_access
        
        # 考虑访问频率的影响
        frequency_boost = min(0.2, 0.01 * self.access_count)
        
        # 考虑重要性评分的影响
        importance_boost = 0.3 * self.importance_score
        
        # 核心记忆额外加成
        core_boost = 0.3 if self.is_core_memory else 0.0
        
        # 合并所有因素
        final_score = min(1.0, decay_score + frequency_boost + importance_boost + core_boost)
        
        return final_score 