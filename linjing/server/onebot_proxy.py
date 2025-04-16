#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
林镜(LingJing) - OneBot协议代理
"""

import json
import asyncio
import logging
import aiohttp
from typing import Dict, Any, List, Callable, Optional, Union
from aiohttp import web

from ..exceptions import ConnectionError, AuthenticationError, RequestError
from ..config import get_config

class OneBotProxy:
    """OneBot协议代理，处理与OneBot协议的通信"""
    
    def __init__(self):
        """初始化OneBot代理"""
        self.logger = logging.getLogger('linjing.onebot')
        self._handlers = []  # 消息处理器列表
        self._app = None     # aiohttp应用实例
        self._runner = None  # aiohttp运行器
        self._site = None    # aiohttp站点
        self._session = None # aiohttp会话
        self._config = get_config().get('server', {})
        self._access_token = self._config.get('access_token', '')
        self._api_base_url = None
    
    async def start_server(self, host: str = '127.0.0.1', port: int = 8080) -> None:
        """
        启动WebSocket服务器
        
        Args:
            host: 服务器主机地址
            port: 服务器端口
        """
        self.logger.info(f"启动OneBot服务器 {host}:{port}")
        
        # 创建aiohttp应用
        self._app = web.Application()
        
        # 注册路由
        self._app.router.add_get('/onebot/ws', self._handle_websocket)
        self._app.router.add_post('/onebot/http', self._handle_http)
        
        # 启动服务器
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, host, port)
        await self._site.start()
        
        # 创建HTTP会话
        self._session = aiohttp.ClientSession()
        
        self.logger.info("OneBot服务器已启动")
    
    async def stop_server(self) -> None:
        """停止WebSocket服务器"""
        self.logger.info("正在关闭OneBot服务器")
        
        # 关闭HTTP会话
        if self._session:
            await self._session.close()
            self._session = None
        
        # 关闭aiohttp站点
        if self._site:
            await self._site.stop()
            self._site = None
        
        # 关闭aiohttp运行器
        if self._runner:
            await self._runner.cleanup()
            self._runner = None
        
        self.logger.info("OneBot服务器已关闭")
    
    def register_handler(self, handler: Callable[[Dict[str, Any]], None]) -> None:
        """
        注册消息处理器
        
        Args:
            handler: 消息处理函数，接收消息数据字典
        """
        self._handlers.append(handler)
        self.logger.debug(f"已注册消息处理器: {handler.__name__}")
    
    async def _handle_websocket(self, request: web.Request) -> web.WebSocketResponse:
        """
        处理WebSocket连接
        
        Args:
            request: WebSocket请求
        
        Returns:
            WebSocket响应
        """
        # 验证访问令牌
        if self._access_token:
            auth_header = request.headers.get('Authorization', '')
            if not auth_header.startswith('Bearer ') or auth_header[7:] != self._access_token:
                self.logger.warning("WebSocket认证失败")
                raise web.HTTPUnauthorized(reason="认证失败")
        
        # 建立WebSocket连接
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        self.logger.info("WebSocket连接已建立")
        
        # 处理WebSocket消息
        try:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        await self._process_message(data)
                    except json.JSONDecodeError:
                        self.logger.error(f"无效的JSON数据: {msg.data}")
                    except Exception as e:
                        self.logger.error(f"处理消息时发生错误: {e}", exc_info=True)
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    self.logger.error(f"WebSocket连接错误: {ws.exception()}")
        finally:
            self.logger.info("WebSocket连接已关闭")
        
        return ws
    
    async def _handle_http(self, request: web.Request) -> web.Response:
        """
        处理HTTP请求
        
        Args:
            request: HTTP请求
        
        Returns:
            HTTP响应
        """
        # 验证访问令牌
        if self._access_token:
            auth_header = request.headers.get('Authorization', '')
            if not auth_header.startswith('Bearer ') or auth_header[7:] != self._access_token:
                self.logger.warning("HTTP认证失败")
                return web.json_response({"status": "failed", "message": "认证失败"}, status=401)
        
        # 解析请求数据
        try:
            data = await request.json()
        except json.JSONDecodeError:
            self.logger.error("无效的JSON数据")
            return web.json_response({"status": "failed", "message": "无效的JSON数据"}, status=400)
        
        # 处理消息
        try:
            await self._process_message(data)
            return web.json_response({"status": "ok"})
        except Exception as e:
            self.logger.error(f"处理消息时发生错误: {e}", exc_info=True)
            return web.json_response({"status": "failed", "message": str(e)}, status=500)
    
    async def _process_message(self, data: Dict[str, Any]) -> None:
        """
        处理接收到的消息
        
        Args:
            data: 消息数据
        """
        # 调用所有注册的处理器
        for handler in self._handlers:
            try:
                await asyncio.create_task(handler(data))
            except Exception as e:
                self.logger.error(f"处理器 {handler.__name__} 处理消息时发生错误: {e}", exc_info=True)
    
    async def send_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        发送消息到OneBot
        
        Args:
            message: 消息数据
            
        Returns:
            响应数据
        """
        # 确保API基础URL已设置
        if not self._api_base_url:
            self._api_base_url = get_config().get('server', {}).get('api_base_url')
            if not self._api_base_url:
                raise ConnectionError("未设置API基础URL")
        
        # 确保HTTP会话已创建
        if not self._session:
            self._session = aiohttp.ClientSession()
        
        # 构建请求头
        headers = {}
        if self._access_token:
            headers['Authorization'] = f"Bearer {self._access_token}"
        
        # 发送请求
        try:
            action = message.get('action', '')
            endpoint = f"{self._api_base_url}/{action}"
            
            async with self._session.post(
                endpoint,
                headers=headers,
                json=message,
                timeout=self._config.get('http_timeout', 30)
            ) as response:
                # 检查状态码
                if response.status != 200:
                    error_text = await response.text()
                    raise RequestError(f"API请求失败: {response.status} {error_text}")
                
                # 解析响应
                result = await response.json()
                return result
        except aiohttp.ClientError as e:
            raise ConnectionError(f"连接OneBot API失败: {e}")
        except json.JSONDecodeError:
            raise RequestError("无法解析OneBot API响应")
        except asyncio.TimeoutError:
            raise RequestError("OneBot API请求超时")
    
    async def set_api_base_url(self, url: str) -> None:
        """
        设置API基础URL
        
        Args:
            url: API基础URL
        """
        self._api_base_url = url
        self.logger.info(f"已设置API基础URL: {url}")
    
    async def send_private_message(self, user_id: int, message: Union[str, List], auto_escape: bool = False) -> Dict[str, Any]:
        """
        发送私聊消息
        
        Args:
            user_id: 目标QQ号
            message: 消息内容，可以是字符串或消息段列表
            auto_escape: 是否转义消息内容
            
        Returns:
            响应数据
        """
        return await self.send_message({
            "action": "send_private_msg",
            "params": {
                "user_id": user_id,
                "message": message,
                "auto_escape": auto_escape
            }
        })
    
    async def send_group_message(self, group_id: int, message: Union[str, List], auto_escape: bool = False) -> Dict[str, Any]:
        """
        发送群聊消息
        
        Args:
            group_id: 群号
            message: 消息内容，可以是字符串或消息段列表
            auto_escape: 是否转义消息内容
            
        Returns:
            响应数据
        """
        return await self.send_message({
            "action": "send_group_msg",
            "params": {
                "group_id": group_id,
                "message": message,
                "auto_escape": auto_escape
            }
        })
    
    async def send_msg(self, message_type: str, user_id: Optional[int] = None, 
                      group_id: Optional[int] = None, message: Union[str, List] = None, 
                      auto_escape: bool = False) -> Dict[str, Any]:
        """
        发送消息
        
        Args:
            message_type: 消息类型，可以是 private、group
            user_id: 目标QQ号（私聊）
            group_id: 群号（群聊）
            message: 消息内容，可以是字符串或消息段列表
            auto_escape: 是否转义消息内容
            
        Returns:
            响应数据
        """
        return await self.send_message({
            "action": "send_msg",
            "params": {
                "message_type": message_type,
                "user_id": user_id,
                "group_id": group_id,
                "message": message,
                "auto_escape": auto_escape
            }
        })
    
    async def delete_msg(self, message_id: int) -> Dict[str, Any]:
        """
        撤回消息
        
        Args:
            message_id: 消息ID
            
        Returns:
            响应数据
        """
        return await self.send_message({
            "action": "delete_msg",
            "params": {
                "message_id": message_id
            }
        })
    
    async def get_login_info(self) -> Dict[str, Any]:
        """
        获取登录号信息
        
        Returns:
            响应数据，包含 user_id(QQ号)和 nickname(QQ昵称)
        """
        return await self.send_message({
            "action": "get_login_info",
            "params": {}
        })
    
    async def get_group_list(self) -> Dict[str, Any]:
        """
        获取群列表
        
        Returns:
            响应数据，包含群信息列表
        """
        return await self.send_message({
            "action": "get_group_list",
            "params": {}
        })
    
    async def get_group_member_info(self, group_id: int, user_id: int, no_cache: bool = False) -> Dict[str, Any]:
        """
        获取群成员信息
        
        Args:
            group_id: 群号
            user_id: QQ号
            no_cache: 是否不使用缓存
            
        Returns:
            响应数据，包含群成员信息
        """
        return await self.send_message({
            "action": "get_group_member_info",
            "params": {
                "group_id": group_id,
                "user_id": user_id,
                "no_cache": no_cache
            }
        })
    
    async def get_group_member_list(self, group_id: int) -> Dict[str, Any]:
        """
        获取群成员列表
        
        Args:
            group_id: 群号
            
        Returns:
            响应数据，包含群成员列表
        """
        return await self.send_message({
            "action": "get_group_member_list",
            "params": {
                "group_id": group_id
            }
        }) 
