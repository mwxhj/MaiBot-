"""
情绪系统模块

该模块负责管理机器人的情绪状态，包括情绪变化、情绪影响因素和情绪对回复的影响。
"""

from .emotion_manager import EmotionManager # 只导入 EmotionManager
from .mood_model import MoodModel, MoodState # 从 mood_model 导入 MoodState
from .emotion_rules import EmotionRules

__all__ = [
    'EmotionManager',
    # 'EmotionState', # 移除不存在的类
    'MoodState', # 导出实际使用的 MoodState
    'MoodModel',
    'EmotionRules'
] 