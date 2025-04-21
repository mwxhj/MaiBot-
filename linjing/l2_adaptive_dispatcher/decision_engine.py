# linjing/l2_adaptive_dispatcher/decision_engine.py
import abc
from typing import Dict, Any, Optional

from linjing.utils.logger import get_logger

logger = get_logger(__name__)

class DecisionEngineInterface(abc.ABC):
    """
    L2 决策引擎的接口。
    负责根据 L1 的 routing_assessment 和全局状态决定处理路径。
    """
    @abc.abstractmethod
    def decide(self, assessment: Dict[str, Any], global_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        进行路由决策。

        Args:
            assessment: 来自 L1 的 routing_assessment 字典。
            global_state: 来自 StateMonitor 的全局状态字典。

        Returns:
            一个包含决策结果的字典 (dispatch_decision)，例如:
            {
                "selected_path": "path_b", # "path_a", "path_b", "path_c", "path_o" (Direct Output/Action)
                "target_resources": {"llm_model": "gpt-4", "max_tokens": 500}, # L3 资源提示
                "priority": 5, # 任务优先级 (可选)
                "decision_reason": "Medium complexity message with mild trigger, requires thoughtful response.",
                "processed_input": assessment # 可以传递原始或处理过的 assessment 给下一层
            }
        """
        raise NotImplementedError

class SimpleRuleBasedDecisionEngine(DecisionEngineInterface):
    """
    一个简单的基于规则的决策引擎实现 (占位符)。
    """
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        logger.info("SimpleRuleBasedDecisionEngine 初始化完成。")
        # TODO: 可以从配置加载更复杂的规则

    def decide(self, assessment: Dict[str, Any], global_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        根据简单的规则进行决策。
        """
        logger.debug(f"DecisionEngine: 开始决策，Assessment: {assessment.get('message_id')}, State Mode: {global_state.get('current_mode')}")

        routing_metrics = assessment.get("routing_metrics", {})
        complexity = routing_metrics.get("estimated_complexity", "low")
        immediacy = routing_metrics.get("immediacy_needed", "low")
        trigger_scan = assessment.get("v12_trigger_scan", {})
        trigger_severity = trigger_scan.get("estimated_severity", "none")
        # intent_hint = assessment.get("basic_analysis", {}).get("intent_hint", {})
        # mentioned_bot = assessment.get("basic_analysis", {}).get("mentioned_bot", False)
        current_mode = global_state.get("current_mode", "standard")

        # --- 决策逻辑 (简单示例) ---
        selected_path = "path_c" # 默认最低成本路径
        target_resources = {"llm_model": "default_fast_model", "max_tokens": 200}
        priority = 5 # 默认优先级
        reason = "Default path for low complexity and low immediacy."

        # 维护模式下可能直接丢弃或简单回应
        if current_mode == "maintenance":
            selected_path = "path_o" # 直接输出/动作 (例如发送维护中消息)
            target_resources = {"action": "send_maintenance_message"}
            priority = 1
            reason = "Bot in maintenance mode."

        # 高优先级：严重触发或高即时性需求 (可能需要最好的模型和快速处理)
        elif trigger_severity == "severe" or immediacy == "high":
            selected_path = "path_a" # 最高质量路径
            target_resources = {"llm_model": "gpt-4-turbo", "max_tokens": 1000} # 示例：最好的模型
            priority = 10 # 最高优先级
            reason = f"High immediacy ({immediacy}) or severe trigger ({trigger_severity}) detected."

        # 中优先级：中等复杂度或中等触发 (使用标准模型)
        elif complexity == "high" or complexity == "medium" or trigger_severity == "medium":
            selected_path = "path_b" # 标准思考路径
            target_resources = {"llm_model": "gpt-3.5-turbo", "max_tokens": 500} # 示例：标准模型
            priority = 7
            reason = f"Medium/High complexity ({complexity}) or medium trigger ({trigger_severity})."

        # 低优先级 (已是默认)
        # else: pass # 保持 path_c

        # --- 决策逻辑结束 ---

        dispatch_decision = {
            "selected_path": selected_path,
            "target_resources": target_resources,
            "priority": priority,
            "decision_reason": reason,
            "processed_input": assessment # 传递完整的 assessment
        }
        logger.info(f"DecisionEngine: 决策结果: Path={selected_path}, Priority={priority}, Reason={reason}")
        return dispatch_decision 