# -*- coding: utf-8 -*-

"""
林镜(LingJing) - OneBot协议代理
"""



class OneBotProxy:
    """OneBot协议代理，处理与OneBot协议的通信"""
    
    def __init__(self):
        """初始化OneBot代理"""
        self.logger = logging.getLogger('linjing.onebot')
        self._handlers = []  # 消息处理器列表
        self._app = None     # aiohttp应用实例
        self._runner = None  # aiohttp运行器
        self._site = None    # aiohttp站点
        self._session = None # aiohttp会话
        self._config = get_config().get('server', {})
        self._access_token = self._config.get('access_token', '')
        self._api_base_url = None
    
    async def start_server(self, host: str = '127.0.0.1', port: int = 8080) -> None:
        """
        启动WebSocket服务器
        
        Args:
            host: 服务器主机地址
            port: 服务器端口
        """
        self.logger.info(f"启动OneBot服务器 {host}:{port}")
        
        # 创建aiohttp应用
        self._app = web.Application()
        
        # 注册路由
        self._app.router.add_get('/onebot/ws', self._handle_websocket)
        self._app.router.add_post('/onebot/http', self._handle_http)
        
        # 启动服务器
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, host, port)
        await self._site.start()
        
        # 创建HTTP会话
        self._session = aiohttp.ClientSession()
        
        self.logger.info("OneBot服务器已启动")
    
    async def stop_server(self) -> None:
        """停止WebSocket服务器"""
        self.logger.info("正在关闭OneBot服务器")
        
        # 关闭HTTP会话
        if self._session:
            await self._session.close()
            self._session = None
        
        # 关闭aiohttp站点
        if self._site:
            await self._site.stop()
            self._site = None
        
        # 关闭aiohttp运行器
        if self._runner:
            await self._runner.cleanup()
            self._runner = None
        
        self.logger.info("OneBot服务器已关闭")
    
    def register_handler(self, handler: Callable[[Dict[str, Any]], None]) -> None:
        """
        注册消息处理器
        
        Args:
            handler: 消息处理函数，接收消息数据字典
        """
        self._handlers.append(handler)
        self.logger.debug(f"已注册消息处理器: {handler.__name__}")
    
    async def _handle_websocket(self, request: web.Request) -> web.WebSocketResponse:
        """
        处理WebSocket连接
        
        Args:
            request: WebSocket请求
        
        Returns:
            WebSocket响应
        """
        # 验证访问令牌
        if self._access_token:
            auth_header = request.headers.get('Authorization', '')
            if not auth_header.startswith('Bearer ') or auth_header[7:] != self._access_token:
                self.logger.warning("WebSocket认证失败")
                raise web.HTTPUnauthorized(reason="认证失败")
        
        # 建立WebSocket连接
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        self.logger.info("WebSocket连接已建立")
        
        # 处理WebSocket消息
        try:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        await self._process_message(data)
                    except json.JSONDecodeError:
                        self.logger.error(f"无效的JSON数据: {msg.data}")
                    except Exception as e:
                        self.logger.error(f"处理消息时发生错误: {e}", exc_info=True)
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    self.logger.error(f"WebSocket连接错误: {ws.exception()}")
        finally:
            self.logger.info("WebSocket连接已关闭")
        
        return ws
    
    async def _handle_http(self, request: web.Request) -> web.Response:
        """
        处理HTTP请求
        
        Args:
            request: HTTP请求
        
        Returns:
            HTTP响应
        """
        # 验证访问令牌
        if self._access_token:
            auth_header = request.headers.get('Authorization', '')
            if not auth_header.startswith('Bearer ') or auth_header[7:] != self._access_token:
                self.logger.warning("HTTP认证失败")
                return web.json_response({"status": "failed", "message": "认证失败"}, status=401)
        
        # 解析请求数据
        try:
            data = await request.json()
        except json.JSONDecodeError:
            self.logger.error("无效的JSON数据")
            return web.json_response({"status": "failed", "message": "无效的JSON数据"}, status=400)
        
        # 处理消息
        try:
            await self._process_message(data)
            return web.json_response({"status": "ok"})
        except Exception as e:
            self.logger.error(f"处理消息时发生错误: {e}", exc_info=True)
            return web.json_response({"status": "failed", "message": str(e)}, status=500)
    
    async def _process_message(self, data: Dict[str, Any]) -> None:
        """
        处理接收到的消息
        
        Args:
            data: 消息数据
        """
        # 调用所有注册的处理器
        for handler in self._handlers:
            try:
                await asyncio.create_task(handler(data))
            except Exception as e:
                self.logger.error(f"处理器 {handler.__name__} 处理消息时发生错误: {e}", exc_info=True)
    
    async def send_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        发送消息到OneBot
        
        Args:
            message: 消息数据
            
        Returns:
            响应数据
        """
        # 确保API基础URL已设置
        if not self._api_base_url:
            self._api_base_url = get_config().get('server', {}).get('api_base_url')
            if not self._api_base_url:
                raise ConnectionError("未设置API基础URL")
        
        # 确保HTTP会话已创建
        if not self._session:
            self._session = aiohttp.ClientSession()
        
        # 构建请求头
        headers = {}
        if self._access_token:
            headers['Authorization'] = f"Bearer {self._access_token}"
        
        # 发送请求
        try:
            action = message.get('action', '')
            endpoint = f"{self._api_base_url}/{action}"
            
            async with self._session.post(
                endpoint,
                headers=headers,
                json=message,
                timeout=self._config.get('http_timeout', 30)
            ) as response:
                # 检查状态码
                if response.status != 200:
                    error_text = await response.text()
                    raise RequestError(f"API请求失败: {response.status} {error_text}")
                
                # 解析响应
                result = await response.json()
                return result
        except aiohttp.ClientError as e:
            raise ConnectionError(f"连接OneBot API失败: {e}")
        except json.JSONDecodeError:
            raise RequestError("无法解析OneBot API响应")
        except asyncio.TimeoutError:
            raise RequestError("OneBot API请求超时")
    
    async def set_api_base_url(self, url: str) -> None:
        """
        设置API基础URL
        
        Args:
            url: API基础URL
        """
        self._api_base_url = url
        self.logger.info(f"已设置API基础URL: {url}")
    
    async def send_private_message(self, user_id: int, message: Union[str, List], auto_escape: bool = False) -> Dict[str, Any]:
        """
        发送私聊消息
        
        Args:
            user_id: 目标QQ号
            message: 消息内容，可以是字符串或消息段列表
            auto_escape: 是否转义消息内容
            
        Returns:
            响应数据
        """
        return await self.send_message({
            "action": "send_private_msg",
            "params": {
                "user_id": user_id,
                "message": message,
                "auto_escape": auto_escape
            }
        })
    
    async def send_group_message(self, group_id: int, message: Union[str, List], auto_escape: bool = False) -> Dict[str, Any]:
        """
        发送群聊消息
        
        Args:
            group_id: 群号
            message: 消息内容，可以是字符串或消息段列表
            auto_escape: 是否转义消息内容
            
        Returns:
            响应数据
        """
        return await self.send_message({
            "action": "send_group_msg",
            "params": {
                "group_id": group_id,
                "message": message,
                "auto_escape": auto_escape
            }
        })
    
    async def send_msg(self, message_type: str, user_id: Optional[int] = None, 
                      group_id: Optional[int] = None, message: Union[str, List] = None, 
                      auto_escape: bool = False) -> Dict[str, Any]:
        """
        发送消息
        
        Args:
            message_type: 消息类型，可以是 private、group
            user_id: 目标QQ号（私聊）
            group_id: 群号（群聊）
            message: 消息内容，可以是字符串或消息段列表
            auto_escape: 是否转义消息内容
            
        Returns:
            响应数据
        """
        return await self.send_message({
            "action": "send_msg",
            "params": {
                "message_type": message_type,
                "user_id": user_id,
                "group_id": group_id,
                "message": message,
                "auto_escape": auto_escape
            }
        })
    
    async def delete_msg(self, message_id: int) -> Dict[str, Any]:
        """
        撤回消息
        
        Args:
            message_id: 消息ID
            
        Returns:
            响应数据
        """
        return await self.send_message({
            "action": "delete_msg",
            "params": {
                "message_id": message_id
            }
        })
    
    async def get_login_info(self) -> Dict[str, Any]:
        """
        获取登录号信息
        
        Returns:
            响应数据，包含 user_id(QQ号)和 nickname(QQ昵称)
        """
        return await self.send_message({
            "action": "get_login_info",
            "params": {}
        })
    
    async def get_group_list(self) -> Dict[str, Any]:
        """
        获取群列表
        
        Returns:
            响应数据，包含群信息列表
        """
        return await self.send_message({
            "action": "get_group_list",
            "params": {}
        })
    
    async def get_group_member_info(self, group_id: int, user_id: int, no_cache: bool = False) -> Dict[str, Any]:
        """
        获取群成员信息
        
        Args:
            group_id: 群号
            user_id: QQ号
            no_cache: 是否不使用缓存
            
        Returns:
            响应数据，包含群成员信息
        """
        return await self.send_message({
            "action": "get_group_member_info",
            "params": {
                "group_id": group_id,
                "user_id": user_id,
                "no_cache": no_cache
            }
        })
    
    async def get_group_member_list(self, group_id: int) -> Dict[str, Any]:
        """
        获取群成员列表
        
        Args:
            group_id: 群号
            
        Returns:
            响应数据，包含群成员列表
        """
        return await self.send_message({
            "action": "get_group_member_list",
            "params": {
                "group_id": group_id
            }
        }) 