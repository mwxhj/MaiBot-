import asyncio
import signal
import os
import sys
from typing import Dict, Any, Optional, Set

from .utils.logger import get_logger
from loguru import logger as loguru_logger
from . import ConfigManager # 从 linjing 包导入 ConfigManager
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
from .l4_context_aggregator.context_aggregator import ContextAggregator

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

    async def setup(self):
        """
        设置应用程序，初始化需要异步操作的资源。
        例如：初始化 LLM Manager, 连接数据库等。
        """
        logger.info("开始异步设置 Application...")
        # --- LLM 和 Prompt Manager 初始化 ---
        # 实例化需要移到 __init__ 或 _create_components，这里只做异步初始化
        if not hasattr(self, 'llm_manager') or not self.llm_manager:
             # 实例化应该在调用 setup 之前完成
             logger.info("LLM Manager 在 setup 之前实例化...") # 或者在 __init__ 中完成
             self.llm_manager = LLMManager(config=self.config)

        if not hasattr(self, 'prompt_manager') or not self.prompt_manager:
             logger.info("Prompt Manager 在 setup 之前实例化...") # 或者在 __init__ 中完成
             self.prompt_manager = PromptManager()
             prompt_configs = self.config.get("prompts", {}).get("templates", {})
             for name, template_str in prompt_configs.items():
                 self.prompt_manager.add_template(name, template_str)
                 logger.info(f"已加载 Prompt 模板: {name}")

        logger.info("正在异步初始化 LLM Manager...")
        if self.llm_manager and hasattr(self.llm_manager, 'initialize'):
             if not await self.llm_manager.initialize():
                 logger.error("LLM Manager 初始化失败！")
             else:
                 logger.info("LLM Manager 初始化成功。")
        else:
             logger.error("LLM Manager 对象不存在或没有 initialize 方法。")

        # --- 初始化 Context Aggregator (Redis) --- 
        if not hasattr(self, 'context_aggregator') or not self.context_aggregator:
             logger.info("Context Aggregator 在 setup 之前实例化...") # 或者在 __init__ 中完成
             redis_config = self.config.get("redis", {})
             self.context_aggregator = ContextAggregator(config=redis_config)

        if self.context_aggregator and hasattr(self.context_aggregator, '_test_redis_connection'):
             asyncio.create_task(self.context_aggregator._test_redis_connection(), name="RedisConnectionTest")
        else:
             logger.warning("ContextAggregator 不存在或没有 _test_redis_connection 方法。")

        logger.info("Application 异步设置完成。")

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
        logger.info(f"共 {len(self.tasks)} 个核心任务已创建。")

    async def run(self):
        """启动并运行应用程序。"""
        try:
            self.loop = asyncio.get_running_loop()
        except RuntimeError:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

        self._setup_signal_handlers()

        try:
            await self.setup() # 执行异步初始化
            self._create_queues() # 创建队列
            self._create_components() # 实例化组件
            await self._create_tasks() # 创建任务

            logger.info("Application 运行中... 按 CTRL+C 停止。")
            # 主任务：等待停止信号
            await self.stop_event.wait()

        except Exception as e:
             logger.critical(f"Application 启动或运行时发生致命错误: {e}", exc_info=True)
        finally:
            logger.info("Application 开始关闭...")
            await self.shutdown()
            logger.info("Application 关闭完成。")

    async def shutdown(self):
        """优雅地关闭应用程序，停止任务并清理资源。"""
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

    # --- 信号处理方法 ---
    def _setup_signal_handlers(self):
        """设置信号处理程序以触发优雅关闭。"""
        if self.loop is None:
            logger.error("事件循环未设置，无法添加信号处理器。")
            return
        logger.info("设置信号处理器...")
        # 在 POSIX 系统上处理常见终止信号
        signals_to_handle = (signal.SIGINT, signal.SIGTERM)
        # 在 Windows 上，只有 SIGINT 通常有效
        if sys.platform == "win32":
            signals_to_handle = (signal.SIGINT,)

        for s in signals_to_handle:
            try:
                self.loop.add_signal_handler(
                    s, lambda s=s: asyncio.create_task(self._handle_exit_signal(s))
                )
            except NotImplementedError:
                 # 对于不支持 asyncio 信号处理的旧系统或特殊情况
                 logger.warning(f"当前系统不支持 asyncio 信号处理器，将使用 signal.signal 处理 {s.name}")
                 try:
                     # signal.signal 必须在主线程调用，并且回调不能是协程
                     # 我们用它来设置事件，由循环检查
                     signal.signal(s, lambda sig, frame: self.stop_event.set())
                 except (ValueError, OSError) as e:
                     logger.error(f"无法为信号 {s.name} 设置 signal.signal 处理器: {e}")
            except ValueError as e:
                 # 例如，在非主线程尝试 add_signal_handler
                 logger.error(f"无法为信号 {s.name} 设置 asyncio 处理器: {e}")

    async def _handle_exit_signal(self, sig: signal.Signals):
        """处理退出信号的异步协程。"""
        logger.info(f"收到退出信号 {sig.name}，正在触发关闭...")
        if not self.stop_event.is_set():
             self.stop_event.set()
        else:
             logger.warning("关闭已在进行中。")

    # --- 辅助方法 (从 main.py 迁移过来) ---
    async def _logging_consumer(self, queue: asyncio.Queue, name: str):
        """简单的异步任务，消耗队列中的项目并记录日志。"""
        # ... (implementation of _logging_consumer method) ...

    # ... (_setup_signal_handlers) ...
    # ... (_handle_exit_signal) ...
    # ... (_logging_consumer) ...
    # --- _simulate_input 方法已被移除 --- 

    def _create_queues(self):
        """创建所有需要的队列。"""
        logger.info("创建层间队列...")
        # ... (implementation of _create_queues method) ...

        # ... (rest of the existing code) ... 