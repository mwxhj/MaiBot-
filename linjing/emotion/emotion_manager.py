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
        # 传递 emotion 配置块给 EmotionRules
        self.emotion_rules = EmotionRules(self.config)

        # 情绪衰减配置 (从 vad_model 配置块读取)
        vad_config = self.config.get("vad_model", {})
        self.decay_rate = vad_config.get("decay_rate", 0.05)
        self.decay_interval = self.config.get("update_interval", 3600)  # 使用顶层的 update_interval
        self.baseline_vad = tuple(vad_config.get("baseline_vad", [0.5, 0.3, 0.5])) # 读取基线 VAD
        if len(self.baseline_vad) != 3:
             logger.warning(f"配置中的 baseline_vad 格式无效，使用默认值 [0.5, 0.3, 0.5]: {self.baseline_vad}")
             self.baseline_vad = (0.5, 0.3, 0.5)

        # 加载情绪描述配置
        self.mood_description_config = self.config.get("mood_description", {})
        
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
        # 使用从 __init__ 加载的 self.baseline_vad 和 self.decay_rate
        for user_id, mood in list(self.emotion_cache.items()): # 使用 emotion_cache
            # 应用衰减
            updated_mood = mood.apply_decay(self.decay_rate, self.baseline_vad) # 传递基线 VAD
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
    
    def _get_vad_description(self, value: float, mapping_key: str) -> str:
        """根据 VAD 值和配置的映射规则获取描述词"""
        mapping = self.mood_description_config.get(mapping_key, [])
        if not mapping:
            return "" # 如果没有配置映射，返回空

        # 映射规则通常按阈值降序排列
        for rule in mapping:
            threshold = rule.get("threshold")
            word = rule.get("word")
            if isinstance(threshold, (int, float)) and word and value >= threshold:
                return word
        return "" # 如果没有匹配的规则

    def mood_to_text(self, mood: MoodState) -> str:
        """
        将 VAD 情绪状态转换为文本描述 (基于配置)。

        Args:
            mood: MoodState 对象。

        Returns:
            情绪的文本描述，例如 "有点愉悦且非常激动"。
        """
        valence_desc = self._get_vad_description(mood.valence, "valence_map")
        arousal_desc = self._get_vad_description(mood.arousal, "arousal_map")
        dominance_desc = self._get_vad_description(mood.dominance, "dominance_map")

        # 组合描述，可以根据需要调整逻辑
        parts = [desc for desc in [valence_desc, arousal_desc, dominance_desc] if desc and desc not in ["平静", "中立"]]

        if not parts:
            return "平静" # 如果所有维度都接近中性

        return "且".join(parts) # 例如 "有点不悦且非常冷静且有点顺从"
    
    async def initialize_tables(self) -> None:
        """初始化数据库表 (已弃用)"""
        # 表创建逻辑已移至 DatabaseManager 的 connect 方法中
        logger.debug("EmotionManager.initialize_tables 已弃用，表创建由 DatabaseManager 处理。")
        pass