"""
情绪模型 (V12 适配版)

该模块定义了新的情绪模型，负责计算背景情绪变化。
"""

from typing import Dict, Any
from ..utils.logger import get_logger

logger = get_logger(__name__)

class MoodModel:
    """情绪模型，负责计算背景情绪变化"""
    
    def __init__(self, config):
        """初始化情绪模型
        
        Args:
            config: 配置字典，包含 emotion 相关配置
        """
        self.config = config.get("emotion", {})
        
        # 从配置中获取情绪参数
        self.event_impact = self.config.get("event_impact", {})
        self.mood_model = self.config.get("mood_model", {})
        
        # 基础参数
        self.decay_rate = self.mood_model.get("decay_rate", 0.05)
        self.baseline_mood = self.mood_model.get("baseline_mood", "平静")
    
    def compute_changes(self, current_emotion, factors: Dict[str, Any], message_text: str = "") -> Dict[str, float]:
        """
        计算情绪变化
        
        Args:
            current_emotion: 当前情绪状态
            factors: 影响因素字典
            message_text: 用户消息文本
            
        Returns:
            情绪变化字典
        """
        changes = {}
        
        # 1. 基于事件因素的情绪变化
        event_changes = self._compute_event_changes(factors)
        
        # 2. 基于消息文本的情绪变化
        text_changes = self._compute_text_changes(message_text)
        
        # 3. 基于随机因素的情绪变化（情绪波动）
        random_changes = self._compute_random_changes()
        
        # 4. 情绪惯性影响（当前情绪状态对变化的影响）
        inertia_effect = self._apply_inertia(current_emotion, event_changes)
        
        # 5. 维度关联影响（一个情绪维度变化对其他维度的影响）
        dimension_effects = self._apply_dimension_correlations(event_changes)
        
        # 合并所有变化
        for dim in current_emotion.dimensions:
            changes[dim] = 0
            
            # 添加各种变化
            if dim in event_changes:
                changes[dim] += event_changes[dim] 
            
            if dim in text_changes:
                changes[dim] += text_changes[dim]
            
            if dim in random_changes:
                changes[dim] += random_changes[dim]
                
            if dim in inertia_effect:
                changes[dim] *= inertia_effect[dim]
                
            if dim in dimension_effects:
                changes[dim] += dimension_effects[dim]
                
            # 限制单次变化量
            max_change = self.config.get("emotion", {}).get("max_change_per_turn", 0.15)  # 从配置读取最大变化量
            changes[dim] = max(-max_change, min(max_change, changes[dim]))
        
        return changes
    
    def _compute_event_changes(self, factors: Dict[str, Any]) -> Dict[str, float]:
        """
        计算基于事件因素的情绪变化
        
        Args:
            factors: 事件因素字典
            
        Returns:
            情绪变化字典
        """
        changes = {}
        
        # 处理常见事件因素
        if "message_type" in factors:
            # 基于消息类型的变化
            msg_type = factors["message_type"]
            
            if msg_type == "question":
                # 问题提高好奇心
                changes["curiosity"] = self.base_change_rate * 2
                
            elif msg_type == "greeting":
                # 问候提高友好度和快乐度
                changes["friendliness"] = self.base_change_rate
                changes["happiness"] = self.base_change_rate * 0.8
                
            elif msg_type == "complaint":
                # 抱怨降低耐心和快乐度
                changes["patience"] = -self.base_change_rate * 1.5
                changes["happiness"] = -self.base_change_rate
        
        # 处理情感评分
        if "sentiment_score" in factors:
            sentiment = factors["sentiment_score"]  # 假设范围为[-1, 1]
            
            # 积极情感提高快乐度和友好度
            if sentiment > 0:
                changes["happiness"] = changes.get("happiness", 0) + self.base_change_rate * sentiment * 2
                changes["friendliness"] = changes.get("friendliness", 0) + self.base_change_rate * sentiment
                
            # 消极情感降低快乐度和友好度
            elif sentiment < 0:
                changes["happiness"] = changes.get("happiness", 0) + self.base_change_rate * sentiment * 2
                changes["friendliness"] = changes.get("friendliness", 0) + self.base_change_rate * sentiment * 0.5
        
        # 处理交互频率
        if "interaction_frequency" in factors:
            frequency = factors["interaction_frequency"]  # 假设范围为[0, 1]，1表示高频交互
            
            # 高频交互提高友好度和信任度
            if frequency > 0.7:
                changes["friendliness"] = changes.get("friendliness", 0) + self.base_change_rate * 0.5
                changes["trust"] = changes.get("trust", 0) + self.base_change_rate * 0.3
                
            # 低频交互轻微降低友好度
            elif frequency < 0.3:
                changes["friendliness"] = changes.get("friendliness", 0) - self.base_change_rate * 0.2
        
        # 处理对话主题
        if "topic" in factors:
            topic = factors["topic"]
            
            # 根据主题调整情绪
            topic_effects = {
                "technical": {"curiosity": 0.5, "confidence": 0.3},
                "emotional": {"empathy": 0.6, "happiness": 0.2},
                "conflict": {"patience": -0.4, "trust": -0.2},
                "praise": {"happiness": 0.6, "confidence": 0.4}
            }
            
            if topic in topic_effects:
                for dim, effect in topic_effects[topic].items():
                    changes[dim] = changes.get(dim, 0) + self.base_change_rate * effect
        
        return changes
    
    def _get_base_impact(self, event_type: str) -> float:
        """获取事件的基础影响值"""
        # 从配置中获取事件影响因子
        impact_mapping = {
            "positive_interaction": self.event_impact.get("positive_interaction_base_impact", 0.1),
            "negative_interaction": self.event_impact.get("negative_interaction_base_impact", -0.2),
            "v12_trigger": self.event_impact.get("v12_trigger_impact_multiplier", {}).get("disrespect", 1.5) *
                          self.event_impact.get("negative_interaction_base_impact", -0.2)
        }
        
        return impact_mapping.get(event_type, 0.0)
    
    def _get_positive_mood(self) -> str:
        """获取积极的情绪类型"""
        # 从配置的情绪词汇中选择一个积极的情绪
        positive_moods = ["愉悦", "好奇", "兴奋"]
        return positive_moods[0]  # 简单实现，可扩展
    
    def _get_negative_mood(self) -> str:
        """获取消极的情绪类型"""
        # 从配置的情绪词汇中选择一个消极的情绪
        negative_moods = ["烦躁", "愤怒", "轻蔑"]
        return negative_moods[0]  # 简单实现，可扩展
    
    def _compute_random_changes(self) -> Dict[str, float]:
        """
        计算随机情绪变化（情绪波动）
        
        Returns:
            随机情绪变化字典
        """
        changes = {}
        
        # 为每个情绪维度添加小幅随机波动
        emotion_dimensions = [
            "happiness", "excitement", "confidence", 
            "friendliness", "curiosity", "patience", "trust"
        ]
        
        for dim in emotion_dimensions:
            # 随机波动范围为 ±0.5 * base_change_rate
            random_factor = (random.random() - 0.5) * self.base_change_rate
            changes[dim] = random_factor
            
        return changes
    
    def _apply_inertia(self, current_emotion, changes: Dict[str, float]) -> Dict[str, float]:
        """
        应用情绪惯性效应
        
        Args:
            current_emotion: 当前情绪状态
            changes: 情绪变化字典
            
        Returns:
            情绪惯性影响系数
        """
        inertia_factors = {}
        
        for dim, value in current_emotion.dimensions.items():
            if dim in changes:
                # 如果当前情绪处于极值附近，则减缓变化速度
                if (value > 0.8 and changes[dim] > 0) or (value < 0.2 and changes[dim] < 0):
                    inertia_factors[dim] = 1 - self.inertia_factor
                else:
                    inertia_factors[dim] = 1.0
                    
        return inertia_factors
    
    def _apply_dimension_correlations(self, changes: Dict[str, float]) -> Dict[str, float]:
        """
        应用维度关联效应
        
        Args:
            changes: 情绪变化字典
            
        Returns:
            维度关联效应变化
        """
        dimension_effects = {}
        
        for dim, change in changes.items():
            if dim in self.dimension_correlations:
                for related_dim, correlation in self.dimension_correlations[dim].items():
                    # 相关维度变化 = 原始变化 * 关联系数
                    related_change = change * correlation
                    dimension_effects[related_dim] = dimension_effects.get(related_dim, 0) + related_change
                    
        return dimension_effects 