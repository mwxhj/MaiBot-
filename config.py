#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import logging
from typing import Dict, Any

def load_config() -> Dict[str, Any]:
    """加载配置文件，优先从环境变量指定的位置加载，否则使用默认配置"""
    config_path = os.environ.get("MAIBOT_CONFIG", "/app/config/config.json")
    logger = logging.getLogger("config")
    
    try:
        # 尝试从文件加载配置
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                logger.info(f"从 {config_path} 加载配置")
                return json.load(f)
    except Exception as e:
        logger.warning(f"加载配置文件失败: {e}，将使用默认配置")
    
    # 从环境变量加载MongoDB配置
    mongodb_uri = os.environ.get("MONGODB_URI", "mongodb://mongodb:27017/maibot")
    
    # 返回基本默认配置
    return {
        "server": {
            "websocket": {
                "host": "0.0.0.0",
                "port": int(os.environ.get("WS_PORT", 8080)),
                "endpoint": "/onebot/v11/ws"
            },
            "http": {
                "host": "0.0.0.0",
                "port": int(os.environ.get("HTTP_PORT", 8081))
            },
            "napcat": {
                "enabled": True,
                "api_base": os.environ.get("NAPCAT_API_BASE", "http://napcat:3000"),
                "auth_token": os.environ.get("NAPCAT_AUTH_TOKEN", "")
            }
        },
        "storage": {
            "mongodb": {
                "uri": mongodb_uri,
                "database": os.environ.get("MONGODB_DATABASE", "maibot")
            },
            "redis": {
                "uri": os.environ.get("REDIS_URI", "redis://redis:6379/0")
            }
        },
        "logging": {
            "level": os.environ.get("LOG_LEVEL", "INFO"),
            "format": "%(asctime)s [%(levelname)s] %(name)s | %(message)s",
            "datefmt": "%m-%d %H:%M:%S"
        }
    } 