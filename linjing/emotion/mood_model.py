"""
情绪模型 (V12 适配版)

该模块定义了新的情绪模型，负责计算背景情绪变化。
"""

from typing import Dict, Any, Optional # <-- 添加 Optional
from ..utils.logger import get_logger

logger = get_logger(__name__)

class MoodModel:
    """情绪模型，负责计算背景情绪变化"""
    
    # 修改 __init__ 以接收 emotion 配置块
    def __init__(self, emotion_config: Optional[Dict[str, Any]] = None):
        """
        初始化情绪模型

        Args:
            emotion_config: 情绪相关的配置字典 (来自 config.yaml 的 emotion 部分)
        """
        self.config = emotion_config or {} # 存储 emotion 配置块

        # 从 mood_model 子配置块获取参数
        self.mood_model_config = self.config.get("mood_model", {})
        self.base_change_rate = self.mood_model_config.get("base_change_rate", 0.05)
        self.inertia_factor = self.mood_model_config.get("inertia_factor", 0.3)
        self.dimension_correlations = self.mood_model_config.get("dimension_correlations", {})

        # 获取情绪维度列表 (从 vad_model 配置块读取，如果存在)
        vad_config = self.config.get("vad_model", {})
        # 假设 VAD 维度是固定的或由其他地方定义，这里不再需要单独配置 dimensions
        self.emotion_dimensions = ["valence", "arousal", "dominance"] # 固定为 VAD

        # 移除旧的/未使用的参数加载
        # self.event_impact = self.config.get("event_impact", {}) # 旧的事件影响配置
        # self.decay_rate = self.mood_model_config.get("decay_rate", 0.05) # 衰减由 EmotionManager 处理
        # self.baseline_mood = self.mood_model_config.get("baseline_mood", "平静") # 基线由 EmotionManager 处理
    
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
        # 使用 self.emotion_dimensions 获取当前模型关注的维度
        for dim in self.emotion_dimensions:
            changes[dim] = 0.0 # 初始化为浮点数

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
    
    # 添加缺失的方法
    def _compute_text_changes(self, message_text: str) -> Dict[str, float]:
        """
        计算基于消息文本的情绪变化 (占位符)
        TODO: 实现基于文本分析的情绪变化逻辑，例如使用情感分析库。
              当前返回空字典，表示文本不直接影响基础情绪模型。
              V12 的主要文本影响通过 ReadAir 分析和 EmotionRules 处理。
        """
        logger.debug(f"MoodModel._compute_text_changes (占位符) for text: {message_text[:50]}...")
        return {}

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
        
        # 为配置中定义的每个情绪维度添加小幅随机波动
        for dim in self.emotion_dimensions:
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
        # 假设 current_emotion 有一个 dimensions 属性或方法返回维度字典
        current_dims = getattr(current_emotion, 'dimensions', {})
        if not isinstance(current_dims, dict):
             logger.warning(f"无法从 current_emotion 获取 dimensions 字典: {current_emotion}")
             current_dims = {} # 避免下面出错

        for dim in self.emotion_dimensions: # 遍历模型定义的维度
            value = current_dims.get(dim, 0.5) # 获取当前维度的值，默认为中性 0.5
            change = changes.get(dim, 0.0) # 获取该维度的变化量

            # 如果当前情绪处于极值附近，则减缓变化速度
            # 注意：这里的 0.8 和 0.2 是硬编码的阈值，可能需要配置
            if (value > 0.8 and change > 0) or (value < 0.2 and change < 0):
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