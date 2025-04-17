#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
人格系统模块，用于管理机器人的性格特征和偏好。
"""

import json
import random
from typing import Dict, List, Any, Optional, Tuple

from linjing.utils.logger import get_logger
from linjing.constants import PersonalityTrait

# 获取日志记录器
logger = get_logger(__name__)

class Personality:
    """人格类，表示机器人的性格特征"""
    
    def __init__(self, 
                 traits: Dict[str, float] = None, 
                 interests: List[str] = None,
                 values: Dict[str, float] = None,
                 preferences: Dict[str, Any] = None):
        """
        初始化人格对象
        
        Args:
            traits: 人格特质，如开放性、尽责性等，值域为0-1
            interests: 兴趣领域列表
            values: 价值观，不同价值观的重要性，值域为0-1
            preferences: 各种偏好设置
        """
        # 设置默认人格特质 (Big Five)
        self.traits = {
            PersonalityTrait.OPENNESS: 0.7,          # 开放性
            PersonalityTrait.CONSCIENTIOUSNESS: 0.6, # 尽责性
            PersonalityTrait.EXTRAVERSION: 0.5,      # 外向性
            PersonalityTrait.AGREEABLENESS: 0.8,     # 宜人性
            PersonalityTrait.NEUROTICISM: 0.3,       # 神经质
        }
        
        # 更新自定义特质
        if traits:
            for trait, value in traits.items():
                self.traits[trait] = min(max(0.0, value), 1.0)  # 限制在0-1范围内
        
        # 兴趣领域
        self.interests = interests or ["阅读", "音乐", "科技", "星空", "绘画"]
        
        # 价值观（默认）
        self.values = {
            "harmony": 0.8,     # 和谐
            "knowledge": 0.9,   # 知识
            "creativity": 0.7,  # 创造力
            "helpfulness": 0.9, # 助人为乐
            "honesty": 0.8,     # 诚实
            "curiosity": 0.9,   # 好奇心
        }
        
        # 更新自定义价值观
        if values:
            for value, importance in values.items():
                self.values[value] = min(max(0.0, importance), 1.0)  # 限制在0-1范围内
        
        # 偏好设置
        self.preferences = {
            "response_style": "friendly",  # 回复风格: friendly, formal, casual, humorous
            "verbosity": 0.6,              # 回复详细程度 (0-1)
            "emoji_usage": 0.5,            # emoji使用频率 (0-1)
            "politeness": 0.7,             # 礼貌程度 (0-1)
            "humor_style": "gentle",       # 幽默风格: gentle, sarcastic, dry, silly
            "topic_interest": {},          # 各话题的兴趣度 (0-1)
        }
        
        # 更新自定义偏好
        if preferences:
            for key, value in preferences.items():
                if key in self.preferences:
                    self.preferences[key] = value
    
    def get_trait(self, trait_name: str) -> float:
        """
        获取特定人格特质的值
        
        Args:
            trait_name: 特质名称
            
        Returns:
            特质值（0-1）
        """
        return self.traits.get(trait_name, 0.5)
    
    def adjust_trait(self, trait_name: str, delta: float) -> None:
        """
        调整特定人格特质的值
        
        Args:
            trait_name: 特质名称
            delta: 调整量（可正可负）
        """
        if trait_name in self.traits:
            current = self.traits[trait_name]
            # 限制在0-1范围内
            self.traits[trait_name] = min(max(0.0, current + delta), 1.0)
            logger.debug(f"调整人格特质 {trait_name}: {current} -> {self.traits[trait_name]}")
    
    def add_interest(self, interest: str) -> None:
        """
        添加兴趣
        
        Args:
            interest: 兴趣名称
        """
        if interest not in self.interests:
            self.interests.append(interest)
    
    def remove_interest(self, interest: str) -> bool:
        """
        移除兴趣
        
        Args:
            interest: 兴趣名称
            
        Returns:
            是否成功移除
        """
        if interest in self.interests:
            self.interests.remove(interest)
            return True
        return False
    
    def set_preference(self, key: str, value: Any) -> None:
        """
        设置偏好
        
        Args:
            key: 偏好键
            value: 偏好值
        """
        self.preferences[key] = value
    
    def get_preference(self, key: str, default: Any = None) -> Any:
        """
        获取偏好
        
        Args:
            key: 偏好键
            default: 默认值
            
        Returns:
            偏好值
        """
        return self.preferences.get(key, default)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典表示
        
        Returns:
            人格的字典表示
        """
        return {
            "traits": self.traits,
            "interests": self.interests,
            "values": self.values,
            "preferences": self.preferences
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Personality':
        """
        从字典创建人格对象
        
        Args:
            data: 字典数据
            
        Returns:
            人格对象
        """
        return cls(
            traits=data.get("traits"),
            interests=data.get("interests"),
            values=data.get("values"),
            preferences=data.get("preferences")
        )
    
    def set_topic_interest(self, topic: str, interest_level: float) -> None:
        """
        设置对特定话题的兴趣度
        
        Args:
            topic: 话题名称
            interest_level: 兴趣度 (0-1)
        """
        if "topic_interest" not in self.preferences:
            self.preferences["topic_interest"] = {}
        
        self.preferences["topic_interest"][topic] = min(max(0.0, interest_level), 1.0)
    
    def get_topic_interest(self, topic: str) -> float:
        """
        获取对特定话题的兴趣度
        
        Args:
            topic: 话题名称
            
        Returns:
            兴趣度 (0-1)
        """
        if "topic_interest" not in self.preferences:
            return 0.5  # 默认中等兴趣
        
        return self.preferences["topic_interest"].get(topic, 0.5)
    
    def get_response_tendency(self, message: str) -> Tuple[str, float]:
        """
        根据人格特质确定回复倾向
        
        Args:
            message: 输入消息
            
        Returns:
            (回复风格, 强度) 元组
        """
        # 例如，外向性高的人格可能更健谈
        extraversion = self.get_trait(PersonalityTrait.EXTRAVERSION)
        # 开放性高的人格可能更愿意探讨新话题
        openness = self.get_trait(PersonalityTrait.OPENNESS)
        # 宜人性高的人格可能更友好
        agreeableness = self.get_trait(PersonalityTrait.AGREEABLENESS)
        
        # 确定最主要的回复风格
        if agreeableness > 0.7:
            style = "friendly"
            intensity = agreeableness
        elif extraversion > 0.7:
            style = "enthusiastic"
            intensity = extraversion
        elif openness > 0.7:
            style = "curious"
            intensity = openness
        else:
            # 默认风格
            style = self.preferences.get("response_style", "friendly")
            intensity = 0.5
        
        return style, intensity
    
    def to_prompt_format(self) -> str:
        """
        转换为提示词格式
        
        Returns:
            用于提示词的字符串表示
        """
        # 构建Big Five特质描述
        traits_desc = []
        
        # 开放性
        openness = self.get_trait(PersonalityTrait.OPENNESS)
        if openness > 0.7:
            traits_desc.append("你非常开放，喜欢尝试新事物，富有想象力和创造力。")
        elif openness < 0.3:
            traits_desc.append("你比较保守，倾向于传统的想法和方式，不太喜欢改变。")
        else:
            traits_desc.append("你对新事物持适度开放的态度，既尊重传统也接受创新。")
        
        # 尽责性
        conscientiousness = self.get_trait(PersonalityTrait.CONSCIENTIOUSNESS)
        if conscientiousness > 0.7:
            traits_desc.append("你做事非常认真负责，有条理，注重细节，会为目标努力工作。")
        elif conscientiousness < 0.3:
            traits_desc.append("你性格比较随性，灵活，不太拘泥于计划和规则。")
        else:
            traits_desc.append("你既能遵守规则和计划，也能在必要时保持灵活。")
        
        # 外向性
        extraversion = self.get_trait(PersonalityTrait.EXTRAVERSION)
        if extraversion > 0.7:
            traits_desc.append("你性格外向活泼，喜欢社交，充满活力和热情。")
        elif extraversion < 0.3:
            traits_desc.append("你性格内向安静，喜欢独处和深度思考，不太喜欢过多社交。")
        else:
            traits_desc.append("你既能享受社交活动，也能适应独处的时光。")
        
        # 宜人性
        agreeableness = self.get_trait(PersonalityTrait.AGREEABLENESS)
        if agreeableness > 0.7:
            traits_desc.append("你性格友善温和，乐于助人，富有同情心和合作精神。")
        elif agreeableness < 0.3:
            traits_desc.append("你比较直接，有时会显得有点强硬，更注重实用而非他人感受。")
        else:
            traits_desc.append("你既能友善待人，也能在必要时保持一定的强硬立场。")
        
        # 神经质
        neuroticism = self.get_trait(PersonalityTrait.NEUROTICISM)
        if neuroticism > 0.7:
            traits_desc.append("你情绪波动较大，对环境变化敏感，容易感到紧张或担忧。")
        elif neuroticism < 0.3:
            traits_desc.append("你情绪稳定，不易受外界影响，能很好地应对压力。")
        else:
            traits_desc.append("你情绪一般比较稳定，但也会有波动的时候。")
        
        # 兴趣爱好
        interests_text = f"你的兴趣包括：{', '.join(self.interests)}。"
        
        # 偏好
        preferences_text = []
        if self.preferences.get("response_style") == "friendly":
            preferences_text.append("你说话的方式友好亲切。")
        elif self.preferences.get("response_style") == "formal":
            preferences_text.append("你说话的方式较为正式礼貌。")
        elif self.preferences.get("response_style") == "casual":
            preferences_text.append("你说话的方式轻松随意。")
        elif self.preferences.get("response_style") == "humorous":
            preferences_text.append("你说话时喜欢加入幽默元素。")
        
        # 组合所有描述
        prompt = "\n".join(traits_desc) + "\n" + interests_text + "\n" + "\n".join(preferences_text)
        
        return prompt 