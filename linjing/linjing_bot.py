import asyncio
from .constants import EventType  # 确保导入 EventType
from .message import Message # 假设需要 Message 类型提示
from .adapters.base import BaseAdapter # 假设需要 BaseAdapter 类型提示
from loguru import logger # 确保 logger 已导入
import json

class LinjingBot:
    # ... (其他属性和方法) ...

    def __init__(self, config_path="config.yml"):
        # ... (其他初始化代码) ...

        self.event_bus = EventBus()
        self.logger.info("事件总线 EventBus 初始化完成")

        # 在初始化 EventBus 后，注册事件监听器
        self._register_event_listeners()

        # ... (加载处理器、适配器等其他初始化代码) ...
        self.logger.info("LinjingBot 初始化完成")

    def _register_event_listeners(self):
        """注册核心事件监听器"""
        self.event_bus.subscribe(EventType.SEND_MESSAGE_REQUEST, self._handle_send_request)
        self.logger.info(f"已注册事件监听器: {EventType.SEND_MESSAGE_REQUEST.name} -> _handle_send_request")
        # 未来可以注册更多事件监听器

    async def _handle_send_request(self, event_data: dict):
        """处理 SEND_MESSAGE_REQUEST 事件，调用适配器发送消息"""
        try:
            adapter = event_data.get("adapter")
            original_message = event_data.get("original_message")
            reply_content = event_data.get("reply_content")
            platform = event_data.get("platform", "Unknown")

            if not isinstance(adapter, BaseAdapter):
                self.logger.error(f"无效的适配器类型在 SEND_MESSAGE_REQUEST 事件中: {type(adapter)}. Data: {event_data}")
                return

            if not original_message:
                self.logger.error(f"缺少原始消息对象 original_message 在 SEND_MESSAGE_REQUEST 事件中. Data: {event_data}")
                return

            if not reply_content:
                self.logger.warning(f"空的回复内容 reply_content 在 SEND_MESSAGE_REQUEST 事件中 (平台: {platform}). Data: {event_data}")
                # 根据策略，可以选择不发送空消息或发送提示
                # return # 例如，如果不想发送空消息
                pass # 或者继续尝试发送（如果适配器能处理）

            self.logger.info(f"接收到 SEND_MESSAGE_REQUEST 事件，准备通过适配器 {adapter.__class__.__name__} (平台: {platform}) 发送消息.")
            self.logger.debug(f"发送详情: Reply Content='{reply_content}', Original Message Context='{original_message}'")

            # 调用适配器的发送方法
            # 注意：假设适配器有 send 方法，并且接受原始消息对象和回复内容
            # 你可能需要根据实际的适配器实现调整此处的调用
            await adapter.send(original_message, reply_content)

            self.logger.info(f"消息已通过适配器 {adapter.__class__.__name__} (平台: {platform}) 成功发送（或已提交发送）。")

        except Exception as e:
            self.logger.error(f"处理 SEND_MESSAGE_REQUEST 事件并发送消息时出错: {e}", exc_info=True)
            self.logger.error(f"事件数据: {event_data}")

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

        # ... (获取历史、情绪、发布事件等) ...

        # --- V12 处理流程：执行处理器管道 ---
        processed_context = await self._execute_processor_pipeline(context)
        
        # 从处理后的上下文中获取最终回复
        # 假设最终回复存储在 processed_context 的 _state['reply'] 中
        final_reply = processed_context.get_state("reply")

        # --- 添加日志：检查 final_reply 和返回值 --- 
        logger.debug(f"_process_single_message: Pipeline finished. Extracted final_reply (type: {type(final_reply)}): {str(final_reply)[:200]}...")
        # --- 日志结束 ---

        # 发布消息发送事件 (注意：这部分现在由事件总线处理，可能需要移除或调整)
        # if final_reply:
        #     await self.event_bus.publish(
        #         EventType.MESSAGE_SENT,
        #         {"message": final_reply, "context": processed_context}
        #     )

        # --- Return the reply first ---
        if final_reply:
             # --- 高戒备模式逻辑 (保持不变) ---
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
             
             # --- 添加返回前日志 --- 
             logger.debug(f"_process_single_message: Returning final_reply: {str(final_reply)[:200]}...")
             # --- 日志结束 --- 
             return final_reply
        else:
             logger.warning(f"消息处理完成但未生成回复: UserID={context.user_id}, SessionID={context.session_id}")
             # --- 无回复时的其他逻辑 (保持不变) ---
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
             # --- 添加返回前日志 --- 
             logger.debug(f"_process_single_message: Returning None (no reply generated).")
             # --- 日志结束 ---
             return None

    # ... (其他方法如 start, stop, handle_message) ...

# ... existing code ... 