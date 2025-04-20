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
    """情绪状态类，包含 VAD 三维模型"""

    def __init__(self, valence: float = 0.5, arousal: float = 0.5, dominance: float = 0.5, timestamp: Optional[float] = None):
        """
        初始化情绪状态 (VAD 模型)

        Args:
            valence: 愉悦度 (0=消极, 0.5=中性, 1=积极)
            arousal: 激动度 (0=平静, 1=激动)
            dominance: 控制感 (0=顺从, 0.5=中性, 1=主导)
            timestamp: 时间戳
        """
        # 确保 VAD 值在 [0, 1] 范围内
        self.valence = max(0.0, min(1.0, valence))
        self.arousal = max(0.0, min(1.0, arousal))
        self.dominance = max(0.0, min(1.0, dominance))
        self.timestamp = timestamp or time.time()

    def apply_decay(self, decay_rate: float, baseline_vad: Tuple[float, float, float] = (0.5, 0.3, 0.5)) -> 'MoodState':
        """
        应用情绪衰减，使 VAD 值趋向基线。

        Args:
            decay_rate: 衰减速率 (0 到 1 之间的小数)
            baseline_vad: 基线 VAD 值 (valence, arousal, dominance)

        Returns:
            衰减后的新 MoodState 对象
        """
        new_valence = self.valence + (baseline_vad[0] - self.valence) * decay_rate
        new_arousal = self.arousal + (baseline_vad[1] - self.arousal) * decay_rate
        new_dominance = self.dominance + (baseline_vad[2] - self.dominance) * decay_rate

        return MoodState(new_valence, new_arousal, new_dominance)

    def apply_changes(self, changes: Dict[str, float]) -> 'MoodState':
        """
        应用情绪变化量到当前 VAD 值。

        Args:
            changes: 包含 VAD 维度变化量的字典 (e.g., {'valence': -0.1, 'arousal': 0.2})

        Returns:
            应用变化后的新 MoodState 对象
        """
        new_valence = self.valence + changes.get("valence", 0.0)
        new_arousal = self.arousal + changes.get("arousal", 0.0)
        new_dominance = self.dominance + changes.get("dominance", 0.0)

        # 再次确保值在 [0, 1] 范围内
        return MoodState(
            valence=max(0.0, min(1.0, new_valence)),
            arousal=max(0.0, min(1.0, new_arousal)),
            dominance=max(0.0, min(1.0, new_dominance))
        )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "valence": self.valence,
            "arousal": self.arousal,
            "dominance": self.dominance,
            "timestamp": self.timestamp
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MoodState':
        """从字典创建"""
        return cls(
            valence=data.get("valence", 0.5),
            arousal=data.get("arousal", 0.5), # 默认激动度也设为 0.5 (中性)
            dominance=data.get("dominance", 0.5),
            timestamp=data.get("timestamp")
        )

    def __str__(self) -> str:
        """字符串表示"""
        # 可以根据 VAD 值映射到更具体的词语，但暂时只显示 VAD 值
        return f"MoodState(V={self.valence:.2f}, A={self.arousal:.2f}, D={self.dominance:.2f})"


class EmotionManager:
    """情绪管理器，负责管理机器人的情绪状态"""
    
    def __init__(self, config: Dict[str, Any], db_manager: DatabaseManager):
        """
        初始化情绪管理器
        
        Args:
            config: 配置信息
            db_manager: 数据库管理器
        """
        # 从 emotion 配置块获取配置
        self.config = config.get("emotion", {}) # 直接获取 emotion 配置块
        self.db_manager = db_manager
        self.mood_model = MoodModel(self.config) # 传递 emotion 配置块
        self.emotion_rules = EmotionRules() # EmotionRules 目前不依赖配置

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
        # 从配置获取基线 VAD 值
        baseline_vad_config = self.config.get("baseline_vad", [0.5, 0.3, 0.5])
        baseline_vad = tuple(baseline_vad_config) if len(baseline_vad_config) == 3 else (0.5, 0.3, 0.5)

        for user_id, mood in list(self.emotion_cache.items()): # 使用 emotion_cache
            # 应用衰减
            updated_mood = mood.apply_decay(self.decay_rate, baseline_vad) # 传递基线 VAD
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
                emotion_data_str = results[0]["emotion_data"]
                if emotion_data_str:
                     emotion_data = json.loads(emotion_data_str)
                     # 使用 MoodState.from_dict 创建 VAD 状态
                     mood = MoodState.from_dict(emotion_data)
                     self.emotion_cache[user_id] = mood
                     return mood
                else:
                     logger.warning(f"数据库中用户 {user_id} 的 emotion_data 为空。")
            
        except Exception as e:
            logger.error(f"获取用户情绪失败: {e}")
        
        # 如果没有找到，返回默认情绪状态
        # default_emotion = EmotionState() # 使用 MoodState
        default_mood = MoodState()
        self.emotion_cache[user_id] = default_mood
        return default_mood
    
    # 改回异步方法以允许 await save_mood
    async def update_emotion(self, user_id: str, factors: Dict[str, Any], message_text: str = "") -> MoodState:
        """
        根据影响因素和规则更新用户的情绪状态 (VAD)。(异步版本)

        Args:
            user_id: 用户ID。
            factors: 影响情绪的因素字典，应包含 'read_air_analysis'。
            message_text: 用户消息文本。

        Returns:
            更新后的 MoodState 对象。
        """
        # 获取当前情绪 (get_emotion 是异步的)
        current_mood: MoodState = await self.get_emotion(user_id)

        # 1. 计算规则驱动的变化 (apply_rules 是同步的)
        rule_changes = self.emotion_rules.apply_rules(current_mood, message_text, factors)

        # 2. (可选) 计算基础情绪模型变化
        # base_changes = self.mood_model.compute_changes(current_mood, factors, message_text)
        # logger.debug(f"基础情绪模型变化: {base_changes}")
        # 暂时只使用规则驱动的变化，因为 V12 核心是规则
        base_changes = {}

        # 3. 合并变化
        combined_changes = {}
        all_dims = set(rule_changes.keys()) | set(base_changes.keys())
        for dim in all_dims:
            combined_changes[dim] = rule_changes.get(dim, 0.0) + base_changes.get(dim, 0.0)

        logger.debug(f"用户 {user_id} 的情绪变化: {combined_changes}")

        # 4. 应用变化到当前情绪状态
        updated_mood = current_mood.apply_changes(combined_changes)
        logger.info(f"用户 {user_id} 情绪更新: {current_mood} -> {updated_mood}")

        # 5. 更新缓存
        self.emotion_cache[user_id] = updated_mood

        # 6. 保存到数据库 (异步)
        await self.save_mood(user_id, updated_mood)

        
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
        """初始化数据库表 (已弃用)"""
        # 表创建逻辑已移至 DatabaseManager 的 connect 方法中
        logger.debug("EmotionManager.initialize_tables 已弃用，表创建由 DatabaseManager 处理。")
        pass