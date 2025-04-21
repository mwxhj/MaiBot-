# linjing/l2_adaptive_dispatcher/state_monitor.py
import abc
import time
from typing import Dict, Any, Optional

from linjing.utils.logger import get_logger

logger = get_logger(__name__)

class StateMonitorInterface(abc.ABC):
    """
    机器人全局状态监控器的接口。
    提供获取 Bot 实时或准实时状态信息的方法。
    """
    @abc.abstractmethod
    async def get_global_state(self) -> Dict[str, Any]:
        """
        获取当前的全局 Bot 状态。

        Returns:
            一个包含状态信息的字典，例如:
            {
                "system_load": {"cpu_percent": 15.5, "memory_percent": 45.0},
                "llm_api_status": {"main_api": "operational", "backup_api": "degraded"},
                "active_conversations": 15,
                "l3_queue_lengths": {"path_a": 5, "path_b": 2, "path_c": 0},
                "current_mode": "standard", # e.g., standard, maintenance, learning
                "rate_limit_status": {"global": 0.8, "user_xyz": 0.5}, # 当前已用速率比例
                "last_update_time": 1678888888.8
            }
        """
        raise NotImplementedError

class SimpleStateMonitor(StateMonitorInterface):
    """
    一个简单的 StateMonitor 实现 (占位符)。
    返回固定的或基于简单计算的状态信息。
    """
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        # 可以从配置初始化一些静态状态
        self.current_mode = self.config.get("initial_bot_mode", "standard")
        logger.info(f"SimpleStateMonitor 初始化完成，当前模式: {self.current_mode}")

    async def get_global_state(self) -> Dict[str, Any]:
        """
        返回一个简单的、大部分是硬编码的状态字典。
        """
        logger.debug("SimpleStateMonitor: 获取全局状态...")
        # TODO: 实现获取真实系统负载、队列长度等的逻辑
        # 这里返回占位符数据
        state = {
            "system_load": {"cpu_percent": 10.0, "memory_percent": 50.0}, # 示例值
            "llm_api_status": {"main_api": "operational", "backup_api": "operational"}, # 示例值
            "active_conversations": 10, # 示例值
            "l3_queue_lengths": {"path_a": 0, "path_b": 0, "path_c": 0}, # 示例值 (需要与 L3 队列集成)
            "current_mode": self.current_mode,
            "rate_limit_status": {"global": 0.1, "user_xyz": 0.0}, # 示例值
            "last_update_time": time.time()
        }
        logger.debug(f"SimpleStateMonitor: 返回状态: {state}")
        return state

    def set_mode(self, mode: str):
        """允许外部修改当前模式 (简单实现)"""
        logger.info(f"SimpleStateMonitor: 模式已更改为 -> {mode}")
        self.current_mode = mode 