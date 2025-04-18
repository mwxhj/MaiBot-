"""
情绪规则

该模块定义了情绪规则，用于根据特定条件触发情绪变化。
"""

import re
import asyncio
import random
from typing import Dict, Any, List, Optional, Pattern, Callable, Tuple

from ..utils.logger import get_logger

logger = get_logger(__name__)

class EmotionRule:
    """情绪规则基类"""
    
    def __init__(self, name: str, description: str = ""):
        """
        初始化情绪规则
        
        Args:
            name: 规则名称
            description: 规则描述
        """
        self.name = name
        self.description = description
    
    async def evaluate(self, current_emotion, message_text: str, factors: Dict[str, Any]) -> Dict[str, float]:
        """
        评估规则并返回情绪变化
        
        Args:
            current_emotion: 当前情绪状态
            message_text: 消息文本
            factors: 影响因素
            
        Returns:
            情绪变化字典
        """
        return {}


class PatternMatchRule(EmotionRule):
    """基于模式匹配的情绪规则"""
    
    def __init__(
        self, 
        name: str, 
        pattern: str, 
        emotion_changes: Dict[str, float],
        description: str = "",
        flags: int = re.IGNORECASE
    ):
        """
        初始化模式匹配规则
        
        Args:
            name: 规则名称
            pattern: 正则表达式模式
            emotion_changes: 情绪变化字典
            description: 规则描述
            flags: 正则表达式标志
        """
        super().__init__(name, description)
        self.pattern = re.compile(pattern, flags)
        self.emotion_changes = emotion_changes
    
    async def evaluate(self, current_emotion, message_text: str, factors: Dict[str, Any]) -> Dict[str, float]:
        """
        评估规则并返回情绪变化
        
        Args:
            current_emotion: 当前情绪状态
            message_text: 消息文本
            factors: 影响因素
            
        Returns:
            情绪变化字典
        """
        if not message_text:
            return {}
            
        if self.pattern.search(message_text):
            logger.debug(f"情绪规则 '{self.name}' 匹配，应用情绪变化: {self.emotion_changes}")
            return self.emotion_changes.copy()
        
        return {}


class ConditionalRule(EmotionRule):
    """基于条件的情绪规则"""
    
    def __init__(
        self, 
        name: str, 
        condition_func: Callable[[Dict[str, Any]], bool],
        emotion_changes: Dict[str, float],
        description: str = ""
    ):
        """
        初始化条件规则
        
        Args:
            name: 规则名称
            condition_func: 条件函数，接收影响因素并返回布尔值
            emotion_changes: 情绪变化字典
            description: 规则描述
        """
        super().__init__(name, description)
        self.condition_func = condition_func
        self.emotion_changes = emotion_changes
    
    async def evaluate(self, current_emotion, message_text: str, factors: Dict[str, Any]) -> Dict[str, float]:
        """
        评估规则并返回情绪变化
        
        Args:
            current_emotion: 当前情绪状态
            message_text: 消息文本
            factors: 影响因素
            
        Returns:
            情绪变化字典
        """
        if self.condition_func(factors):
            logger.debug(f"情绪规则 '{self.name}' 条件满足，应用情绪变化: {self.emotion_changes}")
            return self.emotion_changes.copy()
        
        return {}


class ThresholdRule(EmotionRule):
    """基于情绪阈值的规则"""
    
    def __init__(
        self, 
        name: str, 
        dimension: str,
        threshold: float,
        comparison: str,  # "gt", "lt", "gte", "lte"
        emotion_changes: Dict[str, float],
        description: str = ""
    ):
        """
        初始化阈值规则
        
        Args:
            name: 规则名称
            dimension: 情绪维度
            threshold: 阈值
            comparison: 比较操作符
            emotion_changes: 情绪变化字典
            description: 规则描述
        """
        super().__init__(name, description)
        self.dimension = dimension
        self.threshold = threshold
        self.comparison = comparison
        self.emotion_changes = emotion_changes
        
        # 定义比较函数
        self.compare_funcs = {
            "gt": lambda x, y: x > y,
            "lt": lambda x, y: x < y,
            "gte": lambda x, y: x >= y,
            "lte": lambda x, y: x <= y,
            "eq": lambda x, y: abs(x - y) < 0.01
        }
    
    async def evaluate(self, current_emotion, message_text: str, factors: Dict[str, Any]) -> Dict[str, float]:
        """
        评估规则并返回情绪变化
        
        Args:
            current_emotion: 当前情绪状态
            message_text: 消息文本
            factors: 影响因素
            
        Returns:
            情绪变化字典
        """
        if self.dimension not in current_emotion.dimensions:
            return {}
            
        current_value = current_emotion.dimensions[self.dimension]
        compare_func = self.compare_funcs.get(self.comparison)
        
        if compare_func and compare_func(current_value, self.threshold):
            logger.debug(f"情绪规则 '{self.name}' 阈值条件满足 ({self.dimension} {self.comparison} {self.threshold})，应用情绪变化")
            return self.emotion_changes.copy()
        
        return {}


