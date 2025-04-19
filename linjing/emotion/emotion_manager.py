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
        
        # 用户情绪缓存 {user_id: MoodState} # 修正类型注释
        self.emotion_cache: Dict[str, MoodState] = {} # 使用类型提示
        
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
        baseline_mood = self.config.get("baseline_mood", "平静") # 从配置获取基线情绪
        for user_id, mood in list(self.emotion_cache.items()): # 使用 emotion_cache
            # 应用衰减
            updated_mood = mood.apply_decay(self.decay_rate, baseline_mood) # 传递基线情绪
            self.emotion_cache[user_id] = updated_mood # 更新 emotion_cache
            
            # 保存到数据库
            await self.save_mood(user_id, updated_mood)
    
    async def get_emotion(self, user_id: str) -> MoodState: # 修正返回类型提示
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
                # emotion = EmotionState.from_dict(emotion_data) # 使用 MoodState
                mood = MoodState.from_dict(emotion_data)
                self.emotion_cache[user_id] = mood
                return mood
            
        except Exception as e:
            logger.error(f"获取用户情绪失败: {e}")
        
        # 如果没有找到，返回默认情绪状态
        # default_emotion = EmotionState() # 使用 MoodState
        default_mood = MoodState()
        self.emotion_cache[user_id] = default_mood
        return default_mood
    
    async def update_emotion(self, user_id: str, factors: Dict[str, Any], message_text: str = "") -> MoodState: # 修正返回类型提示
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
        current_mood: MoodState = await self.get_emotion(user_id) # 修正类型提示

        # 计算情绪变化 (假设 mood_model 返回的是强度变化值)
        # 注意：mood_model.compute_changes 的逻辑可能需要调整以适应 MoodState
        # 暂时假设它返回一个影响值 impact
        impact = self.mood_model.compute_changes(
            current_mood,
            factors,
            message_text
        ) # 假设返回 float 或 Dict[str, float]

        # 应用情绪规则 (假设返回影响值)
        rule_impact = await self.emotion_rules.apply_rules(current_mood, message_text, factors) # 假设返回 float
        
        # 合并变化
        # 合并影响 (简化处理，直接相加)
        # TODO: 需要更复杂的逻辑来处理情绪类型变化和强度更新
        total_impact = impact + rule_impact # 简化假设

        # 更新情绪
        # updated_emotion = current_emotion.update(combined_changes) # MoodState 没有 update 方法
        # 使用 apply_impact 更新强度，情绪类型变化逻辑暂缺
        updated_mood = current_mood.apply_impact(total_impact)
        # TODO: 添加逻辑以根据 impact 或 factors 改变 mood_type

        
        # 更新缓存
        self.emotion_cache[user_id] = updated_mood

        # 保存到数据库
        # await self.save_emotion(user_id, updated_emotion) # 方法不存在，应为 save_mood
        await self.save_mood(user_id, updated_mood)

        return updated_mood
    
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
        # 移除此处的表创建逻辑，统一由 DatabaseManager 在 connect 时处理
        # 只保留一个 pass 语句确保方法有效，因为实际操作已移走
        pass # 方法体为空，因为表创建已移至 DatabaseManager