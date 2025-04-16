#!/usr/bin/env python
# -*- coding: utf-8 -*-

import asyncio
import signal
import sys
from typing import Dict, Any

from config import load_config
from utils.logger import setup_logger, get_logger
from storage.mongodb_manager import MongoDBManager
from storage.redis_cache import RedisCache
from storage.vector_db import VectorDBManager
from llm.llm_interface import LLMInterface
from memory.memory_manager import MemoryManager
from emotion.emotion_system import EmotionSystem
from core.message_processor import MessageProcessor
from plugins.plugin_manager import PluginManager
from server.onebot_proxy import OneBotProxy


class MaiBot:
    """MaiBot主类，负责协调所有组件的初始化和运行"""
    
    def __init__(self):
        """初始化MaiBot实例"""
        self.config = load_config()
        self.logger = setup_logger(__name__, self.config.get("logging", {}))
        self.components = {}  # 存储所有组件的引用
        self.is_running = False
        
    async def initialize(self) -> bool:
        """初始化所有组件"""
        try:
            self.logger.info("开始初始化MaiBot组件...")
            
            # 初始化数据存储
            self.components["mongodb"] = await self._init_mongodb()
            self.components["redis"] = await self._init_redis()
            self.components["vector_db"] = await self._init_vector_db()
            
            # 初始化LLM接口
            self.components["llm"] = await self._init_llm()
            
            # 初始化核心系统
            self.components["memory"] = await self._init_memory()
            self.components["emotion"] = await self._init_emotion()
            
            # 初始化插件系统
            self.components["plugins"] = await self._init_plugins()
            
            # 初始化消息处理器
            self.components["processor"] = await self._init_processor()
            
            # 初始化OneBot代理
            self.components["onebot"] = await self._init_onebot()
            
            self.logger.info("MaiBot所有组件初始化完成")
            return True
            
        except Exception as e:
            self.logger.error(f"初始化MaiBot失败: {str(e)}", exc_info=True)
            return False
    
    async def _init_mongodb(self) -> MongoDBManager:
        """初始化MongoDB连接"""
        self.logger.info("初始化MongoDB连接...")
        mongo_config = self.config.get("storage", {}).get("mongodb", {})
        mongodb = MongoDBManager(mongo_config)
        await mongodb.connect()
        return mongodb
    
    async def _init_redis(self) -> RedisCache:
        """初始化Redis缓存"""
        self.logger.info("初始化Redis缓存...")
        redis_config = self.config.get("storage", {}).get("redis", {})
        redis = RedisCache(redis_config)
        await redis.connect()
        return redis
    
    async def _init_vector_db(self) -> VectorDBManager:
        """初始化向量数据库"""
        self.logger.info("初始化向量数据库...")
        vector_config = self.config.get("storage", {}).get("vector_db", {})
        vector_db = VectorDBManager(vector_config)
        await vector_db.connect()
        return vector_db
    
    async def _init_llm(self) -> LLMInterface:
        """初始化LLM接口"""
        self.logger.info("初始化LLM接口...")
        llm_config = self.config.get("llm", {})
        llm = LLMInterface(llm_config)
        await llm.initialize()
        return llm
    
    async def _init_memory(self) -> MemoryManager:
        """初始化记忆系统"""
        self.logger.info("初始化记忆系统...")
        memory_config = self.config.get("memory", {})
        memory = MemoryManager(
            memory_config,
            self.components["vector_db"],
            self.components["mongodb"],
            self.components["llm"]
        )
        await memory.initialize()
        return memory
    
    async def _init_emotion(self) -> EmotionSystem:
        """初始化情绪系统"""
        self.logger.info("初始化情绪系统...")
        emotion_config = self.config.get("emotion", {})
        emotion = EmotionSystem(
            emotion_config,
            self.components["mongodb"],
            self.components["llm"]
        )
        await emotion.initialize()
        return emotion
    
    async def _init_plugins(self) -> PluginManager:
        """初始化插件系统"""
        self.logger.info("初始化插件系统...")
        plugin_config = self.config.get("plugins", {})
        plugin_manager = PluginManager(plugin_config, self.components)
        await plugin_manager.load_plugins()
        return plugin_manager
    
    async def _init_processor(self) -> MessageProcessor:
        """初始化消息处理器"""
        self.logger.info("初始化消息处理器...")
        processor_config = self.config.get("core", {})
        processor = MessageProcessor(
            processor_config,
            self.components["llm"],
            self.components["memory"],
            self.components["emotion"],
            self.components["plugins"]
        )
        return processor
    
    async def _init_onebot(self) -> OneBotProxy:
        """初始化OneBot代理"""
        self.logger.info("初始化OneBot代理...")
        onebot_config = self.config.get("server", {})
        onebot = OneBotProxy(
            onebot_config,
            self.components["processor"]
        )
        return onebot
    
    async def start(self) -> None:
        """启动MaiBot服务"""
        if not self.is_running:
            self.logger.info("启动MaiBot服务...")
            # 启动OneBot代理服务
            await self.components["onebot"].start()
            self.is_running = True
            self.logger.info("MaiBot服务已启动")
    
    async def stop(self) -> None:
        """停止MaiBot服务"""
        if self.is_running:
            self.logger.info("正在停止MaiBot服务...")
            
            # 停止OneBot代理
            await self.components["onebot"].stop()
            
            # 关闭各种连接
            await self.components["mongodb"].close()
            await self.components["redis"].close()
            await self.components["vector_db"].close()
            
            self.is_running = False
            self.logger.info("MaiBot服务已停止")
    
    def setup_signal_handlers(self):
        """设置信号处理器"""
        loop = asyncio.get_event_loop()
        
        # 处理SIGINT和SIGTERM信号
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(
                sig,
                lambda: asyncio.create_task(self.handle_shutdown())
            )
    
    async def handle_shutdown(self):
        """处理关闭信号"""
        self.logger.info("接收到关闭信号，准备优雅关闭...")
        await self.stop()
        asyncio.get_event_loop().stop()


async def main():
    """主函数"""
    logger = get_logger("main")
    logger.info("MaiBot 启动中...")
    
    bot = MaiBot()
    if await bot.initialize():
        bot.setup_signal_handlers()
        await bot.start()
        
        # 保持程序运行
        try:
            while bot.is_running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info("主循环被取消")
        finally:
            await bot.stop()
    else:
        logger.error("MaiBot初始化失败，无法启动服务")
        return 1
    
    return 0


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    exit_code = loop.run_until_complete(main())
    sys.exit(exit_code) 