import asyncio
from .constants import EventType  # 确保导入 EventType
from .message import Message # 假设需要 Message 类型提示
from .adapters.base import BaseAdapter # 假设需要 BaseAdapter 类型提示

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

    # ... (其他方法如 start, stop, handle_message) ...

# ... existing code ... 