class EmotionRules:
    """情绪规则管理器"""
    
    def __init__(self):
        """初始化情绪规则管理器"""
        self.rules = []
        self._initialize_rules()
    
    def _initialize_rules(self):
        """初始化预定义规则"""
        # 添加模式匹配规则
        self.rules.extend([
            # 表情符号规则
            PatternMatchRule(
                name="emoji_happy",
                pattern=r"[😀😁😂🤣😃😄😊😍🥰😘]",
                emotion_changes={"happiness": 0.03, "excitement": 0.02},
                description="检测快乐表情"
            ),
            PatternMatchRule(
                name="emoji_sad",
                pattern=r"[😢😭😞😔😟😕🙁☹️😩😫]",
                emotion_changes={"happiness": -0.03},
                description="检测悲伤表情"
            ),
            PatternMatchRule(
                name="emoji_angry",
                pattern=r"[😠😡🤬👿😤]",
                emotion_changes={"patience": -0.04, "friendliness": -0.02},
                description="检测愤怒表情"
            ),
            
            # 亲密称呼规则
            PatternMatchRule(
                name="intimate_nickname",
                pattern=r"\b(亲爱的|宝贝|亲|小可爱|小林|小猪|林酱)\b",
                emotion_changes={"happiness": 0.04, "friendliness": 0.05},
                description="检测亲密称呼"
            ),
            
            # 负面态度规则
            PatternMatchRule(
                name="negative_attitude",
                pattern=r"\b(滚|傻|蠢|笨|废物|无用|useless|闭嘴|shut up)\b",
                emotion_changes={"happiness": -0.06, "friendliness": -0.05, "confidence": -0.04},
                description="检测负面态度"
            ),
            
            # 连续问题规则
            PatternMatchRule(
                name="continuous_questions",
                pattern=r".*\?.*\?.*(\?|？)",  # 三个或更多问号
                emotion_changes={"patience": -0.03},
                description="检测连续问题"
            ),
            
            # 表扬规则
            PatternMatchRule(
                name="praise",
                pattern=r"\b(好棒|真棒|厉害|聪明|smart|clever|brilliant|优秀|best|最佳)\b",
                emotion_changes={"happiness": 0.05, "confidence": 0.05},
                description="检测表扬"
            ),
            
            # 冒犯或伤害规则
            PatternMatchRule(
                name="offend",
                pattern=r"\b(讨厌你|hate you|烦死你|恨你|恶心|滚开|去死)\b",
                emotion_changes={"happiness": -0.08, "trust": -0.05, "friendliness": -0.06},
                description="检测冒犯或伤害"
            ),
        ])
        
        # 添加阈值规则
        self.rules.extend([
            # 情绪极值自动平衡规则
            ThresholdRule(
                name="happiness_too_high",
                dimension="happiness",
                threshold=0.9,
                comparison="gt",
                emotion_changes={"happiness": -0.02},
                description="过高的快乐会自动降低"
            ),
            ThresholdRule(
                name="happiness_too_low",
                dimension="happiness",
                threshold=0.1,
                comparison="lt",
                emotion_changes={"happiness": 0.02},
                description="过低的快乐会自动提升"
            ),
            # 其他阈值规则...
        ])
        
        # 添加条件规则
        self.rules.extend([
            # 高频互动规则
            ConditionalRule(
                name="high_frequency_interaction",
                condition_func=lambda factors: factors.get("interaction_frequency", 0) > 0.8,
                emotion_changes={"trust": 0.03, "friendliness": 0.02},
                description="高频互动增加信任和友好度"
            ),
            # 长时间无回应规则
            ConditionalRule(
                name="long_no_response",
                condition_func=lambda factors: factors.get("time_since_last_message", 0) > 86400,  # 24小时
                emotion_changes={"friendliness": -0.02},
                description="长时间无回应降低友好度"
            ),
        ])
    
    def add_rule(self, rule: EmotionRule) -> None:
        """
        添加规则
        
        Args:
            rule: 情绪规则对象
        """
        self.rules.append(rule)
    
    def remove_rule(self, rule_name: str) -> bool:
        """
        移除规则
        
        Args:
            rule_name: 规则名称
            
        Returns:
            是否成功移除
        """
        for i, rule in enumerate(self.rules):
            if rule.name == rule_name:
                self.rules.pop(i)
                return True
        return False
    
    async def apply_rules(self, current_emotion, message_text: str, factors: Dict[str, Any]) -> Dict[str, float]:
        """
        应用所有规则并返回情绪变化
        
        Args:
            current_emotion: 当前情绪状态
            message_text: 消息文本
            factors: 影响因素
            
        Returns:
            情绪变化字典
        """
        combined_changes = {}
        
        # 评估所有规则
        for rule in self.rules:
            try:
                rule_changes = await rule.evaluate(current_emotion, message_text, factors)
                
                # 合并变化
                for dim, value in rule_changes.items():
                    combined_changes[dim] = combined_changes.get(dim, 0) + value
            except Exception as e:
                logger.error(f"应用情绪规则 '{rule.name}' 出错: {e}")
        
        return combined_changes 