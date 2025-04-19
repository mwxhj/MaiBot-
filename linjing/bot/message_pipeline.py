#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
消息处理管道模块，用于协调多个处理器按顺序处理消息。
"""

import asyncio
from typing import Dict, List, Any, Optional, Type, Union

from linjing.utils.logger import get_logger
from linjing.constants import ProcessorName

# 获取日志记录器
logger = get_logger(__name__)

class MessageContext:
    """消息上下文，包含处理过程中的状态和数据"""
    
    def __init__(self, message: Any, user_id: str, session_id: str):
        """
        初始化消息上下文
        
        Args:
            message: 原始消息
            user_id: 用户ID
            session_id: 会话ID
        """
        self.message = message  # 原始消息
        self.user_id = user_id  # 用户ID
        self.session_id = session_id  # 会话ID
        self.response = None  # 响应消息
        self.state = {}  # 处理状态，在各处理器之间传递数据
        self.error = None  # 错误信息
        self.history = []  # 对话历史
        self.emotion_state = {}  # 情绪状态
        self.memories = []  # 相关记忆

    def with_history(self, history: List[Any]) -> 'MessageContext':
        """
        设置对话历史
        
        Args:
            history: 对话历史消息列表
            
        Returns:
            当前上下文对象
        """
        self.history = history
        return self
    
    def with_emotion(self, emotion_state: Dict[str, float]) -> 'MessageContext':
        """
        设置情绪状态
        
        Args:
            emotion_state: 情绪状态字典
            
        Returns:
            当前上下文对象
        """
        self.emotion_state = emotion_state
        return self
    
    def with_memories(self, memories: List[Any]) -> 'MessageContext':
        """
        设置相关记忆
        
        Args:
            memories: 记忆列表
            
        Returns:
            当前上下文对象
        """
        self.memories = memories
        return self
    
    def set_state(self, key: str, value: Any) -> None:
        """
        设置状态值
        
        Args:
            key: 状态键
            value: 状态值
        """
        self.state[key] = value
    
    def get_state(self, key: str, default: Any = None) -> Any:
        """
        获取状态值
        
        Args:
            key: 状态键
            default: 默认值
            
        Returns:
            状态值
        """
        return self.state.get(key, default)
    
    def create_response(self, response: Any) -> None:
        """
        创建响应消息
        
        Args:
            response: 响应消息
        """
        self.response = response
    
    def set_error(self, error: Exception) -> None:
        """
        设置错误信息
        
        Args:
            error: 异常对象
        """
        self.error = error
        logger.error(f"消息处理错误: {str(error)}")


class Processor:
    """处理器基类，定义处理器接口"""
    
    def __init__(self, name: str, config: Dict[str, Any] = None):
        """
        初始化处理器
        
        Args:
            name: 处理器名称
            config: 处理器配置
        """
        self.name = name
        self.config = config or {}
        self.enabled = self.config.get("enabled", True)
        logger.debug(f"初始化处理器: {name}, 已启用: {self.enabled}")
    
    async def process(self, context: MessageContext) -> MessageContext:
        """
        处理消息上下文
        
        Args:
            context: 消息上下文
            
        Returns:
            处理后的消息上下文
        """
        if not self.enabled:
            return context
        
        try:
            return await self._process(context)
        except Exception as e:
            logger.error(f"处理器 {self.name} 执行错误: {str(e)}", exc_info=True)
            context.set_error(e)
            return context
    
    async def _process(self, context: MessageContext) -> MessageContext:
        """
        实际处理逻辑，子类需要实现
        
        Args:
            context: 消息上下文
            
        Returns:
            处理后的消息上下文
        """
        raise NotImplementedError("子类必须实现_process方法")
    
    def enable(self) -> None:
        """启用处理器"""
        self.enabled = True
        logger.debug(f"启用处理器: {self.name}")
    
    def disable(self) -> None:
        """禁用处理器"""
        self.enabled = False
        logger.debug(f"禁用处理器: {self.name}")


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