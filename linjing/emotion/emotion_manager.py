#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
林镜(LingJing) - 情绪管理器
"""

import asyncio
import json
import os
import time
import random
import math
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Union, Tuple

from ..utils.logger import get_logger
from ..models.message_models import Message
from ..exceptions import EmotionError

# 单例实例
_emotion_manager_instance = None

class EmotionManager:
    """
    情绪管理器，负责管理机器人的情感状态
    
    这个组件管理机器人的情绪状态，跟踪情绪变化，
    并根据外部事件和内部状态动态调整情绪。
    """
    
    def __init__(self):
        """初始化情绪管理器"""
        self.logger = get_logger('linjing.emotion.emotion_manager')
        self.config = None
        self.storage_path = None
        self.llm_interface = None
        
        # 情绪变量
        self.current_emotion = {
            "emotion": "neutral",  # 当前主导情绪
            "intensity": 0.5,      # 情绪强度 (0-1)
            "last_updated": datetime.now(),
            "duration": 0.0        # 当前情绪持续时间（分钟）
        }
        
        # 基础情绪及其强度
        self.emotion_values = {
            "joy": 0.0,           # 喜悦
            "sadness": 0.0,       # 悲伤
            "anger": 0.0,         # 愤怒
            "fear": 0.0,          # 恐惧
            "surprise": 0.0,      # 惊讶
            "disgust": 0.0,       # 厌恶
            "trust": 0.0,         # 信任
            "anticipation": 0.0,  # 期待
            "neutral": 0.5        # 中性（初始状态）
        }
        
        # 情绪配置
        self.emotion_decay_rate = 0.1      # 情绪衰减率
        self.update_interval = 60          # 情绪更新间隔（秒）
        self.emotion_memory_limit = 20     # 情绪事件记忆上限
        self.emotional_stability = 0.7     # 情绪稳定性 (0-1)
        self.auto_regulation = True        # 是否自动调节情绪
        
        # 情绪历史记录
        self.emotion_history = []
        
        # 情绪事件记录
        self.emotion_events = []
        
        # 情绪变化锁（防止并发更新）
        self.emotion_lock = asyncio.Lock()
    
    async def initialize(self) -> None:
        """初始化情绪管理器"""
        self.logger.info("初始化情绪管理器...")
        
        # 导入配置
        from ..config import async_get_config
        self.config = await async_get_config()
        
        if not self.config:
            self.logger.error("无法获取配置信息")
            return
        
        # 设置存储路径
        emotion_config = self.config.get('emotion', {})
        self.storage_path = emotion_config.get('storage_path', 'data/emotions')
        
        # 确保存储目录存在
        os.makedirs(self.storage_path, exist_ok=True)
        
        # 加载情绪配置
        self.emotion_decay_rate = emotion_config.get('decay_rate', 0.1)
        self.update_interval = emotion_config.get('update_interval', 60)
        self.emotion_memory_limit = emotion_config.get('memory_limit', 20)
        self.emotional_stability = emotion_config.get('stability', 0.7)
        self.auto_regulation = emotion_config.get('auto_regulation', True)
        
        # 初始化情绪状态
        initial_emotion = emotion_config.get('initial_emotion', 'neutral')
        initial_intensity = emotion_config.get('initial_intensity', 0.5)
        self.current_emotion = {
            "emotion": initial_emotion,
            "intensity": initial_intensity,
            "last_updated": datetime.now(),
            "duration": 0.0
        }
        self.emotion_values[initial_emotion] = initial_intensity
        
        # 启动情绪衰减任务
        if self.auto_regulation:
            asyncio.create_task(self._run_emotion_decay())
        
        # 导入LLM接口
        from ..llm.llm_interface import get_llm_interface
        self.llm_interface = await get_llm_interface()
        
        self.logger.info(f"情绪管理器初始化完成，初始情绪: {initial_emotion}, 强度: {initial_intensity}")
    
    async def _load_emotion_state(self) -> None:
        """从磁盘加载情绪状态"""
        try:
            state_path = os.path.join(self.storage_path, 'emotion_state.json')
            
            if os.path.exists(state_path):
                with open(state_path, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                
                self.current_emotion = state.get('current_emotion', 'neutral')
                self.emotion_intensity = state.get('intensity', 0.5)
                
                # 转换时间字符串为datetime对象
                start_time_str = state.get('start_time')
                if start_time_str:
                    self.emotion_start_time = datetime.fromisoformat(start_time_str)
                
                # 加载情绪历史
                history = state.get('history', [])
                self.emotion_history = history
                
                self.logger.debug(f"已加载情绪状态: {self.current_emotion}, 强度: {self.emotion_intensity}")
            
        except Exception as e:
            self.logger.error(f"加载情绪状态失败: {e}")
    
    async def _save_emotion_state(self) -> None:
        """保存情绪状态到磁盘"""
        try:
            state_path = os.path.join(self.storage_path, 'emotion_state.json')
            
            state = {
                'current_emotion': self.current_emotion,
                'intensity': self.emotion_intensity,
                'start_time': self.emotion_start_time.isoformat() if self.emotion_start_time else None,
                'updated_at': datetime.now().isoformat(),
                'history': self.emotion_history
            }
            
            with open(state_path, 'w', encoding='utf-8') as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
                
        except Exception as e:
            self.logger.error(f"保存情绪状态失败: {e}")
    
    async def get_current_emotion(self) -> Dict[str, Any]:
        """
        获取当前情绪状态
        
        Returns:
            Dict[str, Any]: 当前情绪状态
        """
        # 更新情绪持续时间
        now = datetime.now()
        duration_seconds = (now - self.current_emotion["last_updated"]).total_seconds()
        self.current_emotion["duration"] = duration_seconds / 60.0  # 转换为分钟
        
        return {
            "emotion": self.current_emotion["emotion"],
            "intensity": self.current_emotion["intensity"],
            "duration": self.current_emotion["duration"],
            "values": self.emotion_values.copy()
        }
    
    async def update_emotion(self, 
                          emotion_type: str, 
                          intensity_change: float, 
                          reason: str = None) -> Dict[str, Any]:
        """
        更新情绪状态
        
        Args:
            emotion_type: 情绪类型
            intensity_change: 情绪强度变化 (-1.0 到 1.0)
            reason: 情绪变化原因
            
        Returns:
            Dict[str, Any]: 更新后的情绪状态
        """
        async with self.emotion_lock:
            # 检查情绪类型是否有效
            if emotion_type not in self.emotion_values:
                self.logger.warning(f"无效的情绪类型: {emotion_type}")
                return await self.get_current_emotion()
            
            # 计算强度变化（受情绪稳定性影响）
            adjusted_change = intensity_change * (1.0 - self.emotional_stability)
            
            # 更新对应情绪值
            current_value = self.emotion_values[emotion_type]
            new_value = max(0.0, min(1.0, current_value + adjusted_change))
            self.emotion_values[emotion_type] = new_value
            
            # 如果是减少中性情绪，则相应增加其他情绪
            if emotion_type != "neutral" and adjusted_change > 0:
                self.emotion_values["neutral"] = max(0.0, self.emotion_values["neutral"] - adjusted_change * 0.5)
            
            # 如果是增加中性情绪，则相应减少其他情绪
            if emotion_type == "neutral" and adjusted_change > 0:
                # 减少所有非中性情绪
                for emotion in self.emotion_values:
                    if emotion != "neutral":
                        self.emotion_values[emotion] = max(0.0, self.emotion_values[emotion] - adjusted_change * 0.2)
            
            # 重新确定主导情绪
            dominant_emotion = max(self.emotion_values.items(), key=lambda x: x[1])
            
            # 记录情绪变化事件
            if reason:
                emotion_event = {
                    "timestamp": datetime.now().isoformat(),
                    "emotion": emotion_type,
                    "change": adjusted_change,
                    "reason": reason
                }
                self.emotion_events.append(emotion_event)
                
                # 限制情绪事件记录数量
                if len(self.emotion_events) > self.emotion_memory_limit:
                    self.emotion_events = self.emotion_events[-self.emotion_memory_limit:]
            
            # 更新当前情绪
            previous_emotion = self.current_emotion["emotion"]
            now = datetime.now()
            
            # 如果主导情绪改变，重置持续时间
            if dominant_emotion[0] != previous_emotion:
                duration = 0.0
                self.logger.info(f"情绪变化: {previous_emotion} -> {dominant_emotion[0]}, 原因: {reason or '未知'}")
            else:
                duration_seconds = (now - self.current_emotion["last_updated"]).total_seconds()
                duration = duration_seconds / 60.0  # 转换为分钟
            
            self.current_emotion = {
                "emotion": dominant_emotion[0],
                "intensity": dominant_emotion[1],
                "last_updated": now,
                "duration": duration
            }
            
            # 记录到情绪历史
            history_entry = {
                "timestamp": now.isoformat(),
                "emotion": self.current_emotion["emotion"],
                "intensity": self.current_emotion["intensity"],
                "reason": reason
            }
            self.emotion_history.append(history_entry)
            
            # 限制情绪历史记录数量
            if len(self.emotion_history) > 100:
                self.emotion_history = self.emotion_history[-100:]
            
            return await self.get_current_emotion()
    
    async def process_message(self, message: Message) -> Optional[Dict[str, Any]]:
        """
        处理消息并更新情绪
        
        Args:
            message: 接收到的消息
            
        Returns:
            Optional[Dict[str, Any]]: 更新后的情绪状态
        """
        # 分析消息情感倾向
        sentiment = await self._analyze_message_sentiment(message)
        
        if not sentiment:
            return None
        
        # 根据情感分析结果更新情绪
        emotion_updates = []
        
        # 提取主要情感和强度
        primary_emotion = sentiment.get("primary_emotion", "neutral")
        intensity = sentiment.get("intensity", 0.5)
        valence = sentiment.get("valence", 0.0)  # 正面/负面程度 (-1.0 到 1.0)
        
        # 计算情绪变化
        if primary_emotion in self.emotion_values:
            change = (intensity * 0.3)  # 根据强度计算变化幅度
            emotion_updates.append((primary_emotion, change))
        
        # 根据情感极性调整相关情绪
        if valence > 0.2:  # 正面情感
            emotion_updates.append(("joy", valence * 0.2))
            emotion_updates.append(("trust", valence * 0.15))
        elif valence < -0.2:  # 负面情感
            emotion_updates.append(("sadness", -valence * 0.2))
            emotion_updates.append(("disgust", -valence * 0.15))
        
        # 应用所有情绪更新
        updated_emotion = None
        for emotion_type, change in emotion_updates:
            updated_emotion = await self.update_emotion(
                emotion_type=emotion_type,
                intensity_change=change,
                reason=f"收到消息: {message.content[:20]}..." if hasattr(message, 'content') else "收到消息"
            )
        
        return updated_emotion
    
    async def _analyze_message_sentiment(self, message: Message) -> Optional[Dict[str, Any]]:
        """
        分析消息的情感倾向
        
        Args:
            message: 接收到的消息
            
        Returns:
            Optional[Dict[str, Any]]: 情感分析结果
        """
        if not hasattr(message, 'content') or not message.content:
            return None
        
        try:
            # 使用LLM分析情感
            system_prompt = """你是一个情感分析专家。
