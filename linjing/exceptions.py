#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
林镜(LingJing) - 自定义异常类
"""

class LinjingException(Exception):
    """林镜基础异常类"""
    def __init__(self, message="林镜发生异常", code=None):
        self.message = message
        self.code = code
        super().__init__(self.message)

# 配置相关异常
class ConfigError(LinjingException):
    """配置错误"""
    def __init__(self, message="配置错误", code=1001):
        super().__init__(message, code)

# 服务器相关异常
class ServerError(LinjingException):
    """服务器错误"""
    def __init__(self, message="服务器错误", code=2001):
        super().__init__(message, code)

class ConnectionError(ServerError):
    """连接错误"""
    def __init__(self, message="连接错误", code=2002):
        super().__init__(message, code)

class RequestError(ServerError):
    """请求错误"""
    def __init__(self, message="请求错误", code=2003):
        super().__init__(message, code)

class ResponseError(ServerError):
    """响应错误"""
    def __init__(self, message="响应错误", code=2004):
        super().__init__(message, code)

class AuthenticationError(ServerError):
    """认证错误"""
    def __init__(self, message="认证错误", code=2005):
        super().__init__(message, code)

class RateLimitExceededError(ServerError):
    """速率限制错误"""
    def __init__(self, message="请求速率超限", code=2006):
        super().__init__(message, code)

# 消息处理相关异常
class MessageProcessError(LinjingException):
    """消息处理错误"""
    def __init__(self, message="消息处理错误", code=3001):
        super().__init__(message, code)

class MessageParseError(MessageProcessError):
    """消息解析错误"""
    def __init__(self, message="消息解析错误", code=3002):
        super().__init__(message, code)

class MessageFormatError(MessageProcessError):
    """消息格式错误"""
    def __init__(self, message="消息格式错误", code=3003):
        super().__init__(message, code)

# LLM相关异常
class LLMError(LinjingException):
    """LLM错误"""
    def __init__(self, message="LLM错误", code=4001):
        super().__init__(message, code)

class LLMRequestError(LLMError):
    """LLM请求错误"""
    def __init__(self, message="LLM请求错误", code=4002):
        super().__init__(message, code)

class LLMResponseError(LLMError):
    """LLM响应错误"""
    def __init__(self, message="LLM响应错误", code=4003):
        super().__init__(message, code)

class LLMTokenLimitError(LLMError):
    """LLM令牌限制错误"""
    def __init__(self, message="LLM令牌限制错误", code=4004):
        super().__init__(message, code)

class LLMAuthenticationError(LLMError):
    """LLM认证错误"""
    def __init__(self, message="LLM认证错误", code=4005):
        super().__init__(message, code)

# 存储相关异常
class StorageError(LinjingException):
    """存储错误"""
    def __init__(self, message="存储错误", code=5001):
        super().__init__(message, code)

class DatabaseConnectionError(StorageError):
    """数据库连接错误"""
    def __init__(self, message="数据库连接错误", code=5002):
        super().__init__(message, code)

class DatabaseQueryError(StorageError):
    """数据库查询错误"""
    def __init__(self, message="数据库查询错误", code=5003):
        super().__init__(message, code)

class VectorStoreError(StorageError):
    """向量存储错误"""
    def __init__(self, message="向量存储错误", code=5004):
        super().__init__(message, code)

# 记忆相关异常
class MemoryError(LinjingException):
    """记忆错误"""
    def __init__(self, message="记忆错误", code=6001):
        super().__init__(message, code)

class MemoryRetrievalError(MemoryError):
    """记忆检索错误"""
    def __init__(self, message="记忆检索错误", code=6002):
        super().__init__(message, code)

# 情绪相关异常
class EmotionError(LinjingException):
    """情绪错误"""
    def __init__(self, message="情绪错误", code=7001):
        super().__init__(message, code)

# 插件相关异常
class PluginError(LinjingException):
    """插件错误"""
    def __init__(self, message="插件错误", code=8001):
        super().__init__(message, code)

class PluginLoadError(PluginError):
    """插件加载错误"""
    def __init__(self, message="插件加载错误", code=8002):
        super().__init__(message, code)

class PluginExecuteError(PluginError):
    """插件执行错误"""
    def __init__(self, message="插件执行错误", code=8003):
        super().__init__(message, code) 
# -*- coding: utf-8 -*-

"""
林镜(LingJing) - 自定义异常类
"""

class LinjingException(Exception):
    """林镜基础异常类"""
    def __init__(self, message="林镜发生异常", code=None):
        self.message = message
        self.code = code
        super().__init__(self.message)

# 配置相关异常
class ConfigError(LinjingException):
    """配置错误"""
    def __init__(self, message="配置错误", code=1001):
        super().__init__(message, code)

# 服务器相关异常
class ServerError(LinjingException):
    """服务器错误"""
    def __init__(self, message="服务器错误", code=2001):
        super().__init__(message, code)

class ConnectionError(ServerError):
    """连接错误"""
    def __init__(self, message="连接错误", code=2002):
        super().__init__(message, code)

class RequestError(ServerError):
    """请求错误"""
    def __init__(self, message="请求错误", code=2003):
        super().__init__(message, code)

class ResponseError(ServerError):
    """响应错误"""
    def __init__(self, message="响应错误", code=2004):
        super().__init__(message, code)

class AuthenticationError(ServerError):
    """认证错误"""
    def __init__(self, message="认证错误", code=2005):
        super().__init__(message, code)

class RateLimitExceededError(ServerError):
    """速率限制错误"""
    def __init__(self, message="请求速率超限", code=2006):
        super().__init__(message, code)

# 消息处理相关异常
class MessageProcessError(LinjingException):
    """消息处理错误"""
    def __init__(self, message="消息处理错误", code=3001):
        super().__init__(message, code)

class MessageParseError(MessageProcessError):
    """消息解析错误"""
    def __init__(self, message="消息解析错误", code=3002):
        super().__init__(message, code)

class MessageFormatError(MessageProcessError):
    """消息格式错误"""
    def __init__(self, message="消息格式错误", code=3003):
        super().__init__(message, code)

# LLM相关异常
class LLMError(LinjingException):
    """LLM错误"""
    def __init__(self, message="LLM错误", code=4001):
        super().__init__(message, code)

class LLMRequestError(LLMError):
    """LLM请求错误"""
    def __init__(self, message="LLM请求错误", code=4002):
        super().__init__(message, code)

class LLMResponseError(LLMError):
    """LLM响应错误"""
    def __init__(self, message="LLM响应错误", code=4003):
        super().__init__(message, code)

class LLMTokenLimitError(LLMError):
    """LLM令牌限制错误"""
    def __init__(self, message="LLM令牌限制错误", code=4004):
        super().__init__(message, code)

class LLMAuthenticationError(LLMError):
    """LLM认证错误"""
    def __init__(self, message="LLM认证错误", code=4005):
        super().__init__(message, code)

# 存储相关异常
class StorageError(LinjingException):
    """存储错误"""
    def __init__(self, message="存储错误", code=5001):
        super().__init__(message, code)

class DatabaseConnectionError(StorageError):
    """数据库连接错误"""
    def __init__(self, message="数据库连接错误", code=5002):
        super().__init__(message, code)

class DatabaseQueryError(StorageError):
    """数据库查询错误"""
    def __init__(self, message="数据库查询错误", code=5003):
        super().__init__(message, code)

class VectorStoreError(StorageError):
    """向量存储错误"""
    def __init__(self, message="向量存储错误", code=5004):
        super().__init__(message, code)

# 记忆相关异常
class MemoryError(LinjingException):
    """记忆错误"""
    def __init__(self, message="记忆错误", code=6001):
        super().__init__(message, code)

class MemoryRetrievalError(MemoryError):
    """记忆检索错误"""
    def __init__(self, message="记忆检索错误", code=6002):
        super().__init__(message, code)

# 情绪相关异常
class EmotionError(LinjingException):
    """情绪错误"""
    def __init__(self, message="情绪错误", code=7001):
        super().__init__(message, code)

# 插件相关异常
class PluginError(LinjingException):
    """插件错误"""
    def __init__(self, message="插件错误", code=8001):
        super().__init__(message, code)

class PluginLoadError(PluginError):
    """插件加载错误"""
    def __init__(self, message="插件加载错误", code=8002):
        super().__init__(message, code)

class PluginExecuteError(PluginError):
    """插件执行错误"""
    def __init__(self, message="插件执行错误", code=8003):
        super().__init__(message, code) 