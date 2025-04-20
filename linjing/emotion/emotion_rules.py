"""
情绪规则

该模块定义了情绪规则，用于根据特定条件触发情绪变化。
"""

import re
# import asyncio # 不再需要
import random
from typing import Dict, Any, Callable # <--- 移除未使用的 List, Optional, Pattern, Tuple

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

    # 改为同步方法
    def evaluate(self, current_emotion, message_text: str, factors: Dict[str, Any]) -> Dict[str, float]:
        """
        评估规则并返回情绪变化 (同步版本)

        Args:
            current_emotion: 当前情绪状态 (可能包含 VAD 等维度)
            message_text: 消息文本 (可能用于某些规则)
            factors: 影响因素, 预期包含 read_air_analysis

        Returns:
            情绪变化字典 (例如 {'valence': -0.2, 'arousal': 0.1})
        """
        raise NotImplementedError # 基类方法应被子类覆盖


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

    # 改为同步方法
    def evaluate(self, current_emotion, message_text: str, factors: Dict[str, Any]) -> Dict[str, float]:
        """
        评估规则并返回情绪变化 (同步版本)

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

    # 改为同步方法
    def evaluate(self, current_emotion, message_text: str, factors: Dict[str, Any]) -> Dict[str, float]:
        """
        评估规则并返回情绪变化 (同步版本)

        Args:
            current_emotion: 当前情绪状态
            message_text: 消息文本
            factors: 影响因素

        Returns:
            情绪变化字典
        """
        # 检查 condition_func 是否需要 await (如果它是 async lambda)
        # 但通常条件函数是同步的
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

    # 改为同步方法
    def evaluate(self, current_emotion, message_text: str, factors: Dict[str, Any]) -> Dict[str, float]:
        """
        评估规则并返回情绪变化 (同步版本)

        Args:
            current_emotion: 当前情绪状态
            message_text: 消息文本
            factors: 影响因素

        Returns:
            情绪变化字典
        """
        # 假设 current_emotion 有 dimensions 属性
        current_dims = getattr(current_emotion, 'dimensions', {})
        if self.dimension not in current_dims:
            return {}
            
        current_value = current_dims[self.dimension]
        compare_func = self.compare_funcs.get(self.comparison)
        
        if compare_func and compare_func(current_value, self.threshold):
            logger.debug(f"情绪规则 '{self.name}' 阈值条件满足 ({self.dimension} {self.comparison} {self.threshold})，应用情绪变化")
            return self.emotion_changes.copy()
        
        return {}


# --- 新增 V12 触发器规则 ---
class V12TriggerRule(EmotionRule):
    """基于 V12 触发器扫描结果的情绪规则"""
    def __init__(
        self,
        name: str,
        trigger_key: str, # factors['read_air_analysis']['v12_trigger_scan_results'] 中的键名
        emotion_changes: Dict[str, float], # 对 VAD 维度的影响
        description: str = ""
    ):
        super().__init__(name, description)
        self.trigger_key = trigger_key
        self.emotion_changes = emotion_changes

    def evaluate(self, current_emotion, message_text: str, factors: Dict[str, Any]) -> Dict[str, float]:
        """评估 V12 触发器是否激活"""
        read_air_analysis = factors.get("read_air_analysis", {})
        if not isinstance(read_air_analysis, dict):
             logger.warning(f"规则 '{self.name}' 无法评估：read_air_analysis 不是字典或不存在。")
             return {}

        trigger_results = read_air_analysis.get("v12_trigger_scan_results", {})
        if not isinstance(trigger_results, dict):
             logger.warning(f"规则 '{self.name}' 无法评估：v12_trigger_scan_results 不是字典或不存在。")
             return {}

        if trigger_results.get(self.trigger_key, False) is True:
            logger.info(f"V12 情绪规则 '{self.name}' (触发器: {self.trigger_key}) 激活，应用情绪变化: {self.emotion_changes}")
            return self.emotion_changes.copy()

        return {}

class EmotionRules:
    """情绪规则管理器"""

    # 修改 __init__ 以接收配置
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化情绪规则管理器

        Args:
            config: 情绪相关的配置字典 (来自 config.yaml 的 emotion 部分)
        """
        self.config = config or {} # 存储配置
        self.rules: List[EmotionRule] = [] # 明确类型
        self._initialize_v12_rules() # 调用初始化方法

    def _initialize_v12_rules(self):
        """初始化 V12 情绪规则 (从配置加载)"""
        logger.info("初始化 V12 情绪规则 (从配置加载)...")

        # 从配置中读取 V12 触发器效果
        v12_trigger_effects = self.config.get("v12_trigger_effects", {})
        if not v12_trigger_effects:
             logger.warning("配置中未找到 'v12_trigger_effects'，无法加载 V12 触发器规则！")

        for trigger_key, changes in v12_trigger_effects.items():
            rule_name = f"v12_{trigger_key.split('_')[-2]}" # e.g., v12_disrespect
            self.rules.append(
                V12TriggerRule(
                    name=rule_name,
                    trigger_key=trigger_key,
                    emotion_changes=changes,
                    description=f"基于 V12 触发器 {trigger_key} 的情绪反应"
                )
            )
            logger.debug(f"已添加 V12 情绪规则: {rule_name}")

        # 从配置中读取情绪平衡规则
        balance_rules_config = self.config.get("balance_rules", {})
        if not balance_rules_config:
             logger.warning("配置中未找到 'balance_rules'，无法加载情绪平衡规则！")
        else:
             logger.debug(f"加载情绪平衡规则: {balance_rules_config}")

        # 为 VAD 三个维度创建平衡规则
        for dim in ["valence", "arousal", "dominance"]:
            # 处理过高的情况
            high_rule_config = balance_rules_config.get(f"{dim}_high")
            if isinstance(high_rule_config, dict):
                threshold = high_rule_config.get("threshold")
                change = high_rule_config.get("change")
                if isinstance(threshold, (int, float)) and isinstance(change, (int, float)):
                    self.rules.append(ThresholdRule(
                        name=f"{dim}_too_high", dimension=dim, threshold=threshold, comparison="gt",
                        emotion_changes={dim: change}, description=f"过高的 {dim} 自动调整"
                    ))
                    logger.debug(f"已添加平衡规则: {dim}_too_high (阈值>{threshold}, 变化:{change})")
                else:
                     logger.warning(f"平衡规则 '{dim}_high' 配置无效: {high_rule_config}")

            # 处理过低的情况
            low_rule_config = balance_rules_config.get(f"{dim}_low")
            if isinstance(low_rule_config, dict):
                threshold = low_rule_config.get("threshold")
                change = low_rule_config.get("change")
                if isinstance(threshold, (int, float)) and isinstance(change, (int, float)):
                    self.rules.append(ThresholdRule(
                        name=f"{dim}_too_low", dimension=dim, threshold=threshold, comparison="lt",
                        emotion_changes={dim: change}, description=f"过低的 {dim} 自动调整"
                    ))
                    logger.debug(f"已添加平衡规则: {dim}_too_low (阈值<{threshold}, 变化:{change})")
                else:
                     logger.warning(f"平衡规则 '{dim}_low' 配置无效: {low_rule_config}")

        # 移除所有旧的 PatternMatchRule 和 ConditionalRule
        # logger.info("旧的模式匹配和条件规则已被移除，由 V12 触发器规则替代。")
    
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
    
    # 改为同步方法
    def apply_rules(self, current_emotion, message_text: str, factors: Dict[str, Any]) -> Dict[str, float]:
        """
        应用所有规则并返回合并后的情绪变化 (同步版本)

        Args:
            current_emotion: 当前情绪状态
            message_text: 消息文本
            factors: 影响因素 (应包含 read_air_analysis)

        Returns:
            合并后的情绪变化字典 (VAD 变化)
        """
        combined_changes: Dict[str, float] = {} # 明确类型

        # 评估所有规则
        for rule in self.rules:
            try:
                # 调用同步的 evaluate 方法
                rule_changes = rule.evaluate(current_emotion, message_text, factors)

                # 合并变化 (累加)
                for dim, value in rule_changes.items():
                    combined_changes[dim] = combined_changes.get(dim, 0) + value
            except Exception as e:
                logger.error(f"应用情绪规则 '{rule.name}' 出错: {e}")
        
        return combined_changes 