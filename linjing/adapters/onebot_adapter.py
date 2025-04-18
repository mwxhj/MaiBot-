#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
OneBot适配器模块，实现与OneBot协议的通信。
"""

import json
import time
import asyncio
import logging
import websockets
from typing import Dict, List, Any, Optional, Callable, Set, Union

import aiohttp

from linjing.utils.logger import get_logger
from linjing.utils.async_tools import AsyncRetry
from linjing.constants import EventType
from linjing.bot.event_bus import EventBus
from linjing.adapters.message_types import Message, MessageSegment
from linjing.adapters.adapter_utils import (
    ApiRateLimiter, AdapterRegistry, MessageConverter, retry_operation
)

# 获取日志记录器
logger = get_logger(__name__)

@AdapterRegistry.register("onebot")
class OneBotAdapter:
    """OneBot适配器，用于与OneBot协议通信"""
    
    def __init__(self, config: Dict[str, Any], event_bus: EventBus):
        """
        初始化OneBot适配器
        
        Args:
            config: 适配器配置
            event_bus: 事件总线
        """
        self.config = config
        self.event_bus = event_bus
        self.connected = False
        self.websocket = None
        self.session = None
        self.api_url = None
        self.ws_url = None
        self.message_handler = None
        self.heartbeat_task = None
        self.message_listener_task = None
        
        # API限流器
        self.rate_limiter = ApiRateLimiter(
            rate_limit=config.get("rate_limit", 5.0),
            burst_limit=config.get("burst_limit", 10)
        )
        
        # 连接配置
        self.host = config.get("host", "127.0.0.1")
        self.port = config.get("port", 8080)
        self.access_token = config.get("access_token", "")
        self.heartbeat_interval = config.get("heartbeat_interval", 5000) / 1000  # 转换为秒
        
        # HTTP接口URL
        self.api_url = f"http://{self.host}:{self.port}"
        
        # WebSocket接口URL
        ws_query = f"?access_token={self.access_token}" if self.access_token else ""
        self.ws_url = f"ws://{self.host}:{self.port}{ws_query}"
        
        # 已注册的事件处理器
        self.event_handlers: Dict[str, List[Callable]] = {}
    
    async def connect(self) -> bool:
        """
        连接到OneBot服务端
        
        Returns:
            是否连接成功
        """
        if self.connected:
            logger.warning("OneBot适配器已经连接")
            return True
        
        try:
            # 创建HTTP会话
            self.session = aiohttp.ClientSession(
                headers={
                    "Authorization": f"Bearer {self.access_token}" if self.access_token else ""
                }
            )
            
            # 连接WebSocket
            logger.info(f"正在连接到OneBot WebSocket: {self.ws_url}")
            
            # 这里使用重试机制，以处理初始连接失败的情况
            async def connect_ws():
                try:
                    # 尝试使用没有headers的简单连接
                    return await websockets.connect(self.ws_url)
                except Exception as e:
                    logger.warning(f"简单连接失败，尝试其他方式: {e}")
                    # 可能是其他原因导致的错误，重新抛出
                    raise
            
            # 使用更通用的异常处理，适应不同版本的websockets库
            # 新版websockets库已将异常移至顶层命名空间
            self.websocket = await retry_operation(
                connect_ws,
                max_retries=3,
                retry_delay=1.0,
                exceptions=(
                    # 尝试兼容不同版本的websockets库
                    Exception, 
                    ConnectionError,
                    # 如果存在以下异常类，也会被捕获
                    getattr(websockets, 'ConnectionClosed', type('DummyException', (Exception,), {})),
                    getattr(websockets, 'WebSocketException', type('DummyException', (Exception,), {}))
                )
            )
            
            # 标记为已连接
            self.connected = True
            
            # 启动心跳任务
            self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            
            # 启动消息监听任务
            self.message_listener_task = asyncio.create_task(self._message_listener())
            
            logger.info("OneBot适配器连接成功")
            return True
            
        except Exception as e:
            logger.error(f"OneBot适配器连接失败: {str(e)}")
            # 清理资源
            await self._cleanup()
            return False
    
    async def disconnect(self) -> None:
        """断开与OneBot服务端的连接"""
        if not self.connected:
            return
        
        logger.info("正在断开OneBot适配器连接")
        await self._cleanup()
        logger.info("OneBot适配器已断开连接")
    
    async def _cleanup(self) -> None:
        """清理资源"""
        self.connected = False
        
        # 取消心跳任务
        if self.heartbeat_task and not self.heartbeat_task.done():
            self.heartbeat_task.cancel()
            try:
                await self.heartbeat_task
            except asyncio.CancelledError:
                pass
        
        # 取消消息监听任务
        if self.message_listener_task and not self.message_listener_task.done():
            self.message_listener_task.cancel()
            try:
                await self.message_listener_task
            except asyncio.CancelledError:
                pass
        
        # 关闭WebSocket连接
        if self.websocket:
            await self.websocket.close()
            self.websocket = None
        
        # 关闭HTTP会话
        if self.session:
            await self.session.close()
            self.session = None
    
    async def _heartbeat_loop(self) -> None:
        """心跳循环，定期发送心跳包"""
        try:
            while self.connected:
                try:
                    # 发送心跳包
                    await self.websocket.send(json.dumps({
                        "op": 2,
                        "d": {
                            "heartbeat_interval": self.heartbeat_interval * 1000
                        }
                    }))
                    logger.debug(f"OneBot心跳包已发送")
                except Exception as e:
                    logger.error(f"OneBot心跳发送失败: {str(e)}")
                    # 如果发送失败，可能是连接已断开
                    if not self.connected:
                        break
                
                # 等待下一次心跳
                await asyncio.sleep(self.heartbeat_interval)
        except asyncio.CancelledError:
            logger.debug("OneBot心跳任务已取消")
            raise
        except Exception as e:
            logger.error(f"OneBot心跳循环异常: {str(e)}")
            # 尝试重新连接
            if self.connected:
                self.connected = False
                asyncio.create_task(self._reconnect())
    
    async def _message_listener(self) -> None:
        """消息监听循环，接收并处理WebSocket消息"""
        try:
            while self.connected:
                try:
                    # 接收消息
                    raw_message = await self.websocket.recv()
                    await self._handle_ws_message(raw_message)
                except websockets.exceptions.ConnectionClosed as e:
                    logger.error(f"OneBot WebSocket连接已关闭: {str(e)}")
                    break
                except Exception as e:
                    logger.error(f"OneBot消息处理异常: {str(e)}")
        except asyncio.CancelledError:
            logger.debug("OneBot消息监听任务已取消")
            raise
        except Exception as e:
            logger.error(f"OneBot消息监听循环异常: {str(e)}")
        finally:
            # 如果不是主动断开，尝试重新连接
            if self.connected:
                self.connected = False
                asyncio.create_task(self._reconnect())
    
    async def _reconnect(self) -> None:
        """重新连接到OneBot服务端"""
        logger.info("正在尝试重新连接OneBot服务端")
        
        # 先等待一段时间，避免立即重连
        await asyncio.sleep(3)
        
        # 确保资源已清理
        await self._cleanup()
        
        # 尝试连接
        if not await self.connect():
            # 连接失败，等待更长时间后再次尝试
            logger.warning("OneBot重新连接失败，10秒后重试")
            await asyncio.sleep(10)
            asyncio.create_task(self._reconnect())
    
    async def _handle_ws_message(self, raw_message: str) -> None:
        """
        处理WebSocket消息
        
        Args:
            raw_message: 原始消息字符串
        """
        try:
            # 解析消息
            data = json.loads(raw_message)
            
            # 判断消息类型
            if "post_type" in data:
                # OneBot v11 事件
                await self._handle_onebot_event(data)
            elif "op" in data:
                # 协议消息
                op = data.get("op")
                
                if op == 2:  # PING
                    # 回复PONG
                    await self.websocket.send(json.dumps({
                        "op": 3,
                        "d": data.get("d", {})
                    }))
                elif op == 0:  # DISPATCH
                    # 事件分发
                    event_data = data.get("d", {})
                    if "post_type" in event_data:
                        await self._handle_onebot_event(event_data)
            else:
                logger.warning(f"未知的OneBot消息格式: {raw_message}")
        except json.JSONDecodeError:
            logger.error(f"OneBot消息解析失败: {raw_message}")
        except Exception as e:
            logger.error(f"OneBot消息处理失败: {str(e)}", exc_info=True)
    
    async def _handle_onebot_event(self, event: Dict[str, Any]) -> None:
        """
        处理OneBot事件
        
        Args:
            event: OneBot事件数据
        """
        try:
            post_type = event.get("post_type")
            
            # 消息事件
            if post_type == "message":
                await self._handle_message_event(event)
            
            # 通知事件
            elif post_type == "notice":
                await self._handle_notice_event(event)
            
            # 请求事件
            elif post_type == "request":
                await self._handle_request_event(event)
            
            # 元事件
            elif post_type == "meta_event":
                await self._handle_meta_event(event)
            
            # 其他事件
            else:
                logger.debug(f"OneBot未处理的事件类型: {post_type}")
                
            # 发布到事件总线
            await self.event_bus.publish(
                f"onebot.{post_type}",
                {
                    "platform": "onebot",
                    "raw_event": event
                }
            )
            
        except Exception as e:
            logger.error(f"OneBot事件处理失败: {str(e)}", exc_info=True)
    
    async def _handle_message_event(self, event: Dict[str, Any]) -> None:
        """
        处理消息事件
        
        Args:
            event: OneBot消息事件数据
        """
        message_type = event.get("message_type", "")
        logger.debug(f"OneBot消息事件: {message_type}")
        
        # 转换为内部消息格式
        message = MessageConverter.to_internal_message("onebot", event)
        
        # 调用消息处理器
        if self.message_handler:
            try:
                response = await self.message_handler(message)
                
                # 如果有响应，自动回复
                if response:
                    target_info = {
                        "message_type": message_type
                    }
                    
                    # 添加目标信息
                    if message_type == "private":
                        target_info["user_id"] = event.get("user_id")
                    elif message_type == "group":
                        target_info["group_id"] = event.get("group_id")
                    
                    # 发送响应
                    await self.send_message(response, target_info)
            except Exception as e:
                logger.error(f"OneBot消息处理器异常: {str(e)}", exc_info=True)
        
        # 发布到事件总线
        await self.event_bus.publish(
            EventType.MESSAGE_RECEIVED,
            {
                "platform": "onebot",
                "message": message,
                "raw_event": event
            }
        )
    
    async def _handle_notice_event(self, event: Dict[str, Any]) -> None:
        """
        处理通知事件
        
        Args:
            event: OneBot通知事件数据
        """
        notice_type = event.get("notice_type", "")
        logger.debug(f"OneBot通知事件: {notice_type}")
    
    async def _handle_request_event(self, event: Dict[str, Any]) -> None:
        """
        处理请求事件
        
        Args:
            event: OneBot请求事件数据
        """
        request_type = event.get("request_type", "")
        logger.debug(f"OneBot请求事件: {request_type}")
    
    async def _handle_meta_event(self, event: Dict[str, Any]) -> None:
        """
        处理元事件
        
        Args:
            event: OneBot元事件数据
        """
        meta_event_type = event.get("meta_event_type", "")
        logger.debug(f"OneBot元事件: {meta_event_type}")
        
        # 心跳事件
        if meta_event_type == "heartbeat":
            # 这里可以更新状态或计算延迟等
            pass
        
        # 生命周期事件
        elif meta_event_type == "lifecycle":
            sub_type = event.get("sub_type", "")
            if sub_type == "connect":
                logger.info("OneBot服务端已连接")
            elif sub_type == "enable":
                logger.info("OneBot服务端已启用")
            elif sub_type == "disable":
                logger.info("OneBot服务端已禁用")
    
    async def send_message(
        self, message: Union[Message, str], target_info: Dict[str, Any]
    ) -> str:
        """
        发送消息
        
        Args:
            message: 消息对象或文本
            target_info: 目标信息，如message_type、user_id、group_id等
            
        Returns:
            消息ID
        """
        if not self.connected:
            logger.error("OneBot适配器未连接，无法发送消息")
            raise ConnectionError("OneBot适配器未连接")
        
        # 等待速率限制
        await self.rate_limiter.wait_for_token()
        
        # 转换消息格式
        if isinstance(message, str):
            message = Message.from_text(message)
        
        # 获取消息类型
        message_type = target_info.get("message_type", "private")
        
        # 构造API调用参数
        params = {
            "message": MessageConverter.to_platform_message("onebot", message)
        }
        
        # 添加目标信息
        if message_type == "private":
            api_name = "send_private_msg"
            params["user_id"] = target_info.get("user_id")
        elif message_type == "group":
            api_name = "send_group_msg"
            params["group_id"] = target_info.get("group_id")
        else:
            raise ValueError(f"不支持的消息类型: {message_type}")
        
        # 调用API
        try:
            response = await self._call_api(api_name, params)
            message_id = response.get("data", {}).get("message_id", "")
            
            # 发布消息发送事件
            await self.event_bus.publish(
                EventType.MESSAGE_SENT,
                {
                    "platform": "onebot",
                    "message": message,
                    "message_id": message_id,
                    "target_info": target_info
                }
            )
            
            return message_id
        except Exception as e:
            logger.error(f"OneBot发送消息失败: {str(e)}")
            raise
    
    async def _call_api(self, api_name: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        调用OneBot API
        
        Args:
            api_name: API名称
            params: API参数
            
        Returns:
            API响应
        """
        if not self.connected or not self.session:
            logger.error("OneBot适配器未连接，无法调用API")
            raise ConnectionError("OneBot适配器未连接")
        
        # 等待速率限制
        await self.rate_limiter.wait_for_token()
        
        # 构造请求数据
        data = {
            "action": api_name,
            "params": params or {}
        }
        
        # 通过HTTP API调用
        try:
            async with self.session.post(
                f"{self.api_url}/api/{api_name}",
                json=params,
                headers={
                    "Content-Type": "application/json"
                },
                timeout=30
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"API调用失败，状态码: {response.status}, 响应: {error_text}")
                
                result = await response.json()
                
                if result.get("status") != "ok" and result.get("retcode") != 0:
                    raise Exception(f"API调用失败: {result.get('msg') or result.get('message')}")
                
                return result
        except aiohttp.ClientError as e:
            logger.error(f"OneBot API调用网络错误: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"OneBot API调用失败: {str(e)}")
            raise
    
    def register_message_handler(self, handler: Callable) -> None:
        """
        注册消息处理函数
        
        Args:
            handler: 消息处理函数，接收Message对象，返回可选的响应Message
        """
        self.message_handler = handler
        logger.debug("OneBot消息处理器已注册")
    
    def register_event_handler(self, event_type: str, handler: Callable) -> None:
        """
        注册事件处理函数
        
        Args:
            event_type: 事件类型，如message.private, notice.group_increase等
            handler: 事件处理函数，接收事件数据字典
        """
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        
        self.event_handlers[event_type].append(handler)
        logger.debug(f"OneBot事件处理器已注册: {event_type}")
    
    def unregister_event_handler(self, event_type: str, handler: Callable) -> bool:
        """
        取消注册事件处理函数
        
        Args:
            event_type: 事件类型
            handler: 事件处理函数
            
        Returns:
            是否成功取消注册
        """
        if event_type in self.event_handlers:
            if handler in self.event_handlers[event_type]:
                self.event_handlers[event_type].remove(handler)
                logger.debug(f"OneBot事件处理器已取消注册: {event_type}")
                
                # 如果没有处理器了，清除该事件类型
                if not self.event_handlers[event_type]:
                    del self.event_handlers[event_type]
                
                return True
        
        return False 