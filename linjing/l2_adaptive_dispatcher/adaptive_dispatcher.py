# linjing/l2_adaptive_dispatcher/adaptive_dispatcher.py
import asyncio
from typing import Dict, Any, Optional

# 导入 L2 依赖
from .state_monitor import StateMonitorInterface
from .decision_engine import DecisionEngineInterface

# 导入 L1 输出和 L3/L5 输入的队列类型 (占位符)
L1_OUTPUT_QUEUE_TYPE = asyncio.Queue # L1 输出 routing_assessment
L3_PATH_A_QUEUE_TYPE = asyncio.Queue # L3 Path A 输入 dispatch_decision
L3_PATH_B_QUEUE_TYPE = asyncio.Queue # L3 Path B 输入 dispatch_decision
L3_PATH_C_QUEUE_TYPE = asyncio.Queue # L3 Path C 输入 dispatch_decision
L5_ACTION_QUEUE_TYPE = asyncio.Queue # L5 Path O (Direct Action) 输入 dispatch_decision

from linjing.utils.logger import get_logger

logger = get_logger(__name__)

class AdaptiveDispatcher:
    """
    L2 智能分发器。
    负责接收 L1 的评估结果，结合全局状态进行决策，并将任务分发到 L3 或 L5。
    """
    def __init__(self,
                 l1_output_queue: L1_OUTPUT_QUEUE_TYPE,
                 l3_path_a_queue: L3_PATH_A_QUEUE_TYPE,
                 l3_path_b_queue: L3_PATH_B_QUEUE_TYPE,
                 l3_path_c_queue: L3_PATH_C_QUEUE_TYPE,
                 l5_action_queue: L5_ACTION_QUEUE_TYPE,
                 state_monitor: StateMonitorInterface,
                 decision_engine: DecisionEngineInterface,
                 config: Optional[Dict[str, Any]] = None):
        """
        初始化 AdaptiveDispatcher。

        Args:
            l1_output_queue: L1 输出 routing_assessment 的队列。
            l3_path_a_queue: L3 Path A 处理队列。
            l3_path_b_queue: L3 Path B 处理队列。
            l3_path_c_queue: L3 Path C 处理队列。
            l5_action_queue: L5 Path O (直接动作) 处理队列。
            state_monitor: 状态监控器实例。
            decision_engine: 决策引擎实例。
            config: 可选配置字典。
        """
        self.l1_output_queue = l1_output_queue
        self.l3_queues = {
            "path_a": l3_path_a_queue,
            "path_b": l3_path_b_queue,
            "path_c": l3_path_c_queue,
        }
        self.l5_action_queue = l5_action_queue
        self.state_monitor = state_monitor
        self.decision_engine = decision_engine
        self.config = config or {}
        self._running = False
        self._task: Optional[asyncio.Task] = None
        logger.info("AdaptiveDispatcher 初始化完成。")

    async def start_dispatching(self):
        """启动分发循环。"""
        if self._running:
            logger.warning("AdaptiveDispatcher 已经在运行中。")
            return

        self._running = True
        self._task = asyncio.create_task(self._dispatching_loop())
        logger.info("AdaptiveDispatcher 分发循环已启动。")
        try:
            await self._task
        except asyncio.CancelledError:
            logger.info("AdaptiveDispatcher 分发循环被取消。")
        except Exception as e:
            logger.error(f"AdaptiveDispatcher 分发循环异常终止: {e}", exc_info=True)
            self._running = False

    async def stop_dispatching(self):
        """停止分发循环。"""
        if not self._running or not self._task:
            logger.warning("AdaptiveDispatcher 没有在运行中。")
            return

        self._running = False
        if self._task:
            self._task.cancel()
            logger.info("正在停止 AdaptiveDispatcher 分发循环...")
            try:
                await asyncio.wait_for(self._task, timeout=5.0)
            except asyncio.CancelledError:
                logger.info("AdaptiveDispatcher 分发循环已成功取消。")
            except asyncio.TimeoutError:
                logger.warning("停止 AdaptiveDispatcher 循环超时。")
            except Exception as e:
                 logger.error(f"停止 AdaptiveDispatcher 循环时发生错误: {e}", exc_info=True)
        self._task = None
        logger.info("AdaptiveDispatcher 分发循环已停止。")

    async def _dispatching_loop(self):
        """内部循环，持续从 L1 队列获取评估，进行决策和分发。"""
        while self._running:
            try:
                # 1. 从 L1 获取 routing_assessment
                routing_assessment = await self.l1_output_queue.get()
                logger.debug(f"AdaptiveDispatcher 从 L1 收到 Assessment: {routing_assessment.get('message_id')}")

                # 2. 获取全局状态
                global_state = await self.state_monitor.get_global_state()

                # 3. 调用决策引擎
                # 注意：当前 decision_engine.decide 是同步的，如果改为 async 需要 await
                dispatch_decision = self.decision_engine.decide(routing_assessment, global_state)

                # 4. 根据决策分发任务
                selected_path = dispatch_decision.get("selected_path")
                target_queue = None

                if selected_path in self.l3_queues:
                    target_queue = self.l3_queues[selected_path]
                    queue_name = f"L3 {selected_path}"
                elif selected_path == "path_o":
                    target_queue = self.l5_action_queue
                    queue_name = "L5 Action"
                else:
                    logger.error(f"未知的 selected_path: {selected_path}，无法分发任务！")
                    self.l1_output_queue.task_done() # 标记 L1 任务完成，即使分发失败
                    continue # 处理下一个

                # 5. 将 dispatch_decision 放入目标队列
                if target_queue:
                    try:
                        # 可以考虑使用 asyncio.PriorityQueue 如果需要支持优先级
                        await target_queue.put(dispatch_decision)
                        logger.info(f"任务 (Msg ID: {routing_assessment.get('message_id')}) 已分发到 {queue_name} 队列。")
                    except asyncio.QueueFull:
                        logger.error(f"{queue_name} 队列已满！任务可能丢失。请检查后续层处理速度或增加缓冲区大小。")
                        # TODO: 需要考虑队列满时的处理策略（例如重试、丢弃、通知等）
                    except Exception as e_put:
                        logger.error(f"将任务放入 {queue_name} 队列时出错: {e_put}", exc_info=True)

                # 标记 L1 队列中的任务已完成处理
                self.l1_output_queue.task_done()

            except asyncio.CancelledError:
                 logger.info("分发循环在获取 Assessment 时被取消。")
                 break
            except Exception as e:
                logger.error(f"分发循环中发生未捕获错误: {e}", exc_info=True)
                # 标记任务完成，防止队列阻塞？或者不标记让其重试？取决于策略
                try:
                     self.l1_output_queue.task_done()
                except ValueError: # task_done() might raise ValueError if called too many times
                     pass
                await asyncio.sleep(1.0) # 发生错误时休眠 