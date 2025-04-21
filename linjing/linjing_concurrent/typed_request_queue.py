from loguru import logger # 确保 logger 已导入
import asyncio
import time
import uuid # 需要导入 uuid
from enum import Enum # 需要导入 Enum
from linjing.constants import EventType # 从项目根目录的 constants 导入
from typing import Generic, TypeVar, Callable, Awaitable, Optional, Any, Dict, List, Set # 补全 typing 导入

# 定义类型变量用于泛型
T = TypeVar('T')  # 请求类型
R = TypeVar('R')  # 结果类型

# 假设 RequestTask 在此文件或已导入
# from .request_task import RequestTask # 或者类似的导入

# --- 添加 TaskStatus 枚举 (如果未在别处定义) ---
class TaskStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
# --- TaskStatus 定义结束 ---

# --- 添加 ProcessingTask 数据类 (如果未在别处定义) ---
from dataclasses import dataclass, field

@dataclass
class ProcessingTask(Generic[T, R]):
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    processor: Callable[[T], Awaitable[R]] = None
    data: T = None
    send_metadata: Dict[str, Any] = field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[R] = None
    error: Optional[Exception] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
# --- ProcessingTask 定义结束 ---

# --- 获取 RequestQueueType (临时，如果无法导入) ---
try:
    from .queue_manager import RequestQueueType
except ImportError:
    logger.warning("Could not import RequestQueueType from .queue_manager, using temporary Enum.")
    class RequestQueueType(Enum):
        DEFAULT = "default"
        MESSAGE = "message"
        API = "api"
        DATABASE = "database"
        MEDIA = "media"
        FILE = "file"
        NETWORK = "network"
        SESSION = "session"
# --- RequestQueueType 获取结束 ---

