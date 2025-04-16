#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import asyncio
import aiohttp
import time
import uuid
from typing import Dict, Any, List, Optional, Callable, Awaitable, Union, Set
from aiohttp import web, ClientSession, WSMsgType, ClientWebSocketResponse

from utils.logger import get_logger
from core.message_processor import MessageProcessor
from .message_adapter import MessageAdapter
from .server_config import ServerConfig


class OneBotProxy:
    """OneBot协议代理，负责与napcat等客户端通信"""
    
    def __init__(self, config: Dict[str, Any], message_processor: MessageProcessor):
        """初始化OneBot代理"""
        self.config = ServerConfig.from_dict(config)
        self.message_processor = message_processor
        self.message_adapter = MessageAdapter()
        self.logger = get_logger("OneBotProxy")
        
        # HTTP服务器
        self.app = web.Application()
        self.runner = None
        self.site = None
        
        # WebSocket连接
        self.ws_clients: Set[web.WebSocketResponse] = set()
        self.napcat_ws: Optional[ClientWebSocketResponse] = None
        self.napcat_session: Optional[ClientSession] = None
        
        # 连接状态
        self.reconnect_task = None
        self.heartbeat_task = None
        self.is_running = False
        self.reconnect_attempts = 0
        
        # 消息处理回调
        self.event_handlers: Dict[str, List[Callable[[Dict[str, Any]], Awaitable[None]]]] = {
            "message": [],
            "notice": [],
            "request": [],
            "meta": []
        }
        
        # 初始化路由
        self._setup_routes()
    
    def _setup_routes(self):
        """设置HTTP和WebSocket路由"""
        # API路由
        self.app.router.add_post(self.config.http.endpoint, self.handle_http_api)
        self.app.router.add_get(self.config.http.endpoint + "/status", self.handle_status)
        
        # WebSocket路由
        self.app.router.add_get(self.config.websocket.endpoint, self.handle_websocket)
    
    async def start(self):
        """启动OneBot代理服务"""
        if self.is_running:
            return
        
        self.logger.info("启动OneBot代理服务...")
        
        # 启动HTTP服务器
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        self.site = web.TCPSite(
            self.runner, 
            self.config.websocket.host, 
            self.config.websocket.port
        )
        await self.site.start()
        self.logger.info(f"HTTP/WebSocket服务已启动: http://{self.config.websocket.host}:{self.config.websocket.port}")
        
        # 如果启用napcat，连接到napcat
        if self.config.napcat.enabled:
            self.reconnect_task = asyncio.create_task(self.connect_to_napcat())
            
        # 启动心跳任务
        self.heartbeat_task = asyncio.create_task(self.send_heartbeat())
        
        self.is_running = True
    
    async def stop(self):
        """停止OneBot代理服务"""
        if not self.is_running:
            return
        
        self.logger.info("正在停止OneBot代理服务...")
        
        # 取消所有任务
        if self.reconnect_task:
            self.reconnect_task.cancel()
            try:
                await self.reconnect_task
            except asyncio.CancelledError:
                pass
        
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            try:
                await self.heartbeat_task
            except asyncio.CancelledError:
                pass
        
        # 关闭所有WebSocket连接
        for client in self.ws_clients:
            await client.close()
        
        # 关闭napcat连接
        if self.napcat_ws:
            await self.napcat_ws.close()
        
        if self.napcat_session:
            await self.napcat_session.close()
        
        # 关闭HTTP服务器
        if self.site:
            await self.site.stop()
        
        if self.runner:
            await self.runner.cleanup()
        
        self.is_running = False
        self.logger.info("OneBot代理服务已停止")
    
    async def connect_to_napcat(self):
        """连接到napcat WebSocket服务"""
        max_attempts = self.config.napcat.max_reconnect_attempts
        reconnect_interval = self.config.napcat.reconnect_interval
        
        while self.is_running and (max_attempts <= 0 or self.reconnect_attempts < max_attempts):
            try:
                self.logger.info(f"正在连接到napcat WebSocket服务 (尝试 {self.reconnect_attempts + 1})...")
                
                # 创建新会话和WebSocket连接
                if self.napcat_session:
                    await self.napcat_session.close()
                
                self.napcat_session = aiohttp.ClientSession()
                ws_url = f"{self.config.napcat.api_base.replace('http', 'ws')}/ws"
                
                # 添加认证参数
                params = {}
                if self.config.napcat.auth_token:
                    params["access_token"] = self.config.napcat.auth_token
                if self.config.napcat.device_id:
                    params["device_id"] = self.config.napcat.device_id
                
                self.napcat_ws = await self.napcat_session.ws_connect(ws_url, params=params)
                self.logger.info("已成功连接到napcat WebSocket服务")
                
                # 发送连接事件
                await self.send_to_napcat({
                    "type": "meta",
                    "detail_type": "connect",
                    "version": self.config.napcat.protocol_version,
                    "client": {
                        "app_name": self.config.server_name,
                        "app_version": "1.0.0",
                        "protocol_version": self.config.napcat.protocol_version
                    }
                })
                
                # 接收消息
                self.reconnect_attempts = 0  # 重置重连次数
                await self.receive_napcat_messages()
                
            except aiohttp.ClientError as e:
                self.logger.error(f"连接到napcat失败: {e}")
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger.error(f"处理napcat连接时出错: {e}", exc_info=True)
            finally:
                # 清理连接
                if self.napcat_ws:
                    await self.napcat_ws.close()
                    self.napcat_ws = None
                
                # 如果仍在运行，则尝试重连
                if self.is_running:
                    self.reconnect_attempts += 1
                    if max_attempts > 0 and self.reconnect_attempts >= max_attempts:
                        self.logger.error(f"已达到最大重连尝试次数 ({max_attempts})，停止重连")
                        break
                    
                    self.logger.info(f"将在 {reconnect_interval} 秒后尝试重连...")
                    await asyncio.sleep(reconnect_interval)
    
    async def receive_napcat_messages(self):
        """接收来自napcat的WebSocket消息"""
        if not self.napcat_ws:
            return
        
        async for msg in self.napcat_ws:
            if msg.type == WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    await self.handle_napcat_message(data)
                except json.JSONDecodeError:
                    self.logger.error(f"无法解析napcat消息: {msg.data}")
            elif msg.type == WSMsgType.ERROR:
                self.logger.error(f"napcat WebSocket错误: {self.napcat_ws.exception()}")
                break
            elif msg.type == WSMsgType.CLOSED:
                self.logger.info("napcat WebSocket连接已关闭")
                break
    
    async def handle_napcat_message(self, data: Dict[str, Any]):
        """处理来自napcat的消息"""
        try:
            # 提取消息类型
            msg_type = data.get("type", "")
            detail_type = data.get("detail_type", "")
            
            self.logger.debug(f"收到napcat消息: {msg_type}/{detail_type}")
            
            # 处理不同类型的事件
            if msg_type == "message":
                # 处理聊天消息
                await self.process_message(data)
            elif msg_type == "notice":
                # 处理通知事件
                await self.process_notice(data)
            elif msg_type == "request":
                # 处理请求事件
                await self.process_request(data)
            elif msg_type == "meta":
                # 处理元事件
                if detail_type == "heartbeat":
                    # 心跳响应，不需要特殊处理
                    pass
                else:
                    self.logger.debug(f"收到元事件: {detail_type}")
            
            # 广播消息给所有连接的WebSocket客户端
            await self.broadcast_to_clients(data)
            
            # 调用注册的事件处理器
            if msg_type in self.event_handlers:
                for handler in self.event_handlers[msg_type]:
                    await handler(data)
                    
        except Exception as e:
            self.logger.error(f"处理napcat消息时出错: {e}", exc_info=True)
    
    async def process_message(self, data: Dict[str, Any]):
        """处理聊天消息"""
        try:
            # 提取消息内容
            message = data.get("message", [])
            sender = data.get("sender", {})
            user_id = sender.get("user_id", "")
            message_id = data.get("message_id", "")
            
            # 将napcat消息格式转换为标准OneBot格式
            onebot_message = self.message_adapter.adapt_from_napcat(message)
            
            # 转换为内部消息格式
            internal_message = self.message_adapter.adapt_from_onebot(onebot_message)
            
            # 交给消息处理器处理
            processor_response = await self.message_processor.process(
                message=internal_message,
                user_id=user_id,
                message_id=message_id,
                raw_data=data
            )
            
            # 如果有响应，发送回复
            if processor_response:
                # 转换为OneBot格式
                reply_onebot = self.message_adapter.adapt_to_onebot(processor_response)
                
                # 添加回复信息
                reply_with_id = self.message_adapter.create_reply_message(message_id, reply_onebot)
                
                # 转换为napcat格式并发送
                napcat_message = self.message_adapter.adapt_to_napcat(reply_with_id)
                
                # 构建回复数据
                reply_data = {
                    "action": "send_message",
                    "params": {
                        "detail_type": data.get("detail_type", "private"),
                        "message": napcat_message
                    }
                }
                
                # 如果是群聊
                if data.get("detail_type") == "group":
                    reply_data["params"]["group_id"] = data.get("group_id", "")
                else:
                    reply_data["params"]["user_id"] = user_id
                
                # 发送回复
                await self.send_to_napcat(reply_data)
        
        except Exception as e:
            self.logger.error(f"处理消息时出错: {e}", exc_info=True)
    
    async def process_notice(self, data: Dict[str, Any]):
        """处理通知事件"""
        # 这里可以添加通知事件的处理逻辑
        self.logger.debug(f"收到通知事件: {data.get('detail_type', '')}")
    
    async def process_request(self, data: Dict[str, Any]):
        """处理请求事件"""
        # 这里可以添加请求事件的处理逻辑
        self.logger.debug(f"收到请求事件: {data.get('detail_type', '')}")
    
    async def send_to_napcat(self, data: Dict[str, Any]):
        """发送消息到napcat"""
        if not self.napcat_ws or self.napcat_ws.closed:
            self.logger.warning("尝试发送消息但napcat WebSocket未连接")
            return
        
        try:
            # 添加消息ID
            if "echo" not in data:
                data["echo"] = str(uuid.uuid4())
            
            # 序列化并发送
            await self.napcat_ws.send_json(data)
            self.logger.debug(f"发送到napcat: {data.get('action', '')}")
        except Exception as e:
            self.logger.error(f"发送消息到napcat失败: {e}")
    
    async def broadcast_to_clients(self, data: Dict[str, Any]):
        """广播消息给所有连接的WebSocket客户端"""
        if not self.ws_clients:
            return
        
        message_json = json.dumps(data)
        disconnected_clients = set()
        
        for client in self.ws_clients:
            try:
                await client.send_str(message_json)
            except Exception:
                disconnected_clients.add(client)
        
        # 移除断开连接的客户端
        for client in disconnected_clients:
            self.ws_clients.remove(client)
    
    async def send_heartbeat(self):
        """定期发送心跳包"""
        interval = self.config.websocket.heartbeat_interval
        
        while self.is_running:
            try:
                # 发送心跳到napcat
                if self.napcat_ws and not self.napcat_ws.closed:
                    await self.send_to_napcat({
                        "type": "meta",
                        "detail_type": "heartbeat",
                        "interval": interval
                    })
                
                # 发送心跳到所有WebSocket客户端
                heartbeat_data = {
                    "type": "meta",
                    "detail_type": "heartbeat",
                    "time": int(time.time()),
                    "interval": interval,
                    "status": {
                        "good": self.napcat_ws is not None and not self.napcat_ws.closed,
                        "online": True
                    }
                }
                
                await self.broadcast_to_clients(heartbeat_data)
                
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.logger.error(f"发送心跳时出错: {e}")
            
            await asyncio.sleep(interval)
    
    async def handle_websocket(self, request):
        """处理WebSocket连接请求"""
        # 验证访问令牌
        if self.config.websocket.access_token:
            token = request.query.get("access_token")
            if token != self.config.websocket.access_token:
                return web.Response(status=403, text="未授权")
        
        # 建立WebSocket连接
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        
        self.logger.info(f"新的WebSocket客户端已连接: {request.remote}")
        self.ws_clients.add(ws)
        
        try:
            # 发送连接成功通知
            await ws.send_json({
                "type": "meta",
                "detail_type": "connect",
                "version": self.config.napcat.protocol_version
            })
            
            # 接收客户端消息
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        # 处理来自客户端的API调用
                        response = await self.handle_api_request(data)
                        if response:
                            await ws.send_json(response)
                    except json.JSONDecodeError:
                        await ws.send_json({"status": "failed", "message": "Invalid JSON"})
                elif msg.type == WSMsgType.ERROR:
                    self.logger.error(f"WebSocket错误: {ws.exception()}")
        finally:
            # 断开连接时清理
            self.ws_clients.discard(ws)
            self.logger.info(f"WebSocket客户端已断开连接: {request.remote}")
        
        return ws
    
    async def handle_http_api(self, request):
        """处理HTTP API请求"""
        # 验证访问令牌
        if self.config.http.access_token:
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer ") or auth_header[7:] != self.config.http.access_token:
                return web.json_response({"status": "failed", "message": "未授权"}, status=403)
        
        try:
            # 读取并解析请求
            data = await request.json()
            
            # 处理API调用
            response = await self.handle_api_request(data)
            
            # 返回响应
            return web.json_response(response if response else {"status": "ok"})
        except json.JSONDecodeError:
            return web.json_response({"status": "failed", "message": "无效的JSON"}, status=400)
        except Exception as e:
            self.logger.error(f"处理HTTP API请求时出错: {e}", exc_info=True)
            return web.json_response({"status": "failed", "message": str(e)}, status=500)
    
    async def handle_api_request(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """处理API请求并返回响应"""
        action = data.get("action", "")
        params = data.get("params", {})
        echo = data.get("echo", None)
        
        response = {
            "status": "ok",
            "retcode": 0,
            "data": None
        }
        
        if echo:
            response["echo"] = echo
        
        try:
            if action == "send_message":
                # 发送消息
                await self.handle_send_message(params)
            elif action == "get_status":
                # 获取状态
                response["data"] = {
                    "good": True,
                    "online": self.napcat_ws is not None and not self.napcat_ws.closed
                }
            elif action == "get_version":
                # 获取版本信息
                response["data"] = {
                    "impl": "maibot-onebot",
                    "version": "1.0.0",
                    "onebot_version": self.config.napcat.protocol_version
                }
            else:
                # 转发到napcat
                if self.napcat_ws and not self.napcat_ws.closed:
                    await self.send_to_napcat(data)
                    # 对于某些需要等待napcat响应的操作，此处应有更复杂的逻辑
                else:
                    response["status"] = "failed"
                    response["retcode"] = 1404
                    response["message"] = "napcat未连接"
        
        except Exception as e:
            self.logger.error(f"处理API请求'{action}'时出错: {e}", exc_info=True)
            response["status"] = "failed"
            response["retcode"] = 1400
            response["message"] = str(e)
        
        return response
    
    async def handle_send_message(self, params: Dict[str, Any]):
        """处理发送消息的API请求"""
        # 从参数中提取必要信息
        detail_type = params.get("detail_type", "private")
        message = params.get("message", "")
        user_id = params.get("user_id", "")
        group_id = params.get("group_id", "")
        
        # 确保消息格式正确
        if isinstance(message, str):
            # 转换为消息段列表
            message = self.message_adapter.adapt_to_onebot(message)
        
        # 转换为napcat格式
        napcat_message = self.message_adapter.adapt_to_napcat(message)
        
        # 构建请求数据
        request_data = {
            "action": "send_message",
            "params": {
                "detail_type": detail_type,
                "message": napcat_message
            }
        }
        
        # 添加目标ID
        if detail_type == "group":
            request_data["params"]["group_id"] = group_id
        else:
            request_data["params"]["user_id"] = user_id
        
        # 发送到napcat
        if self.napcat_ws and not self.napcat_ws.closed:
            await self.send_to_napcat(request_data)
        else:
            raise Exception("napcat未连接")
    
    async def handle_status(self, request):
        """处理状态查询请求"""
        status = {
            "status": "ok",
            "data": {
                "online": self.is_running,
                "napcat_connected": self.napcat_ws is not None and not self.napcat_ws.closed,
                "client_count": len(self.ws_clients),
                "reconnect_attempts": self.reconnect_attempts,
                "server_name": self.config.server_name,
                "protocol_version": self.config.napcat.protocol_version
            }
        }
        return web.json_response(status)
    
    def register_handler(self, event_type: str, handler: Callable[[Dict[str, Any]], Awaitable[None]]):
        """注册事件处理器"""
        if event_type in self.event_handlers:
            self.event_handlers[event_type].append(handler)
        else:
            self.logger.warning(f"尝试注册未知事件类型的处理器: {event_type}")
    
    def unregister_handler(self, event_type: str, handler: Callable[[Dict[str, Any]], Awaitable[None]]):
        """取消注册事件处理器"""
        if event_type in self.event_handlers and handler in self.event_handlers[event_type]:
            self.event_handlers[event_type].remove(handler) 