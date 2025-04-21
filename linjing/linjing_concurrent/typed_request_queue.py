from loguru import logger # 确保 logger 已导入
import asyncio
import time
from .constants import EventType # 假设 EventType 在同目录的 constants.py

class TypedRequestQueue(Generic[T, R]):
    # ... (__init__ 等) ...

    async def _process_request(self, task: RequestTask[T, R]) -> None:
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

            end_time = time.monotonic()
            processing_time = end_time - task.started_at
            self.logger.info(f"任务 {task.request_id} 处理完成，耗时: {processing_time:.4f} 秒。结果: {result is not None}")
            self.logger.debug(f"任务 {task.request_id} 结果详情: {result}")

            # 标记任务完成并将结果存储起来
            task.mark_completed(result)

            # --- 添加事件发布逻辑 (保持不变) ---
            if self.event_bus and result:
                try:
                    send_metadata = task.metadata.get("send_metadata") if task.metadata else None
                    if send_metadata:
                        adapter = send_metadata.get("adapter")
                        original_message = send_metadata.get("original_message")
                        platform = send_metadata.get("platform", "Unknown") # 获取平台信息

                        if adapter and original_message:
                            event_data = {
                                "adapter": adapter,
                                "original_message": original_message,
                                "reply_content": result,
                                "platform": platform # 传递平台信息
                            }
                            await self.event_bus.publish(EventType.SEND_MESSAGE_REQUEST, event_data)
                            self.logger.info(f"任务 {task.request_id} 结果非空，已发布 SEND_MESSAGE_REQUEST 事件到平台 {platform}")
                        else:
                            self.logger.warning(f"任务 {task.request_id} 的元数据缺少 adapter 或 original_message，无法发布发送事件。Metadata: {send_metadata}")
                    else:
                        self.logger.warning(f"任务 {task.request_id} 缺少 send_metadata，无法发布发送事件。")
                except Exception as e:
                    self.logger.error(f"发布 SEND_MESSAGE_REQUEST 事件时出错 (任务 {task.request_id}): {e}", exc_info=True)
            # --- 事件发布逻辑结束 ---

        except asyncio.CancelledError:
            self.logger.warning(f"任务 {task.request_id} 被取消 (可能由于超时)。")
            task.mark_failed(TimeoutError("Task timed out and was cancelled"))
        except Exception as e:
            self.logger.error(f"处理任务 {task.request_id} 时发生错误: {e}", exc_info=True)
            # 标记任务失败并存储异常信息
            task.mark_failed(e)
        finally:
            # 减少活跃任务计数器
            self.active_tasks -= 1
            self.logger.debug(f"任务 {task.request_id} 处理结束，当前活跃任务数: {self.active_tasks}")
            # 尝试处理下一个任务
            self._try_process_next()
            
    # ... (其余代码) ... 