#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
适配器工具模块，提供适配器通用功能和工具类。
"""

import json
import time
import asyncio
import inspect
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Callable, Awaitable, Set, TypeVar, Union, Type

from linjing.utils.logger import get_logger
from linjing.adapters.message_types import Message, MessageSegment

# 获取日志记录器
logger = get_logger(__name__)

# 类型变量定义
T = TypeVar("T")
BotSelf = TypeVar("BotSelf", bound="Bot")
EventHandler = Callable[["Bot", Dict[str, Any]], Any]

class Bot(ABC):
    """
    Bot适配器基类。
    所有平台特定的Bot实现都应继承此类。
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化Bot适配器
        
        Args:
            config: Bot配置，包含连接和身份验证信息
        """
        self.config = config
        self.platform: str = "base"  # 平台标识，子类应覆盖此属性
        self.self_id: str = config.get("self_id", "")  # 机器人自身ID
        self.connected: bool = False  # 是否已连接到服务
        
        # 事件处理器
        self._event_handlers: Dict[str, List[EventHandler]] = {}
        
        # 任务管理器，用于管理异步任务
        from linjing.utils.task_manager import TaskManager
        self.tasks = TaskManager()
    
    @abstractmethod
    async def connect(self) -> None:
        """连接到平台服务"""
        raise NotImplementedError
    
    @abstractmethod
    async def disconnect(self) -> None:
        """断开与平台服务的连接"""
        raise NotImplementedError
    
    @abstractmethod
    async def send(self, target: str, message: Union[str, Message, MessageSegment]) -> str:
        """
        发送消息
        
        Args:
            target: 目标 ID (用户ID、群ID等)
            message: 要发送的消息
            
        Returns:
            消息ID
        """
        raise NotImplementedError
    
    async def call_api(self, api: str, **params) -> Any:
        """
        调用平台API
        
        Args:
            api: API名称
            **params: API参数
            
        Returns:
            API返回结果
        """
        raise NotImplementedError
    
    def on(self, event: str) -> Callable[[EventHandler], EventHandler]:
        """
        注册事件处理器的装饰器
        
        Args:
            event: 事件名称
            
        Returns:
            装饰器
        """
        def decorator(func: EventHandler) -> EventHandler:
            self.add_event_handler(event, func)
            return func
        return decorator
    
    def add_event_handler(self, event: str, func: EventHandler) -> None:
        """
        添加事件处理器
        
        Args:
            event: 事件名称
            func: 事件处理函数
        """
        if event not in self._event_handlers:
            self._event_handlers[event] = []
        self._event_handlers[event].append(func)
        logger.debug(f"Added event handler for {event}: {func.__name__}")
    
    def remove_event_handler(self, event: str, func: EventHandler) -> bool:
        """
        移除事件处理器
        
        Args:
            event: 事件名称
            func: 事件处理函数
            
        Returns:
            是否成功移除
        """
        if event in self._event_handlers and func in self._event_handlers[event]:
            self._event_handlers[event].remove(func)
            logger.debug(f"Removed event handler for {event}: {func.__name__}")
            return True
        return False
    
    async def handle_event(self, event_type: str, event: Dict[str, Any]) -> List[Any]:
        """
        处理事件
        
        Args:
            event_type: 事件类型
            event: 事件数据
            
        Returns:
            所有处理器的返回值列表
        """
        results = []
        
        # 查找事件处理器
        handlers = self._event_handlers.get(event_type, [])
        if not handlers:
            return results
        
        # 调用所有处理器
        for handler in handlers:
            try:
                result = handler(self, event)
                if inspect.isawaitable(result):
                    result = await result
                results.append(result)
            except Exception as e:
                logger.error(f"Error in event handler {handler.__name__}: {e}", exc_info=True)
        
        return results
    
    async def send_to_user(self, user_id: str, message: Union[str, Message, MessageSegment]) -> str:
        """
        发送私聊消息
        
        Args:
            user_id: 用户ID
            message: 要发送的消息
            
        Returns:
            消息ID
        """
        return await self.send(user_id, message)
    
    async def send_to_group(self, group_id: str, message: Union[str, Message, MessageSegment]) -> str:
        """
        发送群消息
        
        Args:
            group_id: 群ID
            message: 要发送的消息
            
        Returns:
            消息ID
        """
        return await self.send(group_id, message)
    
    def run_task(self, task_func: Callable[..., Any], *args: Any, **kwargs: Any) -> asyncio.Task:
        """
        运行异步任务并进行管理
        
        Args:
            task_func: 任务函数
            *args: 位置参数
            **kwargs: 关键字参数
            
        Returns:
            任务对象
        """
        return self.tasks.create_task(task_func(*args, **kwargs))
    
    def get_name(self) -> str:
        """
        获取Bot名称
        
        Returns:
            Bot名称，默认为平台名+ID
        """
        return f"{self.platform}-{self.self_id}"
    
    @classmethod
    async def create(cls: Type[BotSelf], config: Dict[str, Any]) -> BotSelf:
        """
        创建Bot实例的工厂方法
        
        Args:
            config: Bot配置
            
        Returns:
            Bot实例
        """
        bot = cls(config)
        await bot.connect()
        return bot

class ApiRateLimiter:
    """
    API速率限制器，用于限制API调用频率
    """
    
    def __init__(self, rate_limit: float = 5.0, burst_limit: int = 10):
        """
        初始化速率限制器
        
        Args:
            rate_limit: 每秒请求数限制
            burst_limit: 突发请求数上限
        """
        self.rate_limit = rate_limit
        self.burst_limit = burst_limit
        self.tokens = burst_limit
        self.last_refill_time = time.time()
        self.lock = asyncio.Lock()
    
    async def acquire(self) -> bool:
        """
        获取一个令牌，如果成功返回True
        
        Returns:
            是否获取成功
        """
        async with self.lock:
            # 计算应该补充的令牌
            now = time.time()
            elapsed = now - self.last_refill_time
            self.last_refill_time = now
            
            # 按时间比例补充令牌
            new_tokens = elapsed * self.rate_limit
            self.tokens = min(self.burst_limit, self.tokens + new_tokens)
            
            # 尝试获取令牌
            if self.tokens >= 1.0:
                self.tokens -= 1.0
                return True
            
            return False
    
    async def wait_for_token(self, timeout: Optional[float] = None) -> bool:
        """
        等待直到获取到令牌或超时
        
        Args:
            timeout: 超时时间（秒）
            
        Returns:
            是否获取成功
        """
        start_time = time.time()
        while timeout is None or time.time() - start_time < timeout:
            if await self.acquire():
                return True
            
            # 计算需要等待的时间
            wait_time = 1.0 / self.rate_limit if self.tokens < 1.0 else 0.01
            await asyncio.sleep(min(wait_time, 0.5))
        
        return False

class AdapterRegistry:
    """适配器注册表，用于管理所有可用的适配器"""
    
    _adapters = {}
    
    @classmethod
    def register(cls, name: str):
        """
        注册适配器的装饰器
        
        Args:
            name: 适配器名称
            
        Returns:
            装饰器函数
        """
        def decorator(adapter_class):
            cls._adapters[name] = adapter_class
            logger.debug(f"注册适配器: {name}")
            return adapter_class
        
        return decorator
    
    @classmethod
    def get(cls, name: str) -> Optional[type]:
        """
        获取适配器类
        
        Args:
            name: 适配器名称
            
        Returns:
            适配器类，如果不存在则返回None
        """
        return cls._adapters.get(name)
    
    @classmethod
    def list_adapters(cls) -> Dict[str, type]:
        """
        列出所有已注册的适配器
        
        Returns:
            适配器名称到类的映射
        """
        return cls._adapters.copy()

class MessageConverter:
    """消息转换器，用于在不同平台的消息格式之间转换"""
    
    @staticmethod
    def to_internal_message(platform: str, raw_message: Any) -> Message:
        """
        将平台原始消息转换为内部消息格式
        
        Args:
            platform: 平台名称
            raw_message: 平台原始消息
            
        Returns:
            内部消息对象
        """
        if platform == "onebot":
            # OneBot消息转换
            if isinstance(raw_message, dict) and "message" in raw_message:
                return Message.from_onebot_event(raw_message)
            elif isinstance(raw_message, list):
                segments = []
                for seg in raw_message:
                    if seg["type"] == "text":
                        segments.append(MessageSegment.text(seg["data"]["text"]))
                    # 其他类型的处理...
                return Message(segments)
            elif isinstance(raw_message, str):
                return Message(MessageSegment.text(raw_message))
        
        # 默认情况下尝试转换为文本
        try:
            return Message(MessageSegment.text(str(raw_message)))
        except:
            logger.error(f"无法转换消息: {raw_message}")
            return Message()
    
    @staticmethod
    def to_platform_message(platform: str, message: Message) -> Any:
        """
        将内部消息格式转换为平台原始消息
        
        Args:
            platform: 平台名称
            message: 内部消息对象
            
        Returns:
            平台原始消息
        """
        if platform == "onebot":
            # OneBot消息转换
            return message.to_onebot_format()
        
        # 默认返回字符串表示
        return str(message)

async def retry_operation(
    operation: Callable[[], Awaitable[Any]],
    max_retries: int = 3,
    retry_delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: tuple = (Exception,)
) -> Any:
    """
    重试异步操作
    
    Args:
        operation: 要重试的异步操作
        max_retries: 最大重试次数
        retry_delay: 初始重试延迟（秒）
        backoff_factor: 退避因子
        exceptions: 触发重试的异常类型
        
    Returns:
        操作结果
        
    Raises:
        Exception: 超过最大重试次数后仍然失败
    """
    retries = 0
    last_exception = None
    
    while retries <= max_retries:
        try:
            return await operation()
        except exceptions as e:
            last_exception = e
            retries += 1
            
            if retries > max_retries:
                break
            
            # 计算退避延迟
            delay = retry_delay * (backoff_factor ** (retries - 1))
            logger.debug(f"操作失败，{delay:.2f}秒后重试 ({retries}/{max_retries}): {str(e)}")
            
            await asyncio.sleep(delay)
    
    # 所有重试都失败了
    raise last_exception

def is_command(message: Message, command_prefix: str = "/") -> bool:
    """
    检查消息是否是命令
    
    Args:
        message: 消息对象
        command_prefix: 命令前缀
        
    Returns:
        是否是命令
    """
    text = message.extract_plain_text().strip()
    return text.startswith(command_prefix)

def parse_command(message: Message, command_prefix: str = "/") -> Optional[Dict[str, Any]]:
    """
    解析命令消息
    
    Args:
        message: 消息对象
        command_prefix: 命令前缀
        
    Returns:
        解析结果，包含命令和参数。如果不是命令则返回None
    """
    text = message.extract_plain_text().strip()
    
    if not text.startswith(command_prefix):
        return None
    
    # 移除前缀
    content = text[len(command_prefix):].strip()
    
    # 分割命令和参数
    parts = content.split(maxsplit=1)
    command = parts[0].lower()
    args_text = parts[1] if len(parts) > 1 else ""
    
    # 解析参数
    args = []
    kwargs = {}
    
    # 简单参数解析，支持带引号的参数
    if args_text:
        import re
        # 匹配带引号的参数或普通参数
        pattern = r'([^\s"\']+)|"([^"]*)"|\'([^\']*)\')'
        matches = re.findall(pattern, args_text)
        
        for match in matches:
            # 取第一个非空值
            arg = next((x for x in match if x), "")
            
            # 尝试解析键值对参数
            if "=" in arg and not arg.startswith("="):
                key, value = arg.split("=", 1)
                kwargs[key.strip()] = value.strip()
            else:
                args.append(arg)
    
    return {
        "command": command,
        "args": args,
        "kwargs": kwargs,
        "raw_args": args_text
    }

def escape_message_text(text: str) -> str:
    """
    转义消息文本中的特殊字符
    
    Args:
        text: 原始文本
        
    Returns:
        转义后的文本
    """
    # 转义特殊字符
    text = text.replace("&", "&amp;")
    text = text.replace("[", "&#91;")
    text = text.replace("]", "&#93;")
    text = text.replace(",", "&#44;")
    
    return text

def unescape_message_text(text: str) -> str:
    """
    反转义消息文本中的特殊字符
    
    Args:
        text: 转义后的文本
        
    Returns:
        原始文本
    """
    # 反转义特殊字符
    text = text.replace("&#44;", ",")
    text = text.replace("&#93;", "]")
    text = text.replace("&#91;", "[")
    text = text.replace("&amp;", "&")
    
    return text

async def download_file(url: str, session=None, timeout: float = 30.0) -> bytes:
    """
    下载文件
    
    Args:
        url: 文件URL
        session: aiohttp会话对象，如果为None则创建新会话
        timeout: 超时时间（秒）
        
    Returns:
        文件内容
        
    Raises:
        Exception: 下载失败
    """
    import aiohttp
    
    close_session = False
    if session is None:
        session = aiohttp.ClientSession()
        close_session = True
    
    try:
        async with session.get(url, timeout=timeout) as response:
            if response.status != 200:
                raise Exception(f"下载失败，状态码: {response.status}")
            
            return await response.read()
    finally:
        if close_session:
            await session.close() 