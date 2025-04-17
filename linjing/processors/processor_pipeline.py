#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
处理器管道模块，用于按顺序执行多个处理器。
处理器管道本身也是一个处理器，可以嵌套使用。
"""

import time
from typing import Any, Dict, List, Optional, Union, Set

from linjing.processors.base_processor import BaseProcessor, Processor
from linjing.processors.message_context import MessageContext
from linjing.utils.logger import get_logger

# 获取日志记录器
logger = get_logger(__name__)


class ProcessorPipeline(BaseProcessor):
    """
    处理器管道，按顺序执行多个处理器。
    管道本身也是一个处理器，可以嵌套使用。
    """
    
    name = "processor_pipeline"
    description = "处理器管道，按顺序执行多个处理器"
    version = "1.0.0"
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化处理器管道
        
        Args:
            config: 配置，可以包含预设的处理器列表
        """
        super().__init__(config)
        
        # 处理器列表
        self.processors: List[Processor] = []
        
        # 如果配置中包含处理器列表，则添加
        if config and "processors" in config:
            from linjing.processors.processor_registry import ProcessorRegistry
            
            processors_config = config.get("processors", {})
            for name, proc_config in processors_config.items():
                processor = ProcessorRegistry.get_processor(name, proc_config)
                if processor:
                    self.add_processor(processor)
    
    def add_processor(self, processor: Processor) -> None:
        """
        添加处理器到管道
        
        Args:
            processor: 处理器实例
        """
        self.processors.append(processor)
        logger.debug(f"处理器 {processor.get_name()} 已添加到管道")
    
    def add_processors(self, processors: List[Processor]) -> None:
        """
        批量添加处理器到管道
        
        Args:
            processors: 处理器实例列表
        """
        for processor in processors:
            self.add_processor(processor)
    
    def remove_processor(self, processor_name: str) -> bool:
        """
        从管道中移除处理器
        
        Args:
            processor_name: 处理器名称
            
        Returns:
            是否成功移除
        """
        for i, processor in enumerate(self.processors):
            if processor.get_name() == processor_name:
                self.processors.pop(i)
                logger.debug(f"处理器 {processor_name} 已从管道移除")
                return True
        
        logger.debug(f"处理器 {processor_name} 不在管道中")
        return False
    
    def get_processor(self, processor_name: str) -> Optional[Processor]:
        """
        获取管道中的处理器
        
        Args:
            processor_name: 处理器名称
            
        Returns:
            处理器实例或None
        """
        for processor in self.processors:
            if processor.get_name() == processor_name:
                return processor
        return None
    
    def get_processors(self) -> List[Processor]:
        """
        获取所有处理器
        
        Returns:
            处理器列表
        """
        return self.processors.copy()
    
    def enable_processor(self, processor_name: str) -> bool:
        """
        启用管道中的处理器
        
        Args:
            processor_name: 处理器名称
            
        Returns:
            是否成功启用
        """
        processor = self.get_processor(processor_name)
        if processor:
            processor.enable()
            return True
        return False
    
    def disable_processor(self, processor_name: str) -> bool:
        """
        禁用管道中的处理器
        
        Args:
            processor_name: 处理器名称
            
        Returns:
            是否成功禁用
        """
        processor = self.get_processor(processor_name)
        if processor:
            processor.disable()
            return True
        return False
    
    def clear(self) -> None:
        """清空管道"""
        self.processors.clear()
        logger.debug("处理器管道已清空")
    
    def reorder_processors(self, order: List[str]) -> bool:
        """
        重新排序处理器
        
        Args:
            order: 处理器名称列表，按新顺序排列
            
        Returns:
            是否成功重排序
        """
        if len(order) != len(self.processors):
            logger.error("处理器顺序列表长度与管道中的处理器数量不匹配")
            return False
        
        # 创建名称到处理器的映射
        processor_map = {p.get_name(): p for p in self.processors}
        
        # 检查所有处理器名称是否存在
        for name in order:
            if name not in processor_map:
                logger.error(f"找不到处理器: {name}")
                return False
        
        # 按新顺序重排处理器
        self.processors = [processor_map[name] for name in order]
        logger.debug(f"处理器管道已重新排序: {', '.join(order)}")
        
        return True
    
    async def process(self, context: MessageContext) -> MessageContext:
        """
        处理消息上下文，按顺序执行所有处理器
        
        Args:
            context: 消息上下文
            
        Returns:
            处理后的消息上下文
        """
        if not self.processors:
            logger.warning("处理器管道为空")
            return context
        
        logger.debug(f"开始处理管道，共 {len(self.processors)} 个处理器")
        start_time = time.time()
        
        current_context = context
        
        for i, processor in enumerate(self.processors):
            # 检查是否中止处理
            if current_context.aborted:
                logger.debug(f"处理中止于第 {i} 个处理器")
                break
            
            # 调用处理器
            logger.debug(f"执行处理器 {i+1}/{len(self.processors)}: {processor.get_name()}")
            try:
                current_context = await processor(current_context)
            except Exception as e:
                error_msg = f"处理器 {processor.get_name()} 执行出错: {str(e)}"
                logger.error(error_msg, exc_info=True)
                current_context.log_processor("ProcessorPipeline", error_msg)
                current_context.set_error(e)
                break
        
        # 计算总处理时间
        total_time = time.time() - start_time
        logger.debug(f"处理管道完成，总耗时: {total_time:.4f}s")
        
        # 标记处理完成
        current_context.set_processed()
        
        return current_context 