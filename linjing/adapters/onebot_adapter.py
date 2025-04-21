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
from linjing.constants import EventType

logger = get_logger(__name__)

class OneBotAdapter(Bot):
    """OneBot v11 协议适配器"""

    def __init__(self, config: Dict[str, Any], event_bus: Any): # Added event_bus parameter
        super().__init__(config)
        self.platform = "onebot"
        self.event_bus = event_bus # Store event_bus

        # 用于存储 LinjingBot 的 handle_message 方法
        self._message_handler: Optional[Callable[[Message], Awaitable[Optional[Any]]]] = None # 重命名以示内部使用

        # --- 新增：订阅发送消息请求事件 ---
        if self.event_bus:
            self.event_bus.subscribe(EventType.SEND_MESSAGE_REQUEST, self.handle_send_request)
            logger.info("已订阅 SEND_MESSAGE_REQUEST 事件")
        else:
            logger.warning("EventBus 未提供，无法订阅 SEND_MESSAGE_REQUEST 事件")
        # --- 订阅结束 ---

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
        # **新增：读取 HTTP API 地址配置**
        self.http_api_url = config.get("http_api_url")
        if self.http_api_url:
             # 确保 URL 以 / 结尾，方便拼接
             self.http_api_url = self.http_api_url.rstrip('/') + '/'
             logger.info(f"OneBot HTTP API URL 已配置: {self.http_api_url}")
        else:
             logger.info("未配置 OneBot HTTP API URL，将尝试使用 WebSocket 发送。")

        # API限速器
        from linjing.adapters.adapter_utils import ApiRateLimiter
        # **修改：从配置读取速率限制**
        rate_limit = config.get("rate_limit", 5.0)
        burst_limit = config.get("burst_limit", 10)
        self.rate_limiter = ApiRateLimiter(rate_limit=rate_limit, burst_limit=burst_limit)
        logger.debug(f"API 限速器设置: rate={rate_limit}/s, burst={burst_limit}")

        # 注册适配器
        from linjing.adapters.adapter_utils import AdapterRegistry
        AdapterRegistry.register("onebot")(self.__class__)
        
        # 存储机器人自身ID
        self.self_id = config.get("self_id", "")
        
        # 自身ID验证配置
        self.expected_self_id = config.get("expected_self_id", "")
        self.verify_self_id = config.get("verify_self_id", False)
        if self.expected_self_id and self.verify_self_id:
            logger.info(f"已启用机器人ID验证，预期ID: {self.expected_self_id}")
        elif self.expected_self_id:
            logger.info(f"预期机器人ID: {self.expected_self_id}，但未启用严格验证")

    def register_message_handler(self, handler: Callable[[Message], Awaitable[Optional[Any]]]): # 参数类型改为 Message
        """注册用于处理接收到的消息的主处理函数"""
        self._message_handler = handler # 使用内部变量名
        logger.info(f"已注册消息处理函数: {handler.__name__}")

    # --- 新增：处理发送请求的事件处理器 ---
    async def handle_send_request(self, event_type: str, data: Dict[str, Any]):
        """处理来自事件总线的发送消息请求"""
        logger.debug(f"收到 SEND_MESSAGE_REQUEST 事件: {data}")
        reply = data.get("reply")
        target_info = data.get("target")

        if not reply or not target_info:
            logger.error("发送请求事件缺少 'reply' 或 'target' 数据")
            return

        session_id = target_info.get("session_id")
        user_id = target_info.get("user_id")
        group_id = target_info.get("group_id")
        # platform = target_info.get("platform") # platform 在这里可能不是必需的

        # 确定消息类型和目标 ID
        message_type = None
        target_id = None

        # 优先使用明确的 group_id 或 user_id
        if group_id:
            message_type = "group"
            target_id = str(group_id) # 确保是字符串
            logger.debug(f"从 target_info 确定为群组消息，目标 group_id: {target_id}")
        elif user_id:
            # 需要区分是来自群聊的私聊还是直接私聊，但 OneBot API 通常只认 user_id
            # 简单的处理：如果 session_id 看起来像群聊，也按私聊发给 user_id
            # 更复杂的场景可能需要结合 context 判断，但这里先简化
            message_type = "private"
            target_id = str(user_id) # 确保是字符串
            logger.debug(f"从 target_info 确定为私聊消息，目标 user_id: {target_id}")
        else:
            # 如果 group_id 和 user_id 都没有，尝试从 session_id 解析
            logger.warning("事件数据中缺少明确的 group_id 或 user_id，尝试从 session_id 解析...")
            if session_id and session_id.startswith("group_"):
                message_type = "group"
                try:
                    target_id = session_id.split("_", 1)[1]
                    logger.debug(f"从 session_id '{session_id}' 解析得到群组消息，目标 group_id: {target_id}")
                except IndexError:
                    logger.error(f"无法从 session_id '{session_id}' 解析 group_id")
                    return
            elif session_id and session_id.startswith("private_"):
                 message_type = "private"
                 try:
                     target_id = session_id.split("_", 1)[1]
                     logger.debug(f"从 session_id '{session_id}' 解析得到私聊消息，目标 user_id: {target_id}")
                 except IndexError:
                     logger.error(f"无法从 session_id '{session_id}' 解析 user_id")
                     return
            else:
                logger.error(f"无法从事件数据确定发送目标: {target_info}")
                return

        if target_id and message_type:
            logger.info(f"准备通过 OneBot 发送消息 (类型: {message_type}, 目标: {target_id})")
            try:
                # 调用适配器自身的 send 方法来发送
                # send 方法接收 target_id, message 对象, message_type
                await self.send(target=target_id, message=reply, message_type=message_type)
                logger.info(f"消息已成功请求发送到 {message_type} {target_id}")
            except Exception as e:
                logger.error(f"调用 self.send 发送消息失败: {e}", exc_info=True)
        else:
             logger.error("未能确定有效的 target_id 或 message_type 用于发送")
    # --- 事件处理器结束 ---

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

        # **修改：从配置读取心跳间隔**
        heartbeat_interval_ms = self.config.get("heartbeat_interval", 30000) # 从适配器配置读取
        heartbeat_interval_sec = heartbeat_interval_ms / 1000.0
        logger.debug(f"心跳间隔设置为: {heartbeat_interval_sec} 秒")

        while self.connected:
            try:
                await asyncio.sleep(heartbeat_interval_sec) # 使用配置值
                if self.connected and self.websocket:
                    logger.debug("发送心跳包...") # 添加日志
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
        """处理接收到的事件"""
        logger.debug(f"收到原始消息: {event}") # 打印原始事件数据

        # --- 添加过滤逻辑 ---
        post_type = event.get("post_type")
        if post_type == "meta_event":
            # 特别处理心跳事件以获取 self_id
            if event.get("meta_event_type") == "heartbeat" and not self.self_id:
                 status = event.get("status")
                 if status and status.get("online") and status.get("good"):
                     # OneBot 标准心跳包通常不包含 self_id，但有些实现（如 go-cqhttp HTTP）可能在 status 里有
                     # 尝试从 /get_login_info 获取 self_id
                     try:
                         login_info = await self.call_api("get_login_info")
                         
                         # --- 修正 self_id 提取逻辑 ---
                         fetched_self_id = None # Initialize
                         data = login_info.get("data") # 先获取 'data' 字典
                         if data and isinstance(data, dict):
                             user_id_val = data.get("user_id") # 获取 user_id 的值
                             if user_id_val is not None: # 确保 user_id 存在且不为 None
                                 fetched_self_id = str(user_id_val) # 再从 'data' 中获取 'user_id' 并转为字符串
                         # --- 修正结束 ---

                         if fetched_self_id:
                             if not self.self_id:
                                 self.self_id = fetched_self_id
                                 logger.info(f"通过 get_login_info 获取到 self_id: {self.self_id}")
                                 # 验证 self_id
                                 await self._verify_self_id(self.self_id)
                                 # 发送适配器连接成功事件
                                 await self.event_bus.publish(EventType.ADAPTER_CONNECTED, {
                                     "adapter_name": self.platform,
                                     "adapter": self, # 传递适配器实例
                                     "self_id": self.self_id
                                 })
                             elif self.self_id != fetched_self_id:
                                 logger.warning(f"get_login_info 返回的 ID ({fetched_self_id}) 与当前 ID ({self.self_id}) 不符。")
                         else:
                             logger.warning("get_login_info 未返回有效的 user_id")
                     except Exception as e:
                         logger.warning(f"尝试从 get_login_info 获取 self_id 失败: {e}")

            # 对于所有 meta_event (包括心跳)，记录后直接返回，不进入后续处理
            meta_event_type = event.get("meta_event_type")
            logger.debug(f"忽略元事件 ({meta_event_type})，不处理。")
            return
        # --- 过滤逻辑结束 ---

        # --- 验证 self_id (如果尚未获取) ---
        event_self_id = event.get("self_id")
        if event_self_id:
            event_self_id_str = str(event_self_id)
            if not self.self_id:
                 self.self_id = event_self_id_str
                 logger.info(f"从事件中获取到 self_id: {self.self_id}")
                 await self._verify_self_id(self.self_id)
                 # 发送适配器连接成功事件
                 await self.event_bus.publish(EventType.ADAPTER_CONNECTED, {
                     "adapter_name": self.platform,
                     "adapter": self, # 传递适配器实例
                     "self_id": self.self_id
                 })
            elif self.self_id != event_self_id_str:
                 logger.warning(f"事件中的 self_id ({event_self_id_str}) 与已知的 self_id ({self.self_id}) 不符！")
                 # 如果启用了严格验证，可能需要断开连接或报警
                 if self.verify_self_id and self.expected_self_id and self.expected_self_id != event_self_id_str:
                     logger.error(f"接收到来自非预期机器人 ({event_self_id_str}) 的事件，预期为 {self.expected_self_id}，连接可能存在问题！")
                     # 可以考虑在这里添加断开连接的逻辑 await self.disconnect()


        # --- 消息转换 ---
        # 仅处理 post_type 为 'message' 的事件
        if post_type == 'message':
            try:
                # 使用 MessageConverter 进行转换
                message_obj = MessageConverter.to_internal_message("onebot", event)
                # --- 修改：使用 bind 记录提取到的信息 ---
                user_id = message_obj.get_user_id() if hasattr(message_obj, 'get_user_id') else 'unknown'
                group_id = message_obj.get_meta('group_id') if hasattr(message_obj, 'get_meta') else None
                content = message_obj.extract_plain_text() if hasattr(message_obj, 'extract_plain_text') else str(message_obj)
                logger.bind(user_id=user_id, group_id=group_id, msg_content=content).debug(f"消息转换后的事件对象 (User: {user_id}, Group: {group_id})")
                # logger.debug(f"消息转换后的事件对象: {message_obj}") # 旧日志
                # --- 修改结束 ---

                # 如果转换成功且存在主消息处理函数
                if message_obj and self._message_handler:
                    logger.debug(f"调用主消息处理函数: {self._message_handler.__name__}")
                    # 【【【修改点 1: 只调用，不关心返回值】】】
                    await self._message_handler(message_obj) # 调用 LinjingBot.handle_message, 忽略返回值

                    # 【【【修改点 2: 删除整个错误的 if reply is not None: ... 代码块】】】
                    # (从这里开始删除)
                    # if reply is not None:
                    # ... (整个错误处理逻辑块) ...
                    # else:
                    #     logger.debug("主处理函数未返回回复消息")
                    # (删除到这里结束)

                    # 保留日志，说明任务已交给异步处理器
                    logger.debug(f"消息已传递给主处理函数 {self._message_handler.__name__} 进行异步处理。")

                elif not self._message_handler:
                    logger.warning("收到消息但未注册主消息处理函数")

            except Exception as e: # 这是外层 try-except
                print(f"!!! DEBUG PRINT: ERROR in outer _handle_event try-except: {e} !!!", flush=True) # 新增
                logger.error(f"处理消息事件时出错: {e}", exc_info=True)
        elif post_type == 'notice':
            # 处理通知事件 (如果需要)
            logger.debug(f"收到通知事件: {event.get('notice_type')}")
            # 在这里可以添加对特定通知事件的处理逻辑，例如群成员增加/减少等
            # 可以通过 self.event_bus.publish 发布更具体的事件类型
            pass
        else:
            logger.warning(f"收到未知 post_type 的事件: {post_type}")

    async def _verify_self_id(self, current_self_id: str):
        """验证获取到的 self_id 是否符合预期"""
        if self.verify_self_id and self.expected_self_id:
             if current_self_id != self.expected_self_id:
                 logger.error(f"机器人 self_id ({current_self_id}) 与预期 ({self.expected_self_id}) 不符！请检查配置或连接。")
                 # 可以考虑抛出异常或触发报警
             else:
                 logger.info(f"机器人 self_id ({current_self_id}) 验证通过。")

    # **修改：添加 message_type 参数**
    async def send(self, target: str, message: Union[str, Message, MessageSegment], message_type: str) -> str:
        """发送消息"""
        print(f"!!! DEBUG PRINT: ENTERED self.send (Target: {target}, Type: {message_type}) !!!", flush=True) # 添加 Print
        if not self.connected:
            raise ConnectionError("未连接到OneBot实现")

        # 等待API限速器
        await self.rate_limiter.wait_for_token()

        # 转换消息格式
        if isinstance(message, (str, MessageSegment)):
            message = Message(message)

        onebot_message = MessageConverter.to_platform_message("onebot", message)

        # **新增：记录转换后的 OneBot 消息格式**
        logger.debug(f"转换后的 OneBot 消息格式: {onebot_message}")

        # 构造API请求
        api_request = {
            "action": "send_msg",
            # **修改：使用传入的 message_type 和对应的 id 键**
            "params": {
                "message_type": message_type,
                "user_id" if message_type == "private" else "group_id": int(target), # 使用正确的 ID 键
                "message": onebot_message
            }
        }
        # **新增：记录完整的 API 请求内容**
        logger.debug(f"准备发送的 API 请求: {json.dumps(api_request, ensure_ascii=False)}")

        # **修改：根据是否配置了 HTTP API URL 选择发送方式**
        if self.http_api_url:
            # --- 使用 HTTP API 发送 ---
            api_endpoint = "send_msg"
            full_api_url = self.http_api_url + api_endpoint
            logger.debug(f"准备通过 HTTP POST 发送消息到: {full_api_url}")
            try:
                # 确保 self.session 存在且未关闭
                if not self.session or self.session.closed:
                     logger.error("尝试通过 HTTP 发送消息时 aiohttp session 不可用。")
                     # 尝试重新创建 session (或者在 connect 时确保创建)
                     self.session = aiohttp.ClientSession()
                     logger.info("已重新创建 aiohttp session。")
                     # 如果 session 仍然不可用，则抛出异常
                     if not self.session or self.session.closed:
                          raise ConnectionError("aiohttp session is closed or unavailable.")

                # 发送 POST 请求
                async with self.session.post(full_api_url, json=api_request["params"]) as resp:
                    # 检查响应状态码
                    if resp.status == 200:
                        response_data = await resp.json()
                        logger.debug(f"HTTP API 响应 ({resp.status}): {response_data}")
                        # OneBot HTTP API 通常会返回 message_id
                        message_id = response_data.get("data", {}).get("message_id", str(int(time.time())))
                        return str(message_id)
                    else:
                        error_text = await resp.text()
                        logger.error(f"HTTP API 请求失败 ({resp.status}): {error_text}")
                        raise ConnectionError(f"HTTP API request failed with status {resp.status}: {error_text}")
            except aiohttp.ClientError as e:
                 logger.error(f"HTTP API 请求连接错误: {e}", exc_info=True)
                 raise ConnectionError(f"HTTP API connection error: {e}")
            except Exception as e:
                 logger.error(f"通过 HTTP API 发送消息时发生未知错误: {e}", exc_info=True)
                 raise # 重新抛出异常

        else:
            # --- 回退到 WebSocket 发送 ---
            logger.debug("未配置 HTTP API URL，尝试通过 WebSocket 发送。")
            try:
                # 发送前检查 WebSocket 状态 (移除 .open 检查，因为反向连接可能没有这个属性)
                if not self.websocket:
                     logger.error(f"尝试通过 WebSocket 发送消息时连接不存在 (Target: {target}, Type: {message_type})")
                     raise ConnectionError("WebSocket connection is unavailable.")
                
                # 对于反向 WS，可能没有 .open 属性，直接尝试发送
                # logger.debug(f"WebSocket 状态 (发送前): open={getattr(self.websocket, 'open', 'N/A')}") # 尝试获取 open 属性
                
                # 发送请求
                await self.websocket.send(json.dumps(api_request))
                logger.debug(f"WebSocket send 调用完成 (Target: {target})")

                # 简单实现：返回当前时间戳作为消息ID
                return str(int(time.time()))

            except ConnectionClosed as e:
                 logger.error(f"尝试通过 WebSocket 发送消息时连接已关闭: {e}", exc_info=True)
                 self.connected = False # 更新连接状态
                 raise ConnectionError(f"WebSocket connection closed: {e}")
            except Exception as e:
                logger.error(f"通过 WebSocket 发送消息失败: {e}", exc_info=True)
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

        # **修改：根据是否配置了 HTTP API URL 选择调用方式**
        if self.http_api_url:
            # --- 使用 HTTP API 调用 ---
            api_endpoint = api # API 名称通常直接对应端点路径
            full_api_url = self.http_api_url + api_endpoint
            logger.debug(f"准备通过 HTTP POST 调用 API: {full_api_url}")
            try:
                # 确保 self.session 存在且未关闭
                if not self.session or self.session.closed:
                     logger.error("尝试通过 HTTP 调用 API 时 aiohttp session 不可用。")
                     self.session = aiohttp.ClientSession()
                     logger.info("已重新创建 aiohttp session。")
                     if not self.session or self.session.closed:
                          raise ConnectionError("aiohttp session is closed or unavailable.")

                # 发送 POST 请求，将参数作为 JSON body 发送
                async with self.session.post(full_api_url, json=params) as resp:
                    # 检查响应状态码
                    if resp.status == 200:
                        response_data = await resp.json()
                        logger.debug(f"HTTP API 调用响应 ({resp.status}): {response_data}")
                        # 直接返回 OneBot API 的响应数据
                        return response_data
                    else:
                        error_text = await resp.text()
                        logger.error(f"HTTP API 调用失败 ({resp.status}): {error_text}")
                        # 可以考虑返回一个表示错误的字典，或者抛出异常
                        # return {"status": "failed", "retcode": resp.status, "msg": error_text, "data": None}
                        raise ConnectionError(f"HTTP API call failed with status {resp.status}: {error_text}")
            except aiohttp.ClientError as e:
                 logger.error(f"HTTP API 调用连接错误: {e}", exc_info=True)
                 raise ConnectionError(f"HTTP API connection error: {e}")
            except Exception as e:
                 logger.error(f"通过 HTTP API 调用时发生未知错误: {e}", exc_info=True)
                 raise

        else:
            # --- 回退到 WebSocket 调用 ---
            logger.debug("未配置 HTTP API URL，尝试通过 WebSocket 调用 API。")
            try:
                # 发送前检查 WebSocket 状态
                if not self.websocket:
                     logger.error(f"尝试通过 WebSocket 调用 API 时连接不存在 (API: {api})")
                     raise ConnectionError("WebSocket connection is unavailable.")

                # 发送请求
                await self.websocket.send(json.dumps(api_request))
                logger.debug(f"WebSocket API 调用 ({api}) 发送完成")

                # 简单实现：不等待响应 (保持原逻辑)
                return {"status": "async", "retcode": 0}

            except ConnectionClosed as e:
                 logger.error(f"尝试通过 WebSocket 调用 API 时连接已关闭: {e}", exc_info=True)
                 self.connected = False # 更新连接状态
                 raise ConnectionError(f"WebSocket connection closed: {e}")
            except Exception as e:
                logger.error(f"通过 WebSocket 调用 API 失败: {e}", exc_info=True)
                raise

    def get_self_id(self) -> str:
        """
        获取机器人自身ID
        
        Returns:
            机器人自身ID
        """
        return self.self_id
