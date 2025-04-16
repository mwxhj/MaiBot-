#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
林镜(LingJing) - 情绪数据模型
"""

from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, field
import json
import math

from ..constants import EmotionType, EmotionFactor

@dataclass
class EmotionState:
    """情绪状态"""
    # 基础情绪维度，范围为0.0-1.0
    happy: float = 0.5
    sad: float = 0.0
    angry: float = 0.0
    afraid: float = 0.0
    surprised: float = 0.0
    disgusted: float = 0.0
    
    def to_dict(self) -> Dict[str, float]:
        """
        转换为字典
        
        Returns:
            情绪状态字典
        """
        return {
            'happy': self.happy,
            'sad': self.sad,
            'angry': self.angry,
            'afraid': self.afraid,
            'surprised': self.surprised,
            'disgusted': self.disgusted,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, float]) -> 'EmotionState':
        """
        从字典创建情绪状态
        
        Args:
            data: 情绪状态字典
            
        Returns:
            情绪状态对象
        """
        return cls(
            happy=data.get('happy', 0.5),
            sad=data.get('sad', 0.0),
            angry=data.get('angry', 0.0),
            afraid=data.get('afraid', 0.0),
            surprised=data.get('surprised', 0.0),
            disgusted=data.get('disgusted', 0.0),
        )
    
    def get_dominant_emotion(self) -> Tuple[str, float]:
        """
        获取主导情绪
        
        Returns:
            (情绪类型, 情绪强度)
        """
        emotions = {
            EmotionType.HAPPY: self.happy,
            EmotionType.SAD: self.sad,
            EmotionType.ANGRY: self.angry,
            EmotionType.AFRAID: self.afraid,
            EmotionType.SURPRISED: self.surprised,
            EmotionType.DISGUSTED: self.disgusted,
        }
        
        # 找出最大值
        dominant_emotion = max(emotions.items(), key=lambda x: x[1])
        
        # 如果最大情绪值低于阈值，返回中性
        if dominant_emotion[1] < 0.3:
            return (EmotionType.NEUTRAL, 0.0)
        
        return dominant_emotion
    
    def get_emotion_vector(self) -> List[float]:
        """
        获取情绪向量
        
        Returns:
            情绪向量
        """
        return [
            self.happy,
            self.sad,
            self.angry,
            self.afraid,
            self.surprised,
            self.disgusted,
        ]
    
    def apply_change(self, emotion_type: str, value: float) -> None:
        """
        应用情绪变化
        
        Args:
            emotion_type: 情绪类型
            value: 变化值（可正可负）
        """
        if emotion_type == EmotionType.HAPPY:
            self.happy = max(0.0, min(1.0, self.happy + value))
        elif emotion_type == EmotionType.SAD:
            self.sad = max(0.0, min(1.0, self.sad + value))
        elif emotion_type == EmotionType.ANGRY:
            self.angry = max(0.0, min(1.0, self.angry + value))
        elif emotion_type == EmotionType.AFRAID:
            self.afraid = max(0.0, min(1.0, self.afraid + value))
        elif emotion_type == EmotionType.SURPRISED:
            self.surprised = max(0.0, min(1.0, self.surprised + value))
        elif emotion_type == EmotionType.DISGUSTED:
            self.disgusted = max(0.0, min(1.0, self.disgusted + value))
    
    def normalize(self) -> None:
        """归一化情绪状态，确保所有情绪维度的总和不超过一定阈值"""
        total = (self.happy + self.sad + self.angry + 
                self.afraid + self.surprised + self.disgusted)
        
        # 如果总和超过2.0，则进行归一化
        if total > 2.0:
            factor = 2.0 / total
            self.happy *= factor
            self.sad *= factor
            self.angry *= factor
            self.afraid *= factor
            self.surprised *= factor
            self.disgusted *= factor
    
    def reset_to_neutral(self) -> None:
        """重置为中性情绪状态"""
        self.happy = 0.5
        self.sad = 0.0
        self.angry = 0.0
        self.afraid = 0.0
        self.surprised = 0.0
        self.disgusted = 0.0

@dataclass
class EmotionTrigger:
    """情绪触发事件"""
    trigger_type: str
    timestamp: datetime = field(default_factory=datetime.now)
    source_id: Optional[str] = None
    source_type: Optional[str] = None
    intensity: float = 0.5
    affected_emotions: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典
        
        Returns:
            情绪触发事件字典
        """
        return {
            'trigger_type': self.trigger_type,
            'timestamp': self.timestamp.isoformat(),
            'source_id': self.source_id,
            'source_type': self.source_type,
            'intensity': self.intensity,
            'affected_emotions': self.affected_emotions,
            'metadata': self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EmotionTrigger':
        """
        从字典创建情绪触发事件
        
        Args:
            data: 情绪触发事件字典
            
        Returns:
            情绪触发事件对象
        """
        trigger = cls(
            trigger_type=data.get('trigger_type', ''),
            source_id=data.get('source_id'),
            source_type=data.get('source_type'),
            intensity=data.get('intensity', 0.5),
            affected_emotions=data.get('affected_emotions', {}),
            metadata=data.get('metadata', {}),
        )
        
        # 解析时间戳
        timestamp = data.get('timestamp')
        if timestamp:
            trigger.timestamp = datetime.fromisoformat(timestamp)
        
        return trigger

@dataclass
class Emotion:
    """情绪模型"""
    id: str
    state: EmotionState = field(default_factory=EmotionState)
    context_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    triggers: List[EmotionTrigger] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典
        
        Returns:
            情绪字典
        """
        return {
            'id': self.id,
            'state': self.state.to_dict(),
            'context_id': self.context_id,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'triggers': [trigger.to_dict() for trigger in self.triggers],
            'metadata': self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Emotion':
        """
        从字典创建情绪
        
        Args:
            data: 情绪字典
            
        Returns:
            情绪对象
        """
        emotion = cls(
            id=data.get('id', ''),
            state=EmotionState.from_dict(data.get('state', {})),
            context_id=data.get('context_id'),
            metadata=data.get('metadata', {}),
        )
        
        # 解析时间戳
        created_at = data.get('created_at')
        if created_at:
            emotion.created_at = datetime.fromisoformat(created_at)
        
        updated_at = data.get('updated_at')
        if updated_at:
            emotion.updated_at = datetime.fromisoformat(updated_at)
        
        # 解析触发事件
        triggers = data.get('triggers', [])
        emotion.triggers = [EmotionTrigger.from_dict(trigger) for trigger in triggers]
        
        return emotion
    
    def serialize(self) -> str:
        """
        序列化为JSON字符串
        
        Returns:
            JSON字符串
        """
        return json.dumps(self.to_dict(), ensure_ascii=False)
    
    @classmethod
    def deserialize(cls, data: str) -> 'Emotion':
        """
        从JSON字符串反序列化
        
        Args:
            data: JSON字符串
            
        Returns:
            情绪对象
        """
        return cls.from_dict(json.loads(data))
    
    def add_trigger(self, trigger: EmotionTrigger) -> None:
        """
        添加情绪触发事件
        
        Args:
            trigger: 情绪触发事件
        """
        self.triggers.append(trigger)
        self.updated_at = datetime.now()
        
        # 应用情绪变化
        for emotion_type, value in trigger.affected_emotions.items():
            adjusted_value = value * trigger.intensity
            self.state.apply_change(emotion_type, adjusted_value)
        
        # 归一化情绪状态
        self.state.normalize()
    
    def get_dominant_emotion(self) -> Tuple[str, float]:
        """
        获取主导情绪
        
        Returns:
            (情绪类型, 情绪强度)
        """
        return self.state.get_dominant_emotion()
    
    def get_emotion_level(self, emotion_type: str) -> float:
        """
        获取特定情绪的水平
        
        Args:
            emotion_type: 情绪类型
            
        Returns:
            情绪水平
        """
        if emotion_type == EmotionType.HAPPY:
            return self.state.happy
        elif emotion_type == EmotionType.SAD:
            return self.state.sad
        elif emotion_type == EmotionType.ANGRY:
            return self.state.angry
        elif emotion_type == EmotionType.AFRAID:
            return self.state.afraid
        elif emotion_type == EmotionType.SURPRISED:
            return self.state.surprised
        elif emotion_type == EmotionType.DISGUSTED:
            return self.state.disgusted
        else:
            return 0.0
    
    def update_emotion(self, emotion_type: str, value: float) -> None:
        """
        更新特定情绪的值
        
        Args:
            emotion_type: 情绪类型
            value: 新值
        """
        self.state.apply_change(emotion_type, value)
        self.state.normalize()
        self.updated_at = datetime.now()
    
    def apply_time_decay(self, decay_rate: float = 0.1) -> None:
        """
        应用时间衰减
        
        Args:
            decay_rate: 衰减率
        """
        # 快乐情绪衰减到0.5（中性值）
        if self.state.happy > 0.5:
            self.state.happy = max(0.5, self.state.happy - decay_rate)
        elif self.state.happy < 0.5:
            self.state.happy = min(0.5, self.state.happy + decay_rate)
        
        # 其他负面情绪衰减到0
        self.state.sad = max(0.0, self.state.sad - decay_rate)
        self.state.angry = max(0.0, self.state.angry - decay_rate)
        self.state.afraid = max(0.0, self.state.afraid - decay_rate)
        self.state.disgusted = max(0.0, self.state.disgusted - decay_rate)
        
        # 惊讶情绪快速衰减
        self.state.surprised = max(0.0, self.state.surprised - decay_rate * 2)
        
        # 更新时间戳
        self.updated_at = datetime.now()
        
        # 添加衰减触发器
        decay_trigger = EmotionTrigger(
            trigger_type=EmotionFactor.TIME_DECAY,
            intensity=decay_rate,
            affected_emotions={}
        )
        self.triggers.append(decay_trigger)
    
    def get_mood_description(self) -> str:
        """
        获取情绪描述
        
        Returns:
            情绪描述文本
        """
        dominant_emotion, intensity = self.get_dominant_emotion()
        
        # 如果强度低，返回中性描述
        if dominant_emotion == EmotionType.NEUTRAL or intensity < 0.3:
            return "平静"
        
        # 根据强度级别调整描述
        intensity_level = ""
        if intensity >= 0.8:
            intensity_level = "非常"
        elif intensity >= 0.6:
            intensity_level = "相当"
        elif intensity >= 0.4:
            intensity_level = "有点"
        
        # 情绪类型描述
        emotion_desc = {
            EmotionType.HAPPY: "开心",
            EmotionType.SAD: "悲伤",
            EmotionType.ANGRY: "生气",
            EmotionType.AFRAID: "害怕",
            EmotionType.SURPRISED: "惊讶",
            EmotionType.DISGUSTED: "厌恶"
        }.get(dominant_emotion, "")
        
        return f"{intensity_level}{emotion_desc}"
    
    def reset_to_neutral(self) -> None:
        """重置为中性情绪状态"""
        self.state.reset_to_neutral()
        self.updated_at = datetime.now()
        
        # 添加重置触发器
        reset_trigger = EmotionTrigger(
            trigger_type="reset",
            intensity=1.0,
            affected_emotions={}
        )
        self.triggers.append(reset_trigger)
    
    def get_recent_triggers(self, limit: int = 5) -> List[EmotionTrigger]:
        """
        获取最近的情绪触发事件
        
        Args:
            limit: 返回的最大事件数
            
        Returns:
            情绪触发事件列表
        """
        return sorted(
            self.triggers,
            key=lambda trigger: trigger.timestamp,
            reverse=True
        )[:limit]
    
    def get_valence_arousal(self) -> Tuple[float, float]:
        """
        获取价-唤醒模型值
        
        Returns:
            (价, 唤醒) 元组，两个维度均为-1.0到1.0
        """
        # 价值（负面到正面，-1到1）
        valence = self.state.happy - (self.state.sad + self.state.disgusted + self.state.angry * 0.5)
        valence = max(-1.0, min(1.0, valence))
        
        # 唤醒度（低到高，-1到1）
        arousal = (self.state.angry + self.state.afraid + self.state.surprised) - self.state.sad * 0.5
        arousal = max(-1.0, min(1.0, arousal))
        
        return (valence, arousal) 
# -*- coding: utf-8 -*-

"""
林镜(LingJing) - 情绪数据模型
"""



@dataclass
class EmotionState:
    """情绪状态"""
    # 基础情绪维度，范围为0.0-1.0
    happy: float = 0.5
    sad: float = 0.0
    angry: float = 0.0
    afraid: float = 0.0
    surprised: float = 0.0
    disgusted: float = 0.0
    
    def to_dict(self) -> Dict[str, float]:
        """
        转换为字典
        
        Returns:
            情绪状态字典
        """
        return {
            'happy': self.happy,
            'sad': self.sad,
            'angry': self.angry,
            'afraid': self.afraid,
            'surprised': self.surprised,
            'disgusted': self.disgusted,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, float]) -> 'EmotionState':
        """
        从字典创建情绪状态
        
        Args:
            data: 情绪状态字典
            
        Returns:
            情绪状态对象
        """
        return cls(
            happy=data.get('happy', 0.5),
            sad=data.get('sad', 0.0),
            angry=data.get('angry', 0.0),
            afraid=data.get('afraid', 0.0),
            surprised=data.get('surprised', 0.0),
            disgusted=data.get('disgusted', 0.0),
        )
    
    def get_dominant_emotion(self) -> Tuple[str, float]:
        """
        获取主导情绪
        
        Returns:
            (情绪类型, 情绪强度)
        """
        emotions = {
            EmotionType.HAPPY: self.happy,
            EmotionType.SAD: self.sad,
            EmotionType.ANGRY: self.angry,
            EmotionType.AFRAID: self.afraid,
            EmotionType.SURPRISED: self.surprised,
            EmotionType.DISGUSTED: self.disgusted,
        }
        
        # 找出最大值
        dominant_emotion = max(emotions.items(), key=lambda x: x[1])
        
        # 如果最大情绪值低于阈值，返回中性
        if dominant_emotion[1] < 0.3:
            return (EmotionType.NEUTRAL, 0.0)
        
        return dominant_emotion
    
    def get_emotion_vector(self) -> List[float]:
        """
        获取情绪向量
        
        Returns:
            情绪向量
        """
        return [
            self.happy,
            self.sad,
            self.angry,
            self.afraid,
            self.surprised,
            self.disgusted,
        ]
    
    def apply_change(self, emotion_type: str, value: float) -> None:
        """
        应用情绪变化
        
        Args:
            emotion_type: 情绪类型
            value: 变化值（可正可负）
        """
        if emotion_type == EmotionType.HAPPY:
            self.happy = max(0.0, min(1.0, self.happy + value))
        elif emotion_type == EmotionType.SAD:
            self.sad = max(0.0, min(1.0, self.sad + value))
        elif emotion_type == EmotionType.ANGRY:
            self.angry = max(0.0, min(1.0, self.angry + value))
        elif emotion_type == EmotionType.AFRAID:
            self.afraid = max(0.0, min(1.0, self.afraid + value))
        elif emotion_type == EmotionType.SURPRISED:
            self.surprised = max(0.0, min(1.0, self.surprised + value))
        elif emotion_type == EmotionType.DISGUSTED:
            self.disgusted = max(0.0, min(1.0, self.disgusted + value))
    
    def normalize(self) -> None:
        """归一化情绪状态，确保所有情绪维度的总和不超过一定阈值"""
        total = (self.happy + self.sad + self.angry + 
                self.afraid + self.surprised + self.disgusted)
        
        # 如果总和超过2.0，则进行归一化
        if total > 2.0:
            factor = 2.0 / total
            self.happy *= factor
            self.sad *= factor
            self.angry *= factor
            self.afraid *= factor
            self.surprised *= factor
            self.disgusted *= factor
    
    def reset_to_neutral(self) -> None:
        """重置为中性情绪状态"""
        self.happy = 0.5
        self.sad = 0.0
        self.angry = 0.0
        self.afraid = 0.0
        self.surprised = 0.0
        self.disgusted = 0.0

@dataclass
class EmotionTrigger:
    """情绪触发事件"""
    trigger_type: str
    timestamp: datetime = field(default_factory=datetime.now)
    source_id: Optional[str] = None
    source_type: Optional[str] = None
    intensity: float = 0.5
    affected_emotions: Dict[str, float] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典
        
        Returns:
            情绪触发事件字典
        """
        return {
            'trigger_type': self.trigger_type,
            'timestamp': self.timestamp.isoformat(),
            'source_id': self.source_id,
            'source_type': self.source_type,
            'intensity': self.intensity,
            'affected_emotions': self.affected_emotions,
            'metadata': self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EmotionTrigger':
        """
        从字典创建情绪触发事件
        
        Args:
            data: 情绪触发事件字典
            
        Returns:
            情绪触发事件对象
        """
        trigger = cls(
            trigger_type=data.get('trigger_type', ''),
            source_id=data.get('source_id'),
            source_type=data.get('source_type'),
            intensity=data.get('intensity', 0.5),
            affected_emotions=data.get('affected_emotions', {}),
            metadata=data.get('metadata', {}),
        )
        
        # 解析时间戳
        timestamp = data.get('timestamp')
        if timestamp:
            trigger.timestamp = datetime.fromisoformat(timestamp)
        
        return trigger

@dataclass
class Emotion:
    """情绪模型"""
    id: str
    state: EmotionState = field(default_factory=EmotionState)
    context_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    triggers: List[EmotionTrigger] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典
        
        Returns:
            情绪字典
        """
        return {
            'id': self.id,
            'state': self.state.to_dict(),
            'context_id': self.context_id,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'triggers': [trigger.to_dict() for trigger in self.triggers],
            'metadata': self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Emotion':
        """
        从字典创建情绪
        
        Args:
            data: 情绪字典
            
        Returns:
            情绪对象
        """
        emotion = cls(
            id=data.get('id', ''),
            state=EmotionState.from_dict(data.get('state', {})),
            context_id=data.get('context_id'),
            metadata=data.get('metadata', {}),
        )
        
        # 解析时间戳
        created_at = data.get('created_at')
        if created_at:
            emotion.created_at = datetime.fromisoformat(created_at)
        
        updated_at = data.get('updated_at')
        if updated_at:
            emotion.updated_at = datetime.fromisoformat(updated_at)
        
        # 解析触发事件
        triggers = data.get('triggers', [])
        emotion.triggers = [EmotionTrigger.from_dict(trigger) for trigger in triggers]
        
        return emotion
    
    def serialize(self) -> str:
        """
        序列化为JSON字符串
        
        Returns:
            JSON字符串
        """
        return json.dumps(self.to_dict(), ensure_ascii=False)
    
    @classmethod
    def deserialize(cls, data: str) -> 'Emotion':
        """
        从JSON字符串反序列化
        
        Args:
            data: JSON字符串
            
        Returns:
            情绪对象
        """
        return cls.from_dict(json.loads(data))
    
    def add_trigger(self, trigger: EmotionTrigger) -> None:
        """
        添加情绪触发事件
        
        Args:
            trigger: 情绪触发事件
        """
        self.triggers.append(trigger)
        self.updated_at = datetime.now()
        
        # 应用情绪变化
        for emotion_type, value in trigger.affected_emotions.items():
            adjusted_value = value * trigger.intensity
            self.state.apply_change(emotion_type, adjusted_value)
        
        # 归一化情绪状态
        self.state.normalize()
    
    def get_dominant_emotion(self) -> Tuple[str, float]:
        """
        获取主导情绪
        
        Returns:
            (情绪类型, 情绪强度)
        """
        return self.state.get_dominant_emotion()
    
    def get_emotion_level(self, emotion_type: str) -> float:
        """
        获取特定情绪的水平
        
        Args:
            emotion_type: 情绪类型
            
        Returns:
            情绪水平
        """
        if emotion_type == EmotionType.HAPPY:
            return self.state.happy
        elif emotion_type == EmotionType.SAD:
            return self.state.sad
        elif emotion_type == EmotionType.ANGRY:
            return self.state.angry
        elif emotion_type == EmotionType.AFRAID:
            return self.state.afraid
        elif emotion_type == EmotionType.SURPRISED:
            return self.state.surprised
        elif emotion_type == EmotionType.DISGUSTED:
            return self.state.disgusted
        else:
            return 0.0
    
    def update_emotion(self, emotion_type: str, value: float) -> None:
        """
        更新特定情绪的值
        
        Args:
            emotion_type: 情绪类型
            value: 新值
        """
        self.state.apply_change(emotion_type, value)
        self.state.normalize()
        self.updated_at = datetime.now()
    
    def apply_time_decay(self, decay_rate: float = 0.1) -> None:
        """
        应用时间衰减
        
        Args:
            decay_rate: 衰减率
        """
        # 快乐情绪衰减到0.5（中性值）
        if self.state.happy > 0.5:
            self.state.happy = max(0.5, self.state.happy - decay_rate)
        elif self.state.happy < 0.5:
            self.state.happy = min(0.5, self.state.happy + decay_rate)
        
        # 其他负面情绪衰减到0
        self.state.sad = max(0.0, self.state.sad - decay_rate)
        self.state.angry = max(0.0, self.state.angry - decay_rate)
        self.state.afraid = max(0.0, self.state.afraid - decay_rate)
        self.state.disgusted = max(0.0, self.state.disgusted - decay_rate)
        
        # 惊讶情绪快速衰减
        self.state.surprised = max(0.0, self.state.surprised - decay_rate * 2)
        
        # 更新时间戳
        self.updated_at = datetime.now()
        
        # 添加衰减触发器
        decay_trigger = EmotionTrigger(
            trigger_type=EmotionFactor.TIME_DECAY,
            intensity=decay_rate,
            affected_emotions={}
        )
        self.triggers.append(decay_trigger)
    
    def get_mood_description(self) -> str:
        """
        获取情绪描述
        
        Returns:
            情绪描述文本
        """
        dominant_emotion, intensity = self.get_dominant_emotion()
        
        # 如果强度低，返回中性描述
        if dominant_emotion == EmotionType.NEUTRAL or intensity < 0.3:
            return "平静"
        
        # 根据强度级别调整描述
        intensity_level = ""
        if intensity >= 0.8:
            intensity_level = "非常"
        elif intensity >= 0.6:
            intensity_level = "相当"
        elif intensity >= 0.4:
            intensity_level = "有点"
        
        # 情绪类型描述
        emotion_desc = {
            EmotionType.HAPPY: "开心",
            EmotionType.SAD: "悲伤",
            EmotionType.ANGRY: "生气",
            EmotionType.AFRAID: "害怕",
            EmotionType.SURPRISED: "惊讶",
            EmotionType.DISGUSTED: "厌恶"
        }.get(dominant_emotion, "")
        
        return f"{intensity_level}{emotion_desc}"
    
    def reset_to_neutral(self) -> None:
        """重置为中性情绪状态"""
        self.state.reset_to_neutral()
        self.updated_at = datetime.now()
        
        # 添加重置触发器
        reset_trigger = EmotionTrigger(
            trigger_type="reset",
            intensity=1.0,
            affected_emotions={}
        )
        self.triggers.append(reset_trigger)
    
    def get_recent_triggers(self, limit: int = 5) -> List[EmotionTrigger]:
        """
        获取最近的情绪触发事件
        
        Args:
            limit: 返回的最大事件数
            
        Returns:
            情绪触发事件列表
        """
        return sorted(
            self.triggers,
            key=lambda trigger: trigger.timestamp,
            reverse=True
        )[:limit]
    
    def get_valence_arousal(self) -> Tuple[float, float]:
        """
        获取价-唤醒模型值
        
        Returns:
            (价, 唤醒) 元组，两个维度均为-1.0到1.0
        """
        # 价值（负面到正面，-1到1）
        valence = self.state.happy - (self.state.sad + self.state.disgusted + self.state.angry * 0.5)
        valence = max(-1.0, min(1.0, valence))
        
        # 唤醒度（低到高，-1到1）
        arousal = (self.state.angry + self.state.afraid + self.state.surprised) - self.state.sad * 0.5
        arousal = max(-1.0, min(1.0, arousal))
        
        return (valence, arousal) 