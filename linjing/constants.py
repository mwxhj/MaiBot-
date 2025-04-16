#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
林镜(LingJing) - 常量定义
"""

# 消息类型
class MessageType:
    PRIVATE = "private"
    GROUP = "group"
    TEMP = "temp"

# 消息子类型
class MessageSubType:
    NORMAL = "normal"
    NOTICE = "notice"
    ANONYMOUS = "anonymous"
    FRIEND = "friend"
    GROUP = "group"
    GROUP_SELF = "group_self"

# 事件类型
class EventType:
    MESSAGE = "message"
    NOTICE = "notice"
    REQUEST = "request"
    META = "meta_event"

# 响应状态码
class ResponseCode:
    SUCCESS = 0
    FAILED = -1
    PERMISSION_DENIED = -2
    NOT_FOUND = -3
    INVALID_PARAMS = -4
    RATE_LIMITED = -5
    INTERNAL_ERROR = -6

# 权限级别
class PermissionLevel:
    MASTER = 100  # 主人
    ADMIN = 50    # 管理员
    USER = 10     # 普通用户
    BANNED = -10  # 被禁用
    STRANGER = 0  # 陌生人

# 情绪类型
class EmotionType:
    HAPPY = "happy"
    SAD = "sad"
    ANGRY = "angry"
    AFRAID = "afraid"
    SURPRISED = "surprised"
    DISGUSTED = "disgusted"
    NEUTRAL = "neutral"

# 情绪变化因素
class EmotionFactor:
    PRAISE = "praise"          # 被表扬
    CRITICISM = "criticism"    # 被批评
    GREETING = "greeting"      # 打招呼
    INSULT = "insult"          # 被侮辱
    COMFORT = "comfort"        # 被安慰
    TIME_DECAY = "time_decay"  # 时间衰减

# 记忆类型
class MemoryType:
    EPISODIC = "episodic"    # 情景记忆
    SEMANTIC = "semantic"    # 语义记忆
    SOCIAL = "social"        # 社交记忆
    FACTUAL = "factual"      # 事实记忆
    PROCEDURAL = "procedural" # 程序记忆

# 记忆优先级
class MemoryPriority:
    HIGH = 3     # 高优先级
    MEDIUM = 2   # 中优先级
    LOW = 1      # 低优先级
    TRIVIAL = 0  # 琐碎记忆

# LLM提供商
class LLMProvider:
    OPENAI = "openai"
    AZURE = "azure"
    CUSTOM = "custom"

# 社交意图类型
class SocialIntent:
    QUESTION = "question"            # 提问
    STATEMENT = "statement"          # 陈述
    DIRECTIVE = "directive"          # 指令
    EXPRESSIVES = "expressives"      # 表达情感
    COMMISSIVES = "commissives"      # 承诺
    GREETINGS = "greetings"          # 问候
    THANKS = "thanks"                # 感谢
    APOLOGY = "apology"              # 道歉
    FAREWELL = "farewell"            # 告别
    MENTION = "mention"              # 提及机器人
    AT = "at"                        # @机器人
    IRRELEVANT = "irrelevant"        # 无关信息
    
# HTTP状态码
class HTTPStatus:
    OK = 200
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    TOO_MANY_REQUESTS = 429
    INTERNAL_SERVER_ERROR = 500
    SERVICE_UNAVAILABLE = 503 
# -*- coding: utf-8 -*-

"""
林镜(LingJing) - 常量定义
"""

# 消息类型
class MessageType:
    PRIVATE = "private"
    GROUP = "group"
    TEMP = "temp"

# 消息子类型
class MessageSubType:
    NORMAL = "normal"
    NOTICE = "notice"
    ANONYMOUS = "anonymous"
    FRIEND = "friend"
    GROUP = "group"
    GROUP_SELF = "group_self"

# 事件类型
class EventType:
    MESSAGE = "message"
    NOTICE = "notice"
    REQUEST = "request"
    META = "meta_event"

# 响应状态码
class ResponseCode:
    SUCCESS = 0
    FAILED = -1
    PERMISSION_DENIED = -2
    NOT_FOUND = -3
    INVALID_PARAMS = -4
    RATE_LIMITED = -5
    INTERNAL_ERROR = -6

# 权限级别
class PermissionLevel:
    MASTER = 100  # 主人
    ADMIN = 50    # 管理员
    USER = 10     # 普通用户
    BANNED = -10  # 被禁用
    STRANGER = 0  # 陌生人

# 情绪类型
class EmotionType:
    HAPPY = "happy"
    SAD = "sad"
    ANGRY = "angry"
    AFRAID = "afraid"
    SURPRISED = "surprised"
    DISGUSTED = "disgusted"
    NEUTRAL = "neutral"

# 情绪变化因素
class EmotionFactor:
    PRAISE = "praise"          # 被表扬
    CRITICISM = "criticism"    # 被批评
    GREETING = "greeting"      # 打招呼
    INSULT = "insult"          # 被侮辱
    COMFORT = "comfort"        # 被安慰
    TIME_DECAY = "time_decay"  # 时间衰减

# 记忆类型
class MemoryType:
    EPISODIC = "episodic"    # 情景记忆
    SEMANTIC = "semantic"    # 语义记忆
    SOCIAL = "social"        # 社交记忆
    FACTUAL = "factual"      # 事实记忆
    PROCEDURAL = "procedural" # 程序记忆

# 记忆优先级
class MemoryPriority:
    HIGH = 3     # 高优先级
    MEDIUM = 2   # 中优先级
    LOW = 1      # 低优先级
    TRIVIAL = 0  # 琐碎记忆

# LLM提供商
class LLMProvider:
    OPENAI = "openai"
    AZURE = "azure"
    CUSTOM = "custom"

# 社交意图类型
class SocialIntent:
    QUESTION = "question"            # 提问
    STATEMENT = "statement"          # 陈述
    DIRECTIVE = "directive"          # 指令
    EXPRESSIVES = "expressives"      # 表达情感
    COMMISSIVES = "commissives"      # 承诺
    GREETINGS = "greetings"          # 问候
    THANKS = "thanks"                # 感谢
    APOLOGY = "apology"              # 道歉
    FAREWELL = "farewell"            # 告别
    MENTION = "mention"              # 提及机器人
    AT = "at"                        # @机器人
    IRRELEVANT = "irrelevant"        # 无关信息
    
# HTTP状态码
class HTTPStatus:
    OK = 200
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    TOO_MANY_REQUESTS = 429
    INTERNAL_SERVER_ERROR = 500
    SERVICE_UNAVAILABLE = 503 