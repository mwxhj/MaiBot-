#!/usr/bin/env python
# -*- coding: utf-8 -*-

from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, field


@dataclass
class WebSocketConfig:
    """WebSocket服务器配置"""
    host: str = "0.0.0.0"
    port: int = 8080
    endpoint: str = "/onebot/v11/ws"
    access_token: Optional[str] = None
    heartbeat_interval: int = 30  # 心跳间隔（秒）
    enable_tls: bool = False
    cert_file: Optional[str] = None
    key_file: Optional[str] = None


@dataclass
class HTTPConfig:
    """HTTP服务器配置"""
    host: str = "0.0.0.0"
    port: int = 8081
    endpoint: str = "/api"
    access_token: Optional[str] = None
    enable_tls: bool = False
    cert_file: Optional[str] = None
    key_file: Optional[str] = None


@dataclass
class NapcatConfig:
    """napcat特定配置"""
    enabled: bool = True
    api_base: str = "http://napcat:3000"  # napcat API基础URL
    auth_token: Optional[str] = None
    device_id: Optional[str] = None
    protocol_version: str = "11"  # napcat支持的协议版本
    reconnect_interval: int = 5  # 重连间隔（秒）
    max_reconnect_attempts: int = 10
    features: List[str] = field(default_factory=lambda: [
        "message", "notice", "request", "meta"
    ])  # 启用的功能列表


@dataclass
class MiddlewareConfig:
    """中间件配置"""
    enabled: List[str] = field(default_factory=lambda: ["authentication", "rate_limiter"])
    rate_limit: Dict[str, Any] = field(default_factory=lambda: {
        "default": 20,  # 默认每分钟请求次数限制
        "admin": 100    # 管理员每分钟请求次数限制
    })


@dataclass
class ServerConfig:
    """服务器总体配置"""
    server_name: str = "MaiBot"
    log_level: str = "INFO"
    debug_mode: bool = False
    websocket: WebSocketConfig = field(default_factory=WebSocketConfig)
    http: HTTPConfig = field(default_factory=HTTPConfig)
    napcat: NapcatConfig = field(default_factory=NapcatConfig)
    middleware: MiddlewareConfig = field(default_factory=MiddlewareConfig)
    admin_users: List[int] = field(default_factory=list)
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> 'ServerConfig':
        """从字典创建配置对象"""
        # 读取顶层键
        server_config = {
            k: v for k, v in config_dict.items() 
            if k not in ['websocket', 'http', 'napcat', 'middleware']
        }
        
        # 创建嵌套配置对象
        if 'websocket' in config_dict:
            server_config['websocket'] = WebSocketConfig(**config_dict['websocket'])
        if 'http' in config_dict:
            server_config['http'] = HTTPConfig(**config_dict['http'])
        if 'napcat' in config_dict:
            server_config['napcat'] = NapcatConfig(**config_dict['napcat'])
        if 'middleware' in config_dict:
            server_config['middleware'] = MiddlewareConfig(**config_dict['middleware'])
            
        return cls(**server_config)
    
    def to_dict(self) -> Dict[str, Any]:
        """将配置转换为字典"""
        result = {
            'server_name': self.server_name,
            'log_level': self.log_level,
            'debug_mode': self.debug_mode,
            'admin_users': self.admin_users,
            'websocket': {
                'host': self.websocket.host,
                'port': self.websocket.port,
                'endpoint': self.websocket.endpoint,
                'access_token': self.websocket.access_token,
                'heartbeat_interval': self.websocket.heartbeat_interval,
                'enable_tls': self.websocket.enable_tls,
                'cert_file': self.websocket.cert_file,
                'key_file': self.websocket.key_file
            },
            'http': {
                'host': self.http.host,
                'port': self.http.port,
                'endpoint': self.http.endpoint,
                'access_token': self.http.access_token,
                'enable_tls': self.http.enable_tls,
                'cert_file': self.http.cert_file,
                'key_file': self.http.key_file
            },
            'napcat': {
                'enabled': self.napcat.enabled,
                'api_base': self.napcat.api_base,
                'auth_token': self.napcat.auth_token,
                'device_id': self.napcat.device_id,
                'protocol_version': self.napcat.protocol_version,
                'reconnect_interval': self.napcat.reconnect_interval,
                'max_reconnect_attempts': self.napcat.max_reconnect_attempts,
                'features': self.napcat.features
            },
            'middleware': {
                'enabled': self.middleware.enabled,
                'rate_limit': self.middleware.rate_limit
            }
        }
        return result 