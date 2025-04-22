import asyncio
import signal
import os
import sys
from typing import Dict, Any, Optional, Set

from .utils.logger import get_logger
from loguru import logger as loguru_logger
from .config import ConfigManager # 假设 ConfigManager 在 linjing/config.py
from .l1_fast_sense.input_buffer import InputBuffer
from .l1_fast_sense.processor import FastSenseProcessor
from .l2_adaptive_dispatcher.state_monitor import SimpleStateMonitor
from .l2_adaptive_dispatcher.decision_engine import SimpleRuleBasedDecisionEngine
from .l2_adaptive_dispatcher.adaptive_dispatcher import AdaptiveDispatcher
from .llm.llm_manager import LLMManager
from .llm.prompt_templates import PromptManager
from .l3_processing_paths.path_a_processor import PathAProcessor
from .l3_processing_paths.path_c_simple import SimplePathCProcessor
from .adapters.onebot_adapter import OneBotAdapter

logger = get_logger(__name__)

class Application:
    """
    林镜机器人应用程序类 (新架构 V12)。
    负责加载配置、初始化组件、管理任务和生命周期。
    """
    def __init__(self, config: Dict[str, Any]):
        """
        初始化应用程序。

        Args:
            config: 加载后的配置字典。
        """
        self.config = config
        self.stop_event = asyncio.Event()
        self.tasks: Set[asyncio.Task] = set()
        self.loop: Optional[asyncio.AbstractEventLoop] = None

        self.input_buffer: Optional[InputBuffer] = None
        self.llm_manager: Optional[LLMManager] = None
        self.prompt_manager: Optional[PromptManager] = None
        self.context_aggregator: Optional[ContextAggregator] = None
        self.l1_processor: Optional[FastSenseProcessor] = None
        self.l2_dispatcher: Optional[AdaptiveDispatcher] = None
        self.path_a_processor: Optional[PathAProcessor] = None
        self.simple_path_c_processor: Optional[SimplePathCProcessor] = None
        self.adapters: Dict[str, Any] = {}
        self.l1_output_queue: Optional[asyncio.Queue] = None
        self.l3_path_a_queue: Optional[asyncio.Queue] = None

        logger.info("Application 初始化。")

    def _create_components(self):
        """实例化所有核心组件，包括适配器。"""
        logger.info("实例化核心组件...")
        # ... (Ensure dependencies) ...

        try:
            # ... (L1, L2, L3 instantiation) ...

            # --- 实例化适配器 ---
            adapters_config = self.config.get("adapters", [])
            if not isinstance(adapters_config, list):
                logger.error("配置中的 'adapters' 必须是一个列表。")
                adapters_config = []
            
            for adapter_config in adapters_config:
                adapter_type = adapter_config.get("type")
                adapter_id = adapter_config.get("id", adapter_type)
                enabled = adapter_config.get("enabled", True)

                if not enabled:
                    logger.info(f"适配器 '{adapter_id}' (类型: {adapter_type}) 已禁用，跳过。")
                    continue
                
                if not adapter_id or not adapter_type:
                     logger.warning(f"无效的适配器配置，缺少 id 或 type: {adapter_config}")
                     continue

                if adapter_type == "onebot":
                    try:
                        # TODO: EventBus 需要实例化并传入 Application
                        event_bus_instance = None # 占位符, 需要 Application 提供 EventBus
                        if not self.input_buffer:
                             raise ValueError("InputBuffer 未初始化，无法创建 OneBotAdapter")
                        
                        adapter_instance = OneBotAdapter(adapter_config, event_bus_instance, self.input_buffer)
                        self.adapters[adapter_id] = adapter_instance
                        logger.info(f"已实例化适配器: '{adapter_id}' (类型: {adapter_type})")
                    except Exception as e_adapter:
                        logger.error(f"实例化适配器 '{adapter_id}' (类型: {adapter_type}) 时出错: {e_adapter}", exc_info=True)
                else:
                    logger.warning(f"配置中发现未知或当前不支持的适配器类型: {adapter_type}")

            logger.info("核心组件实例化完成。")
        except Exception as e:
            logger.error(f"实例化组件时出错: {e}", exc_info=True)
            raise

    async def _create_tasks(self):
        """创建所有需要运行的 asyncio 任务，包括适配器连接任务。"""
        logger.info("创建后台任务...")
        # ... (Check core components) ...

        # --- 创建核心组件任务 ---
        self.tasks.add(asyncio.create_task(self.l1_processor.start_processing(), name="L1_FastSenseProcessor"))
        # ... (L2, L3 tasks) ...

        # --- 创建适配器任务 ---
        for adapter_id, adapter_instance in self.adapters.items():
            if hasattr(adapter_instance, 'connect') and callable(adapter_instance.connect):
                logger.info(f"为适配器 '{adapter_id}' 创建连接/运行任务...")
                self.tasks.add(asyncio.create_task(adapter_instance.connect(), name=f"Adapter_{adapter_id}"))
            else:
                 logger.warning(f"适配器 '{adapter_id}' 没有可调用的 connect 方法。")

        # --- 移除模拟输入任务 ---
        # if self.config.get("system", {}).get("run_simulation", True):
        #     if not self.input_buffer:
        #          raise RuntimeError("模拟输入需要 InputBuffer。")
        #     self.tasks.add(asyncio.create_task(self._simulate_input(self.input_buffer), name="SimulateInput"))
        logger.info(f"共 {len(self.tasks)} 个任务已创建 (包括适配器)。")

    async def shutdown(self):
        """优雅地关闭应用程序，停止任务并清理资源，包括适配器。"""
        # ... (Stop event and cancel tasks) ...

        # 清理资源
        logger.info("正在清理资源...")
        # --- 关闭适配器 ---
        for adapter_id, adapter_instance in self.adapters.items():
             if hasattr(adapter_instance, 'disconnect') and callable(adapter_instance.disconnect):
                 try:
                     logger.info(f"正在断开适配器 '{adapter_id}'...")
                     await adapter_instance.disconnect()
                     logger.info(f"适配器 '{adapter_id}' 已断开。")
                 except Exception as e_disc:
                     logger.error(f"断开适配器 '{adapter_id}' 时出错: {e_disc}", exc_info=True)

        # ... (Context Aggregator, LLM Manager cleanup) ...

    # ... (_setup_signal_handlers) ...
    # ... (_handle_exit_signal) ...
    # ... (_logging_consumer) ...
    # --- _simulate_input 方法已被移除 --- 