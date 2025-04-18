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
from typing import Dict, Any, Optional, Union, Callable, Awaitable # 导入 Callable 和 Awaitable

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

        # 用于存储 LinjingBot 的 handle_message 方法
        self._message_handler: Optional[Callable[[Message], Awaitable[Optional[Any]]]] = None # 重命名以示内部使用

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

    def register_message_handler(self, handler: Callable[[Message], Awaitable[Optional[Any]]]): # 参数类型改为 Message
        """注册用于处理接收到的消息的主处理函数"""
        self._message_handler = handler # 使用内部变量名
        logger.info(f"已注册消息处理函数: {handler.__name__}")

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
        logger.info("消息监听循环已启动") # 添加启动日志
        loop_count = 0
        try: # 包裹整个循环
            while self.connected and self.websocket:
                loop_count += 1
                logger.debug(f"消息监听循环迭代: {loop_count}")
                try:
                    message = await self.websocket.recv()
                    logger.debug(f"收到原始消息: {message}") # 添加原始消息日志
                    if not message:
                        logger.debug("收到空消息，继续监听")
                        continue

                    try:
                        event = json.loads(message)
                        await self._handle_event(event)
                    except json.JSONDecodeError:
                        logger.error(f"无效的JSON消息: {message}")
                    except Exception as e_handle: # 捕获处理事件时的异常
                        logger.error(f"处理事件时发生异常: {e_handle}", exc_info=True)

                except ConnectionClosed as e_closed:
                    logger.warning(f"WebSocket连接已关闭 (监听循环内，迭代 {loop_count}): {e_closed}")
                    self.connected = False
                    break # 明确退出循环
                except Exception as e_recv: # 捕获接收消息时的其他异常
                    logger.error(f"接收消息时发生异常 (迭代 {loop_count}): {e_recv}", exc_info=True)
                    self.connected = False # 假设连接已断开
                    break # 明确退出循环
        except Exception as e_outer: # 捕获循环外的异常
             logger.error(f"消息监听循环意外终止 (迭代 {loop_count}): {e_outer}", exc_info=True)
        finally:
             logger.info(f"消息监听循环已结束 (迭代 {loop_count})") # 添加结束日志
             self.connected = False # 确保状态更新


    async def _handle_event(self, event: Dict[str, Any]):
        """处理OneBot事件"""
        event_type = event.get("post_type")
        if not event_type:
            logger.warning(f"收到缺少 'post_type' 的事件: {event}")
            return

        # 只对消息事件打印详细的 INFO 日志
        if event_type == "message":
            logger.debug("进入 message 事件处理分支") # 确认进入分支
            # 提取发送者信息
            user_id = event.get('user_id', '未知')
            nickname = event.get('sender', {}).get('nickname', '未知')

            # 格式化消息内容以供日志记录 (添加 try-except)
            message_content_str = ""
            try:
                if 'message' in event and isinstance(event['message'], list):
                    logger.debug("开始格式化消息段列表")
                    segments_str = []
                    for i, seg in enumerate(event['message']):
                        logger.debug(f"处理段 {i}: {seg}")
                        seg_type = seg.get('type')
                        seg_data = seg.get('data', {})
                        if seg_type == 'text':
                            segments_str.append(seg_data.get('text', ''))
                        elif seg_type == 'image':
                            file = seg_data.get('file', '未知图片')
                            url = seg_data.get('url', '') # 尝试获取 URL
                            display_name = file if file != '未知图片' else url
                            segments_str.append(f"[图片: {display_name}]")
                        elif seg_type == 'at':
                            qq = seg_data.get('qq', '未知用户')
                            segments_str.append(f"[@{qq}]")
                        elif seg_type == 'reply':
                            msg_id = seg_data.get('id', '未知消息')
                            segments_str.append(f"[回复: {msg_id}]")
                        elif seg_type == 'face':
                            face_id = seg_data.get('id', '?')
                            segments_str.append(f"[表情: {face_id}]")
                        elif seg_type == 'record':
                             segments_str.append(f"[语音]") # 简单表示
                        elif seg_type == 'video':
                             segments_str.append(f"[视频]") # 简单表示
                        # 可以根据需要添加更多类型的格式化
                        else:
                            # 对于其他未显式处理的类型，打印类型和数据摘要
                            data_summary = str(seg_data)[:30] + ('...' if len(str(seg_data)) > 30 else '')
                            segments_str.append(f"[{seg_type}: {data_summary}]")
                    message_content_str = "".join(segments_str)
                    logger.debug(f"格式化后的消息字符串: {message_content_str}")
                else:
                    logger.debug("消息内容不是列表，回退到 raw_message")
                    # 如果没有 message 列表，回退到 raw_message
                    message_content_str = event.get('raw_message', '无消息内容')
            except Exception as e_format:
                 logger.error(f"格式化消息内容时出错: {e_format}", exc_info=True)
                 message_content_str = event.get('raw_message', '[格式化失败]') # 发生错误时提供明确提示

            # 添加群号信息（如果存在）
            group_id = event.get('group_id')
            log_prefix = f"[群聊：{group_id}]" if group_id else ""

            logger.debug("准备记录 INFO 日志") # 确认即将记录 INFO
            # 使用 INFO 级别记录格式化后的消息日志
            logger.info(f"{log_prefix}[QQ号：{user_id}][QQ名称：{nickname}]：发送了 {message_content_str}")
        else:
             # 对于非消息事件，可以记录一个简单的 DEBUG 日志（可选）
             logger.debug(f"处理事件: {event_type} - {event.get('sub_type', '')}")


        # 转换消息格式
        # 注意：这里需要处理原始的 event['message']，而不是转换后的 Message 对象
        original_message_list = event.get("message") # 先保存原始列表
        if "message" in event and isinstance(original_message_list, list):
            try:
                # 注意：这里修改了原始 event 字典中的 'message' 键
                event["message"] = Message.from_onebot_event(event)
                logger.debug(f"消息转换后的事件对象: {event['message']}") # 记录转换后的对象
            except Exception as e:
                logger.error(f"消息转换失败: {e}", exc_info=True)
                # 即使转换失败，也可能需要处理事件本身（例如通知事件）
                # 如果转换失败，将 message 恢复为原始列表，以便后续处理（如果需要）
                event["message"] = original_message_list
                # return # 决定是否在转换失败时中止

        # 调用通过 bot.on() 注册的事件处理器 (位于 adapter_utils.py 的 Bot 基类中)
        # 传递完整的 event 字典
        await self.handle_event(event_type, event)

        # 如果是消息事件并且已注册主消息处理器，则调用它
        # 注意：我们传递转换后的 Message 对象给 LinjingBot.handle_message
        if event_type == "message" and self._message_handler and isinstance(event.get("message"), Message): # 使用内部变量名
            try:
                logger.debug(f"调用主消息处理函数: {self._message_handler.__name__}")
                # LinjingBot.handle_message 期望接收转换后的 Message 对象
                await self._message_handler(event["message"]) # 使用内部变量名
            except Exception as e:
                logger.error(f"调用主消息处理函数时出错: {e}", exc_info=True)
        elif event_type == "message" and not self._message_handler: # 使用内部变量名
             logger.warning("收到消息事件，但没有注册主消息处理函数")


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
