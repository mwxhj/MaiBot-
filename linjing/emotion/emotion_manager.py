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

class MoodState:
    """背景情绪状态类，表示机器人的当前背景情绪"""
    
    def __init__(self, mood_type: str = "平静", intensity: float = 0.5, timestamp: Optional[float] = None):
        """
        初始化背景情绪状态
        
        Args:
            mood_type: 情绪类型，必须来自 config.yaml 中的 emotion_vocabulary
            intensity: 情绪强度 (0-1)
            timestamp: 时间戳
        """
        self.mood_type = mood_type
        self.intensity = max(0, min(1, intensity))  # 确保在0-1范围内
        self.timestamp = timestamp or time.time()
    
    def apply_decay(self, decay_rate: float, baseline_mood: str) -> 'MoodState':
        """
        应用情绪衰减
        
        Args:
            decay_rate: 衰减速率
            baseline_mood: 基线情绪类型
            
        Returns:
            更新后的情绪状态
        """
        # 强度向0.5衰减
        if self.intensity > 0.5:
            new_intensity = self.intensity - decay_rate
        elif self.intensity < 0.5:
            new_intensity = self.intensity + decay_rate
        else:
            new_intensity = 0.5
            
        # 如果强度接近中性且当前情绪不是基线情绪，则切换情绪类型
        if abs(new_intensity - 0.5) < 0.1 and self.mood_type != baseline_mood:
            return MoodState(baseline_mood, 0.5)
            
        return MoodState(self.mood_type, new_intensity)
    
    def apply_impact(self, impact: float) -> 'MoodState':
        """
        应用情绪影响
        
        Args:
            impact: 影响值 (正值为提升，负值为降低)
            
        Returns:
            更新后的情绪状态
        """
        new_intensity = max(0, min(1, self.intensity + impact))
        return MoodState(self.mood_type, new_intensity)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "mood_type": self.mood_type,
            "intensity": self.intensity,
            "timestamp": self.timestamp
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MoodState':
        """从字典创建"""
        return cls(
            mood_type=data.get("mood_type", "平静"),
            intensity=data.get("intensity", 0.5),
            timestamp=data.get("timestamp")
        )
    
    def __str__(self) -> str:
        """字符串表示"""
        intensity_level = "中等"
        if self.intensity > 0.7:
            intensity_level = "强烈"
        elif self.intensity > 0.5:
            intensity_level = "明显"
        elif self.intensity < 0.3:
            intensity_level = "轻微"
        return f"MoodState({self.mood_type}, {intensity_level})"


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
        self.mood_model = MoodModel(config)
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
        for user_id, mood in list(self.mood_cache.items()):
            # 应用衰减
            updated_mood = mood.apply_decay(self.decay_rate, self.baseline_mood)
            self.mood_cache[user_id] = updated_mood
            
            # 保存到数据库
            await self.save_mood(user_id, updated_mood)
    
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
    
    async def save_mood(self, user_id: str, mood: MoodState) -> None:
        """
        保存背景情绪状态到数据库
        
        Args:
            user_id: 用户ID
            mood: 背景情绪状态对象
        """
        try:
            mood_data = json.dumps(mood.to_dict())
            timestamp = mood.timestamp
            
            query = """
            INSERT INTO user_moods (user_id, mood_data, timestamp)
            VALUES (?, ?, ?)
            """
            await self.db_manager.execute_insert(query, (user_id, mood_data, timestamp))
            
        except Exception as e:
            logger.error(f"保存用户背景情绪失败: {e}")
    
    def mood_to_text(self, mood: MoodState) -> str:
        """
        将背景情绪状态转换为文本描述
        
        Args:
            mood: 背景情绪状态对象
            
        Returns:
            情绪的文本描述
        """
        intensity_map = {
            "extreme": "极其",
            "high": "非常",
            "medium": "相当",
            "low": "有些"
        }
        
        # 根据强度值确定描述词
        if mood.intensity > 0.8:
            intensity = intensity_map.get("extreme", "极其")
        elif mood.intensity > 0.65:
            intensity = intensity_map.get("high", "非常")
        elif mood.intensity > 0.5:
            intensity = intensity_map.get("medium", "相当")
        elif mood.intensity > 0.35:
            intensity = intensity_map.get("low", "有些")
        else:
            intensity = ""
            
        return f"{intensity}{mood.mood_type}" if intensity else mood.mood_type
    
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