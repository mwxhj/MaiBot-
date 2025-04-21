# MaiBot-/linjing/l3_processing_paths/path_a_processor.py
import asyncio
from typing import Dict, Any, Optional

from linjing.utils.logger import get_logger
# 模拟依赖项导入 (实际应从相应模块导入)
# from linjing.llm.llm_interface import LLMInterface
# from linjing.prompts.prompt_assembler import PromptAssembler
from __main__ import MockLLMInterface as LLMInterface # 暂时从 main 导入 Mock
from __main__ import MockPromptAssembler as PromptAssembler # 暂时从 main 导入 Mock

logger = get_logger(__name__)

# 定义 L3 输出队列类型 (占位符)
L3_OUTPUT_QUEUE_TYPE = asyncio.Queue # L3 输出 mind_info

class PathAProcessor:
    """
    L3 Path A 处理器。
    接收来自 L2 的 dispatch_decision，调用 LLM 生成回复，
    并将结果包装成 mind_info 发送到 L4 输入队列。
    """
    def __init__(self,
                 input_queue: asyncio.Queue,           # L2->L3 队列 (l3_path_a_queue)
                 output_queue: L3_OUTPUT_QUEUE_TYPE,  # L3->L4 队列 (l3_output_queue)
                 llm_interface: LLMInterface,        # LLM 调用接口
                 prompt_assembler: PromptAssembler, # Prompt 组装器
                 config: Optional[Dict[str, Any]] = None):
        self.input_queue = input_queue
        self.output_queue = output_queue
        self.llm_interface = llm_interface
        self.prompt_assembler = prompt_assembler
        self.config = config or {}
        self._running = False
        self._task: Optional[asyncio.Task] = None
        logger.info("PathAProcessor 初始化完成。")

    async def start_processing(self):
        """启动处理循环。"""
        if self._running:
            logger.warning(f"{self.__class__.__name__} 已经在运行中。")
            return

        self._running = True
        self._task = asyncio.create_task(self._processing_loop(), name="PathAProcessorLoop")
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
                assessment = dispatch_decision.get("processed_input", {})
                message_id = assessment.get("message_id", "unknown")
                logger.debug(f"[{self.__class__.__name__}] 收到 Dispatch Decision: {message_id}")

                # --- Path A 处理逻辑 ---
                # 1. 准备 Prompt 上下文
                prompt_context = {
                    "raw_text": assessment.get("raw_text", ""),
                    "sender_info": assessment.get("sender_info", {}),
                    "basic_analysis": assessment.get("basic_analysis", {}),
                    "context_summary": assessment.get("context_summary", {}),
                    "decision_reason": dispatch_decision.get("decision_reason", "")
                    # 可以根据需要添加更多信息
                }

                # 2. 组装 Prompt
                prompt_key = "path_a.response_prompt" # 定义一个用于 Path A 的 Prompt key
                prompt = self.prompt_assembler.assemble(prompt_key, prompt_context)

                if not prompt:
                    logger.error(f"[{self.__class__.__name__}] 无法为消息 {message_id} 组装 Prompt (Key: {prompt_key})。跳过处理。")
                    self.input_queue.task_done()
                    continue

                # 3. 调用 LLM
                llm_model = dispatch_decision.get("target_resources", {}).get("llm_model", "default_llm") # 从决策获取目标模型
                llm_config = self.config.get("llm_config", {}).get(llm_model, {}) # 获取特定模型的配置

                logger.debug(f"[{self.__class__.__name__}] 调用 LLM (模型: {llm_model}) for message {message_id}...")
                try:
                    llm_reply_raw = await self.llm_interface.invoke(prompt, llm_model, llm_config)
                    # TODO: 解析 LLM 回复，可能需要更复杂的逻辑
                    reply_text = llm_reply_raw # 假设 MockLLM 返回的是可以直接使用的文本
                    logger.debug(f"[{self.__class__.__name__}] 从 LLM 收到回复: {reply_text[:50]}...")
                except Exception as llm_e:
                    logger.error(f"[{self.__class__.__name__}] 调用 LLM 时出错 for message {message_id}: {llm_e}", exc_info=True)
                    # 可以在这里生成一个错误回复的 mind_info
                    reply_text = "抱歉，处理您的请求时遇到了内部错误。"

                # 4. 构造 mind_info
                mind_info = {
                    "reply_text": reply_text,
                    "processing_path": "path_a",
                    "originating_assessment_id": message_id,
                    "llm_metadata": {
                        "model_used": llm_model,
                        "prompt_key": prompt_key,
                        # "tokens_used": ... # 如果 LLM 接口返回此信息
                    }
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

                self.input_queue.task_done()

            except asyncio.CancelledError:
                logger.info(f"[{self.__class__.__name__}] 处理循环被取消。")
                break
            except Exception as e:
                logger.error(f"[{self.__class__.__name__}] 处理循环中发生错误: {e}", exc_info=True)
                try:
                    self.input_queue.task_done()
                except ValueError:
                    pass
                await asyncio.sleep(1.0) 