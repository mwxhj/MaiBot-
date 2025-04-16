#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
林镜(LingJing) - 关系数据模型
"""

from typing import Dict, Any, List, Optional, Set
from datetime import datetime
from dataclasses import dataclass, field
import json

@dataclass
class Impression:
    """印象类，表示一方对另一方的印象"""
    familiarity: float = 0.0  # 熟悉度，0-1
    trust: float = 0.0  # 信任度，0-1
    likability: float = 0.0  # 好感度，0-1
    respect: float = 0.0  # 尊重度，0-1
    last_updated: datetime = field(default_factory=datetime.now)
    tags: List[str] = field(default_factory=list)  # 印象标签
    notes: List[str] = field(default_factory=list)  # 印象笔记
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'familiarity': self.familiarity,
            'trust': self.trust,
            'likability': self.likability,
            'respect': self.respect,
            'last_updated': self.last_updated.isoformat(),
            'tags': self.tags,
            'notes': self.notes,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Impression':
        """从字典创建印象"""
        impression = cls(
            familiarity=data.get('familiarity', 0.0),
            trust=data.get('trust', 0.0),
            likability=data.get('likability', 0.0),
            respect=data.get('respect', 0.0),
            tags=data.get('tags', []),
            notes=data.get('notes', []),
        )
        
        # 解析时间戳
        last_updated = data.get('last_updated')
        if last_updated:
            impression.last_updated = datetime.fromisoformat(last_updated)
        
        return impression
    
    def update(self, field: str, value: float) -> None:
        """
        更新印象字段
        
        Args:
            field: 字段名
            value: 值
        """
        if field == 'familiarity':
            self.familiarity = max(0.0, min(1.0, value))
        elif field == 'trust':
            self.trust = max(0.0, min(1.0, value))
        elif field == 'likability':
            self.likability = max(0.0, min(1.0, value))
        elif field == 'respect':
            self.respect = max(0.0, min(1.0, value))
        
        self.last_updated = datetime.now()
    
    def add_tag(self, tag: str) -> None:
        """
        添加标签
        
        Args:
            tag: 标签
        """
        if tag not in self.tags:
            self.tags.append(tag)
            self.last_updated = datetime.now()
    
    def remove_tag(self, tag: str) -> None:
        """
        移除标签
        
        Args:
            tag: 标签
        """
        if tag in self.tags:
            self.tags.remove(tag)
            self.last_updated = datetime.now()
    
    def add_note(self, note: str) -> None:
        """
        添加笔记
        
        Args:
            note: 笔记
        """
        self.notes.append(note)
        self.last_updated = datetime.now()

@dataclass
class Interaction:
    """互动记录"""
    timestamp: datetime = field(default_factory=datetime.now)
    interaction_type: str = ""  # 互动类型
    sentiment: float = 0.0  # 情感值，-1.0到1.0
    content: str = ""  # 互动内容
    metadata: Dict[str, Any] = field(default_factory=dict)  # 元数据
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'timestamp': self.timestamp.isoformat(),
            'interaction_type': self.interaction_type,
            'sentiment': self.sentiment,
            'content': self.content,
            'metadata': self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Interaction':
        """从字典创建互动记录"""
        interaction = cls(
            interaction_type=data.get('interaction_type', ''),
            sentiment=data.get('sentiment', 0.0),
            content=data.get('content', ''),
            metadata=data.get('metadata', {}),
        )
        
        # 解析时间戳
        timestamp = data.get('timestamp')
        if timestamp:
            interaction.timestamp = datetime.fromisoformat(timestamp)
        
        return interaction

@dataclass
class Relationship:
    """关系模型"""
    source_id: str  # 源实体ID
    target_id: str  # 目标实体ID
    relationship_type: str  # 关系类型
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    impression: Impression = field(default_factory=Impression)  # 印象
    interactions: List[Interaction] = field(default_factory=list)  # 互动记录
    metadata: Dict[str, Any] = field(default_factory=dict)  # 元数据
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'source_id': self.source_id,
            'target_id': self.target_id,
            'relationship_type': self.relationship_type,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'impression': self.impression.to_dict(),
            'interactions': [interaction.to_dict() for interaction in self.interactions],
            'metadata': self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Relationship':
        """从字典创建关系"""
        relationship = cls(
            source_id=data.get('source_id', ''),
            target_id=data.get('target_id', ''),
            relationship_type=data.get('relationship_type', ''),
            impression=Impression.from_dict(data.get('impression', {})),
            metadata=data.get('metadata', {}),
        )
        
        # 解析时间戳
        created_at = data.get('created_at')
        if created_at:
            relationship.created_at = datetime.fromisoformat(created_at)
        
        updated_at = data.get('updated_at')
        if updated_at:
            relationship.updated_at = datetime.fromisoformat(updated_at)
        
        # 解析互动记录
        interactions = data.get('interactions', [])
        relationship.interactions = [Interaction.from_dict(interaction) for interaction in interactions]
        
        return relationship
    
    def serialize(self) -> str:
        """
        序列化为JSON字符串
        
        Returns:
            JSON字符串
        """
        return json.dumps(self.to_dict(), ensure_ascii=False)
    
    @classmethod
    def deserialize(cls, data: str) -> 'Relationship':
        """
        从JSON字符串反序列化
        
        Args:
            data: JSON字符串
            
        Returns:
            关系对象
        """
        return cls.from_dict(json.loads(data))
    
    def add_interaction(self, interaction: Interaction) -> None:
        """
        添加互动记录
        
        Args:
            interaction: 互动记录
        """
        self.interactions.append(interaction)
        self.updated_at = datetime.now()
        
        # 更新印象
        # 根据互动类型和情感值，可以调整印象中的不同维度
        sentiment = interaction.sentiment
        
        # 根据互动类型更新不同的印象维度
        if interaction.interaction_type == 'chat':
            # 聊天增加熟悉度
            self.impression.familiarity = min(1.0, self.impression.familiarity + 0.02)
            # 根据情感值调整好感度
            sentiment_adjustment = sentiment * 0.05
            self.impression.likability = max(0.0, min(1.0, self.impression.likability + sentiment_adjustment))
        
        elif interaction.interaction_type == 'help':
            # 帮助增加信任度和好感度
            self.impression.trust = min(1.0, self.impression.trust + 0.05)
            self.impression.likability = min(1.0, self.impression.likability + 0.03)
        
        elif interaction.interaction_type == 'conflict':
            # 冲突减少好感度，可能减少信任度
            self.impression.likability = max(0.0, self.impression.likability - 0.05)
            if sentiment < -0.5:
                self.impression.trust = max(0.0, self.impression.trust - 0.03)
        
        # 更新印象最后更新时间
        self.impression.last_updated = datetime.now()
    
    def get_recent_interactions(self, limit: int = 5) -> List[Interaction]:
        """
        获取最近的互动记录
        
        Args:
            limit: 返回的最大记录数
            
        Returns:
            互动记录列表
        """
        return sorted(
            self.interactions,
            key=lambda interaction: interaction.timestamp,
            reverse=True
        )[:limit]
    
    def calculate_relationship_strength(self) -> float:
        """
        计算关系强度
        
        Returns:
            关系强度，0.0-1.0
        """
        # 关系强度由印象的各个维度加权组成
        weights = {
            'familiarity': 0.3,
            'trust': 0.3,
            'likability': 0.3,
            'respect': 0.1
        }
        
        strength = (
            weights['familiarity'] * self.impression.familiarity +
            weights['trust'] * self.impression.trust +
            weights['likability'] * self.impression.likability +
            weights['respect'] * self.impression.respect
        )
        
        return min(1.0, max(0.0, strength))
    
    def get_relationship_description(self) -> str:
        """
        获取关系描述
        
        Returns:
            关系描述文本
        """
        strength = self.calculate_relationship_strength()
        
        if strength < 0.2:
            if self.impression.likability < 0.2:
                return "陌生且疏远"
            return "陌生"
        
        elif strength < 0.4:
            if self.impression.likability > 0.6:
                return "有好感的泛泛之交"
            elif self.impression.likability < 0.3:
                return "不太友好的泛泛之交"
            return "泛泛之交"
        
        elif strength < 0.6:
            if self.impression.trust > 0.6:
                return "值得信赖的朋友"
            if self.impression.likability > 0.7:
                return "友好的朋友"
            return "朋友"
        
        elif strength < 0.8:
            if self.impression.trust > 0.8:
                return "密友"
            return "好朋友"
        
        else:
            if self.impression.trust > 0.9 and self.impression.likability > 0.9:
                return "挚友"
            return "亲密朋友"
    
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
        self.updated_at = datetime.now()
    
    def remove_metadata(self, key: str) -> None:
        """
        移除元数据
        
        Args:
            key: 键
        """
        if key in self.metadata:
            del self.metadata[key]
            self.updated_at = datetime.now() 
# -*- coding: utf-8 -*-

"""
林镜(LingJing) - 关系数据模型
"""


@dataclass
class Impression:
    """印象类，表示一方对另一方的印象"""
    familiarity: float = 0.0  # 熟悉度，0-1
    trust: float = 0.0  # 信任度，0-1
    likability: float = 0.0  # 好感度，0-1
    respect: float = 0.0  # 尊重度，0-1
    last_updated: datetime = field(default_factory=datetime.now)
    tags: List[str] = field(default_factory=list)  # 印象标签
    notes: List[str] = field(default_factory=list)  # 印象笔记
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'familiarity': self.familiarity,
            'trust': self.trust,
            'likability': self.likability,
            'respect': self.respect,
            'last_updated': self.last_updated.isoformat(),
            'tags': self.tags,
            'notes': self.notes,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Impression':
        """从字典创建印象"""
        impression = cls(
            familiarity=data.get('familiarity', 0.0),
            trust=data.get('trust', 0.0),
            likability=data.get('likability', 0.0),
            respect=data.get('respect', 0.0),
            tags=data.get('tags', []),
            notes=data.get('notes', []),
        )
        
        # 解析时间戳
        last_updated = data.get('last_updated')
        if last_updated:
            impression.last_updated = datetime.fromisoformat(last_updated)
        
        return impression
    
    def update(self, field: str, value: float) -> None:
        """
        更新印象字段
        
        Args:
            field: 字段名
            value: 值
        """
        if field == 'familiarity':
            self.familiarity = max(0.0, min(1.0, value))
        elif field == 'trust':
            self.trust = max(0.0, min(1.0, value))
        elif field == 'likability':
            self.likability = max(0.0, min(1.0, value))
        elif field == 'respect':
            self.respect = max(0.0, min(1.0, value))
        
        self.last_updated = datetime.now()
    
    def add_tag(self, tag: str) -> None:
        """
        添加标签
        
        Args:
            tag: 标签
        """
        if tag not in self.tags:
            self.tags.append(tag)
            self.last_updated = datetime.now()
    
    def remove_tag(self, tag: str) -> None:
        """
        移除标签
        
        Args:
            tag: 标签
        """
        if tag in self.tags:
            self.tags.remove(tag)
            self.last_updated = datetime.now()
    
    def add_note(self, note: str) -> None:
        """
        添加笔记
        
        Args:
            note: 笔记
        """
        self.notes.append(note)
        self.last_updated = datetime.now()

@dataclass
class Interaction:
    """互动记录"""
    timestamp: datetime = field(default_factory=datetime.now)
    interaction_type: str = ""  # 互动类型
    sentiment: float = 0.0  # 情感值，-1.0到1.0
    content: str = ""  # 互动内容
    metadata: Dict[str, Any] = field(default_factory=dict)  # 元数据
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'timestamp': self.timestamp.isoformat(),
            'interaction_type': self.interaction_type,
            'sentiment': self.sentiment,
            'content': self.content,
            'metadata': self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Interaction':
        """从字典创建互动记录"""
        interaction = cls(
            interaction_type=data.get('interaction_type', ''),
            sentiment=data.get('sentiment', 0.0),
            content=data.get('content', ''),
            metadata=data.get('metadata', {}),
        )
        
        # 解析时间戳
        timestamp = data.get('timestamp')
        if timestamp:
            interaction.timestamp = datetime.fromisoformat(timestamp)
        
        return interaction

@dataclass
class Relationship:
    """关系模型"""
    source_id: str  # 源实体ID
    target_id: str  # 目标实体ID
    relationship_type: str  # 关系类型
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    impression: Impression = field(default_factory=Impression)  # 印象
    interactions: List[Interaction] = field(default_factory=list)  # 互动记录
    metadata: Dict[str, Any] = field(default_factory=dict)  # 元数据
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'source_id': self.source_id,
            'target_id': self.target_id,
            'relationship_type': self.relationship_type,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'impression': self.impression.to_dict(),
            'interactions': [interaction.to_dict() for interaction in self.interactions],
            'metadata': self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Relationship':
        """从字典创建关系"""
        relationship = cls(
            source_id=data.get('source_id', ''),
            target_id=data.get('target_id', ''),
            relationship_type=data.get('relationship_type', ''),
            impression=Impression.from_dict(data.get('impression', {})),
            metadata=data.get('metadata', {}),
        )
        
        # 解析时间戳
        created_at = data.get('created_at')
        if created_at:
            relationship.created_at = datetime.fromisoformat(created_at)
        
        updated_at = data.get('updated_at')
        if updated_at:
            relationship.updated_at = datetime.fromisoformat(updated_at)
        
        # 解析互动记录
        interactions = data.get('interactions', [])
        relationship.interactions = [Interaction.from_dict(interaction) for interaction in interactions]
        
        return relationship
    
    def serialize(self) -> str:
        """
        序列化为JSON字符串
        
        Returns:
            JSON字符串
        """
        return json.dumps(self.to_dict(), ensure_ascii=False)
    
    @classmethod
    def deserialize(cls, data: str) -> 'Relationship':
        """
        从JSON字符串反序列化
        
        Args:
            data: JSON字符串
            
        Returns:
            关系对象
        """
        return cls.from_dict(json.loads(data))
    
    def add_interaction(self, interaction: Interaction) -> None:
        """
        添加互动记录
        
        Args:
            interaction: 互动记录
        """
        self.interactions.append(interaction)
        self.updated_at = datetime.now()
        
        # 更新印象
        # 根据互动类型和情感值，可以调整印象中的不同维度
        sentiment = interaction.sentiment
        
        # 根据互动类型更新不同的印象维度
        if interaction.interaction_type == 'chat':
            # 聊天增加熟悉度
            self.impression.familiarity = min(1.0, self.impression.familiarity + 0.02)
            # 根据情感值调整好感度
            sentiment_adjustment = sentiment * 0.05
            self.impression.likability = max(0.0, min(1.0, self.impression.likability + sentiment_adjustment))
        
        elif interaction.interaction_type == 'help':
            # 帮助增加信任度和好感度
            self.impression.trust = min(1.0, self.impression.trust + 0.05)
            self.impression.likability = min(1.0, self.impression.likability + 0.03)
        
        elif interaction.interaction_type == 'conflict':
            # 冲突减少好感度，可能减少信任度
            self.impression.likability = max(0.0, self.impression.likability - 0.05)
            if sentiment < -0.5:
                self.impression.trust = max(0.0, self.impression.trust - 0.03)
        
        # 更新印象最后更新时间
        self.impression.last_updated = datetime.now()
    
    def get_recent_interactions(self, limit: int = 5) -> List[Interaction]:
        """
        获取最近的互动记录
        
        Args:
            limit: 返回的最大记录数
            
        Returns:
            互动记录列表
        """
        return sorted(
            self.interactions,
            key=lambda interaction: interaction.timestamp,
            reverse=True
        )[:limit]
    
    def calculate_relationship_strength(self) -> float:
        """
        计算关系强度
        
        Returns:
            关系强度，0.0-1.0
        """
        # 关系强度由印象的各个维度加权组成
        weights = {
            'familiarity': 0.3,
            'trust': 0.3,
            'likability': 0.3,
            'respect': 0.1
        }
        
        strength = (
            weights['familiarity'] * self.impression.familiarity +
            weights['trust'] * self.impression.trust +
            weights['likability'] * self.impression.likability +
            weights['respect'] * self.impression.respect
        )
        
        return min(1.0, max(0.0, strength))
    
    def get_relationship_description(self) -> str:
        """
        获取关系描述
        
        Returns:
            关系描述文本
        """
        strength = self.calculate_relationship_strength()
        
        if strength < 0.2:
            if self.impression.likability < 0.2:
                return "陌生且疏远"
            return "陌生"
        
        elif strength < 0.4:
            if self.impression.likability > 0.6:
                return "有好感的泛泛之交"
            elif self.impression.likability < 0.3:
                return "不太友好的泛泛之交"
            return "泛泛之交"
        
        elif strength < 0.6:
            if self.impression.trust > 0.6:
                return "值得信赖的朋友"
            if self.impression.likability > 0.7:
                return "友好的朋友"
            return "朋友"
        
        elif strength < 0.8:
            if self.impression.trust > 0.8:
                return "密友"
            return "好朋友"
        
        else:
            if self.impression.trust > 0.9 and self.impression.likability > 0.9:
                return "挚友"
            return "亲密朋友"
    
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
        self.updated_at = datetime.now()
    
    def remove_metadata(self, key: str) -> None:
        """
        移除元数据
        
        Args:
            key: 键
        """
        if key in self.metadata:
            del self.metadata[key]
            self.updated_at = datetime.now() 