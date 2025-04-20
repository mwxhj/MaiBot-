#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
林静机器人主类模块，作为整个机器人的核心控制器。
"""

# import os # 在此文件中未使用
# import sys # 在此文件中未使用
import asyncio
import json # 导入 json 模块
import importlib
import inspect
import os # <--- 重新导入 os 用于文件路径操作
import yaml # <-- 导入 yaml 库
from typing import Dict, List, Any, Optional, Tuple, Type, Callable

from linjing.utils.logger import get_logger
from linjing.constants import EventType, ProcessorName
from linjing.bot.event_bus import EventBus
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
        # 新增：存储加载的配置文本
        self.personality_principles_text: str = ""
        self.style_guide_text: str = ""

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
            # 加载人格和风格指南文本
            await self._load_personality_principles()
            await self._load_style_guide()

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
            config=self.config, # <-- 传递 self.config
            session_id=message.get_session_id() if hasattr(message, 'get_session_id') else "default"
            # platform 参数可以稍后从 message 中提取或保持默认
        )
        
        # 确保用户记录存在
        if self.memory_manager:
            try:
                # 尝试从消息中获取平台和昵称信息 (需要适配器支持)
                platform = message.get_platform() if hasattr(message, 'get_platform') else "unknown"
                name = message.get_user_name() if hasattr(message, 'get_user_name') else None
                await self.memory_manager.ensure_user_exists(
                    user_id=context.user_id,
                    platform=platform,
                    name=name
                )
            except Exception as e:
                logger.error(f"处理用户存在性检查时出错 (用户ID: {context.user_id}): {e}", exc_info=True)
                # 即使检查失败，也可能继续处理，但后续保存可能会失败

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
        
        # --- V12 重构：在管道中处理情绪更新 ---
        processed_context = context # 使用新变量，避免覆盖初始 context

        # 1. 手动执行 ReadAirProcessor (如果存在)
        read_air_processor = self.get_processor(ProcessorName.READ_AIR)
        if read_air_processor:
            logger.debug("手动执行 ReadAirProcessor...")
            processed_context = await read_air_processor.process(processed_context)
            logger.debug("ReadAirProcessor 执行完毕。")
        else:
            logger.warning(f"处理器管道中未找到 {ProcessorName.READ_AIR}，无法执行读空气分析。")

        # 2. 更新情绪状态 (基于 ReadAir 分析结果)
        if self.emotion_manager:
            logger.debug("开始更新情绪状态...")
            read_air_analysis = processed_context.get_state("read_air_analysis")
            message_text = message.extract_plain_text() if hasattr(message, 'extract_plain_text') else str(message)
            # 将 read_air_analysis 包装在 factors 字典中传递
            factors = {"read_air_analysis": read_air_analysis if isinstance(read_air_analysis, dict) else {}}

            try:
                updated_emotion = await self.emotion_manager.update_emotion(
                    processed_context.user_id,
                    factors,
                    message_text
                )
                # 将更新后的情绪状态设置回上下文
                processed_context.with_emotion(updated_emotion.to_dict())
                logger.debug(f"情绪状态已更新并设置回上下文: {updated_emotion}")
            except Exception as e:
                 logger.error(f"更新情绪状态时出错 (UserID: {processed_context.user_id}): {e}", exc_info=True)
                 # 即使情绪更新失败，也继续处理

        # 3. 执行管道中剩余的处理器
        logger.debug("开始执行剩余的消息处理器...")
        pipeline_order = self.config.get("bot", {}).get("processor_pipeline", [])
        try:
            read_air_index = pipeline_order.index(ProcessorName.READ_AIR)
            start_index = read_air_index + 1
        except ValueError:
            logger.warning(f"管道顺序中未找到 {ProcessorName.READ_AIR}，将从头开始执行所有处理器。")
            start_index = 0 # 如果没有 ReadAir，从头执行

        for i in range(start_index, len(pipeline_order)):
            processor_name = pipeline_order[i]
            processor = self.get_processor(processor_name)
            if processor:
                logger.debug(f"执行处理器: {processor_name}...")
                try:
                    processed_context = await processor.process(processed_context)
                    logger.debug(f"处理器 {processor_name} 执行完毕。")
                except Exception as e:
                     logger.error(f"执行处理器 {processor_name} 时出错: {e}", exc_info=True)
                     # 可以选择在这里中断处理或继续下一个处理器
                     # break # 如果希望出错时中断
            else:
                 logger.warning(f"在管道顺序中找到但在实例中未找到处理器: {processor_name}")

        result_context = processed_context # 最终的处理结果上下文
        logger.debug("所有剩余处理器执行完毕。")

        # 从处理后的上下文中获取最终回复
        final_reply = result_context.get_state("reply")

        # --- 移除延迟的情绪更新，因为它已在管道中处理 ---

        # (情绪更新逻辑已移到管道处理中)

        # 发布消息发送事件
        if final_reply:
            await self.event_bus.publish(
                EventType.MESSAGE_SENT,
                {"message": final_reply, "context": result_context}
            )

        # --- Return the reply first ---
        if final_reply:
             # 为了尽快响应用户，将耗时的数据库写入和情绪更新操作放入后台任务执行
             asyncio.create_task(self._save_conversation_async(context, result_context, message, final_reply))
             return final_reply
        else:
             # If no reply, still try to save user message? Or just return None.
             # Let's just return None for now if no reply was generated.
             logger.warning(f"消息处理完成但未生成回复: UserID={context.user_id}, SessionID={context.session_id}")
             return None


    async def _save_conversation_async(self, context: MessageContext, result_context: MessageContext, user_message: Any, bot_reply: Any):
        """Helper coroutine to save conversation and update emotion asynchronously."""
        # Save user message
        if self.memory_manager:
            try:
                # 检查 user_message 是否有 to_dict 方法
                if hasattr(user_message, 'to_dict') and callable(user_message.to_dict):
                    user_content_serializable = user_message.to_dict()
                    user_content = json.dumps(user_content_serializable, ensure_ascii=False)
                else:
                    # 回退到字符串表示
                    user_content = str(user_message)
                await self.memory_manager.add_conversation_memory(
                    user_id=context.user_id,
                    session_id=context.session_id,
                    content=user_content, # 传递 JSON 字符串或普通字符串
                    role="user"
                )
            except Exception as e:
                logger.error(f"后台存储用户消息失败 (UserID: {context.user_id}): {e}", exc_info=True)

        # Save bot reply
        if bot_reply and self.memory_manager and hasattr(bot_reply, 'extract_plain_text'):
            try: # 修正：检查 bot_reply 是否有 to_dict
                if hasattr(bot_reply, 'to_dict') and callable(bot_reply.to_dict):
                    bot_content_serializable = bot_reply.to_dict()
                    bot_content = json.dumps(bot_content_serializable, ensure_ascii=False)
                else:
                    # 回退到字符串表示
                    bot_content = str(bot_reply)

                await self.memory_manager.add_conversation_memory(
                    user_id=context.user_id,
                    session_id=context.session_id,
                    content=bot_content, # 传递 JSON 字符串或普通字符串
                    role="assistant" # 修正：保持 role 为 assistant
                )
            except Exception as e:
                logger.error(f"后台存储机器人回复失败 (UserID: {context.user_id}): {e}", exc_info=True)

        # 移除后台情绪更新逻辑
        # if bot_reply and self.emotion_manager:
        #     try:
        #         # ... (旧代码已移除) ...
        #     except Exception as e:
        #          logger.error(f"后台更新情绪状态失败 (UserID: {context.user_id}): {e}", exc_info=True)

        # Note: MESSAGE_SENT event is already published in handle_message before this task runs.
        # No need to publish it again here.
        # Also, no need to return anything from this background task.
    
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
    
    async def _load_personality_principles(self) -> None:
        """加载人格原则文件内容"""
        # 注意：这里的路径是相对于项目根目录还是当前文件？假设是相对于 linjing 包
        # 需要确认实际运行时的 CWD 或使用绝对路径/更可靠的相对路径
        # 假设 config.yaml 所在的目录是项目根目录
        # TODO: 确认配置文件的准确路径加载方式
        principles_path = self.config.get("paths", {}).get("personality_principles", "linjing/config/personality_principles.md")
        logger.info(f"尝试从 '{principles_path}' 加载人格原则...")
        try:
            # 假设 Bot 实例在项目根目录创建，或者路径是绝对的
            # 如果在 Docker 中，路径可能是 /app/linjing/config/...
            # 尝试构建相对于 /app 的路径 (如果适用)
            if not os.path.isabs(principles_path) and os.getenv("APP_HOME"): # 检查是否在容器内
                 principles_path = os.path.join(os.getenv("APP_HOME", "/app"), principles_path)

            if os.path.exists(principles_path):
                 with open(principles_path, "r", encoding="utf-8") as f:
                     self.personality_principles_text = f.read()
                 logger.info(f"成功加载人格原则 ({len(self.personality_principles_text)} 字符)")
            else:
                 logger.error(f"人格原则文件未找到: {principles_path}")
                 self.personality_principles_text = "错误：人格原则文件未找到！"
        except Exception as e:
            logger.error(f"加载人格原则文件失败: {e}", exc_info=True)
            self.personality_principles_text = "错误：加载人格原则文件失败！"
        # self.personality = None # 移除旧的逻辑

    async def _load_style_guide(self) -> None:
        """加载沟通风格指南文件内容"""
        style_guide_path = self.config.get("paths", {}).get("style_guide", "linjing/config/style_guide.md")
        logger.info(f"尝试从 '{style_guide_path}' 加载风格指南...")
        try:
            # 同样处理路径问题
            if not os.path.isabs(style_guide_path) and os.getenv("APP_HOME"):
                 style_guide_path = os.path.join(os.getenv("APP_HOME", "/app"), style_guide_path)

            if os.path.exists(style_guide_path):
                 with open(style_guide_path, "r", encoding="utf-8") as f:
                     self.style_guide_text = f.read()
                 logger.info(f"成功加载风格指南 ({len(self.style_guide_text)} 字符)")
            else:
                 logger.error(f"风格指南文件未找到: {style_guide_path}")
                 self.style_guide_text = "错误：风格指南文件未找到！"
        except Exception as e:
            logger.error(f"加载风格指南文件失败: {e}", exc_info=True)
            self.style_guide_text = "错误：加载风格指南文件失败！"
    
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
            # 再次尝试过滤，确保只传递 DatabaseManager.__init__ 关心的顶级键
            db_config_raw = self.config.get("storage", {}).get("database", {})
            # --- DEBUG LOGGING START ---
            logger.debug(f"LinjingBot._init_storage passing config to DatabaseManager: {db_config_raw}")
            # --- DEBUG LOGGING END ---
            # DatabaseManager.__init__ 只直接使用 config 参数本身
            # 它内部会去 .get("type"), .get("host") 等
            # 所以我们应该直接传递原始的 db_config_raw，让 DatabaseManager 内部处理
            # 但为了解决 TypeError，我们假设问题出在传递了多余的键
            # 让我们尝试创建一个只包含已知安全键的新字典
            known_keys = ["type", "host", "port", "user", "password", "database", "path", "connection", "create_tables_on_connect"]
            db_config_for_init = {k: db_config_raw[k] for k in known_keys if k in db_config_raw}

            # 特别处理 connection 子字典，也过滤一下（虽然理论上不应导致__init__的TypeError）
            if "connection" in db_config_for_init and isinstance(db_config_for_init["connection"], dict):
                 connection_config_raw = db_config_for_init["connection"]
                 known_conn_keys = ["timeout", "isolation_level", "pragma"] # 根据 database.py connect 方法
                 db_config_for_init["connection"] = {k: connection_config_raw[k] for k in known_conn_keys if k in connection_config_raw}

            self.storage_manager = DatabaseManager(config=db_config_for_init)
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
            
            # 在配置中添加数据库路径 (这部分可能不再需要，因为 db_manager 已包含连接信息)
            # memory_config["db_path"] = self.config.get("storage", {}).get("db_path", "data/database.db")

            # 传递已初始化的 DatabaseManager 实例给 MemoryManager
            if not self.storage_manager:
                 logger.error("Storage manager 未初始化，无法创建 MemoryManager！")
                 raise RuntimeError("Storage manager not initialized before MemoryManager") # 或者返回 False

            self.memory_manager = MemoryManager(db_manager=self.storage_manager, config=memory_config)
            
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

            # 初始化情绪管理器表结构 (调用新方法)
            if hasattr(self.emotion_manager, '_initialize_tables'):
                 await self.emotion_manager._initialize_tables()
            # else: # 移除旧的兼容逻辑，因为我们知道新方法存在
            #      if hasattr(self.emotion_manager, 'initialize_tables'):
            #           await self.emotion_manager.initialize_tables()

            
        except ImportError as e:
            logger.error(f"情绪系统导入失败: {str(e)}")
            raise
    
    async def _init_processors(self) -> None:
        """初始化处理器"""
        logger.info("正在初始化处理器...")

        # --- 加载 prompts.yaml ---
        all_prompts_config = {}
        prompts_path = self.config.get("paths", {}).get("prompts", "linjing/config/prompts.yaml")
        logger.info(f"尝试从 '{prompts_path}' 加载处理器 Prompts...")
        try:
            # 处理 Docker 路径
            if not os.path.isabs(prompts_path) and os.getenv("APP_HOME"):
                 prompts_path = os.path.join(os.getenv("APP_HOME", "/app"), prompts_path)

            if os.path.exists(prompts_path):
                 with open(prompts_path, "r", encoding="utf-8") as f:
                     all_prompts_config = yaml.safe_load(f) or {}
                 logger.info(f"成功加载 Prompts 文件 ({len(all_prompts_config)} 个处理器配置)")
            else:
                 logger.error(f"Prompts 文件未找到: {prompts_path}")
        except yaml.YAMLError as e:
            logger.error(f"解析 Prompts 文件失败: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"加载 Prompts 文件时发生未知错误: {e}", exc_info=True)
        # --- Prompts 加载完毕 ---

        # 获取处理器具体配置和管道顺序配置 (来自 config.yaml)
        processor_configs = self.config.get("processors", {})
        # 从 bot 配置块读取管道顺序，如果不存在则使用默认值
        pipeline_order = self.config.get("bot", {}).get("processor_pipeline", [
            ProcessorName.READ_AIR,
            ProcessorName.THOUGHT_GENERATOR,
            ProcessorName.RESPONSE_COMPOSER
        ])
        
        # 导入并初始化处理器
        for name in pipeline_order:
            try:
                # 获取该处理器的特定配置 (来自 config.yaml)
                processor_config = processor_configs.get(name, {}).copy() # 使用 copy 避免修改原始配置
                processor_config["enabled"] = processor_config.get("enabled", True) # 确保 enabled 存在

                # --- 合并来自 prompts.yaml 的配置 ---
                # 将 prompts.yaml 中对应处理器的配置放到 processor_config['prompts'] 下
                if name in all_prompts_config:
                    processor_config["prompts"] = all_prompts_config[name]
                    logger.debug(f"已合并来自 prompts.yaml 的 '{name}' 配置。")
                else:
                    processor_config["prompts"] = {} # 确保 prompts 键存在

                # --- 将加载的人格/风格文本注入到需要它们的处理器的配置中 ---
                if name in [ProcessorName.THOUGHT_GENERATOR, ProcessorName.WILLINGNESS_CHECKER]:
                    processor_config["personality_text"] = self.personality_principles_text
                    logger.debug(f"已为人格原则注入到处理器 '{name}' 的配置中")
                if name == ProcessorName.RESPONSE_COMPOSER:
                    processor_config["v12_style_guide"] = self.style_guide_text
                    logger.debug(f"已为风格指南注入到处理器 '{name}' 的配置中")
                # 将全局配置传递给处理器，以便它们可以访问 bot.name 等信息
                processor_config["global_config"] = self.config

                # 根据处理器名称导入相应模块
                if name == ProcessorName.READ_AIR:
                    from linjing.processors.read_air import ReadAirProcessor
                    processor = ReadAirProcessor(name=name, config=processor_config) # 传递 name 参数
                    processor.set_llm_manager(self.llm_manager)
                
                elif name == ProcessorName.THOUGHT_GENERATOR:
                    from linjing.processors.thought_generator import ThoughtGenerator
                    processor = ThoughtGenerator(name=name, config=processor_config) # 传递 name 参数
                    processor.set_llm_manager(self.llm_manager)
                    # 注入 memory_manager
                    if hasattr(processor, 'set_memory_manager') and self.memory_manager:
                         processor.set_memory_manager(self.memory_manager)
                    # processor.set_personality(self.personality) # 移除旧的调用

                # **新增：初始化 WillingnessChecker**
                elif name == ProcessorName.WILLINGNESS_CHECKER: # 使用常量
                    from linjing.processors.willingness_checker import WillingnessChecker
                    processor = WillingnessChecker(name=name, config=processor_config)
                    processor.set_llm_manager(self.llm_manager)
                    # processor.set_personality(self.personality) # 移除旧的调用
                
                elif name == ProcessorName.RESPONSE_COMPOSER:
                    from linjing.processors.response_composer import ResponseComposer
                    processor = ResponseComposer(name=name, config=processor_config) # 传递 name 参数
                    processor.set_llm_manager(self.llm_manager)
                    # processor.set_personality(self.personality) # 移除旧的调用
                
                else:
                    # 尝试根据处理器名称动态导入模块 (例如 "read_air" -> linjing.processors.read_air)
                    module_path = f"linjing.processors.{name.lower()}"
                    try:
                        # 动态导入模块
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
                # 添加更详细的错误日志
                logger.critical(f"!!! 初始化处理器 '{name}' 失败，该处理器将不会被添加到管道中 !!!", exc_info=True)
                # logger.error(f"初始化处理器 {name} 失败: {str(e)}", exc_info=True) # 保留原始错误日志（可选）
    
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
                    # 尝试根据适配器名称动态导入模块 (例如 "myadapter" -> linjing.adapters.myadapter_adapter)
                    module_path = f"linjing.adapters.{name}_adapter"
                    try:
                        # 动态导入模块
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
    
    # 注意：参数 event_type 在当前实现中未使用，可以考虑移除或添加日志记录
    def _on_error(self, event_type: str, data: Dict[str, Any]) -> None:
        """
        错误事件处理函数，由 EventBus 在接收到 ERROR_OCCURRED 事件时调用。

        Args:
            event_type: 事件类型 (当前未使用)
            data: 事件数据，应包含 "error" 和可选的 "source" 键
        """
        error = data.get("error", "未知错误") # 提供默认值
        source = data.get("source", "未知来源") # 提供默认值
        logger.error(f"事件总线报告来自 [{source}] 的错误: {str(error)}")


# 创建机器人单例实例
_bot_instance = None

def get_bot_instance(config: Dict[str, Any] = None) -> LinjingBot:
    """
    获取机器人实例（单例模式）。
    确保全局只有一个 LinjingBot 实例。首次调用时必须提供 config 来创建实例。

    Args:
        config: 全局配置字典，仅在首次创建实例时需要提供。

    Returns:
        全局唯一的 LinjingBot 实例。如果实例尚未创建且未提供 config，则可能返回 None 或引发错误（取决于调用方）。
    """
    global _bot_instance
    if _bot_instance is None:
        if config is None:
            # 考虑是否应该在此处引发错误，而不是依赖调用方处理 None
            logger.warning("首次调用 get_bot_instance 时未提供配置，返回 None")
            return None
        logger.info("首次创建 LinjingBot 单例实例...")
        _bot_instance = LinjingBot(config)

    return _bot_instance