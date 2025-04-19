#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
林静机器人主类模块，作为整个机器人的核心控制器。
"""

import os
import sys
import asyncio
import importlib
import inspect
from typing import Dict, List, Any, Optional, Tuple, Type, Callable

from linjing.utils.logger import get_logger
from linjing.constants import EventType, ProcessorName
from linjing.bot.event_bus import EventBus
from linjing.bot.personality import Personality
from linjing.bot.message_pipeline import MessagePipeline
from linjing.processors.message_context import MessageContext
from linjing.processors.base_processor import BaseProcessor as Processor
from linjing.storage.database import DatabaseManager
from linjing.storage.vector_db_manager_factory import VectorDBManagerFactory

# 获取日志记录器
logger = get_logger(__name__)

class LinjingBot:
    """林静机器人主类，负责协调各个组件"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化机器人主类
        
        Args:
            config: 全局配置
        """
        self.config = config
        self.event_bus = EventBus()
        self.message_pipeline = MessagePipeline(config.get("processors"))
        self.personality = None
        self.adapters = {}
        self.processors = {}
        self.storage_manager = None
        self.memory_manager = None
        self.emotion_manager = None
        self.llm_manager = None
        self.plugin_manager = None
        self.running = False
        
        # 注册事件处理器
        self._register_event_handlers()
    
    async def initialize(self) -> bool:
        """
        初始化机器人组件
        
        Returns:
            初始化是否成功
        """
        logger.info("正在初始化林静机器人...")
        
        try:
            # 初始化人格系统
            await self._init_personality()
            
            # 初始化LLM管理器
            await self._init_llm_manager()
            
            # 初始化存储系统
            await self._init_storage()
            
            # 初始化记忆系统
            await self._init_memory()
            
            # 初始化情绪系统
            await self._init_emotion()
            
            # 初始化处理器
            await self._init_processors()
            
            # 初始化适配器
            await self._init_adapters()
            
            # 初始化插件系统
            await self._init_plugins()
            
            logger.info("林静机器人初始化完成")
            return True
            
        except Exception as e:
            logger.error(f"初始化失败: {str(e)}", exc_info=True)
            return False
    
    async def start(self) -> None:
        """启动机器人及其组件"""
        if self.running:
            logger.warning("机器人已经在运行")
            return
        
        logger.info("正在启动林静机器人...")
        
        try:
            # 启动所有适配器
            for adapter_name, adapter in self.adapters.items():
                if hasattr(adapter, 'connect') and callable(adapter.connect):
                    logger.info(f"正在连接适配器: {adapter_name}")
                    await adapter.connect()
            
            self.running = True
            
            # 发布启动事件
            await self.event_bus.publish(EventType.BOT_STARTED, {"bot": self})
            
            logger.info("林静机器人启动完成")
            
        except Exception as e:
            logger.error(f"启动失败: {str(e)}", exc_info=True)
            raise
    
    async def stop(self) -> None:
        """停止机器人及其组件"""
        if not self.running:
            logger.warning("机器人没有运行")
            return
        
        logger.info("正在停止林静机器人...")
        
        try:
            # 发布停止事件
            await self.event_bus.publish(EventType.BOT_STOPPED, {"bot": self})
            
            # 断开所有适配器
            for adapter_name, adapter in self.adapters.items():
                if hasattr(adapter, 'disconnect') and callable(adapter.disconnect):
                    logger.info(f"正在断开适配器: {adapter_name}")
                    await adapter.disconnect()
            
            self.running = False
            logger.info("林静机器人停止完成")
            
        except Exception as e:
            logger.error(f"停止失败: {str(e)}", exc_info=True)
            raise
    
    async def handle_message(self, message: Any) -> Optional[Any]:
        """
        处理接收到的消息
        
        Args:
            message: 消息对象
            
        Returns:
            处理后的响应消息
        """
        if not self.running:
            logger.warning("机器人没有运行，无法处理消息")
            return None
        
        # 创建消息上下文
        context = MessageContext(
            message=message,
            user_id=message.get_user_id() if hasattr(message, 'get_user_id') else str(message),
            session_id=message.get_session_id() if hasattr(message, 'get_session_id') else "default"
        )
        
        # 获取对话历史
        if self.memory_manager:
            history = await self.memory_manager.get_conversation_history(
                context.user_id, 
                limit=self.config.get("memory", {}).get("max_conversation_history", 10)
            )
            context.with_history(history)
        
        # 获取情绪状态
        if self.emotion_manager:
            emotion = await self.emotion_manager.get_emotion(context.user_id)
            context.with_emotion(emotion.to_dict() if hasattr(emotion, 'to_dict') else emotion)
        
        # 发布消息接收事件
        await self.event_bus.publish(
            EventType.MESSAGE_RECEIVED, 
            {"message": message, "context": context}
        )
        
        # 通过消息管道处理消息
        result_context = await self.message_pipeline.process(context)
        
        # 从处理后的上下文中获取最终回复
        final_reply = result_context.get_state("reply")

        # 存储对话到记忆 (分别存储用户消息和机器人回复)
        if self.memory_manager:
            # 存储用户消息
            try:
                user_content = message.extract_plain_text() if hasattr(message, 'extract_plain_text') else str(message)
                await self.memory_manager.add_conversation_memory(
                    user_id=context.user_id,
                    session_id=context.session_id,
                    content=user_content,
                    role="user"
                    # metadata 可以从 message 对象中提取，如果需要的话
                )
            except Exception as e:
                logger.error(f"存储用户消息到记忆失败: {e}", exc_info=True)

            # 存储机器人回复 (如果存在)
            if final_reply and hasattr(final_reply, 'extract_plain_text'):
                 try:
                    bot_content = final_reply.extract_plain_text()
                    await self.memory_manager.add_conversation_memory(
                        user_id=context.user_id,
                        session_id=context.session_id,
                        content=bot_content,
                        role="assistant" # 或者 "bot"
                    )
                 except Exception as e:
                     logger.error(f"存储机器人回复到记忆失败: {e}", exc_info=True)

        # 更新情绪状态
        if final_reply and self.emotion_manager:
            # 假设从上下文中提取情绪因素
            emotion_factors = result_context.get_state("emotion_factors", {})
            await self.emotion_manager.update_emotion(context.user_id, emotion_factors)

        # 发布消息发送事件
        if final_reply:
            await self.event_bus.publish(
                EventType.MESSAGE_SENT,
                {"message": final_reply, "context": result_context}
            )

        return final_reply
    
    def get_adapter(self, name: str) -> Optional[Any]:
        """
        获取指定名称的适配器
        
        Args:
            name: 适配器名称
            
        Returns:
            适配器对象或None
        """
        return self.adapters.get(name)
    
    def get_processor(self, name: str) -> Optional[Processor]:
        """
        获取指定名称的处理器
        
        Args:
            name: 处理器名称
            
        Returns:
            处理器对象或None
        """
        return self.message_pipeline.get_processor(name)
    
    async def _init_personality(self) -> None:
        """初始化人格系统"""
        logger.info("正在初始化人格系统...")
        
        personality_config = self.config.get("personality", {})
        self.personality = Personality(
            traits=personality_config.get("traits"),
            interests=personality_config.get("interests"),
            values=personality_config.get("values"),
            preferences=personality_config.get("preferences")
        )
        
        logger.debug(f"人格特质: {self.personality.traits}")
    
    async def _init_llm_manager(self) -> None:
        """初始化LLM管理器"""
        logger.info("正在初始化LLM管理器...")
        
        # 导入LLM管理器
        try:
            from linjing.llm.llm_manager import LLMManager
            # 传递完整的配置字典，而不是仅仅 llm 部分
            self.llm_manager = LLMManager(self.config)
            await self.llm_manager.initialize()
        except ImportError as e:
            logger.error(f"LLM管理器导入失败: {str(e)}")
            raise
    
    async def _init_storage(self) -> None:
        """初始化存储系统"""
        logger.info("正在初始化存储系统...")
        
        # 导入存储管理器
        try:
            from linjing.storage.database import DatabaseManager
            
            # 数据库管理器
            self.storage_manager = DatabaseManager(
                self.config.get("storage", {}).get("database", {})
            )
            await self.storage_manager.connect()
            
            # 向量数据库管理器
            self.vector_db_manager = VectorDBManagerFactory.create(
                self.config.get("storage", {}).get("vector_db", {})
            )
            await self.vector_db_manager.connect()
            
        except ImportError as e:
            logger.error(f"存储系统导入失败: {str(e)}")
            raise
    
    async def _init_memory(self) -> None:
        """初始化记忆系统"""
        logger.info("正在初始化记忆系统...")
        
        # 导入记忆管理器
        try:
            from linjing.memory.memory_manager import MemoryManager
            
            # 创建记忆管理器
            memory_config = self.config.get("memory", {})
            
            # 确保vector_db配置是字典而不是字符串
            vector_db_config = self.config.get("storage", {}).get("vector_db", {})
            if not isinstance(vector_db_config, dict):
                vector_db_config = {}
                
            # 在配置中添加向量数据库配置
            memory_config["vector_db"] = vector_db_config
            
            # 在配置中添加数据库路径
            memory_config["db_path"] = self.config.get("storage", {}).get("db_path", "data/database.db")
            
            self.memory_manager = MemoryManager(config=memory_config)
            
            # 初始化记忆管理器
            await self.memory_manager.initialize()
            
        except ImportError as e:
            logger.error(f"记忆系统导入失败: {str(e)}")
            raise
    
    async def _init_emotion(self) -> None:
        """初始化情绪系统"""
        logger.info("正在初始化情绪系统...")
        
        # 导入情绪管理器
        try:
            from linjing.emotion.emotion_manager import EmotionManager
            
            # 创建情绪管理器
            self.emotion_manager = EmotionManager(
                config=self.config.get("emotion", {}),
                db_manager=self.storage_manager
            )
            
            # 初始化情绪管理器
            await self.emotion_manager.initialize_tables()
            
        except ImportError as e:
            logger.error(f"情绪系统导入失败: {str(e)}")
            raise
    
    async def _init_processors(self) -> None:
        """初始化处理器"""
        logger.info("正在初始化处理器...")
        
        # 获取处理器配置
        processor_configs = self.config.get("processors", {})
        pipeline_order = processor_configs.get("pipeline", [
            ProcessorName.READ_AIR,
            ProcessorName.THOUGHT_GENERATOR,
            ProcessorName.RESPONSE_COMPOSER
        ])
        
        # 导入并初始化处理器
        for name in pipeline_order:
            try:
                processor_config = processor_configs.get(name, {"enabled": True})
                
                # 根据处理器名称导入相应模块
                if name == ProcessorName.READ_AIR:
                    from linjing.processors.read_air import ReadAirProcessor
                    processor = ReadAirProcessor(config=processor_config)
                    processor.set_llm_manager(self.llm_manager)
                
                elif name == ProcessorName.THOUGHT_GENERATOR:
                    from linjing.processors.thought_generator import ThoughtGenerator
                    processor = ThoughtGenerator(config=processor_config)
                    processor.set_llm_manager(self.llm_manager)
                    processor.set_personality(self.personality)
                
                elif name == ProcessorName.RESPONSE_COMPOSER:
                    from linjing.processors.response_composer import ResponseComposer
                    processor = ResponseComposer(config=processor_config)
                    processor.set_llm_manager(self.llm_manager)
                    processor.set_personality(self.personality)
                
                else:
                    # 尝试动态导入
                    module_path = f"linjing.processors.{name.lower()}"
                    try:
                        module = importlib.import_module(module_path)
                        # 查找处理器类
                        for _, obj in inspect.getmembers(module):
                            if (inspect.isclass(obj) and issubclass(obj, Processor) 
                                    and obj.__name__ != 'Processor'):
                                processor_class = obj
                                break
                        else:
                            raise ImportError(f"在模块 {module_path} 中找不到处理器类")
                        
                        # 创建处理器实例
                        processor = processor_class(name=name, config=processor_config)
                        
                    except (ImportError, AttributeError) as e:
                        logger.error(f"无法导入处理器 {name}: {str(e)}")
                        continue
                
                # 添加处理器到管道
                self.processors[name] = processor
                self.message_pipeline.add_processor(processor)
                logger.debug(f"已添加处理器: {name}")
                
            except Exception as e:
                logger.error(f"初始化处理器 {name} 失败: {str(e)}", exc_info=True)
    
    async def _init_adapters(self) -> None:
        """初始化适配器"""
        logger.info("正在初始化适配器...")
        
        # 获取适配器配置
        adapter_configs = self.config.get("adapters", {})
        
        # 导入并初始化适配器
        for name, config in adapter_configs.items():
            if not config.get("enabled", True):
                continue
            
            try:
                # 导入适配器
                if name == "onebot":
                    from linjing.adapters.onebot_adapter import OneBotAdapter
                    adapter = OneBotAdapter(config, self.event_bus)
                else:
                    # 尝试动态导入
                    module_path = f"linjing.adapters.{name}_adapter"
                    try:
                        module = importlib.import_module(module_path)
                        adapter_class = getattr(module, f"{name.capitalize()}Adapter")
                        adapter = adapter_class(config, self.event_bus)
                    except (ImportError, AttributeError) as e:
                        logger.error(f"无法导入适配器 {name}: {str(e)}")
                        continue
                
                # 注册消息处理函数
                if hasattr(adapter, 'register_message_handler'):
                    adapter.register_message_handler(self.handle_message)
                
                # 添加适配器
                self.adapters[name] = adapter
                logger.debug(f"已添加适配器: {name}")
                
            except Exception as e:
                logger.error(f"初始化适配器 {name} 失败: {str(e)}", exc_info=True)
    
    async def _init_plugins(self) -> None:
        """初始化插件系统"""
        logger.info("正在初始化插件系统...")
        
        # 导入插件管理器
        try:
            from linjing.plugins.plugin_manager import PluginManager
            
            # 创建组件映射
            components = {
                "bot": self,
                "event_bus": self.event_bus,
                "personality": self.personality,
                "llm_manager": self.llm_manager,
                "memory_manager": self.memory_manager,
                "storage_manager": self.storage_manager,
                "emotion_manager": self.emotion_manager
            }
            
            # 创建插件管理器
            self.plugin_manager = PluginManager(
                config=self.config.get("plugins", {}),
                components=components
            )
            
            # 加载插件
            await self.plugin_manager.load_plugins()
            
        except ImportError as e:
            logger.error(f"插件系统导入失败: {str(e)}")
            raise
    
    def _register_event_handlers(self) -> None:
        """注册事件处理器"""
        # 订阅错误事件
        self.event_bus.subscribe(EventType.ERROR_OCCURRED, self._on_error)
    
    def _on_error(self, event_type: str, data: Dict[str, Any]) -> None:
        """
        错误事件处理函数
        
        Args:
            event_type: 事件类型
            data: 事件数据
        """
        error = data.get("error")
        source = data.get("source", "unknown")
        logger.error(f"来自 {source} 的错误: {str(error)}")


# 创建机器人单例实例
_bot_instance = None

def get_bot_instance(config: Dict[str, Any] = None) -> LinjingBot:
    """
    获取机器人实例（单例模式）
    
    Args:
        config: 配置字典，仅在首次调用时有效
        
    Returns:
        机器人实例
    """
    global _bot_instance
    if _bot_instance is None and config is not None:
        _bot_instance = LinjingBot(config)
    
    return _bot_instance 