#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
常量定义模块，定义全局使用的常量。
"""

# 版本信息
VERSION = "0.1.0"
AUTHOR = "LinjingBot Team"

# 事件类型
class EventType:
    """事件类型常量"""
    MESSAGE_RECEIVED = "message_received"
    MESSAGE_SENT = "message_sent"
    EMOTION_UPDATED = "emotion_updated"
    MEMORY_STORED = "memory_stored"
    PLUGIN_LOADED = "plugin_loaded"
    BOT_STARTED = "bot_started"
    BOT_STOPPED = "bot_stopped"
    ERROR_OCCURRED = "error_occurred"

# 消息类型
class MessageType:
    """消息类型常量"""
    TEXT = "text"
    IMAGE = "image"
    VOICE = "voice"
    VIDEO = "video"
    FILE = "file"
    LOCATION = "location"
    CONTACT = "contact"
    REPLY = "reply"
    AT = "at"
    EMOJI = "emoji"
    RAW = "raw"

# 记忆类型
class MemoryType:
    """记忆类型常量"""
    CONVERSATION = "conversation"
    FACT = "fact"
    RELATIONSHIP = "relationship"
    EVENT = "event"
    PREFERENCE = "preference"

# 情绪维度
class EmotionDimension:
    """情绪维度常量"""
    HAPPINESS = "happiness"
    SADNESS = "sadness"
    ANGER = "anger"
    FEAR = "fear"
    SURPRISE = "surprise"
    DISGUST = "disgust"

# 人格特质维度
class PersonalityTrait:
    """人格特质维度常量"""
    OPENNESS = "openness"
    CONSCIENTIOUSNESS = "conscientiousness"
    EXTRAVERSION = "extraversion"
    AGREEABLENESS = "agreeableness"
    NEUROTICISM = "neuroticism"

# 处理器名称
class ProcessorName:
    """处理器名称常量"""
    READ_AIR = "read_air"
    THOUGHT_GENERATOR = "thought_generator"
    RESPONSE_COMPOSER = "response_composer"

# 错误代码
class ErrorCode:
    """错误代码常量"""
    CONFIG_ERROR = 1001
    ADAPTER_ERROR = 1002
    LLM_ERROR = 1003
    DATABASE_ERROR = 1004
    PLUGIN_ERROR = 1005
    PROCESSOR_ERROR = 1006
    PERMISSION_ERROR = 1007
    RATE_LIMIT_ERROR = 1008
    NETWORK_ERROR = 1009
    UNKNOWN_ERROR = 9999 