class TypedRequestQueue(Generic[T, R]):
    # ... (__init__ 等) ...

    def __init__(
        self,
        queue_type: RequestQueueType,
        event_bus: Any, # 使用 Any 或具体的 EventBus 类型
        max_size: int = 0, # 0 表示无限
        num_workers: int = 1,
        default_timeout: float = 60.0 # 添加默认超时参数
    ):
        self.queue_type = queue_type
        self.event_bus = event_bus
        self.max_size = max_size
        self.num_workers = num_workers
        self.default_timeout = default_timeout # 保存默认超时

        self.queue = asyncio.Queue(maxsize=self.max_size)
        self._workers: List[asyncio.Task] = []
        self._semaphore = asyncio.Semaphore(num_workers) # 用于控制并发
        self.active_tasks = 0 # 用于跟踪活跃任务（如果有用）
        self.tasks_processed = 0
        self.tasks_failed = 0
        self.tasks_timed_out = 0
        self.tasks_cancelled = 0
        self.last_activity_time = time.monotonic() # 记录最后活动时间
        self.running = False # 标记队列是否正在运行

        logger.info(f"TypedQueue {self.queue_type.value} initialized: max_size={max_size}, workers={num_workers}")

    async def _process_request(self, task: ProcessingTask) -> None: # 参数类型修正
        """处理单个请求任务"""
        logger.debug(f"--- TypedRequestQueue._process_request START --- Task ID: {task.task_id}, Data type: {type(task.data)}, Data value: {str(task.data)[:100]}...")
        start_time = time.monotonic()
        task.started_at = start_time # 记录开始时间
        result = None
        # self.active_tasks += 1 # 移动到调用者处或使用信号量管理
        try:
            # 执行处理器函数
            logger.debug(f"Task {task.task_id}: Awaiting processor {getattr(task.processor, '__name__', 'N/A')}")
            # --- 使用 asyncio.wait_for 添加超时控制 ---
            
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

    async def _worker(self, worker_id: int):
        """工作协程，从队列中获取并处理任务。"""
        logger.info(f"Worker {worker_id} for queue type {self.queue_type} starting.")
        while True:
            task = None # 初始化
            try:
                task = await self.queue.get() # 从队列获取任务
                logger.debug(f"Worker {worker_id}: Got task from queue. Task ID: {task.task_id}, Data: {task.data}") # 新增日志
                
                # 增加 Semaphore 获取
                logger.debug(f"Worker {worker_id}: Attempting to acquire semaphore (current value: {self._semaphore._value})")
                async with self._semaphore:
                    logger.debug(f"Worker {worker_id}: Semaphore acquired. Processing task {task.task_id}")
                    await self._process_request(task)
                    logger.debug(f"Worker {worker_id}: Finished processing task {task.task_id}. Releasing semaphore.")
                
                # 任务处理完毕后，通知队列
                self.queue.task_done()
                logger.debug(f"Worker {worker_id}: Task {task.task_id} marked as done.")

            except asyncio.CancelledError:
                logger.info(f"Worker {worker_id} received cancellation request. Exiting.")
                break
            except Exception as e:
                # --- 新增：更详细的异常日志 --- 
                task_id_info = f"task {task.task_id}" if task else "an unknown task"
                logger.error(f"Worker {worker_id}: Error processing {task_id_info}: {e}", exc_info=True)
                # 如果任务存在，可能需要标记为失败或重试
                if task:
                    self.queue.task_done() # 确保即使出错也调用 task_done
                    logger.warning(f"Worker {worker_id}: Marked errored task {task.task_id} as done to prevent queue blocking.")
                    # 这里可以添加逻辑将任务标记为失败，或者放入重试队列
                # 短暂休眠以避免快速失败循环
                await asyncio.sleep(1)
        logger.info(f"Worker {worker_id} for queue type {self.queue_type} stopped.")

    async def start_workers(self):
        """启动工作协程"""
        if self.running:
            logger.warning(f"Queue {self.queue_type.value} workers already running.")
            return
        self.running = True
        self._workers = [
            asyncio.create_task(self._worker(i)) for i in range(self.num_workers)
        ]
        logger.info(f"Started {self.num_workers} workers for queue {self.queue_type.value}")

    async def stop_workers(self):
        """停止工作协程"""
        if not self.running:
            logger.warning(f"Queue {self.queue_type.value} workers not running.")
            return
        self.running = False
        logger.info(f"Stopping workers for queue {self.queue_type.value}...")
        for worker in self._workers:
            if not worker.done():
                worker.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers = []
        logger.info(f"Workers for queue {self.queue_type.value} stopped.")

    async def add_task(
        self,
        processor: Callable[[T], Awaitable[R]],
        data: T,
        send_metadata: Dict[str, Any]
    ) -> ProcessingTask:
        """添加任务到队列"""
        task = ProcessingTask(
            processor=processor,
            data=data,
            send_metadata=send_metadata
        )
        await self.queue.put(task)
        self.last_activity_time = time.monotonic()
        logger.debug(f"Task {task.task_id} added to queue {self.queue_type.value}. Queue size: {self.queue.qsize()}")
        return task

    def get_status(self) -> Dict[str, Any]:
         """获取队列状态"""
         return {
             "queue_type": self.queue_type.value,
             "max_size": self.max_size,
             "num_workers": self.num_workers,
             "queue_size": self.queue.qsize(),
             "running": self.running,
             "processing": self.active_tasks, # 使用 active_tasks 或 semaphore._value
             "tasks_processed": self.tasks_processed,
             "tasks_failed": self.tasks_failed,
             "tasks_timed_out": self.tasks_timed_out,
             "tasks_cancelled": self.tasks_cancelled,
             "last_activity": self.last_activity_time,
         }

    def is_idle(self, idle_threshold: float) -> bool:
         """检查队列是否空闲"""
         return (time.monotonic() - self.last_activity_time > idle_threshold and
                 self.queue.qsize() == 0 and
                 self.active_tasks == 0)

    # ... (其余代码，需要确保 RequestTask, active_tasks, _try_process_next 等存在且定义正确) ... 