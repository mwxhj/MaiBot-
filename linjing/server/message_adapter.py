#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
林镜(LingJing) - 消息格式适配器
"""

import json
import logging
from typing import Dict, Any, List, Union, Optional
from datetime import datetime

from ..constants import MessageType, EventType
from ..exceptions import MessageParseError, MessageFormatError

class MessageAdapter:
    """消息格式适配器，用于转换内外部消息格式"""
    
    def __init__(self):
        """初始化消息适配器"""
        self.logger = logging.getLogger('linjing.message_adapter')
    
    def convert_to_internal(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        将OneBot消息转为内部格式
        
        Args:
            data: OneBot消息数据
            
        Returns:
            内部格式消息数据
        """
        try:
            # 检查必要字段
            if "post_type" not in data:
                raise MessageParseError("消息缺少post_type字段")
            
            # 获取事件类型
            post_type = data.get("post_type")
            
            # 根据事件类型处理
            if post_type == "message":
                return self._convert_message_event(data)
            elif post_type == "notice":
                return self._convert_notice_event(data)
            elif post_type == "request":
                return self._convert_request_event(data)
            elif post_type == "meta_event":
                return self._convert_meta_event(data)
            else:
                self.logger.warning(f"未知的事件类型: {post_type}")
                return self._convert_unknown_event(data)
        except Exception as e:
            self.logger.error(f"转换消息格式时发生错误: {e}", exc_info=True)
            raise MessageParseError(f"转换消息格式时发生错误: {e}")
    
    def _convert_message_event(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        转换消息事件
        
        Args:
            data: OneBot消息事件数据
            
        Returns:
            内部格式消息事件数据
        """
        # 检查必要字段
        for field in ["message_type", "user_id", "message", "time"]:
            if field not in data:
                raise MessageParseError(f"消息缺少{field}字段")
        
        # 获取消息类型和内容
        message_type = data.get("message_type")
        raw_message = data.get("message", "")
        
        # 格式化消息内容
        if isinstance(raw_message, str):
            # 尝试解析CQ码
            message_content = self._parse_cq_code(raw_message)
        else:
            # 已经是数组格式
            message_content = raw_message
        
        # 构建基本消息结构
        internal_message = {
            "id": data.get("message_id", ""),
            "type": EventType.MESSAGE,
            "message_type": message_type,
            "sender": {
                "user_id": data.get("user_id"),
                "nickname": data.get("sender", {}).get("nickname", ""),
                "card": data.get("sender", {}).get("card", ""),
                "role": data.get("sender", {}).get("role", ""),
                "title": data.get("sender", {}).get("title", ""),
                "is_admin": data.get("sender", {}).get("role") in ["admin", "owner"],
            },
            "content": message_content,
            "raw_content": raw_message,
            "time": datetime.fromtimestamp(data.get("time")),
            "self_id": data.get("self_id"),
            "original": data
        }
        
        # 根据消息类型添加特定字段
        if message_type == MessageType.GROUP:
            internal_message["group_id"] = data.get("group_id")
            internal_message["sub_type"] = data.get("sub_type", "normal")
            internal_message["anonymous"] = data.get("anonymous")
        
        return internal_message
    
    def _convert_notice_event(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        转换通知事件
        
        Args:
            data: OneBot通知事件数据
            
        Returns:
            内部格式通知事件数据
        """
        # 检查必要字段
        if "notice_type" not in data:
            raise MessageParseError("通知缺少notice_type字段")
        
        # 基本通知结构
        internal_notice = {
            "type": EventType.NOTICE,
            "notice_type": data.get("notice_type"),
            "time": datetime.fromtimestamp(data.get("time", datetime.now().timestamp())),
            "self_id": data.get("self_id"),
            "original": data
        }
        
        # 根据通知类型添加特定字段
        notice_type = data.get("notice_type")
        
        if notice_type == "group_upload":
            internal_notice["group_id"] = data.get("group_id")
            internal_notice["user_id"] = data.get("user_id")
            internal_notice["file"] = data.get("file")
        elif notice_type == "group_admin":
            internal_notice["group_id"] = data.get("group_id")
            internal_notice["user_id"] = data.get("user_id")
            internal_notice["sub_type"] = data.get("sub_type")  # set/unset
        elif notice_type == "group_decrease" or notice_type == "group_increase":
            internal_notice["group_id"] = data.get("group_id")
            internal_notice["user_id"] = data.get("user_id")
            internal_notice["operator_id"] = data.get("operator_id")
            internal_notice["sub_type"] = data.get("sub_type")
        elif notice_type == "friend_add":
            internal_notice["user_id"] = data.get("user_id")
        elif notice_type == "notify":
            internal_notice["group_id"] = data.get("group_id")
            internal_notice["user_id"] = data.get("user_id")
            internal_notice["sub_type"] = data.get("sub_type")
            if data.get("sub_type") == "poke":
                internal_notice["target_id"] = data.get("target_id")
        
        return internal_notice
    
    def _convert_request_event(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        转换请求事件
        
        Args:
            data: OneBot请求事件数据
            
        Returns:
            内部格式请求事件数据
        """
        # 检查必要字段
        if "request_type" not in data:
            raise MessageParseError("请求缺少request_type字段")
        
        # 基本请求结构
        internal_request = {
            "type": EventType.REQUEST,
            "request_type": data.get("request_type"),
            "user_id": data.get("user_id"),
            "comment": data.get("comment", ""),
            "flag": data.get("flag"),
            "time": datetime.fromtimestamp(data.get("time", datetime.now().timestamp())),
            "self_id": data.get("self_id"),
            "original": data
        }
        
        # 根据请求类型添加特定字段
        request_type = data.get("request_type")
        
        if request_type == "friend":
            pass  # 已经包含所有需要的字段
        elif request_type == "group":
            internal_request["group_id"] = data.get("group_id")
            internal_request["sub_type"] = data.get("sub_type")  # add/invite
        
        return internal_request
    
    def _convert_meta_event(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        转换元事件
        
        Args:
            data: OneBot元事件数据
            
        Returns:
            内部格式元事件数据
        """
        # 检查必要字段
        if "meta_event_type" not in data:
            raise MessageParseError("元事件缺少meta_event_type字段")
        
        # 基本元事件结构
        internal_meta = {
            "type": EventType.META,
            "meta_event_type": data.get("meta_event_type"),
            "time": datetime.fromtimestamp(data.get("time", datetime.now().timestamp())),
            "self_id": data.get("self_id"),
            "original": data
        }
        
        # 根据元事件类型添加特定字段
        meta_event_type = data.get("meta_event_type")
        
        if meta_event_type == "lifecycle":
            internal_meta["sub_type"] = data.get("sub_type")  # enable/disable/connect
        elif meta_event_type == "heartbeat":
            internal_meta["status"] = data.get("status", {})
            internal_meta["interval"] = data.get("interval")
        
        return internal_meta
    
    def _convert_unknown_event(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        转换未知事件
        
        Args:
            data: 未知事件数据
            
        Returns:
            内部格式未知事件数据
        """
        return {
            "type": "unknown",
            "original": data,
            "time": datetime.fromtimestamp(data.get("time", datetime.now().timestamp())),
            "self_id": data.get("self_id")
        }
    
    def _parse_cq_code(self, text: str) -> List[Dict[str, Any]]:
        """
        解析CQ码
        
        Args:
            text: 包含CQ码的文本
            
        Returns:
            消息段列表
        """
        segments = []
        
        # 如果不包含CQ码，直接返回文本段
        if "[CQ:" not in text:
            segments.append({"type": "text", "data": {"text": text}})
            return segments
        
        # 解析文本中的CQ码
        current_index = 0
        text_length = len(text)
        
        while current_index < text_length:
            # 查找CQ码开始位置
            cq_start = text.find("[CQ:", current_index)
            
            # 如果没有找到CQ码，添加剩余文本并结束
            if cq_start == -1:
                if current_index < text_length:
                    segments.append({
                        "type": "text",
                        "data": {"text": text[current_index:]}
                    })
                break
            
            # 如果CQ码前有文本，添加文本段
            if cq_start > current_index:
                segments.append({
                    "type": "text",
                    "data": {"text": text[current_index:cq_start]}
                })
            
            # 查找CQ码结束位置
            cq_end = text.find("]", cq_start)
            if cq_end == -1:
                # CQ码没有正确结束，作为普通文本处理
                segments.append({
                    "type": "text",
                    "data": {"text": text[cq_start:]}
                })
                break
            
            # 解析CQ码
            cq_code = text[cq_start:cq_end + 1]
            try:
                segment = self._parse_single_cq_code(cq_code)
                segments.append(segment)
            except MessageParseError as e:
                self.logger.warning(f"解析CQ码失败: {e}")
                segments.append({
                    "type": "text",
                    "data": {"text": cq_code}
                })
            
            # 更新当前位置
            current_index = cq_end + 1
        
        return segments
    
    def _parse_single_cq_code(self, cq_code: str) -> Dict[str, Any]:
        """
        解析单个CQ码
        
        Args:
            cq_code: CQ码字符串
            
        Returns:
            消息段字典
        """
        # 去除前后的方括号
        if not (cq_code.startswith("[CQ:") and cq_code.endswith("]")):
            raise MessageParseError(f"无效的CQ码格式: {cq_code}")
        
        cq_content = cq_code[4:-1]
        
        # 分离类型和参数
        parts = cq_content.split(",")
        if not parts:
            raise MessageParseError(f"无效的CQ码内容: {cq_content}")
        
        cq_type = parts[0].strip()
        cq_params = {}
        
        # 解析参数
        for part in parts[1:]:
            if "=" in part:
                key, value = part.split("=", 1)
                cq_params[key.strip()] = value.strip()
        
        # 根据CQ码类型构建消息段
        segment = {
            "type": cq_type,
            "data": cq_params
        }
        
        return segment
    
    def convert_to_external(self, message: Union[Dict[str, Any], str, List]) -> Union[str, List]:
        """
        将内部消息转为OneBot格式
        
        Args:
            message: 内部消息数据，可以是字符串、消息段列表或完整消息字典
            
        Returns:
            OneBot格式消息
        """
        try:
            # 如果已经是字符串，直接返回
            if isinstance(message, str):
                return message
            
            # 如果是列表，假定已经是消息段列表，转换为OneBot格式
            if isinstance(message, list):
                return self._convert_segments_to_onebot(message)
            
            # 如果是字典，检查是否为完整消息字典
            if isinstance(message, dict):
                if "content" in message:
                    # 完整消息字典，提取content字段
                    return self._convert_segments_to_onebot(message["content"])
                else:
                    # 可能是单个消息段
                    return self._convert_segments_to_onebot([message])
            
            # 其他情况，尝试转换为字符串
            return str(message)
        except Exception as e:
            self.logger.error(f"转换为外部格式时发生错误: {e}", exc_info=True)
            raise MessageFormatError(f"转换为外部格式时发生错误: {e}")
    
    def _convert_segments_to_onebot(self, segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        将消息段列表转换为OneBot格式
        
        Args:
            segments: 消息段列表
            
        Returns:
            OneBot格式消息段列表
        """
        onebot_segments = []
        
        for segment in segments:
            if not isinstance(segment, dict) or "type" not in segment:
                # 无效的消息段，跳过
                continue
            
            segment_type = segment.get("type")
            segment_data = segment.get("data", {})
            
            if segment_type == "text":
                onebot_segments.append({
                    "type": "text",
                    "data": {"text": segment_data.get("text", "")}
                })
            elif segment_type in ["image", "record", "video", "at", "share", "music", "reply"]:
                # 这些类型可以直接传递，只需确保格式正确
                onebot_segments.append({
                    "type": segment_type,
                    "data": segment_data
                })
            else:
                # 对于其他类型，记录日志并尝试保留
                self.logger.debug(f"未知的消息段类型: {segment_type}")
                onebot_segments.append({
                    "type": segment_type,
                    "data": segment_data
                })
        
        return onebot_segments
    
    def create_text_message(self, text: str) -> List[Dict[str, Any]]:
        """
        创建文本消息
        
        Args:
            text: 文本内容
            
        Returns:
            消息段列表
        """
        return [{
            "type": "text",
            "data": {"text": text}
        }]
    
    def create_image_message(self, file: str, url: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        创建图片消息
        
        Args:
            file: 图片文件路径或Base64编码
            url: 图片URL
            
        Returns:
            消息段列表
        """
        data = {"file": file}
        if url:
            data["url"] = url
            
        return [{
            "type": "image",
            "data": data
        }]
    
    def create_at_message(self, user_id: Union[int, str]) -> List[Dict[str, Any]]:
        """
        创建@消息
        
        Args:
            user_id: 用户QQ号
            
        Returns:
            消息段列表
        """
        return [{
            "type": "at",
            "data": {"qq": str(user_id)}
        }]
    
    def create_reply_message(self, message_id: Union[int, str]) -> List[Dict[str, Any]]:
        """
        创建回复消息
        
        Args:
            message_id: 被回复消息ID
            
        Returns:
            消息段列表
        """
        return [{
            "type": "reply",
            "data": {"id": str(message_id)}
        }]
    
    def combine_message_segments(self, *segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        合并多个消息段列表
        
        Args:
            *segments: 多个消息段列表
            
        Returns:
            合并后的消息段列表
        """
        combined = []
        for segment in segments:
            combined.extend(segment)
        return combined
    
    def extract_plain_text(self, message: Union[str, List[Dict[str, Any]], Dict[str, Any]]) -> str:
        """
        提取消息中的纯文本内容
        
        Args:
            message: 消息内容，可以是字符串、消息段列表或完整消息字典
            
        Returns:
            纯文本内容
        """
        # 如果是字符串，直接返回
        if isinstance(message, str):
            return message
        
        # 如果是字典，检查是否为完整消息字典
        if isinstance(message, dict):
            if "content" in message:
                # 完整消息字典，提取content字段
                segments = message["content"]
            else:
                # 可能是单个消息段
                segments = [message]
        else:
            # 否则假定为消息段列表
            segments = message
        
        # 提取文本内容
        text_parts = []
        for segment in segments:
            if isinstance(segment, dict) and segment.get("type") == "text":
                text_parts.append(segment.get("data", {}).get("text", ""))
        
        return "".join(text_parts) 
# -*- coding: utf-8 -*-

"""
林镜(LingJing) - 消息格式适配器
"""



class MessageAdapter:
    """消息格式适配器，用于转换内外部消息格式"""
    
    def __init__(self):
        """初始化消息适配器"""
        self.logger = logging.getLogger('linjing.message_adapter')
    
    def convert_to_internal(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        将OneBot消息转为内部格式
        
        Args:
            data: OneBot消息数据
            
        Returns:
            内部格式消息数据
        """
        try:
            # 检查必要字段
            if "post_type" not in data:
                raise MessageParseError("消息缺少post_type字段")
            
            # 获取事件类型
            post_type = data.get("post_type")
            
            # 根据事件类型处理
            if post_type == "message":
                return self._convert_message_event(data)
            elif post_type == "notice":
                return self._convert_notice_event(data)
            elif post_type == "request":
                return self._convert_request_event(data)
            elif post_type == "meta_event":
                return self._convert_meta_event(data)
            else:
                self.logger.warning(f"未知的事件类型: {post_type}")
                return self._convert_unknown_event(data)
        except Exception as e:
            self.logger.error(f"转换消息格式时发生错误: {e}", exc_info=True)
            raise MessageParseError(f"转换消息格式时发生错误: {e}")
    
    def _convert_message_event(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        转换消息事件
        
        Args:
            data: OneBot消息事件数据
            
        Returns:
            内部格式消息事件数据
        """
        # 检查必要字段
        for field in ["message_type", "user_id", "message", "time"]:
            if field not in data:
                raise MessageParseError(f"消息缺少{field}字段")
        
        # 获取消息类型和内容
        message_type = data.get("message_type")
        raw_message = data.get("message", "")
        
        # 格式化消息内容
        if isinstance(raw_message, str):
            # 尝试解析CQ码
            message_content = self._parse_cq_code(raw_message)
        else:
            # 已经是数组格式
            message_content = raw_message
        
        # 构建基本消息结构
        internal_message = {
            "id": data.get("message_id", ""),
            "type": EventType.MESSAGE,
            "message_type": message_type,
            "sender": {
                "user_id": data.get("user_id"),
                "nickname": data.get("sender", {}).get("nickname", ""),
                "card": data.get("sender", {}).get("card", ""),
                "role": data.get("sender", {}).get("role", ""),
                "title": data.get("sender", {}).get("title", ""),
                "is_admin": data.get("sender", {}).get("role") in ["admin", "owner"],
            },
            "content": message_content,
            "raw_content": raw_message,
            "time": datetime.fromtimestamp(data.get("time")),
            "self_id": data.get("self_id"),
            "original": data
        }
        
        # 根据消息类型添加特定字段
        if message_type == MessageType.GROUP:
            internal_message["group_id"] = data.get("group_id")
            internal_message["sub_type"] = data.get("sub_type", "normal")
            internal_message["anonymous"] = data.get("anonymous")
        
        return internal_message
    
    def _convert_notice_event(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        转换通知事件
        
        Args:
            data: OneBot通知事件数据
            
        Returns:
            内部格式通知事件数据
        """
        # 检查必要字段
        if "notice_type" not in data:
            raise MessageParseError("通知缺少notice_type字段")
        
        # 基本通知结构
        internal_notice = {
            "type": EventType.NOTICE,
            "notice_type": data.get("notice_type"),
            "time": datetime.fromtimestamp(data.get("time", datetime.now().timestamp())),
            "self_id": data.get("self_id"),
            "original": data
        }
        
        # 根据通知类型添加特定字段
        notice_type = data.get("notice_type")
        
        if notice_type == "group_upload":
            internal_notice["group_id"] = data.get("group_id")
            internal_notice["user_id"] = data.get("user_id")
            internal_notice["file"] = data.get("file")
        elif notice_type == "group_admin":
            internal_notice["group_id"] = data.get("group_id")
            internal_notice["user_id"] = data.get("user_id")
            internal_notice["sub_type"] = data.get("sub_type")  # set/unset
        elif notice_type == "group_decrease" or notice_type == "group_increase":
            internal_notice["group_id"] = data.get("group_id")
            internal_notice["user_id"] = data.get("user_id")
            internal_notice["operator_id"] = data.get("operator_id")
            internal_notice["sub_type"] = data.get("sub_type")
        elif notice_type == "friend_add":
            internal_notice["user_id"] = data.get("user_id")
        elif notice_type == "notify":
            internal_notice["group_id"] = data.get("group_id")
            internal_notice["user_id"] = data.get("user_id")
            internal_notice["sub_type"] = data.get("sub_type")
            if data.get("sub_type") == "poke":
                internal_notice["target_id"] = data.get("target_id")
        
        return internal_notice
    
    def _convert_request_event(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        转换请求事件
        
        Args:
            data: OneBot请求事件数据
            
        Returns:
            内部格式请求事件数据
        """
        # 检查必要字段
        if "request_type" not in data:
            raise MessageParseError("请求缺少request_type字段")
        
        # 基本请求结构
        internal_request = {
            "type": EventType.REQUEST,
            "request_type": data.get("request_type"),
            "user_id": data.get("user_id"),
            "comment": data.get("comment", ""),
            "flag": data.get("flag"),
            "time": datetime.fromtimestamp(data.get("time", datetime.now().timestamp())),
            "self_id": data.get("self_id"),
            "original": data
        }
        
        # 根据请求类型添加特定字段
        request_type = data.get("request_type")
        
        if request_type == "friend":
            pass  # 已经包含所有需要的字段
        elif request_type == "group":
            internal_request["group_id"] = data.get("group_id")
            internal_request["sub_type"] = data.get("sub_type")  # add/invite
        
        return internal_request
    
    def _convert_meta_event(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        转换元事件
        
        Args:
            data: OneBot元事件数据
            
        Returns:
            内部格式元事件数据
        """
        # 检查必要字段
        if "meta_event_type" not in data:
            raise MessageParseError("元事件缺少meta_event_type字段")
        
        # 基本元事件结构
        internal_meta = {
            "type": EventType.META,
            "meta_event_type": data.get("meta_event_type"),
            "time": datetime.fromtimestamp(data.get("time", datetime.now().timestamp())),
            "self_id": data.get("self_id"),
            "original": data
        }
        
        # 根据元事件类型添加特定字段
        meta_event_type = data.get("meta_event_type")
        
        if meta_event_type == "lifecycle":
            internal_meta["sub_type"] = data.get("sub_type")  # enable/disable/connect
        elif meta_event_type == "heartbeat":
            internal_meta["status"] = data.get("status", {})
            internal_meta["interval"] = data.get("interval")
        
        return internal_meta
    
    def _convert_unknown_event(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        转换未知事件
        
        Args:
            data: 未知事件数据
            
        Returns:
            内部格式未知事件数据
        """
        return {
            "type": "unknown",
            "original": data,
            "time": datetime.fromtimestamp(data.get("time", datetime.now().timestamp())),
            "self_id": data.get("self_id")
        }
    
    def _parse_cq_code(self, text: str) -> List[Dict[str, Any]]:
        """
        解析CQ码
        
        Args:
            text: 包含CQ码的文本
            
        Returns:
            消息段列表
        """
        segments = []
        
        # 如果不包含CQ码，直接返回文本段
        if "[CQ:" not in text:
            segments.append({"type": "text", "data": {"text": text}})
            return segments
        
        # 解析文本中的CQ码
        current_index = 0
        text_length = len(text)
        
        while current_index < text_length:
            # 查找CQ码开始位置
            cq_start = text.find("[CQ:", current_index)
            
            # 如果没有找到CQ码，添加剩余文本并结束
            if cq_start == -1:
                if current_index < text_length:
                    segments.append({
                        "type": "text",
                        "data": {"text": text[current_index:]}
                    })
                break
            
            # 如果CQ码前有文本，添加文本段
            if cq_start > current_index:
                segments.append({
                    "type": "text",
                    "data": {"text": text[current_index:cq_start]}
                })
            
            # 查找CQ码结束位置
            cq_end = text.find("]", cq_start)
            if cq_end == -1:
                # CQ码没有正确结束，作为普通文本处理
                segments.append({
                    "type": "text",
                    "data": {"text": text[cq_start:]}
                })
                break
            
            # 解析CQ码
            cq_code = text[cq_start:cq_end + 1]
            try:
                segment = self._parse_single_cq_code(cq_code)
                segments.append(segment)
            except MessageParseError as e:
                self.logger.warning(f"解析CQ码失败: {e}")
                segments.append({
                    "type": "text",
                    "data": {"text": cq_code}
                })
            
            # 更新当前位置
            current_index = cq_end + 1
        
        return segments
    
    def _parse_single_cq_code(self, cq_code: str) -> Dict[str, Any]:
        """
        解析单个CQ码
        
        Args:
            cq_code: CQ码字符串
            
        Returns:
            消息段字典
        """
        # 去除前后的方括号
        if not (cq_code.startswith("[CQ:") and cq_code.endswith("]")):
            raise MessageParseError(f"无效的CQ码格式: {cq_code}")
        
        cq_content = cq_code[4:-1]
        
        # 分离类型和参数
        parts = cq_content.split(",")
        if not parts:
            raise MessageParseError(f"无效的CQ码内容: {cq_content}")
        
        cq_type = parts[0].strip()
        cq_params = {}
        
        # 解析参数
        for part in parts[1:]:
            if "=" in part:
                key, value = part.split("=", 1)
                cq_params[key.strip()] = value.strip()
        
        # 根据CQ码类型构建消息段
        segment = {
            "type": cq_type,
            "data": cq_params
        }
        
        return segment
    
    def convert_to_external(self, message: Union[Dict[str, Any], str, List]) -> Union[str, List]:
        """
        将内部消息转为OneBot格式
        
        Args:
            message: 内部消息数据，可以是字符串、消息段列表或完整消息字典
            
        Returns:
            OneBot格式消息
        """
        try:
            # 如果已经是字符串，直接返回
            if isinstance(message, str):
                return message
            
            # 如果是列表，假定已经是消息段列表，转换为OneBot格式
            if isinstance(message, list):
                return self._convert_segments_to_onebot(message)
            
            # 如果是字典，检查是否为完整消息字典
            if isinstance(message, dict):
                if "content" in message:
                    # 完整消息字典，提取content字段
                    return self._convert_segments_to_onebot(message["content"])
                else:
                    # 可能是单个消息段
                    return self._convert_segments_to_onebot([message])
            
            # 其他情况，尝试转换为字符串
            return str(message)
        except Exception as e:
            self.logger.error(f"转换为外部格式时发生错误: {e}", exc_info=True)
            raise MessageFormatError(f"转换为外部格式时发生错误: {e}")
    
    def _convert_segments_to_onebot(self, segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        将消息段列表转换为OneBot格式
        
        Args:
            segments: 消息段列表
            
        Returns:
            OneBot格式消息段列表
        """
        onebot_segments = []
        
        for segment in segments:
            if not isinstance(segment, dict) or "type" not in segment:
                # 无效的消息段，跳过
                continue
            
            segment_type = segment.get("type")
            segment_data = segment.get("data", {})
            
            if segment_type == "text":
                onebot_segments.append({
                    "type": "text",
                    "data": {"text": segment_data.get("text", "")}
                })
            elif segment_type in ["image", "record", "video", "at", "share", "music", "reply"]:
                # 这些类型可以直接传递，只需确保格式正确
                onebot_segments.append({
                    "type": segment_type,
                    "data": segment_data
                })
            else:
                # 对于其他类型，记录日志并尝试保留
                self.logger.debug(f"未知的消息段类型: {segment_type}")
                onebot_segments.append({
                    "type": segment_type,
                    "data": segment_data
                })
        
        return onebot_segments
    
    def create_text_message(self, text: str) -> List[Dict[str, Any]]:
        """
        创建文本消息
        
        Args:
            text: 文本内容
            
        Returns:
            消息段列表
        """
        return [{
            "type": "text",
            "data": {"text": text}
        }]
    
    def create_image_message(self, file: str, url: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        创建图片消息
        
        Args:
            file: 图片文件路径或Base64编码
            url: 图片URL
            
        Returns:
            消息段列表
        """
        data = {"file": file}
        if url:
            data["url"] = url
            
        return [{
            "type": "image",
            "data": data
        }]
    
    def create_at_message(self, user_id: Union[int, str]) -> List[Dict[str, Any]]:
        """
        创建@消息
        
        Args:
            user_id: 用户QQ号
            
        Returns:
            消息段列表
        """
        return [{
            "type": "at",
            "data": {"qq": str(user_id)}
        }]
    
    def create_reply_message(self, message_id: Union[int, str]) -> List[Dict[str, Any]]:
        """
        创建回复消息
        
        Args:
            message_id: 被回复消息ID
            
        Returns:
            消息段列表
        """
        return [{
            "type": "reply",
            "data": {"id": str(message_id)}
        }]
    
    def combine_message_segments(self, *segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        合并多个消息段列表
        
        Args:
            *segments: 多个消息段列表
            
        Returns:
            合并后的消息段列表
        """
        combined = []
        for segment in segments:
            combined.extend(segment)
        return combined
    
    def extract_plain_text(self, message: Union[str, List[Dict[str, Any]], Dict[str, Any]]) -> str:
        """
        提取消息中的纯文本内容
        
        Args:
            message: 消息内容，可以是字符串、消息段列表或完整消息字典
            
        Returns:
            纯文本内容
        """
        # 如果是字符串，直接返回
        if isinstance(message, str):
            return message
        
        # 如果是字典，检查是否为完整消息字典
        if isinstance(message, dict):
            if "content" in message:
                # 完整消息字典，提取content字段
                segments = message["content"]
            else:
                # 可能是单个消息段
                segments = [message]
        else:
            # 否则假定为消息段列表
            segments = message
        
        # 提取文本内容
        text_parts = []
        for segment in segments:
            if isinstance(segment, dict) and segment.get("type") == "text":
                text_parts.append(segment.get("data", {}).get("text", ""))
        
        return "".join(text_parts) 