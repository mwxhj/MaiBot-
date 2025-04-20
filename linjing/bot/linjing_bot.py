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
from typing import Dict, List, Any, Optional, Tuple, Type, Callable, Set, Union

from linjing.utils.logger import get_logger
from linjing.constants import EventType, ProcessorName
from linjing.bot.event_bus import EventBus
from linjing.bot.message_pipeline import MessagePipeline
from linjing.processors.message_context import MessageContext
from linjing.processors.base_processor import BaseProcessor as Processor
from linjing.storage.database import DatabaseManager
from linjing.storage.vector_db_manager_factory import VectorDBManagerFactory

# 导入并发控制组件
from linjing.linjing_concurrent import (
    QueueManager, MessageDebouncer, 
    ResourceLockManager, EasyResourceLock, ResourceType
)

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

        # 初始化并发控制组件
        self.queue_manager = None
        self.message_debouncer = None
        self.resource_lock = None

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
            await self._init_concurrent_controls()
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

            # 启动并发控制组件
            if self.queue_manager:
                await self.queue_manager.start()
            if self.message_debouncer:
                await self.message_debouncer.start()

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

            # 停止并发控制组件
            if self.queue_manager:
                await self.queue_manager.stop()
            if self.message_debouncer:
                await self.message_debouncer.stop()
            # 停止资源锁管理器
            if self.resource_lock:
                if hasattr(self.resource_lock, 'stop') and callable(self.resource_lock.stop):
                    await self.resource_lock.stop()
                    logger.info("资源锁管理器已停止")

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

        # --- 新增：检查是否处于高警戒模式，用于消息合并 ---
        is_high_alert = False
        if self.storage_manager:
            try:
                session_id = message.get_session_id() if hasattr(message, 'get_session_id') else "default"
                session_state = await self.storage_manager.get_session_state(session_id)
                is_high_alert = session_state and session_state.get("is_high_alert", False)
            except Exception as e:
                logger.error(f"获取会话状态失败: {e}", exc_info=True)
        
        # --- 新增：尝试消息合并 ---
        if self.message_debouncer:
            try:
                was_debounced, group_id = await self.message_debouncer.process_message(
                    message=message,
                    context=context,
                    processor=self._process_single_message,
                    is_high_alert=is_high_alert
                )
                if was_debounced:
                    logger.debug(f"消息已被合并到组 {group_id}，稍后处理")
                    return None  # 消息被合并，暂不处理
            except Exception as e:
                logger.error(f"消息合并处理失败: {e}", exc_info=True)
        
        # --- 新增：通过队列管理器处理单条消息 ---
        if self.queue_manager:
            try:
                success = await self.queue_manager.add_message(
                    message=message,
                    context=context,
                    processor=self._process_single_message
                )
                if success:
                    logger.debug("消息已加入队列，按顺序处理")
                    return None  # 消息已加入队列，实际处理和返回将在队列处理时完成
                else:
                    logger.error("消息加入队列失败，尝试直接处理")
            except Exception as e:
                logger.error(f"消息队列处理失败: {e}", exc_info=True)
        
        # 如果并发控制组件不可用或失败，则直接处理消息
        logger.warning("并发控制失败或未启用，直接处理消息")
        return await self._process_single_message(message)

    async def _process_single_message(self, message: Any) -> Optional[Any]:
        """
        处理单条消息（在队列中或直接处理）
        
        Args:
            message: 消息对象
            
        Returns:
            处理后的响应消息
        """
        logger.info(f"开始处理消息: {message}")
        
        # 创建消息上下文
        context = MessageContext(
            message=message,
            user_id=message.get_user_id() if hasattr(message, 'get_user_id') else str(message),
            config=self.config,
            session_id=message.get_session_id() if hasattr(message, 'get_session_id') else "default"
        )

        # --- 使用资源锁保护共享资源访问 ---
        if self.resource_lock:
            # 使用资源锁保护记忆系统访问
            async with self.resource_lock.lock(ResourceType.MEMORY):
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
        else:
            # 如果没有资源锁，直接执行
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

        # 使用资源锁保护情绪系统访问
        if self.resource_lock and self.emotion_manager:
            async with self.resource_lock.lock(ResourceType.EMOTION):
                emotion = await self.emotion_manager.get_emotion(context.user_id)
                context.with_emotion(emotion.to_dict() if hasattr(emotion, 'to_dict') else emotion)
                logger.debug(f"获取到情绪状态: {context.get_state('emotion')}")
        elif self.emotion_manager:
            # 如果没有资源锁，直接执行
            emotion = await self.emotion_manager.get_emotion(context.user_id)
            context.with_emotion(emotion.to_dict() if hasattr(emotion, 'to_dict') else emotion)
            logger.debug(f"获取到情绪状态: {context.get_state('emotion')}")

        # 发布消息接收事件
        await self.event_bus.publish(
            EventType.MESSAGE_RECEIVED, {"message": message, "context": context}
        )

        # --- V12 处理流程：执行处理器管道 ---
        processed_context = await self._execute_processor_pipeline(context)
        
        # 从处理后的上下文中获取最终回复
        final_reply = processed_context.get_state("reply")

        # 发布消息发送事件
        if final_reply:
            await self.event_bus.publish(
                EventType.MESSAGE_SENT,
                {"message": final_reply, "context": processed_context}
            )

        # --- Return the reply first ---
        if final_reply:
             # --- 使用资源锁保护会话状态更新 ---
             if self.high_alert_mode_trigger_enabled and self.storage_manager:
                 session_id = message.get_session_id() if hasattr(message, 'get_session_id') else "default"
                 
                 if self.resource_lock:
                     async with self.resource_lock.lock(ResourceType.SESSION):
                         logger.info(f"机器人回复成功，会话 {session_id} 进入高戒备模式 (持续 {self.high_alert_duration} 条消息)。")
                         await self.storage_manager.update_session_state(
                             session_id,
                             is_high_alert=True,
                             high_alert_counter=0
                         )
                 else:
                     # 如果没有资源锁，直接执行
                     logger.info(f"机器人回复成功，会话 {session_id} 进入高戒备模式 (持续 {self.high_alert_duration} 条消息)。")
                     await self.storage_manager.update_session_state(
                         session_id,
                         is_high_alert=True,
                         high_alert_counter=0
                     )
             # --- 高戒备触发结束 ---

             # 为了尽快响应用户，将耗时的数据库写入操作放入后台任务执行
             asyncio.create_task(self._save_conversation_async(context, processed_context, message, final_reply))
             return final_reply
        else:
             logger.warning(f"消息处理完成但未生成回复: UserID={context.user_id}, SessionID={context.session_id}")
             # --- 即使没有回复，如果被提及，也可能需要开启高戒备 ---
             mentioned_or_named = await self._check_if_mentioned(message)
             if mentioned_or_named and self.high_alert_mode_trigger_enabled and self.storage_manager:
                 session_id = message.get_session_id() if hasattr(message, 'get_session_id') else "default"
                 
                 if self.resource_lock:
                     async with self.resource_lock.lock(ResourceType.SESSION):
                         # 检查是否已处于高戒备，避免重复日志和更新
                         current_state = await self.storage_manager.get_session_state(session_id)
                         if not current_state or not current_state.get("is_high_alert"):
                             logger.info(f"会话 {session_id} 因被提及但无回复而进入高戒备模式 (持续 {self.high_alert_duration} 条消息)。")
                             await self.storage_manager.update_session_state(
                                 session_id,
                                 is_high_alert=True,
                                 high_alert_counter=0
                             )
                 else:
                     # 如果没有资源锁，直接执行
                     # 检查是否已处于高戒备，避免重复日志和更新
                     current_state = await self.storage_manager.get_session_state(session_id)
                     if not current_state or not current_state.get("is_high_alert"):
                         logger.info(f"会话 {session_id} 因被提及但无回复而进入高戒备模式 (持续 {self.high_alert_duration} 条消息)。")
                         await self.storage_manager.update_session_state(
                             session_id,
                             is_high_alert=True,
                             high_alert_counter=0
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

        # 添加日志记录确认机器人ID
        logger.debug(f"检查消息触发条件，当前机器人ID: {self.self_id}, 机器人名字列表: {self.bot_names}")
        
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
            logger.debug(f"检查名字触发，消息文本: '{message_text}'")
            for name in self.bot_names:
                # 完整匹配 (消息等于名字)
                if message_text == name:
                    logger.debug(f"检测到完全匹配机器人名字: {name}")
                    mentioned_or_named = True
                    break
                # 开头匹配 (消息以名字开头，后跟空格)
                if message_text.startswith(name + " "):
                    logger.debug(f"检测到开头匹配机器人名字: {name}")
                    mentioned_or_named = True
                    break
                # 结尾匹配 (消息以空格加名字结尾)
                if message_text.endswith(" " + name):
                    logger.debug(f"检测到结尾匹配机器人名字: {name}")
                    mentioned_or_named = True
                    break
                # 中间包含 (消息中包含空格+名字+空格)
                if f" {name} " in f" {message_text} ":
                    logger.debug(f"检测到中间包含机器人名字: {name}")
                    mentioned_or_named = True
                    break
        
        # --- 特殊情况处理：始终在高戒备模式下处理 ---
        is_high_alert = session_state["is_high_alert"]
        # 当调试或开发时，可以开启此选项使机器人始终处于高戒备状态
        always_high_alert = getattr(self, 'always_high_alert', False) or self.config.get("debug", {}).get("always_high_alert", False)
        if always_high_alert:
            logger.debug("开发调试模式：始终保持高戒备状态")
            is_high_alert = True
            session_state["is_high_alert"] = True
            update_payload["is_high_alert"] = True
            
        # --- 检查是否应该处理消息 ---
        should_trigger_processing = False # 默认不处理

        # 1. 检查是否处于高戒备状态
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
            # 无论之前的高戒备状态如何，只要被提及就重置计数器
            logger.info(f"会话 {session_id} 因被提及而进入高戒备模式 (持续 {self.high_alert_duration} 条消息)。")
            update_payload["high_alert_counter"] = 0 # 重置计数器
            update_payload["is_high_alert"] = True # 确保开启或维持高戒备

        # --- 统一更新数据库状态 ---
        if needs_db_update or is_new_session:
             await self.storage_manager.update_session_state(session_id, **update_payload)
             
        # 添加最终决策日志
        logger.debug(f"消息处理决策: should_trigger_processing={should_trigger_processing}, mentioned_or_named={mentioned_or_named}")

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
                    if hasattr(processor, 'set_memory_manager') and self.memory_manager:
                         processor.set_memory_manager(self.memory_manager)
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
                    if hasattr(processor, 'set_memory_manager') and self.memory_manager:
                         processor.set_memory_manager(self.memory_manager)
                elif name == ProcessorName.RESPONSE_COMPOSER:
                    from linjing.processors.response_composer import ResponseComposer
                    processor = ResponseComposer(name=name, config=processor_config)
                    processor.set_llm_manager(self.llm_manager)
                    if hasattr(processor, 'set_memory_manager') and self.memory_manager:
                         processor.set_memory_manager(self.memory_manager)
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
                        # 为其他处理器也注入 LLM 和 Memory 管理器
                        if hasattr(processor, 'set_llm_manager') and self.llm_manager:
                            processor.set_llm_manager(self.llm_manager)
                        if hasattr(processor, 'set_memory_manager') and self.memory_manager:
                            processor.set_memory_manager(self.memory_manager)
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

    async def _init_concurrent_controls(self) -> None:
        """初始化并发控制组件"""
        logger.info("正在初始化并发控制组件...")
        
        # 创建并发控制配置的默认值
        concurrent_config = self.config.get("concurrent", {})
        
        # 初始化队列管理器
        queue_config = concurrent_config.get("queue_manager", {})
        self.queue_manager = QueueManager(
            default_queue_size=queue_config.get("default_queue_size", 100),
            default_concurrent=queue_config.get("default_concurrent", 5),
            default_timeout=queue_config.get("default_timeout", 60.0),
            idle_cleanup_interval=queue_config.get("idle_cleanup_interval", 300.0),
            event_bus=self.event_bus
        )
        await self.queue_manager.start()
        logger.info("队列管理器初始化完成")
        
        # 初始化消息去重/合并器
        debounce_config = concurrent_config.get("debounce", {})
        self.message_debouncer = MessageDebouncer(
            debounce_window=debounce_config.get("window", 0.5),
            min_messages_to_combine=debounce_config.get("min_messages", 2),
            max_messages_to_combine=debounce_config.get("max_messages", 5),
            high_alert_only=debounce_config.get("high_alert_only", True),
            check_interval=debounce_config.get("check_interval", 0.1)
        )
        await self.message_debouncer.start()
        # 设置合并后的处理函数
        self.message_debouncer.set_processor(self._process_message_batch)
        logger.info("消息去重/合并器初始化完成")
        
        # 初始化资源锁管理器
        lock_config = concurrent_config.get("lock", {})
        use_simplified_locks = lock_config.get("use_simplified", True)
        if use_simplified_locks:
            self.resource_lock = EasyResourceLock()
            self.resource_lock.start()
            logger.info("使用简化版资源锁管理器")
        else:
            self.resource_lock = ResourceLockManager(
                lock_timeout=lock_config.get("timeout", 30.0)
            )
            self.resource_lock.start()
            logger.info("使用完整版资源锁管理器")
        
        logger.info("并发控制组件初始化完成")
    
    async def _process_message_batch(self, messages: List[Any], contexts: List[Any], processor: Callable) -> None:
        """
        处理消息批次（合并消息）
        
        Args:
            messages: 消息列表
            contexts: 上下文列表
            processor: 处理函数
        """
        logger.info(f"开始处理合并消息组，共 {len(messages)} 条消息")
        
        if not messages:
            logger.warning("收到空的消息组，跳过处理")
            return
        
        # 目前简单处理：只处理组内最后一条消息
        last_message = messages[-1]
        last_context = contexts[-1] # 获取对应的上下文
        
        # 添加日志，标记这是从合并消息组中选取的
        logger.info(f"从合并消息组中选择最后一条消息进行处理: {last_message}")
        
        # 处理选中的消息
        try:
            # 确保 processor 是有效的 callable
            if callable(processor):
                 # 使用关键字参数调用处理器
                 await processor(message=last_message) 
            else:
                 logger.error(f"传递给 _process_message_batch 的处理器无效 (类型: {type(processor)})，无法处理消息组")
        except Exception as e:
            logger.error(f"处理合并消息中的选定消息时出错: {e}", exc_info=True)
    
    async def _execute_processor_pipeline(self, context: MessageContext) -> MessageContext:
        """
        执行处理器管道
        
        Args:
            context: 消息上下文
            
        Returns:
            处理后的上下文
        """
        processed_context = context
        
        # 1. 手动执行 ReadAirProcessor (如果存在)
        read_air_processor = self.get_processor(ProcessorName.READ_AIR)
        if read_air_processor:
            logger.debug("手动执行 ReadAirProcessor...")
            try:
                processed_context = await read_air_processor.process(processed_context)
                logger.debug(f"ReadAirProcessor 执行完毕。Context 状态: read_air_analysis={processed_context.get_state('read_air_analysis')}")
                
                # 打印读空气分析结果报告
                self._print_component_report("读空气分析", processed_context.get_state("read_air_analysis"))
                
                if not processed_context.get_state("read_air_analysis"):
                     logger.error("ReadAirProcessor 执行成功但未能生成有效的分析结果，终止处理。")
                     return processed_context
            except Exception as e:
                 logger.error(f"执行处理器 {ProcessorName.READ_AIR} 时出错，终止处理: {e}", exc_info=True)
                 return processed_context
        else:
            logger.warning(f"处理器管道中未找到 {ProcessorName.READ_AIR}，无法执行读空气分析。")

        # 2. 更新情绪状态 (基于 ReadAir 分析结果)
        if self.emotion_manager:
            logger.debug("开始更新情绪状态...")
            read_air_analysis = processed_context.get_state("read_air_analysis")
            message_text = processed_context.message.extract_plain_text() if hasattr(processed_context.message, 'extract_plain_text') else str(processed_context.message)
            factors = {"read_air_analysis": read_air_analysis if isinstance(read_air_analysis, dict) else {}}
            
            # 使用资源锁保护情绪更新
            if self.resource_lock:
                async with self.resource_lock.lock(ResourceType.EMOTION):
                    try:
                        updated_emotion = await self.emotion_manager.update_emotion(
                            processed_context.user_id, factors, message_text
                        )
                        processed_context.with_emotion(updated_emotion.to_dict() if hasattr(updated_emotion, 'to_dict') else updated_emotion)
                        logger.debug(f"情绪状态已更新并设置回上下文: {updated_emotion}")
                        
                        # 打印情绪状态报告
                        self._print_component_report("情绪状态", processed_context.get_state("emotion"))
                    except Exception as e:
                         logger.error(f"更新情绪状态时出错 (UserID: {processed_context.user_id}): {e}", exc_info=True)
            else:
                # 如果没有资源锁，直接执行
                try:
                    updated_emotion = await self.emotion_manager.update_emotion(
                        processed_context.user_id, factors, message_text
                    )
                    processed_context.with_emotion(updated_emotion.to_dict() if hasattr(updated_emotion, 'to_dict') else updated_emotion)
                    logger.debug(f"情绪状态已更新并设置回上下文: {updated_emotion}")
                    
                    # 打印情绪状态报告
                    self._print_component_report("情绪状态", processed_context.get_state("emotion"))
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
                        # 打印思考生成结果报告
                        self._print_component_report("思考生成", processed_context.get_state("thought"))
                    elif processor_name == ProcessorName.WILLINGNESS_CHECKER:
                        logger.debug(f"WillingnessChecker 执行完毕。Context 状态: is_willing_to_reply={processed_context.get_state('is_willing_to_reply')}")
                        # 打印意愿检查结果报告
                        willingness_report = {
                            "is_willing_to_reply": processed_context.get_state("is_willing_to_reply"),
                            "unwilling_reason": processed_context.get_state("unwilling_reason", ""),
                            "willingness_analysis": processed_context.get_state("willingness_analysis", {})
                        }
                        self._print_component_report("意愿检查", willingness_report)
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

        logger.debug("所有剩余处理器执行完毕。")
        return processed_context
    
    async def _check_if_mentioned(self, message: Any) -> bool:
        """
        检查消息是否提及了机器人
        
        Args:
            message: 消息对象
            
        Returns:
            是否提及了机器人
        """
        # 代码从 _should_process_message 方法中提取出来
        mentioned = False
        
        # 检查是否包含@提及
        if hasattr(message, 'segments') and isinstance(message.segments, list):
            for segment in message.segments:
                if (segment.type and segment.type.name == "AT" and 
                    segment.data and segment.data.get("qq") == self.self_id):
                    mentioned = True
                    break
        
        # 如果没找到@提及，检查文本中是否包含机器人名字
        if not mentioned and self.name_trigger_enabled:
            bot_names = self.config.get("bot", {}).get("bot_names", ["林静", "Linjing"])
            message_text = message.extract_plain_text() if hasattr(message, 'extract_plain_text') else str(message)
            
            for name in bot_names:
                if name in message_text:
                    mentioned = True
                    break
        
        return mentioned

    def _print_component_report(self, component_name: str, data: Any, prefix: str = "") -> None:
        """
        打印组件处理结果的详细报告
        
        Args:
            component_name: 组件名称
            data: 组件处理结果数据
            prefix: 日志前缀
        """
        if data is None:
            logger.info(f"{prefix}【{component_name}】处理结果为空")
            return

        logger.info(f"{prefix}【{component_name}】处理结果报告开始 ───────────────────")
        
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, dict) and len(value) > 5:
                    sub_items = list(value.items())[:5]
                    logger.info(f"{prefix}  {key}: {dict(sub_items)}... (共{len(value)}项)")
                elif isinstance(value, list) and len(value) > 5:
                    logger.info(f"{prefix}  {key}: {value[:5]}... (共{len(value)}项)")
                else:
                    value_str = str(value)
                    if len(value_str) > 100:
                        value_str = value_str[:97] + "..."
                    logger.info(f"{prefix}  {key}: {value_str}")
        elif isinstance(data, list):
            if len(data) > 5:
                for i, item in enumerate(data[:5]):
                    item_str = str(item)
                    if len(item_str) > 100:
                        item_str = item_str[:97] + "..."
                    logger.info(f"{prefix}  [{i}]: {item_str}")
                logger.info(f"{prefix}  ... (共{len(data)}项)")
            else:
                for i, item in enumerate(data):
                    item_str = str(item)
                    if len(item_str) > 100:
                        item_str = item_str[:97] + "..."
                    logger.info(f"{prefix}  [{i}]: {item_str}")
        else:
            value_str = str(data)
            if len(value_str) > 500:
                lines = value_str[:500].split('\n')
                for line in lines[:5]:
                    logger.info(f"{prefix}  {line}")
                logger.info(f"{prefix}  ... (内容过长，已截断)")
            else:
                lines = value_str.split('\n')
                for line in lines:
                    logger.info(f"{prefix}  {line}")
                    
        logger.info(f"{prefix}【{component_name}】处理结果报告结束 ───────────────────")

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