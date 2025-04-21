# linjing/l1_fast_sense/processor.py
import asyncio
import time
from typing import Dict, Any, Optional

# 导入 L1 子组件
from .fast_sense_nlp import FastSenseNLPModule
from .trigger_scanner import LightweightV12TriggerScanner
from .context_aggregator import ContextAggregator
from .input_buffer import InputBuffer

# 假设 L2 dispatcher 的接口或输出队列
# from ..l2_adaptive_dispatcher import AdaptiveDispatcher # 假设存在
# 或者使用一个输出队列
L2_OUTPUT_QUEUE_TYPE = asyncio.Queue # 示例类型

from linjing.utils.logger import get_logger

logger = get_logger(__name__)

class FastSenseProcessor:
    """
    L1 核心处理器：编排 L1 组件，处理来自 InputBuffer 的事件，
    生成 routing_assessment 并传递给 L2。
    """
    def __init__(self,
                 input_buffer: InputBuffer,
                 l2_dispatcher_queue: L2_OUTPUT_QUEUE_TYPE, # 假设传递给 L2 的队列
                 nlp_module: FastSenseNLPModule,            # 实际接收 NLP 模块
                 trigger_scanner: LightweightV12TriggerScanner, # 实际接收扫描器
                 context_aggregator: ContextAggregator,      # 实际接收聚合器
                 config: Optional[Dict[str, Any]] = None):
        """
        初始化 FastSenseProcessor。

        Args:
            input_buffer: L1 输入缓冲队列实例。
            l2_dispatcher_queue: 用于将 routing_assessment 发送到 L2 的队列。
            nlp_module: 轻量级 NLP 分析模块实例。
            trigger_scanner: V12 触发器扫描模块实例。
            context_aggregator: 上下文聚合模块实例。
            config: 可选的配置字典。
        """
        self.input_buffer = input_buffer
        self.l2_dispatcher_queue = l2_dispatcher_queue
        self.nlp_module = nlp_module # 存储 NLP 模块
        self.trigger_scanner = trigger_scanner # 存储扫描器
        self.context_aggregator = context_aggregator # 存储聚合器
        self.config = config or {}
        self._running = False
        self._task: Optional[asyncio.Task] = None
        logger.info("FastSenseProcessor 初始化完成 (已链接子组件)。") # 更新日志

    async def start_processing(self):
        """启动事件处理循环。"""
        if self._running:
            logger.warning("FastSenseProcessor 已经在运行中。")
            return

        self._running = True
        self._task = asyncio.create_task(self._processing_loop())
        logger.info("FastSenseProcessor 事件处理循环已启动。")
        try:
             await self._task # 等待任务完成或被取消
        except asyncio.CancelledError:
             logger.info("FastSenseProcessor 处理循环被取消。")
        except Exception as e:
             logger.error(f"FastSenseProcessor 处理循环异常终止: {e}", exc_info=True)
             self._running = False # 确保标记为未运行


    async def stop_processing(self):
        """停止事件处理循环。"""
        if not self._running or not self._task:
            logger.warning("FastSenseProcessor 没有在运行中。")
            return

        self._running = False
        if self._task: # 检查任务是否存在
            self._task.cancel()
            logger.info("正在停止 FastSenseProcessor 事件处理循环...")
            try:
                await asyncio.wait_for(self._task, timeout=5.0) # 等待任务结束，设置超时
            except asyncio.CancelledError:
                logger.info("FastSenseProcessor 处理循环已成功取消。")
            except asyncio.TimeoutError:
                logger.warning("停止 FastSenseProcessor 循环超时。")
            except Exception as e:
                 logger.error(f"停止 FastSenseProcessor 循环时发生错误: {e}", exc_info=True)
        self._task = None # 清理任务引用
        logger.info("FastSenseProcessor 事件处理循环已停止。")


    async def _processing_loop(self):
        """内部循环，持续从 InputBuffer 获取并处理事件。"""
        while self._running:
            try:
                raw_event = await self.input_buffer.get()
                logger.debug(f"FastSenseProcessor 从 InputBuffer 获取到事件: {raw_event.get('post_type')}")
                routing_assessment = await self._process_single_event(raw_event)

                # 在处理完事件后，更新上下文缓存
                if routing_assessment: # 只有成功处理的事件才更新上下文（可选策略）
                    await self.context_aggregator.update_context(routing_assessment["session_id"], raw_event)

                # 将评估结果发送到 L2
                if routing_assessment:
                    logger.debug(f"生成的 Routing Assessment: {routing_assessment}")
                    try:
                        await self.l2_dispatcher_queue.put(routing_assessment)
                        logger.info(f"Routing Assessment 已发送到 L2 队列。")
                    except asyncio.QueueFull:
                         logger.error("L2 Dispatcher 队列已满！Routing Assessment 可能丢失。请检查 L2 处理速度或增加缓冲区大小。")
                    except Exception as e_put:
                         logger.error(f"将 Routing Assessment 发送到 L2 队列时出错: {e_put}", exc_info=True)

            except asyncio.CancelledError:
                 logger.info("处理循环在获取事件时被取消。")
                 break # 退出循环
            except Exception as e:
                logger.error(f"处理事件循环中发生未捕获错误: {e}", exc_info=True)
                # 根据策略决定是否继续循环，这里选择继续
                await asyncio.sleep(1.0) # 发生错误时休眠稍长时间

    async def _process_single_event(self, raw_event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        处理单个原始事件，调用 L1 子组件，生成 routing_assessment。
        """
        start_time = time.monotonic()
        message_id = raw_event.get("message_id") # 提前获取用于日志
        try:
            # 1. 提取基础信息
            user_id = raw_event.get("user_id")
            group_id = raw_event.get("group_id")
            raw_text = raw_event.get("raw_message") or raw_event.get("message", "")
            # 统一处理文本格式
            if isinstance(raw_text, list):
                 raw_text = "".join(str(seg.get("data", {}).get("text", "")) if isinstance(seg, dict) and seg.get("type") == "text" else "" for seg in raw_text)
            if not isinstance(raw_text, str):
                 raw_text = str(raw_text)

            post_type = raw_event.get("post_type")

            # 如果不是预期处理的类型 (例如 message)，可以提前返回 None
            # TODO: 将可处理的 post_type 配置化
            if post_type not in ["message"]:
                 logger.debug(f"跳过非消息类型的事件: {post_type}")
                 return None

            sender_info = raw_event.get("sender", {})
            # 修正 session_id 生成逻辑，优先使用 group_id
            session_id_suffix = group_id if group_id else (user_id if user_id else "unknown")
            # session_id = f"{post_type}_{session_id_suffix}" # 旧逻辑
            if post_type == 'message' and group_id:
                session_id = f"group_{group_id}"
            elif post_type == 'message' and user_id:
                 session_id = f"private_{user_id}"
            else: # 对于其他 post_type 或缺少 id 的情况，保持之前的逻辑或进一步细化
                session_id = f"{post_type}_{session_id_suffix}"


            # 2. 调用 FastSenseNLPModule
            logger.debug("调用 FastSenseNLPModule...")
            nlp_results = await self.nlp_module.process(raw_text)
            # 检查 NLP 模块是否返回错误
            if isinstance(nlp_results, dict) and "error" in nlp_results:
                logger.error(f"FastSenseNLPModule 返回错误: {nlp_results['error']}")
                nlp_results = {} # 出错时使用空结果

            # 3. 调用 LightweightV12TriggerScanner
            logger.debug("调用 LightweightV12TriggerScanner...")
            # 注意：当前的 scan 是同步的，如果改为 async 需要 await
            trigger_results = self.trigger_scanner.scan(raw_event)

            # 4. 调用 ContextAggregator
            logger.debug("调用 ContextAggregator...")
            context_summary = await self.context_aggregator.get_summary(session_id, message_id) # 传入当前消息 ID 避免获取自身


            # 5. 评估路由指标 (保持简单示例逻辑)
            estimated_complexity = "low"
            immediacy_needed = "low"
            mentioned_bot = raw_event.get("at_me", False) or (self.config.get("bot_name", "林镜") in raw_text) # 简单提及检测
            if "紧急" in raw_text or "马上" in raw_text or mentioned_bot:
                immediacy_needed = "high"
            if len(raw_text) > 150 or trigger_results.get("estimated_severity") in ["medium", "severe"]:
                estimated_complexity = "medium"
            if len(raw_text) > 500: # 很长的消息可能更复杂
                 estimated_complexity = "high"


            # 6. 组装 routing_assessment
            assessment = {
                "message_id": message_id,
                "analysis_timestamp": time.time(),
                "sender_info": sender_info,
                "user_id": str(user_id) if user_id else None, # 确保 user_id 是字符串或 None
                "group_id": str(group_id) if group_id else None, # 确保 group_id 是字符串或 None
                "session_id": session_id,
                "post_type": post_type,
                "raw_text": raw_text,
                "basic_analysis": {
                    # 从 nlp_results 获取，提供默认值
                    "style": nlp_results.get("style", []),
                    "sentiment_hint": nlp_results.get("sentiment_hint", {"primary": "neutral", "score": 0.0}),
                    "intent_hint": nlp_results.get("intent_hint", {"primary": "unknown", "confidence": 0.0}),
                    "keywords": nlp_results.get("keywords", []),
                    "mentioned_bot": mentioned_bot
                },
                "v12_trigger_scan": {
                    # 从 trigger_results 获取
                    "potential_triggers": trigger_results.get("potential_triggers", []), 
                    "estimated_severity": trigger_results.get("estimated_severity", "none")
                },
                "context_summary": context_summary, # 从 ContextAggregator 获取
                "routing_metrics": {
                    "estimated_complexity": estimated_complexity,
                    "immediacy_needed": immediacy_needed
                },
                "l1_processing_time_ms": (time.monotonic() - start_time) * 1000,
                "raw_event_snippet": {k: v for k, v in raw_event.items() if k not in ['message', 'raw_message']} # 包含除长消息外的原始事件信息
            }
            return assessment

        except Exception as e:
            logger.error(f"处理单个事件时发生严重错误 (Event ID: {message_id}): {e}", exc_info=True)
            return None # 出错时返回 None 