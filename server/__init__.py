"""
MaiBot服务层
提供与OneBot（特别是napcat实现）的通信接口
"""

from .onebot_proxy import OneBotProxy
from .message_adapter import MessageAdapter
from .server_config import ServerConfig

__all__ = ['OneBotProxy', 'MessageAdapter', 'ServerConfig'] 