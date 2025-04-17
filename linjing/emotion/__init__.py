"""
情绪系统模块

该模块负责管理机器人的情绪状态，包括情绪变化、情绪影响因素和情绪对回复的影响。
"""

from .emotion_manager import EmotionManager, EmotionState
from .mood_model import MoodModel
from .emotion_rules import EmotionRules

__all__ = [
    'EmotionManager',
    'EmotionState',
    'MoodModel',
    'EmotionRules'
] 