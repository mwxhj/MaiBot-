# linjing/l1_fast_sense/input_buffer.py
import asyncio
from typing import List, Dict, Any

from linjing.utils.logger import get_logger

logger = get_logger(__name__)

class InputBuffer:
    """
    接收、缓冲并可能批处理来自适配器的原始事件。
    """
    def __init__(self, max_size: int = 0, batch_size: int = 1, batch_timeout: float = 0.1):
        """
        初始化 InputBuffer。

        Args:
            max_size: 队列的最大容量 (0 表示无限)。
            batch_size: 批处理大小 (暂未使用，但可用于未来扩展)。
            batch_timeout: 批处理超时 (暂未使用，但可用于未来扩展)。
        """
        self._queue = asyncio.Queue(maxsize=max_size)
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        logger.info(f"InputBuffer 初始化完成，最大容量: {max_size if max_size > 0 else '无限'}")

    async def put(self, raw_event: Dict[str, Any]):
        """
        将单个原始事件放入缓冲队列。
        这是供适配器调用的主要方法。

        Args:
            raw_event: 从适配器接收到的原始事件字典。

        Raises:
            asyncio.QueueFull: 如果队列已满且 max_size > 0。
        """
        try:
            await self._queue.put(raw_event)
            logger.trace(f"事件已放入 InputBuffer 队列: {raw_event.get('post_type')}")
        except asyncio.QueueFull:
            logger.error("InputBuffer 队列已满！事件无法放入。")
            raise # 重新抛出异常，让调用方知道失败了

    async def get(self) -> Dict[str, Any]:
        """
        从队列中获取单个原始事件。
        这是供 L1 处理器 (如 FastSenseProcessor) 消费事件的主要方法。
        """
        try:
            event = await self._queue.get()
            self._queue.task_done() # 标记任务完成
            logger.trace(f"事件已从 InputBuffer 队列取出: {event.get('post_type')}")
            return event
        except Exception as e:
            logger.error(f"从 InputBuffer 获取事件时出错: {e}", exc_info=True)
            raise # 重新抛出，以便上层处理

    # TODO: 可以根据需要实现 get_batch() 方法，用于批处理
    # async def get_batch(self) -> List[Dict[str, Any]]:
    #     """获取一批事件 (需要实现批处理逻辑)"""
    #     pass

    def qsize(self) -> int:
        """返回队列中当前的项数。"""
        return self._queue.qsize()

    def empty(self) -> bool:
        """如果队列为空则返回 True。"""
        return self._queue.empty() 