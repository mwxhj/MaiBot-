# MaiBot-/linjing/l3_processing_paths/path_c_simple.py
import asyncio
from typing import Dict, Any, Optional

# from loguru import logger # 如果需要日志记录
from linjing.utils.logger import get_logger # 或者使用项目统一的 logger

logger = get_logger(__name__)

# 定义 L3 输出队列类型 (占位符)
L3_OUTPUT_QUEUE_TYPE = asyncio.Queue # L3 输出 mind_info

class SimplePathCProcessor:
    """
    一个非常简单的 L3 Path C 处理器。
    接收来自 L2 的 dispatch_decision，生成一个固定的或基于简单规则的回复文本，
    并将其包装成简化的 mind_info 结构发送到 L4 输入队列。
    """
    def __init__(self,
                 input_queue: asyncio.Queue,      # L2->L3 队列 (l3_path_c_queue)
                 output_queue: L3_OUTPUT_QUEUE_TYPE, # L3->L4 队列 (l3_output_queue)
                 config: Optional[Dict[str, Any]] = None):
        self.input_queue = input_queue
        self.output_queue = output_queue
        self.config = config or {}
        self._running = False
        self._task: Optional[asyncio.Task] = None
        logger.info("SimplePathCProcessor 初始化完成。")

    async def start_processing(self):
        """启动处理循环。"""
        if self._running:
            logger.warning(f"{self.__class__.__name__} 已经在运行中。")
            return

        self._running = True
        self._task = asyncio.create_task(self._processing_loop(), name="SimplePathCProcessorLoop")
        logger.info(f"{self.__class__.__name__} 处理循环已启动。")
        try:
            await self._task
        except asyncio.CancelledError:
            logger.info(f"{self.__class__.__name__} 处理循环被取消。")
        except Exception as e:
            logger.error(f"{self.__class__.__name__} 处理循环异常终止: {e}", exc_info=True)
            self._running = False

    async def stop_processing(self):
        """停止处理循环。"""
        if not self._running or not self._task:
            logger.warning(f"{self.__class__.__name__} 没有在运行中。")
            return

        self._running = False
        if self._task:
            self._task.cancel()
            logger.info(f"正在停止 {self.__class__.__name__} 处理循环...")
            try:
                await asyncio.wait_for(self._task, timeout=5.0)
            except asyncio.CancelledError:
                logger.info(f"{self.__class__.__name__} 处理循环已成功取消。")
            except asyncio.TimeoutError:
                logger.warning(f"停止 {self.__class__.__name__} 循环超时。")
            except Exception as e:
                logger.error(f"停止 {self.__class__.__name__} 循环时发生错误: {e}", exc_info=True)
        self._task = None
        logger.info(f"{self.__class__.__name__} 处理循环已停止。")

    async def _processing_loop(self):
        """内部处理循环。"""
        while self._running:
            try:
                dispatch_decision: Dict[str, Any] = await self.input_queue.get()
                logger.debug(f"[{self.__class__.__name__}] 收到 Dispatch Decision: {dispatch_decision.get('processed_input', {}).get('message_id')}")

                # --- 简单的处理逻辑 (Path C) ---
                # 提取原始 assessment
                assessment = dispatch_decision.get("processed_input", {})
                message_id = assessment.get("message_id", "unknown")
                raw_text = assessment.get("raw_text", "")
                
                # 生成简单的回复 (可以更复杂，例如基于 decision_reason)
                reply_text = f"收到您的消息 (ID: {message_id})。这是来自 Path C 的简单回复。您的消息是：'{raw_text[:30]}...'"
                if "维护模式" in dispatch_decision.get("decision_reason", ""):
                     reply_text = "抱歉，我现在正在维护中，稍后再试吧。"

                # 构造简化的 mind_info
                mind_info = {
                    "reply_text": reply_text,
                    "processing_path": "path_c",
                    "originating_assessment_id": message_id
                    # 可以根据需要添加 L2 的决策信息等
                    # "decision_info": dispatch_decision
                }
                # --- 处理逻辑结束 ---

                # 将 mind_info 发送到输出队列 (L3 -> L4)
                try:
                    await self.output_queue.put(mind_info)
                    logger.info(f"[{self.__class__.__name__}] Mind Info (ID: {message_id}) 已发送到 L4 队列。")
                except asyncio.QueueFull:
                    logger.error(f"[{self.__class__.__name__}] L4 输入队列已满！Mind Info 可能丢失。")
                except Exception as e_put:
                    logger.error(f"[{self.__class__.__name__}] 将 Mind Info 发送到 L4 队列时出错: {e_put}", exc_info=True)

                # 标记输入队列任务完成
                self.input_queue.task_done()

            except asyncio.CancelledError:
                logger.info(f"[{self.__class__.__name__}] 处理循环被取消。")
                break
            except Exception as e:
                logger.error(f"[{self.__class__.__name__}] 处理循环中发生错误: {e}", exc_info=True)
                # 即使处理失败，也尝试标记完成，防止队列阻塞
                try:
                    self.input_queue.task_done()
                except ValueError:
                    pass 
                await asyncio.sleep(1.0) # 错误后休眠 