分析给定文本的情感，提供以下信息:
1. 主要情绪 (选择一项): joy, sadness, anger, fear, surprise, disgust, trust, anticipation, neutral
2. 情绪强度 (0.0-1.0)
3. 情感极性 (-1.0 到 1.0，负值表示负面情感，正值表示正面情感)

只返回JSON格式的分析结果，不要有其他文字。格式如下:
{
  "primary_emotion": "emotion_name",
  "intensity": float_value,
  "valence": float_value
}"""

            user_prompt = f"分析以下文本的情感:\n\n{message.content}"
            
            response = await self.llm_interface.chat_completion(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=150
            )
            
            # 解析JSON结果
            try:
                sentiment = json.loads(response)
                return sentiment
            except json.JSONDecodeError:
                # 如果不是有效的JSON，尝试提取JSON部分
                import re
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    try:
                        sentiment = json.loads(json_match.group(0))
                        return sentiment
                    except json.JSONDecodeError:
                        self.logger.error("无法解析情感分析结果JSON")
                        return None
                
                self.logger.error("情感分析返回的不是有效的JSON格式")
                return None
        
        except Exception as e:
            self.logger.error(f"分析消息情感时出错: {e}")
            return None
    
    async def apply_event_impact(self, 
                              event_type: str, 
                              impact_level: float, 
                              description: str = None) -> Dict[str, Any]:
        """
        应用事件对情绪的影响
        
        Args:
            event_type: 事件类型
            impact_level: 影响程度 (-1.0 到 1.0)
            description: 事件描述
            
        Returns:
            Dict[str, Any]: 更新后的情绪状态
        """
        # 不同事件类型的情绪影响映射
        event_emotion_map = {
            "praise": {"joy": 0.8, "trust": 0.6},
            "criticism": {"sadness": 0.4, "anger": 0.3},
            "greeting": {"joy": 0.3, "trust": 0.2},
            "question": {"anticipation": 0.4, "surprise": 0.2},
            "gratitude": {"joy": 0.5, "trust": 0.4},
            "apology": {"trust": 0.3, "sadness": -0.2},
            "joke": {"joy": 0.6, "surprise": 0.3},
            "insult": {"anger": 0.7, "disgust": 0.5},
            "compliment": {"joy": 0.6, "trust": 0.5},
            "confusion": {"fear": 0.3, "surprise": 0.4},
            "agreement": {"trust": 0.4, "joy": 0.3},
            "disagreement": {"anger": 0.3, "disgust": 0.2},
            "request": {"anticipation": 0.3},
            "command": {"anger": 0.2, "surprise": 0.3},
            "threat": {"fear": 0.8, "anger": 0.6},
            "excitement": {"joy": 0.7, "anticipation": 0.6},
            "sadness": {"sadness": 0.7, "fear": 0.3},
        }
        
        # 检查事件类型是否有效
        if event_type not in event_emotion_map:
            self.logger.warning(f"未定义的事件类型: {event_type}，使用中性影响")
            event_emotion_map[event_type] = {"neutral": 0.5}
        
        # 根据事件类型和影响程度更新情绪
        emotion_map = event_emotion_map[event_type]
        updated_emotion = None
        
        for emotion, factor in emotion_map.items():
            # 计算情绪变化（考虑影响程度）
            change = factor * impact_level
            
            updated_emotion = await self.update_emotion(
                emotion_type=emotion,
                intensity_change=change,
                reason=description or f"事件: {event_type}, 影响: {impact_level}"
            )
        
        return updated_emotion
    
    async def get_emotion_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        获取情绪历史记录
        
        Args:
            limit: 历史记录条数限制
            
        Returns:
            List[Dict[str, Any]]: 情绪历史记录
        """
        return self.emotion_history[-limit:]
    
    async def get_emotion_events(self, limit: int = 5) -> List[Dict[str, Any]]:
        """
        获取情绪事件记录
        
        Args:
            limit: 事件记录条数限制
            
        Returns:
            List[Dict[str, Any]]: 情绪事件记录
        """
        return self.emotion_events[-limit:]
    
    async def reset_emotion(self) -> Dict[str, Any]:
        """
        重置情绪状态为默认
        
        Returns:
            Dict[str, Any]: 重置后的情绪状态
        """
        async with self.emotion_lock:
            # 重置所有情绪值
            for emotion in self.emotion_values:
                self.emotion_values[emotion] = 0.0
            
            # 设置默认中性情绪
            self.emotion_values["neutral"] = 0.5
            
            # 更新当前情绪
            self.current_emotion = {
                "emotion": "neutral",
                "intensity": 0.5,
                "last_updated": datetime.now(),
                "duration": 0.0
            }
            
            # 记录重置事件
            history_entry = {
                "timestamp": datetime.now().isoformat(),
                "emotion": "neutral",
                "intensity": 0.5,
                "reason": "情绪重置"
            }
            self.emotion_history.append(history_entry)
            
            self.logger.info("情绪状态已重置为默认")
            
            return await self.get_current_emotion()
    
    async def _run_emotion_decay(self) -> None:
        """运行情绪衰减任务"""
        self.logger.info("启动情绪衰减任务")
        
        while True:
            try:
                await asyncio.sleep(self.update_interval)
                await self._decay_emotions()
            except asyncio.CancelledError:
                self.logger.info("情绪衰减任务已取消")
                break
            except Exception as e:
                self.logger.error(f"情绪衰减任务出错: {e}")
                await asyncio.sleep(5)  # 错误后短暂休眠
    
    async def _decay_emotions(self) -> None:
        """衰减情绪强度"""
        async with self.emotion_lock:
            # 检查当前情绪持续时间
            now = datetime.now()
            duration_minutes = (now - self.current_emotion["last_updated"]).total_seconds() / 60.0
            
            # 计算衰减因子（随持续时间增加而增加）
            base_decay = self.emotion_decay_rate
            duration_factor = min(1.0, duration_minutes / 60.0)  # 1小时后达到最大衰减
            decay_factor = base_decay * (1.0 + duration_factor)
            
            # 对所有非中性情绪进行衰减
            for emotion in self.emotion_values:
                if emotion != "neutral":
                    # 计算本次衰减量
                    decay_amount = self.emotion_values[emotion] * decay_factor
                    # 应用衰减
                    self.emotion_values[emotion] = max(0.0, self.emotion_values[emotion] - decay_amount)
            
            # 相应地增加中性情绪
            neutral_increase = decay_factor * 0.2
            self.emotion_values["neutral"] = min(1.0, self.emotion_values["neutral"] + neutral_increase)
            
            # 重新确定主导情绪
            dominant_emotion = max(self.emotion_values.items(), key=lambda x: x[1])
            
            # 如果主导情绪发生变化，更新情绪状态
            if dominant_emotion[0] != self.current_emotion["emotion"]:
                self.logger.debug(f"情绪自然变化: {self.current_emotion['emotion']} -> {dominant_emotion[0]}")
                
                self.current_emotion = {
                    "emotion": dominant_emotion[0],
                    "intensity": dominant_emotion[1],
                    "last_updated": now,
                    "duration": 0.0
                }
                
                # 记录到情绪历史
                history_entry = {
                    "timestamp": now.isoformat(),
                    "emotion": self.current_emotion["emotion"],
                    "intensity": self.current_emotion["intensity"],
                    "reason": "情绪自然衰减"
                }
                self.emotion_history.append(history_entry)

async def get_emotion_manager() -> EmotionManager:
    """
    获取情绪管理器单例实例
    
    Returns:
        EmotionManager: 情绪管理器实例
    """
    global _emotion_manager_instance
    
    if _emotion_manager_instance is None:
        _emotion_manager_instance = EmotionManager()
        await _emotion_manager_instance.initialize()
    
    return _emotion_manager_instance 