#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
消息处理管道模块，用于协调多个处理器按顺序处理消息。
"""

import asyncio
from typing import Dict, List, Any, Optional, Type, Union

from linjing.utils.logger import get_logger
from linjing.constants import ProcessorName
# 导入正确的 MessageContext 和 Processor 基类
from linjing.processors.message_context import MessageContext
from linjing.processors.base_processor import BaseProcessor as Processor # 使用别名

# 获取日志记录器
logger = get_logger(__name__)

# 移除了此文件中冗余的 MessageContext 和 Processor 类定义
class MessagePipeline:
    """
    消息处理管道，按顺序协调多个处理器处理消息
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        初始化消息处理管道
        
        Args:
            config: 管道配置
        """
        self.config = config or {}
        self.processors: List[Processor] = []
        logger.debug("初始化消息处理管道")
    
    def add_processor(self, processor: Processor) -> None:
        """
        添加处理器
        
        Args:
            processor: 处理器对象
        """
        self.processors.append(processor)
        logger.debug(f"添加处理器: {processor.name}")
    
    def add_processors(self, processors: List[Processor]) -> None:
        """
        添加多个处理器
        
        Args:
            processors: 处理器对象列表
        """
        for processor in processors:
            self.add_processor(processor)
    
    def get_processor(self, name: str) -> Optional[Processor]:
        """
        获取指定名称的处理器
        
        Args:
            name: 处理器名称
            
        Returns:
            处理器对象或None
        """
        for processor in self.processors:
            if processor.name == name:
                return processor
        return None
    
    def remove_processor(self, name: str) -> bool:
        """
        移除指定名称的处理器
        
        Args:
            name: 处理器名称
            
        Returns:
            是否成功移除
        """
        for i, processor in enumerate(self.processors):
            if processor.name == name:
                del self.processors[i]
                logger.debug(f"移除处理器: {name}")
                return True
        return False
    
    def get_processors(self) -> List[Processor]:
        """
        获取所有处理器
        
        Returns:
            处理器列表
        """
        return self.processors
    
    async def process(self, context: MessageContext) -> MessageContext:
        """
        处理消息上下文
        
        Args:
            context: 消息上下文
            
        Returns:
            处理后的消息上下文
        """
        if not self.processors:
            logger.warning("消息管道中没有处理器")
            return context
        
        logger.debug(f"开始处理消息: {context.user_id}, {context.session_id}")
        
        current_context = context
        
        # 按顺序执行处理器
        for processor in self.processors:
            # 如果前面的处理器设置了错误或响应，则停止处理
            if current_context.error is not None or current_context.response is not None:
                break
            
            logger.debug(f"执行处理器: {processor.name}")
            current_context = await processor.process(current_context)

            # **新增：检查 should_reply 状态 (来自 ReadAir)，如果为 False 则中止管道**
            should_reply = current_context.get_state("should_reply", True) # 默认为 True
            if not should_reply:
                logger.info(f"处理器 {processor.name} (ReadAir) 判断不应回复，中止消息处理管道。")
                # 清除可能已生成的 response，确保最终不回复
                current_context.response = None
                break # 退出处理器循环

            # **新增：检查 is_willing_to_reply 状态 (来自 WillingnessChecker)，如果为 False 则中止管道**
            # 这个检查只在 willingness_checker 处理器执行后才有意义
            if processor.name == "willingness_checker":
                 is_willing = current_context.get_state("is_willing_to_reply", True) # 默认为 True
                 if not is_willing:
                      logger.info(f"处理器 {processor.name} 判断不愿回复，中止消息处理管道。")
                      # 清除可能已生成的 response，确保最终不回复
                      current_context.response = None
                      break # 退出处理器循环
        
        # 如果所有处理器执行完毕但没有生成响应，且没有错误
        if current_context.response is None and current_context.error is None:
            logger.warning("所有处理器执行完毕，但没有生成响应")
        
        logger.debug(f"消息处理完成: {context.user_id}, {context.session_id}")
        return current_context
    
    def enable_processor(self, name: str) -> bool:
        """
        启用指定名称的处理器
        
        Args:
            name: 处理器名称
            
        Returns:
            是否成功启用
        """
        processor = self.get_processor(name)
        if processor:
            processor.enable()
            return True
        return False
    
    def disable_processor(self, name: str) -> bool:
        """
        禁用指定名称的处理器
        
        Args:
            name: 处理器名称
            
        Returns:
            是否成功禁用
        """
        processor = self.get_processor(name)
        if processor:
            processor.disable()
            return True
        return False
    
    def reorder_processors(self, order: List[str]) -> bool:
        """
        重新排序处理器
        
        Args:
            order: 处理器名称列表，按新顺序排列
            
        Returns:
            是否成功重排序
        """
        # 检查所有名称是否都存在
        current_names = {p.name for p in self.processors}
        if not all(name in current_names for name in order):
            return False
        
        # 检查是否包含所有处理器
        if len(order) != len(self.processors):
            return False
        
        # 创建新顺序
        new_processors = []
        for name in order:
            for p in self.processors:
                if p.name == name:
                    new_processors.append(p)
                    break
        
        # 更新处理器列表
        self.processors = new_processors
        logger.debug(f"重新排序处理器: {order}")
        return True 