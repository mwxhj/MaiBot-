# linjing/l1_fast_sense/trigger_scanner.py
import re
import yaml # 导入 yaml
from typing import Dict, Any, List, Optional, Tuple

from linjing.utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_RULES_CONFIG_PATH = "config/l1_trigger_rules.yaml" # 定义默认路径

class LightweightV12TriggerScanner:
    """
    L1 轻量级 V12 触发器扫描器。
    基于规则快速扫描原始事件，识别潜在的 V12 原则触发点，并初步评估严重性。
    从配置文件加载规则。
    """
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化 LightweightV12TriggerScanner。

        Args:
            config: 可选的配置字典，应包含规则文件路径等。
        """
        self.config = config or {}
        self.rules_config_path = self.config.get("l1_trigger_rules_path", DEFAULT_RULES_CONFIG_PATH)
        self.trigger_rules: List[Dict[str, Any]] = [] # 存储解析后的规则字典列表
        self._load_rules() # 调用加载方法
        logger.info(f"LightweightV12TriggerScanner 初始化完成，加载了 {len(self.trigger_rules)} 条规则。")


    def _load_rules(self):
        """从 YAML 文件加载和解析触发规则。"""
        try:
            with open(self.rules_config_path, 'r', encoding='utf-8') as f:
                rules_data = yaml.safe_load(f)

            if not rules_data or "rules" not in rules_data or not isinstance(rules_data["rules"], list):
                logger.error(f"规则文件 '{self.rules_config_path}' 格式错误或 'rules' 列表不存在/为空。")
                return

            loaded_rules = rules_data["rules"]
            valid_rules = []
            for i, rule in enumerate(loaded_rules):
                # 验证规则基本结构
                if not isinstance(rule, dict) or not all(k in rule for k in ["id", "type", "pattern", "severity"]):
                    logger.warning(f"跳过格式错误的规则 #{i+1} (缺少必要字段): {rule}")
                    continue
                # 验证 pattern 是否为字符串
                if not isinstance(rule["pattern"], str):
                     logger.warning(f"跳过规则 '{rule['id']}' (pattern 不是字符串): {rule['pattern']}")
                     continue
                # 验证 severity 是否为整数
                if not isinstance(rule["severity"], int) or not (0 < rule["severity"] <= 3): # 严重级别限制在 1-3
                     logger.warning(f"跳过规则 '{rule['id']}' (severity 无效，应为 1-3 的整数): {rule['severity']}")
                     continue
                # 尝试编译正则表达式以提前发现错误 (对于 keyword 类型也尝试编译，因为我们用 re.search)
                try:
                    re.compile(rule["pattern"], re.IGNORECASE if rule["type"] == "keyword" else 0)
                except re.error as e:
                    logger.error(f"跳过规则 '{rule['id']}' (正则表达式编译错误: {e}): {rule['pattern']}")
                    continue

                valid_rules.append(rule)

            self.trigger_rules = valid_rules
            logger.info(f"从 '{self.rules_config_path}' 成功加载并验证了 {len(self.trigger_rules)} 条规则。")

        except FileNotFoundError:
            logger.error(f"规则文件 '{self.rules_config_path}' 未找到！将使用空规则列表。")
        except yaml.YAMLError as e:
            logger.error(f"解析规则文件 '{self.rules_config_path}' 时出错: {e}")
        except Exception as e:
            logger.error(f"加载规则时发生未知错误: {e}", exc_info=True)


    def scan(self, raw_event: Dict[str, Any]) -> Dict[str, Any]:
        """
        扫描单个原始事件，查找潜在的 V12 触发器。
        """
        potential_triggers: List[str] = []
        max_severity_level = 0
        severity_map = {0: "none", 1: "mild", 2: "medium", 3: "severe"}

        text = raw_event.get("raw_message") or raw_event.get("message", "")
        if isinstance(text, list):
             text = "".join(str(seg.get("data", {}).get("text", "")) if isinstance(seg, dict) and seg.get("type") == "text" else "" for seg in text)

        if not text or not isinstance(text, str):
            # logger.trace("事件无有效文本内容，跳过触发器扫描。") # 日志级别可能过低
            return {"potential_triggers": [], "estimated_severity": "none"}

        # logger.debug(f"TriggerScanner 开始扫描文本: '{text[:100]}...'") # 日志级别可能过低

        for rule in self.trigger_rules:
            rule_id = rule["id"]
            pattern_type = rule["type"]
            pattern = rule["pattern"]
            severity_level = rule["severity"]
            match_found = False
            try:
                if pattern_type == "keyword":
                    # 使用 re.search 支持正则表达式形式的关键词匹配，默认忽略大小写
                    if re.search(pattern, text, re.IGNORECASE):
                        match_found = True
                elif pattern_type == "regex":
                    # 正则匹配通常区分大小写，除非模式本身包含(?i)
                    if re.search(pattern, text):
                        match_found = True
                # 可以添加其他 pattern_type

                if match_found:
                    logger.trace(f"文本触发规则: {rule_id} (Severity: {severity_level})") # 使用 Trace 级别
                    potential_triggers.append(rule_id)
                    if severity_level > max_severity_level:
                        max_severity_level = severity_level

            except re.error as e: # 理论上加载时已检查，但以防万一
                logger.error(f"处理规则 '{rule_id}' 的正则表达式时出错: {e} (Pattern: {pattern})")
            except Exception as e:
                 logger.error(f"扫描规则 '{rule_id}' 时发生未知错误: {e}", exc_info=True)


        estimated_severity = severity_map.get(max_severity_level, "none")
        result = {
            "potential_triggers": list(set(potential_triggers)),
            "estimated_severity": estimated_severity
        }
        # logger.debug(f"TriggerScanner 扫描结果: {result}") # 日志级别可能过低
        return result 