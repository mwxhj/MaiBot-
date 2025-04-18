#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
OneBot v11 协议适配器
支持正向WebSocket和反向WebSocket两种连接方式
"""

import asyncio
import json
import logging
import socket
import time
from typing import Dict, Any, Optional, Union

import aiohttp
import websockets
from websockets.exceptions import ConnectionClosed

from linjing.adapters.adapter_utils import Bot, MessageConverter, retry_operation
from linjing.adapters.message_types import Message, MessageSegment
from linjing.utils.logger import get_logger

logger = get_logger(__name__)

class OneBotAdapter(Bot):
    """OneBot v11 协议适配器"""
    
    def __init__(self, config: Dict[str, Any], event_bus: Any): # Added event_bus parameter
        super().__init__(config)
        self.platform = "onebot"
        self.event_bus = event_bus # Store event_bus
        
        # WebSocket连接配置
        self.ws_url = config.get("ws_url", "")  # 正向WS地址
        self.reverse_ws_host = config.get("reverse_ws_host", "0.0.0.0")
        # 优先使用环境变量中的端口配置
        import os
        self.reverse_ws_port = int(os.getenv("ONEBOT_PORT", config.get("reverse_ws_port", 6700)))
        self.is_reverse = config.get("is_reverse", False)
        
        # 连接状态
        self.websocket = None
        self.session = None
        self.server_task = None
        self.message_listener_task = None
        self.heartbeat_task = None
        
        # API限速器
        from linjing.adapters.adapter_utils import ApiRateLimiter
        self.rate_limiter = ApiRateLimiter(rate_limit=5.0, burst_limit=10)
        
        # 注册适配器
        from linjing.adapters.adapter_utils import AdapterRegistry
        AdapterRegistry.register("onebot")(self.__class__)

    async def connect(self) -> bool:
        """连接到OneBot实现"""
        try:
            # 创建aiohttp会话
            self.session = aiohttp.ClientSession()
            
            if self.is_reverse:
                return await self._start_reverse_server()
            else:
                return await self._start_forward_connection()
                
        except Exception as e:
            logger.error(f"连接失败: {e}", exc_info=True)
            await self._cleanup()
            return False

    async def _start_reverse_server(self) -> bool:
        """启动反向WebSocket服务器"""
        try:
            # 定义连接处理器（使用嵌套函数确保正确绑定self）
            async def handle_connection(websocket):
                """处理反向WebSocket连接"""
                try:
                    # 尝试从 websocket.request.path 获取路径
                    try:
                        path = websocket.request.path
                        logger.debug(f"成功获取 websocket.request.path: {path}")
                    except AttributeError as e:
                        logger.error(f"无法获取 websocket.request.path: {e}. Websocket 对象类型: {type(websocket)}, Request 对象类型: {type(websocket.request)}, 可用属性/方法: {dir(websocket)}", exc_info=True)
                        await websocket.close(code=1011, reason="Internal server error accessing request path")
                        return

                    # 标准化路径处理
                    path = str(path).split('?')[0]  # 去除查询参数
                    path = path.rstrip('/')    # 统一去除尾部斜杠

                    # 验证WebSocket路径是否符合OneBot协议
                    if path != "/onebot/v11/ws":
                        logger.warning(f"拒绝无效路径: {path} (原始: {websocket.request.path if hasattr(websocket, 'request') and hasattr(websocket.request, 'path') else 'N/A'})")
                        await websocket.close(code=1003, reason="Invalid path")
                        return

                    logger.info(f"接受来自 {websocket.remote_address} 的反向WebSocket连接 (路径: {path})")
                    
                    # 更新连接状态
                    self.websocket = websocket
                    self.connected = True
                    
                    # 启动消息监听任务
                    self.message_listener_task = self.run_task(self._message_listener)
                    
                    # 保持连接直到监听任务完成
                    try:
                        await self.message_listener_task
                    except Exception as e:
                        logger.error(f"消息监听异常: {e}", exc_info=True)
                    finally:
                        self.connected = False
                        self.websocket = None
                        
                except Exception as e:
                    logger.error(f"连接处理异常: {e}", exc_info=True)
                    raise

            # 启动WebSocket服务器
            # 创建底层socket并配置
            # 确保端口是整数
            port = int(self.reverse_ws_port)
            
            # 创建并配置socket
            sock = socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("0.0.0.0", port))
            sock.listen()
            
            # 使用预配置的socket创建WebSocket服务器
            self.server_task = await websockets.serve(
                handle_connection,
                sock=sock
            )
            
            logger.info(f"反向WebSocket服务器已启动，监听 {self.reverse_ws_host}:{self.reverse_ws_port}")
            return True
            
        except OSError as e:
            logger.error(f"无法启动反向WebSocket服务器: {e}")
            return False
        except Exception as e:
            logger.error(f"反向服务器启动异常: {e}", exc_info=True)
            return False

    async def _start_forward_connection(self) -> bool:
        """建立正向WebSocket连接"""
        try:
            # 使用重试机制连接
            self.websocket = await retry_operation(
                lambda: websockets.connect(self.ws_url),
                max_retries=3,
                retry_delay=1.0,
                backoff_factor=2.0,
                exceptions=(ConnectionError,)
            )
            
            self.connected = True
            logger.info(f"已连接到正向WebSocket: {self.ws_url}")
            
            # 启动心跳和消息监听
            self.heartbeat_task = self.run_task(self._heartbeat_loop)
            self.message_listener_task = self.run_task(self._message_listener)
            
            return True
            
        except Exception as e:
            logger.error(f"正向连接失败: {e}", exc_info=True)
            return False

    async def disconnect(self) -> None:
        """断开连接"""
        await self._cleanup()

    async def _cleanup(self):
        """清理资源"""
        # 取消所有任务
        for task in [self.server_task, self.message_listener_task, self.heartbeat_task]:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass

        # 关闭WebSocket连接
        if self.websocket:
            try:
                await self.websocket.close()
            except Exception:
                pass
            self.websocket = None

        # 关闭aiohttp会话
        if self.session:
            await self.session.close()
            self.session = None

        self.connected = False
        logger.info("连接已关闭，资源已清理")

    async def _heartbeat_loop(self):
        """心跳循环（仅正向连接需要）"""
        if self.is_reverse:
            return
            
        while self.connected:
            try:
                await asyncio.sleep(30)
                if self.connected and self.websocket:
                    await self.websocket.send(json.dumps({
                        "post_type": "meta_event",
                        "meta_event_type": "heartbeat",
                        "time": int(time.time())
                    }))
            except ConnectionClosed:
                logger.warning("心跳检测到连接已关闭")
                self.connected = False
                break
            except Exception as e:
                logger.error(f"心跳异常: {e}", exc_info=True)
                self.connected = False
                break

    async def _message_listener(self):
        """消息监听循环"""
        while self.connected and self.websocket:
            try:
                message = await self.websocket.recv()
                logger.debug(f"收到原始消息: {message}") # 添加原始消息日志
                if not message:
                    continue

                try:
                    event = json.loads(message)
                    await self._handle_event(event)
                except json.JSONDecodeError:
                    logger.error(f"无效的JSON消息: {message}")
                except Exception as e:
                    logger.error(f"处理消息异常: {e}", exc_info=True)

            except ConnectionClosed:
                logger.warning("WebSocket连接已关闭")
                self.connected = False
                break
            except Exception as e:
                logger.error(f"消息监听异常: {e}", exc_info=True)
                self.connected = False
                break

    async def _handle_event(self, event: Dict[str, Any]):
        """处理OneBot事件"""
        logger.debug(f"处理事件: {event}") # 添加解析后事件日志
        event_type = event.get("post_type")
        if not event_type:
            logger.warning(f"收到缺少 'post_type' 的事件: {event}")
            return

        # 转换消息格式
        if "message" in event and isinstance(event["message"], list): # 确保 message 是列表才转换
            try:
                # 注意：这里修改了原始 event 字典
                event["message"] = Message.from_onebot_event(event)
                logger.debug(f"消息转换后的事件: {event}")
            except Exception as e:
                logger.error(f"消息转换失败: {e}", exc_info=True)
                # 即使转换失败，也可能需要处理事件本身（例如通知事件）
                # return # 决定是否在转换失败时中止

        # 调用事件处理器 (位于 adapter_utils.py 的 Bot 基类中)
        await self.handle_event(event_type, event)

    async def send(self, target: str, message: Union[str, Message, MessageSegment]) -> str:
        """发送消息"""
        if not self.connected:
            raise ConnectionError("未连接到OneBot实现")
            
        # 等待API限速器
        await self.rate_limiter.wait_for_token()
        
        # 转换消息格式
        if isinstance(message, (str, MessageSegment)):
            message = Message(message)
            
        onebot_message = MessageConverter.to_platform_message("onebot", message)
        
        # 构造API请求
        api_request = {
            "action": "send_msg",
            "params": {
                "message_type": "private" if target.isdigit() else "group",
                target.isdigit() and "user_id" or "group_id": target,
                "message": onebot_message
            }
        }
        
        try:
            # 发送请求
            await self.websocket.send(json.dumps(api_request))
            
            # 简单实现：返回当前时间戳作为消息ID
            return str(int(time.time()))
            
        except Exception as e:
            logger.error(f"发送消息失败: {e}", exc_info=True)
            raise

    async def call_api(self, api: str, **params) -> Any:
        """调用OneBot API"""
        if not self.connected:
            raise ConnectionError("未连接到OneBot实现")
            
        # 等待API限速器
        await self.rate_limiter.wait_for_token()
        
        # 构造API请求
        api_request = {
            "action": api,
            "params": params
        }
        
        try:
            # 发送请求
            await self.websocket.send(json.dumps(api_request))
            
            # 简单实现：不等待响应
            return {"status": "async", "retcode": 0}
            
        except Exception as e:
            logger.error(f"调用API失败: {e}", exc_info=True)
            raise
