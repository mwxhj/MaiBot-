"""
情绪管理器

该模块负责管理机器人的情绪状态，包括获取、更新和保存情绪状态。
"""

import json
import time
import logging
import asyncio
from typing import Dict, Any, List, Optional, Tuple

from ..storage.database import DatabaseManager
from ..utils.logger import get_logger
from .mood_model import MoodModel
from .emotion_rules import EmotionRules

logger = get_logger(__name__)

class EmotionState:
    """情绪状态类，表示机器人在某一时刻的情绪状态"""
    
    # 默认情绪维度及其初始值
    DEFAULT_DIMENSIONS = {
        "happiness": 0.5,      # 快乐-悲伤
        "excitement": 0.3,     # 兴奋-平静
        "confidence": 0.6,     # 自信-怯懦
        "friendliness": 0.7,   # 友好-疏远
        "curiosity": 0.8,      # 好奇-冷漠
        "patience": 0.6,       # 耐心-急躁
        "trust": 0.5,          # 信任-怀疑
    }
    
    def __init__(self, dimensions: Optional[Dict[str, float]] = None, timestamp: Optional[float] = None):
        """
        初始化情绪状态
        
        Args:
            dimensions: 情绪维度字典，键为维度名称，值为维度值（0-1）
            timestamp: 情绪状态的时间戳
        """
        self.dimensions = dimensions or self.DEFAULT_DIMENSIONS.copy()
        self.timestamp = timestamp or time.time()
        
        # 验证情绪值范围
        for dim, value in self.dimensions.items():
            if value < 0 or value > 1:
                logger.warning(f"情绪维度 {dim} 的值 {value} 超出范围 [0,1]，已调整")
                self.dimensions[dim] = max(0, min(1, value))
    
    def update(self, changes: Dict[str, float]) -> 'EmotionState':
        """
        根据变化量更新情绪状态
        
        Args:
            changes: 情绪变化字典，键为维度名称，值为变化量
            
        Returns:
            更新后的情绪状态对象
        """
        new_dimensions = self.dimensions.copy()
        
        for dim, delta in changes.items():
            if dim in new_dimensions:
                new_value = new_dimensions[dim] + delta
                # 确保情绪值在 [0,1] 范围内
                new_dimensions[dim] = max(0, min(1, new_value))
                
        return EmotionState(new_dimensions)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        将情绪状态转换为字典
        
        Returns:
            包含情绪状态信息的字典
        """
        return {
            "dimensions": self.dimensions,
            "timestamp": self.timestamp
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EmotionState':
        """
        从字典创建情绪状态对象
        
        Args:
            data: 包含情绪状态信息的字典
            
        Returns:
            情绪状态对象
        """
        return cls(
            dimensions=data.get("dimensions"),
            timestamp=data.get("timestamp")
        )
    
    def get_dominant_emotion(self) -> Tuple[str, float]:
        """
        获取当前最显著的情绪
        
        Returns:
            (情绪名称, 情绪强度)的元组
        """
        if not self.dimensions:
            return ("neutral", 0.5)
        
        # 获取值最高的情绪维度
        dominant_dim = max(self.dimensions.items(), key=lambda x: x[1])
        return dominant_dim
    
    def __str__(self) -> str:
        """字符串表示"""
        dominant = self.get_dominant_emotion()
        return f"EmotionState(dominant={dominant[0]}:{dominant[1]:.2f}, dims={len(self.dimensions)})"


class EmotionManager:
    """情绪管理器，负责管理机器人的情绪状态"""
    
    def __init__(self, config: Dict[str, Any], db_manager: DatabaseManager):
        """
        初始化情绪管理器
        
        Args:
            config: 配置信息
            db_manager: 数据库管理器
        """
        self.config = config
        self.db_manager = db_manager
        self.mood_model = MoodModel()
        self.emotion_rules = EmotionRules()
        
        # 情绪衰减配置
        self.decay_rate = config.get("emotion_decay_rate", 0.05)
        self.decay_interval = config.get("emotion_decay_interval", 3600)  # 默认1小时
        
        # 用户情绪缓存 {user_id: EmotionState}
        self.emotion_cache = {}
        
        # 启动情绪衰减任务
        self._start_decay_task()
    
    def _start_decay_task(self):
        """启动情绪衰减定时任务"""
        asyncio.create_task(self._decay_loop())
    
    async def _decay_loop(self):
        """情绪衰减循环"""
        while True:
            try:
                await asyncio.sleep(self.decay_interval)
                await self._apply_emotion_decay()
                logger.debug(f"已执行情绪衰减，当前缓存用户数: {len(self.emotion_cache)}")
            except Exception as e:
                logger.error(f"情绪衰减任务出错: {e}")
    
    async def _apply_emotion_decay(self):
        """应用情绪衰减"""
        for user_id, emotion in list(self.emotion_cache.items()):
            # 计算情绪衰减
            decay_changes = {}
            for dim, value in emotion.dimensions.items():
                # 情绪向中性值(0.5)衰减
                if value > 0.5:
                    decay_changes[dim] = -self.decay_rate
                elif value < 0.5:
                    decay_changes[dim] = self.decay_rate
                
            # 应用衰减
            updated_emotion = emotion.update(decay_changes)
            self.emotion_cache[user_id] = updated_emotion
            
            # 保存到数据库
            await self.save_emotion(user_id, updated_emotion)
    
    async def get_emotion(self, user_id: str) -> EmotionState:
        """
        获取用户的情绪状态
        
        Args:
            user_id: 用户ID
            
        Returns:
            情绪状态对象
        """
        # 优先从缓存获取
        if user_id in self.emotion_cache:
            return self.emotion_cache[user_id]
        
        # 从数据库获取
        try:
            query = "SELECT emotion_data FROM user_emotions WHERE user_id = ? ORDER BY timestamp DESC LIMIT 1"
            results = await self.db_manager.execute_query(query, (user_id,))
            
            if results and results[0].get("emotion_data"):
                emotion_data = json.loads(results[0]["emotion_data"])
                emotion = EmotionState.from_dict(emotion_data)
                self.emotion_cache[user_id] = emotion
                return emotion
            
        except Exception as e:
            logger.error(f"获取用户情绪失败: {e}")
        
        # 如果没有找到，返回默认情绪状态
        default_emotion = EmotionState()
        self.emotion_cache[user_id] = default_emotion
        return default_emotion
    
    async def update_emotion(self, user_id: str, factors: Dict[str, Any], message_text: str = "") -> EmotionState:
        """
        更新用户的情绪状态
        
        Args:
            user_id: 用户ID
            factors: 影响情绪的因素
            message_text: 用户消息文本
            
        Returns:
            更新后的情绪状态
        """
        # 获取当前情绪
        current_emotion = await self.get_emotion(user_id)
        
        # 计算情绪变化
        emotion_changes = self.mood_model.compute_changes(
            current_emotion, 
            factors, 
            message_text
        )
        
        # 应用情绪规则
        rule_changes = await self.emotion_rules.apply_rules(current_emotion, message_text, factors)
        
        # 合并变化
        combined_changes = emotion_changes.copy()
        for dim, value in rule_changes.items():
            combined_changes[dim] = combined_changes.get(dim, 0) + value
        
        # 更新情绪
        updated_emotion = current_emotion.update(combined_changes)
        
        # 更新缓存
        self.emotion_cache[user_id] = updated_emotion
        
        # 保存到数据库
        await self.save_emotion(user_id, updated_emotion)
        
        return updated_emotion
    
    async def save_emotion(self, user_id: str, emotion: EmotionState) -> None:
        """
        保存情绪状态到数据库
        
        Args:
            user_id: 用户ID
            emotion: 情绪状态对象
        """
        try:
            emotion_data = json.dumps(emotion.to_dict())
            timestamp = emotion.timestamp
            
            query = """
            INSERT INTO user_emotions (user_id, emotion_data, timestamp) 
            VALUES (?, ?, ?)
            """
            await self.db_manager.execute_insert(query, (user_id, emotion_data, timestamp))
            
        except Exception as e:
            logger.error(f"保存用户情绪失败: {e}")
    
    def emotion_to_text(self, emotion: EmotionState) -> str:
        """
        将情绪状态转换为文本描述
        
        Args:
            emotion: 情绪状态对象
            
        Returns:
            情绪的文本描述
        """
        # 获取主导情绪
        dominant_dim, dominant_value = emotion.get_dominant_emotion()
        
        # 根据情绪值生成描述
        intensity = ""
        if dominant_value > 0.8:
            intensity = "非常"
        elif dominant_value > 0.65:
            intensity = "相当"
        elif dominant_value > 0.5:
            intensity = "有些"
        
        # 情绪名称映射
        emotion_names = {
            "happiness": "开心",
            "excitement": "兴奋",
            "confidence": "自信",
            "friendliness": "友好",
            "curiosity": "好奇",
            "patience": "耐心",
            "trust": "信任",
        }
        
        # 生成描述
        if dominant_value > 0.5:
            emotion_name = emotion_names.get(dominant_dim, dominant_dim)
            description = f"{intensity}{emotion_name}"
        elif dominant_value < 0.35:
            # 反向情绪
            reverse_emotions = {
                "happiness": "忧郁",
                "excitement": "平静",
                "confidence": "不自信",
                "friendliness": "疏远",
                "curiosity": "冷漠",
                "patience": "急躁",
                "trust": "怀疑",
            }
            emotion_name = reverse_emotions.get(dominant_dim, f"不{emotion_names.get(dominant_dim, dominant_dim)}")
            description = f"{intensity}{emotion_name}"
        else:
            description = "平静"
        
        return description
    
    async def initialize_tables(self) -> None:
        """初始化数据库表"""
        try:
            query = """
            CREATE TABLE IF NOT EXISTS user_emotions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                emotion_data TEXT NOT NULL,
                timestamp REAL NOT NULL,
                UNIQUE(user_id, timestamp)
            )
            """
            await self.db_manager.execute_query(query)
            
            # 创建索引
            index_query = """
            CREATE INDEX IF NOT EXISTS idx_user_emotions_user_id_timestamp 
            ON user_emotions(user_id, timestamp)
            """
            await self.db_manager.execute_query(index_query)
            
            logger.info("情绪数据库表初始化完成")
            
        except Exception as e:
            logger.error(f"初始化情绪数据库表失败: {e}")
            raise 