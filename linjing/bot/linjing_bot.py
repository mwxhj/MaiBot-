#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
林静机器人主类模块，作为整个机器人的核心控制器。
"""

import asyncio
import time # <--- 导入 time 模块
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
        self.storage_manager: Optional[DatabaseManager] = None # 添加类型提示
        self.memory_manager = None
        self.emotion_manager = None
        self.llm_manager = None
        self.plugin_manager = None
        self.running = False
        self.self_id: Optional[str] = None # 用于存储机器人自身 ID
        # 新增：存储加载的配置文本
        self.personality_principles_text: str = ""
        self.style_guide_text: str = ""
        # 新增：读取触发条件配置
        trigger_config = config.get("bot", {}).get("trigger_conditions", {})
        self.mention_trigger_enabled = trigger_config.get("mention_trigger_enabled", True)
        self.message_count_trigger_enabled = trigger_config.get("message_count_trigger_enabled", False)
        self.message_count_threshold = trigger_config.get("message_count_threshold", 10)
        self.time_interval_trigger_enabled = trigger_config.get("time_interval_trigger_enabled", False)
        self.time_interval_threshold = trigger_config.get("time_interval_threshold", 300)
        self.high_alert_mode_trigger_enabled = trigger_config.get("high_alert_mode_trigger_enabled", True) # 从配置读取，默认为 True
        self.high_alert_duration = trigger_config.get("high_alert_duration", 5) # 从配置读取，默认为 5
        # 新增：读取名字触发配置
        self.name_trigger_enabled = trigger_config.get("name_trigger_enabled", True)
        self.bot_names = trigger_config.get("bot_names", ["林静", "Linjing"])

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
            await self._load_personality_principles()
            await self._load_style_guide()
            await self._init_llm_manager()
            await self._init_storage()
            await self._init_memory()
            await self._init_emotion()
            await self._init_processors()
            await self._init_adapters()
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
            for adapter_name, adapter in self.adapters.items():
                if hasattr(adapter, 'connect') and callable(adapter.connect):
                    logger.info(f"正在连接适配器: {adapter_name}")
                    await adapter.connect()
            self.running = True
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
            await self.event_bus.publish(EventType.BOT_STOPPED, {"bot": self})
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

        # --- V12 触发条件判断 ---
        should_process, mentioned_or_named = await self._should_process_message(message) # 获取是否处理及是否被提及
        if not should_process:
            # logger.debug("消息未满足触发条件，跳过处理。")
            return None
        # --- 触发条件判断结束 ---

        # 创建消息上下文
        context = MessageContext(
            message=message,
            user_id=message.get_user_id() if hasattr(message, 'get_user_id') else str(message),
            config=self.config,
            session_id=message.get_session_id() if hasattr(message, 'get_session_id') else "default"
        )

        # 确保用户记录存在
        if self.memory_manager:
            try:
                platform = message.get_platform() if hasattr(message, 'get_platform') else "unknown"
                name = message.get_user_name() if hasattr(message, 'get_user_name') else None
                await self.memory_manager.ensure_user_exists(
                    user_id=context.user_id, platform=platform, name=name
                )
            except Exception as e:
                logger.error(f"处理用户存在性检查时出错 (用户ID: {context.user_id}): {e}", exc_info=True)

        # 获取对话历史
        if self.memory_manager:
            history = await self.memory_manager.get_conversation_history(
                context.user_id,
                limit=self.config.get("memory", {}).get("max_conversation_history", 10)
            )
            context.with_history(history)
            logger.debug(f"获取到对话历史: {len(history)} 条")

        # 获取情绪状态
        if self.emotion_manager:
            emotion = await self.emotion_manager.get_emotion(context.user_id)
            context.with_emotion(emotion.to_dict() if hasattr(emotion, 'to_dict') else emotion)
            logger.debug(f"获取到情绪状态: {context.get_state('emotion')}")

        # 发布消息接收事件
        await self.event_bus.publish(
            EventType.MESSAGE_RECEIVED, {"message": message, "context": context}
        )

        # --- V12 重构：在管道中处理情绪更新 ---
        processed_context = context

        # 1. 手动执行 ReadAirProcessor (如果存在)
        read_air_processor = self.get_processor(ProcessorName.READ_AIR)
        if read_air_processor:
            logger.debug("手动执行 ReadAirProcessor...")
            try:
                processed_context = await read_air_processor.process(processed_context)
                logger.debug(f"ReadAirProcessor 执行完毕。Context 状态: read_air_analysis={processed_context.get_state('read_air_analysis')}")
                if not processed_context.get_state("read_air_analysis"):
                     logger.error("ReadAirProcessor 执行成功但未能生成有效的分析结果，终止处理。")
                     return None
            except Exception as e:
                 logger.error(f"执行处理器 {ProcessorName.READ_AIR} 时出错，终止处理: {e}", exc_info=True)
                 return None
        else:
            logger.warning(f"处理器管道中未找到 {ProcessorName.READ_AIR}，无法执行读空气分析。")

        # 2. 更新情绪状态 (基于 ReadAir 分析结果)
        if self.emotion_manager:
            logger.debug("开始更新情绪状态...")
            read_air_analysis = processed_context.get_state("read_air_analysis")
            message_text = message.extract_plain_text() if hasattr(message, 'extract_plain_text') else str(message)
            factors = {"read_air_analysis": read_air_analysis if isinstance(read_air_analysis, dict) else {}}
            try:
                updated_emotion = await self.emotion_manager.update_emotion(
                    processed_context.user_id, factors, message_text
                )
                processed_context.with_emotion(updated_emotion.to_dict())
                logger.debug(f"情绪状态已更新并设置回上下文: {updated_emotion}")
            except Exception as e:
                 logger.error(f"更新情绪状态时出错 (UserID: {processed_context.user_id}): {e}", exc_info=True)

        # 3. 执行管道中剩余的处理器
        logger.debug("开始执行剩余的消息处理器...")
        pipeline_order = self.config.get("bot", {}).get("processor_pipeline", [])
        try:
            read_air_index = pipeline_order.index(ProcessorName.READ_AIR)
            start_index = read_air_index + 1
        except ValueError:
            logger.warning(f"管道顺序中未找到 {ProcessorName.READ_AIR}，将从头开始执行所有处理器。")
            start_index = 0

        for i in range(start_index, len(pipeline_order)):
            processor_name = pipeline_order[i]
            processor = self.get_processor(processor_name)
            if processor:
                logger.debug(f"执行处理器: {processor_name}...")
                try:
                    processed_context = await processor.process(processed_context)
                    # --- 添加日志记录关键状态 ---
                    if processor_name == ProcessorName.THOUGHT_GENERATOR:
                        logger.debug(f"ThoughtGenerator 执行完毕。Context 状态: thought={processed_context.get_state('thought')}")
                    elif processor_name == ProcessorName.WILLINGNESS_CHECKER:
                        logger.debug(f"WillingnessChecker 执行完毕。Context 状态: is_willing_to_reply={processed_context.get_state('is_willing_to_reply')}")
                    elif processor_name == ProcessorName.RESPONSE_COMPOSER:
                        logger.debug(f"ResponseComposer 执行完毕。Context 状态: reply={processed_context.get_state('reply')}")
                    else:
                        logger.debug(f"处理器 {processor_name} 执行完毕。")
                    # --- 日志记录结束 ---

                    # --- V12 检查点 ---
                    if processor_name == ProcessorName.THOUGHT_GENERATOR and not processed_context.get_state("thought"):
                        logger.error("ThoughtGenerator 执行成功但未能生成有效的思考结果，终止处理。")
                        break
                    if processor_name == ProcessorName.WILLINGNESS_CHECKER:
                        is_willing = processed_context.get_state("is_willing_to_reply", True)
                        if not is_willing:
                            logger.info("WillingnessChecker 判断不适合回复，终止处理。")
                            break
                except Exception as e:
                     logger.error(f"执行处理器 {processor_name} 时出错，终止处理: {e}", exc_info=True)
                     break
            else:
                 logger.warning(f"在管道顺序中找到但在实例中未找到处理器: {processor_name}")

        result_context = processed_context
        logger.debug("所有剩余处理器执行完毕。")

        # 从处理后的上下文中获取最终回复
        final_reply = result_context.get_state("reply")

        # 发布消息发送事件
        if final_reply:
            await self.event_bus.publish(
                EventType.MESSAGE_SENT,
                {"message": final_reply, "context": result_context}
            )

        # --- Return the reply first ---
        if final_reply:
             # --- 重新加入：回复成功后开启高戒备 ---
             if self.high_alert_mode_trigger_enabled and self.storage_manager:
                 session_id = message.get_session_id() if hasattr(message, 'get_session_id') else "default"
                 logger.info(f"机器人回复成功，会话 {session_id} 进入高戒备模式 (持续 {self.high_alert_duration} 条消息)。")
                 await self.storage_manager.update_session_state(
                     session_id,
                     is_high_alert=True,
                     high_alert_counter=0
                 )
             # --- 高戒备触发结束 ---

             # 为了尽快响应用户，将耗时的数据库写入操作放入后台任务执行
             asyncio.create_task(self._save_conversation_async(context, result_context, message, final_reply))
             return final_reply
        else:
             logger.warning(f"消息处理完成但未生成回复: UserID={context.user_id}, SessionID={context.session_id}")
             # --- 即使没有回复，如果被提及，也可能需要开启高戒备 ---
             if mentioned_or_named and self.high_alert_mode_trigger_enabled and self.storage_manager:
                 session_id = message.get_session_id() if hasattr(message, 'get_session_id') else "default"
                 # 检查是否已处于高戒备，避免重复日志和更新
                 current_state = await self.storage_manager.get_session_state(session_id)
                 if not current_state or not current_state.get("is_high_alert"):
                     logger.info(f"会话 {session_id} 因被提及但无回复而进入高戒备模式 (持续 {self.high_alert_duration} 条消息)。")
                     await self.storage_manager.update_session_state(
                         session_id,
                         is_high_alert=True,
                         high_alert_counter=0
                         # 注意：这里不更新 last_active_ts 和 message_count，因为 _should_process_message 中已更新
                     )
             return None


    async def _save_conversation_async(self, context: MessageContext, result_context: MessageContext, user_message: Any, bot_reply: Any):
        """Helper coroutine to save conversation asynchronously."""
        # Save user message
        if self.memory_manager:
            try:
                if hasattr(user_message, 'to_dict') and callable(user_message.to_dict):
                    user_content_serializable = user_message.to_dict()
                    user_content = json.dumps(user_content_serializable, ensure_ascii=False)
                else:
                    user_content = str(user_message)
                await self.memory_manager.add_conversation_memory(
                    user_id=context.user_id, session_id=context.session_id,
                    content=user_content, role="user"
                )
            except Exception as e:
                logger.error(f"后台存储用户消息失败 (UserID: {context.user_id}): {e}", exc_info=True)

        # Save bot reply
        if bot_reply and self.memory_manager and hasattr(bot_reply, 'extract_plain_text'):
            try:
                if hasattr(bot_reply, 'to_dict') and callable(bot_reply.to_dict):
                    bot_content_serializable = bot_reply.to_dict()
                    bot_content = json.dumps(bot_content_serializable, ensure_ascii=False)
                else:
                    bot_content = str(bot_reply)
                await self.memory_manager.add_conversation_memory(
                    user_id=context.user_id, session_id=context.session_id,
                    content=bot_content, role="assistant"
                )
            except Exception as e:
                logger.error(f"后台存储机器人回复失败 (UserID: {context.user_id}): {e}", exc_info=True)

    # --- 修改：触发条件判断逻辑 (V3) ---
    async def _should_process_message(self, message: Any) -> Tuple[bool, bool]:
        """
        判断是否应该处理当前消息，并检测是否被提及。
        处理触发器: 高戒备状态, @mention, 名字提及, 消息计数, 时间间隔。
        高戒备开启器: @mention, 名字提及。 (回复成功的高戒备开启在 handle_message 中)

        Args:
            message: 传入的消息对象。

        Returns:
            Tuple[bool, bool]: (是否应该处理消息, 是否被 @ 或名字提及)
        """
        current_ts = time.time()
        session_id = message.get_session_id() if hasattr(message, 'get_session_id') else "default"

        # --- 从数据库获取当前会话状态 ---
        if not self.storage_manager:
            logger.warning("StorageManager 未初始化，无法检查会话状态，默认不处理。")
            return False, False

        session_state = await self.storage_manager.get_session_state(session_id)
        is_new_session = session_state is None
        if is_new_session:
            session_state = {
                "last_active_ts": 0.0, "message_count": 0,
                "is_high_alert": False, "high_alert_counter": 0
            }

        # --- 更新基础状态 (计数和时间戳) ---
        current_message_count = session_state["message_count"] + 1
        update_payload = {
            "last_active_ts": current_ts,
            "message_count": current_message_count
        }
        needs_db_update = True # 默认需要更新数据库

        # --- 检查是否被 @ 或提及名字 ---
        mentioned_or_named = False
        # 1. @Mention 检查
        if self.mention_trigger_enabled and self.self_id:
            segments = getattr(message, 'segments', None)
            if isinstance(segments, list):
                for segment in message.segments:
                    segment_type = getattr(segment, 'type', None) or segment.get('type') if isinstance(segment, dict) else None
                    segment_data = getattr(segment, 'data', None) or segment.get('data') if isinstance(segment, dict) else {}
                    if segment_type == "at" and str(segment_data.get("qq")) == self.self_id:
                        logger.debug(f"检测到 @mention (QQ: {self.self_id})")
                        mentioned_or_named = True
                        break
        # 2. 名字检查 (仅在未被 @ 时检查)
        if not mentioned_or_named and self.name_trigger_enabled:
            message_text = message.extract_plain_text() if hasattr(message, 'extract_plain_text') else str(message)
            for name in self.bot_names:
                if (f" {name} " in f" {message_text} " or
                    message_text.startswith(name + " ") or
                    message_text.endswith(" " + name) or
                    message_text == name):
                    logger.debug(f"检测到机器人名字提及: {name}")
                    mentioned_or_named = True
                    break

        # --- 检查是否应该处理消息 ---
        should_trigger_processing = False # 默认不处理

        # 1. 检查是否处于高戒备状态
        is_high_alert = session_state["is_high_alert"]
        alert_count = session_state["high_alert_counter"]
        if is_high_alert:
            if alert_count < self.high_alert_duration:
                 logger.debug(f"消息触发条件：处于高戒备模式 (计数 {alert_count + 1}/{self.high_alert_duration})")
                 update_payload["high_alert_counter"] = alert_count + 1 # 增加计数器
                 should_trigger_processing = True # 高戒备模式下触发处理
            else:
                 # 高戒备计数已满，退出高戒备模式
                 logger.debug(f"会话 {session_id} 高戒备计数已满，退出高戒备模式。")
                 update_payload["is_high_alert"] = False
                 update_payload["high_alert_counter"] = 0 # 重置计数器

        # 2. 检查 @mention 或名字提及 (如果未被高戒备触发)
        if not should_trigger_processing and mentioned_or_named:
            logger.debug("消息触发条件：被 @ 或名字提及。")
            should_trigger_processing = True
            # 如果因此触发，也重置消息计数器
            update_payload["message_count"] = 0

        # 3. 消息计数检查 (如果未被前面条件触发)
        if not should_trigger_processing and self.message_count_trigger_enabled:
            if current_message_count >= self.message_count_threshold:
                logger.debug(f"消息触发条件：达到消息计数阈值 ({current_message_count}/{self.message_count_threshold})")
                update_payload["message_count"] = 0 # 重置计数器
                should_trigger_processing = True

        # 4. 时间间隔检查 (如果未被前面条件触发)
        if not should_trigger_processing and self.time_interval_trigger_enabled:
            last_active_ts = session_state["last_active_ts"]
            if last_active_ts != 0 and (current_ts - last_active_ts > self.time_interval_threshold):
                 logger.debug(f"消息触发条件：达到时间间隔阈值 ({(current_ts - last_active_ts):.1f}s > {self.time_interval_threshold}s)")
                 update_payload["message_count"] = 0 # 重置计数器
                 should_trigger_processing = True

        # --- 如果被提及，则开启高戒备 (无论是否触发处理) ---
        if mentioned_or_named and self.high_alert_mode_trigger_enabled:
            # 仅在当前不处于高戒备时才记录日志并重置计数器
            if not session_state["is_high_alert"]:
                logger.info(f"会话 {session_id} 因被提及而进入高戒备模式 (持续 {self.high_alert_duration} 条消息)。")
                update_payload["high_alert_counter"] = 0 # 重置计数器
            update_payload["is_high_alert"] = True # 确保开启或维持高戒备

        # --- 统一更新数据库状态 ---
        if needs_db_update or is_new_session:
             await self.storage_manager.update_session_state(session_id, **update_payload)

        return should_trigger_processing, mentioned_or_named # 返回是否处理和是否被提及

    def get_adapter(self, name: str) -> Optional[Any]:
        """获取指定名称的适配器"""
        return self.adapters.get(name)

    def get_processor(self, name: str) -> Optional[Processor]:
        """获取指定名称的处理器"""
        return self.message_pipeline.get_processor(name)

    async def _load_personality_principles(self) -> None:
        """加载人格原则文件内容"""
        principles_path = self.config.get("paths", {}).get("personality_principles", "linjing/config/personality_principles.md")
        logger.info(f"尝试从 '{principles_path}' 加载人格原则...")
        try:
            if not os.path.isabs(principles_path) and os.getenv("APP_HOME"):
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

    async def _load_style_guide(self) -> None:
        """加载沟通风格指南文件内容"""
        style_guide_path = self.config.get("paths", {}).get("style_guide", "linjing/config/style_guide.md")
        logger.info(f"尝试从 '{style_guide_path}' 加载风格指南...")
        try:
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
        try:
            from linjing.llm.llm_manager import LLMManager
            self.llm_manager = LLMManager(self.config)
            await self.llm_manager.initialize()
        except ImportError as e:
            logger.error(f"LLM管理器导入失败: {str(e)}")
            raise

    async def _init_storage(self) -> None:
        """初始化存储系统"""
        logger.info("正在初始化存储系统...")
        try:
            from linjing.storage.database import DatabaseManager
            db_config_raw = self.config.get("storage", {}).get("database", {})
            logger.debug(f"LinjingBot._init_storage passing config to DatabaseManager: {db_config_raw}")
            known_keys = ["type", "host", "port", "user", "password", "database", "path", "connection", "create_tables_on_connect"]
            db_config_for_init = {k: db_config_raw[k] for k in known_keys if k in db_config_raw}
            if "connection" in db_config_for_init and isinstance(db_config_for_init["connection"], dict):
                 connection_config_raw = db_config_for_init["connection"]
                 known_conn_keys = ["timeout", "isolation_level", "pragma"]
                 db_config_for_init["connection"] = {k: connection_config_raw[k] for k in known_conn_keys if k in connection_config_raw}
            self.storage_manager = DatabaseManager(config=db_config_for_init)
            await self.storage_manager.connect()
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
        try:
            from linjing.memory.memory_manager import MemoryManager
            memory_config = self.config.get("memory", {})
            vector_db_config = self.config.get("storage", {}).get("vector_db", {})
            if not isinstance(vector_db_config, dict):
                vector_db_config = {}
            memory_config["vector_db"] = vector_db_config
            if not self.storage_manager:
                 logger.error("Storage manager 未初始化，无法创建 MemoryManager！")
                 raise RuntimeError("Storage manager not initialized before MemoryManager")
            self.memory_manager = MemoryManager(db_manager=self.storage_manager, config=memory_config)
            await self.memory_manager.initialize()
        except ImportError as e:
            logger.error(f"记忆系统导入失败: {str(e)}")
            raise

    async def _init_emotion(self) -> None:
        """初始化情绪系统"""
        logger.info("正在初始化情绪系统...")
        try:
            from linjing.emotion.emotion_manager import EmotionManager
            self.emotion_manager = EmotionManager(
                config=self.config.get("emotion", {}),
                db_manager=self.storage_manager
            )
            if hasattr(self.emotion_manager, '_initialize_tables'):
                 await self.emotion_manager._initialize_tables()
        except ImportError as e:
            logger.error(f"情绪系统导入失败: {str(e)}")
            raise

    async def _init_processors(self) -> None:
        """初始化处理器"""
        logger.info("正在初始化处理器...")
        all_prompts_config = {}
        prompts_path = self.config.get("paths", {}).get("prompts", "linjing/config/prompts.yaml")
        logger.info(f"尝试从 '{prompts_path}' 加载处理器 Prompts...")
        try:
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

        processor_configs = self.config.get("processors", {})
        pipeline_order = self.config.get("bot", {}).get("processor_pipeline", [
            ProcessorName.READ_AIR, ProcessorName.THOUGHT_GENERATOR, ProcessorName.RESPONSE_COMPOSER
        ])

        for name in pipeline_order:
            try:
                processor_config = processor_configs.get(name, {}).copy()
                processor_config["enabled"] = processor_config.get("enabled", True)
                if name in all_prompts_config:
                    processor_config["prompts"] = all_prompts_config[name]
                    logger.debug(f"已合并来自 prompts.yaml 的 '{name}' 配置。")
                else:
                    processor_config["prompts"] = {}
                if name in [ProcessorName.THOUGHT_GENERATOR, ProcessorName.WILLINGNESS_CHECKER]:
                    processor_config["personality_text"] = self.personality_principles_text
                    logger.debug(f"已为人格原则注入到处理器 '{name}' 的配置中")
                if name == ProcessorName.RESPONSE_COMPOSER:
                    processor_config["v12_style_guide"] = self.style_guide_text
                    logger.debug(f"已为风格指南注入到处理器 '{name}' 的配置中")
                processor_config["global_config"] = self.config

                if name == ProcessorName.READ_AIR:
                    from linjing.processors.read_air import ReadAirProcessor
                    processor = ReadAirProcessor(name=name, config=processor_config)
                    processor.set_llm_manager(self.llm_manager)
                elif name == ProcessorName.THOUGHT_GENERATOR:
                    from linjing.processors.thought_generator import ThoughtGenerator
                    processor = ThoughtGenerator(name=name, config=processor_config)
                    processor.set_llm_manager(self.llm_manager)
                    if hasattr(processor, 'set_memory_manager') and self.memory_manager:
                         processor.set_memory_manager(self.memory_manager)
                elif name == ProcessorName.WILLINGNESS_CHECKER:
                    from linjing.processors.willingness_checker import WillingnessChecker
                    bot_qq_from_config = self.config.get("bot", {}).get("self_qq") or \
                                         self.config.get("adapters", {}).get("onebot", {}).get("self_id")
                    if bot_qq_from_config:
                        processor_config["bot_qq"] = str(bot_qq_from_config)
                        logger.debug(f"已将 bot_qq ({processor_config['bot_qq']}) 注入到 WillingnessChecker 配置。")
                    else:
                        processor_config["bot_qq"] = self.self_id
                        logger.warning(f"未在配置中找到 bot_qq/self_id，尝试使用 self.self_id ({self.self_id}) 注入 WillingnessChecker。")
                    processor = WillingnessChecker(name=name, config=processor_config)
                    processor.set_llm_manager(self.llm_manager)
                elif name == ProcessorName.RESPONSE_COMPOSER:
                    from linjing.processors.response_composer import ResponseComposer
                    processor = ResponseComposer(name=name, config=processor_config)
                    processor.set_llm_manager(self.llm_manager)
                else:
                    module_path = f"linjing.processors.{name.lower()}"
                    try:
                        module = importlib.import_module(module_path)
                        for _, obj in inspect.getmembers(module):
                            if (inspect.isclass(obj) and issubclass(obj, Processor)
                                    and obj.__name__ != 'Processor'):
                                processor_class = obj
                                break
                        else:
                            raise ImportError(f"在模块 {module_path} 中找不到处理器类")
                        processor = processor_class(name=name, config=processor_config)
                    except (ImportError, AttributeError) as e:
                        logger.error(f"无法导入处理器 {name}: {str(e)}")
                        continue

                self.processors[name] = processor
                self.message_pipeline.add_processor(processor)
                logger.debug(f"已添加处理器: {name}")
            except Exception as e:
                logger.critical(f"!!! 初始化处理器 '{name}' 失败，该处理器将不会被添加到管道中 !!!", exc_info=True)

    async def _init_adapters(self) -> None:
        """初始化适配器"""
        logger.info("正在初始化适配器...")
        adapter_configs = self.config.get("adapters", {})
        for name, config in adapter_configs.items():
            if not config.get("enabled", True):
                continue
            try:
                if name == "onebot":
                    from linjing.adapters.onebot_adapter import OneBotAdapter
                    adapter = OneBotAdapter(config, self.event_bus)
                else:
                    module_path = f"linjing.adapters.{name}_adapter"
                    try:
                        module = importlib.import_module(module_path)
                        adapter_class = getattr(module, f"{name.capitalize()}Adapter")
                        adapter = adapter_class(config, self.event_bus)
                    except (ImportError, AttributeError) as e:
                        logger.error(f"无法导入适配器 {name}: {str(e)}")
                        continue
                if hasattr(adapter, 'register_message_handler'):
                    adapter.register_message_handler(self.handle_message)
                self.adapters[name] = adapter
                logger.debug(f"已添加适配器: {name}")
            except Exception as e:
                logger.error(f"初始化适配器 {name} 失败: {str(e)}", exc_info=True)

    async def _init_plugins(self) -> None:
        """初始化插件系统"""
        logger.info("正在初始化插件系统...")
        try:
            from linjing.plugins.plugin_manager import PluginManager
            components = {
                "bot": self, "event_bus": self.event_bus, "personality": self.personality,
                "llm_manager": self.llm_manager, "memory_manager": self.memory_manager,
                "storage_manager": self.storage_manager, "emotion_manager": self.emotion_manager
            }
            self.plugin_manager = PluginManager(
                config=self.config.get("plugins", {}), components=components
            )
            await self.plugin_manager.load_plugins()
        except ImportError as e:
            logger.error(f"插件系统导入失败: {str(e)}")
            raise

    def _register_event_handlers(self) -> None:
        """注册事件处理器"""
        self.event_bus.subscribe(EventType.ERROR_OCCURRED, self._on_error)
        self.event_bus.subscribe(EventType.ADAPTER_CONNECTED, self._on_adapter_connected)

    def _on_error(self, event_type: str, data: Dict[str, Any]) -> None:
        """错误事件处理函数"""
        error = data.get("error", "未知错误")
        source = data.get("source", "未知来源")
        logger.error(f"事件总线报告来自 [{source}] 的错误: {str(error)}")

    def _on_adapter_connected(self, event_type: str, data: Dict[str, Any]) -> None:
        """当适配器连接成功时，尝试获取并存储 self_id"""
        adapter_name = data.get("adapter_name")
        adapter_instance = data.get("adapter")
        if adapter_instance and hasattr(adapter_instance, 'get_self_id'):
            self_id = adapter_instance.get_self_id()
            if self_id:
                if self.self_id and self.self_id != self_id:
                     logger.warning(f"适配器 {adapter_name} 报告了不同的 self_id ({self_id})，将覆盖旧值 ({self.self_id})。")
                self.self_id = str(self_id)
                logger.info(f"从适配器 {adapter_name} 获取到 self_id: {self.self_id}")
            else:
                 logger.warning(f"适配器 {adapter_name} 连接成功，但未能提供 self_id。")
        else:
             logger.debug(f"适配器 {adapter_name} 连接事件未提供实例或 get_self_id 方法。")


# 创建机器人单例实例
_bot_instance = None

def get_bot_instance(config: Dict[str, Any] = None) -> "LinjingBot": # 使用字符串避免循环导入
    """获取机器人实例（单例模式）"""
    global _bot_instance
    if _bot_instance is None:
        if config is None:
            logger.warning("首次调用 get_bot_instance 时未提供配置，返回 None")
            return None
        logger.info("首次创建 LinjingBot 单例实例...")
        _bot_instance = LinjingBot(config)
    return _bot_instance