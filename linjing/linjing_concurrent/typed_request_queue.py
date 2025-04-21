from loguru import logger # 确保 logger 已导入
import asyncio
import time
from linjing.constants import EventType # 从项目根目录的 constants 导入
from typing import Generic, TypeVar, Callable, Awaitable, Optional, Any, Dict, List, Set # 补全 typing 导入

# 定义类型变量用于泛型
T = TypeVar('T')  # 请求类型
R = TypeVar('R')  # 结果类型

# 假设 RequestTask 在此文件或已导入
# from .request_task import RequestTask # 或者类似的导入

class TypedRequestQueue(Generic[T, R]):
    # ... (__init__ 等) ...

    async def _process_request(self, task: 'RequestTask[T, R]') -> None: # 使用字符串避免前向引用问题
        """处理单个请求任务"""
        try:
            # --- 添加日志：记录开始处理和 data 信息 ---
            logger.debug(
                f"TypedQueue {self.queue_type.value}: Processing task {task.request_id}. "
                f"Preparing to call processor for data type: {type(task.data)}, "
                f"value: {str(task.data)[:200]}..."
            )
            # --- 日志结束 ---
            
            self.active_tasks += 1
            task.mark_started()
            
            # 运行实际的处理函数 (传递 task.data)
            result = await task.processor(task.data) 

            # --- 添加日志：确认 processor 返回后协程恢复 --- 
            logger.debug(f"Task {task.request_id}: Processor awaited and returned. Coroutine resumed. Result type: {type(result)}")
            # --- 日志结束 --- 

            end_time = time.monotonic()
            processing_time = end_time - task.started_at
            logger.info(f"任务 {task.request_id} 处理完成，耗时: {processing_time:.4f} 秒。结果: {result is not None}")
            logger.debug(f"任务 {task.request_id} 结果详情: {str(result)[:200]}...")

            # 标记任务完成并将结果存储起来
            task.mark_completed(result)

            # --- 添加日志：检查事件发布条件 --- 
            logger.debug(f"Task {task.request_id} completed. Result type: {type(result)}, Result empty/None: {not result}")
            logger.debug(f"Task {task.request_id} metadata: {task.metadata}")
            # 假设 self.event_bus 在初始化时设置
            logger.debug(f"Event bus available: {hasattr(self, 'event_bus') and self.event_bus is not None}") 
            # --- 日志结束 --- 

            # --- 修改：添加更详细的事件发布日志 --- 
            if hasattr(self, 'event_bus') and self.event_bus and result: 
                logger.debug(f"Task {task.request_id}: Result is not empty, attempting to publish send event.")
                try:
                    logger.debug(f"Task {task.request_id}: Entering publish try block.")
                    send_metadata = task.metadata.get("send_metadata") if task.metadata else None
                    logger.debug(f"Task {task.request_id}: Extracted send_metadata: {send_metadata}")
                    
                    if send_metadata:
                        logger.debug(f"Task {task.request_id}: send_metadata found.")
                        adapter = send_metadata.get("adapter")
                        original_message = send_metadata.get("original_message")
                        platform = send_metadata.get("platform", "Unknown") # 获取平台信息
                        logger.debug(f"Task {task.request_id}: Extracted adapter: {adapter is not None}, original_message: {original_message is not None}, platform: {platform}")

                        if adapter and original_message:
                            logger.debug(f"Task {task.request_id}: adapter and original_message found, preparing event data.")
                            event_data = {
                                "adapter": adapter,
                                "original_message": original_message,
                                "reply_content": result,
                                "platform": platform
                            }
                            await self.event_bus.publish(EventType.SEND_MESSAGE_REQUEST, event_data)
                            logger.info(f"任务 {task.request_id} 结果非空，已成功发布 SEND_MESSAGE_REQUEST 事件到平台 {platform}") # 修改成功日志
                        else:
                            logger.warning(f"任务 {task.request_id}: send_metadata 中缺少 adapter 或 original_message，无法发布发送事件。Adapter: {adapter is not None}, Message: {original_message is not None}")
                    else:
                        logger.warning(f"任务 {task.request_id}: 缺少 send_metadata，无法发布发送事件。")
                except Exception as e:
                    logger.error(f"发布 SEND_MESSAGE_REQUEST 事件时出错 (任务 {task.request_id}): {e}", exc_info=True)
            elif not result:
                 logger.debug(f"Task {task.request_id}: Result is empty or None, skipping send event publish.")
            # --- 事件发布逻辑修改结束 --- 

        except asyncio.CancelledError:
            logger.warning(f"任务 {task.request_id} 被取消 (可能由于超时)。")
            # 标记任务失败并存储异常信息，确保使用正确的错误类型
            # task.mark_failed(TimeoutError("Task timed out and was cancelled")) # 可能需要 asyncio.TimeoutError
            task.mark_failed(asyncio.TimeoutError(f"Task {task.request_id} timed out and was cancelled"))
        except Exception as e:
            logger.error(f"处理任务 {task.request_id} 时发生错误: {e}", exc_info=True)
            # 标记任务失败并存储异常信息
            task.mark_failed(e)
        finally:
            # 减少活跃任务计数器
            if hasattr(self, 'active_tasks') and self.active_tasks > 0: # 确保属性存在且大于0
                self.active_tasks -= 1
            logger.debug(f"任务 {task.request_id} 处理结束，当前活跃任务数: {getattr(self, 'active_tasks', 'N/A')}") # 使用 getattr 防御
            # 尝试处理下一个任务 (确保 _try_process_next 存在)
            if hasattr(self, '_try_process_next') and callable(self._try_process_next):
                self._try_process_next()
            else:
                 logger.warning(f"Method '_try_process_next' not found or not callable in {self.__class__.__name__}")

    # ... (其余代码，需要确保 RequestTask, active_tasks, _try_process_next 等存在且定义正确) ... 