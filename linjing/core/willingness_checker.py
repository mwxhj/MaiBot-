#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
林镜(LingJing) - 回应意愿检查器
"""

import asyncio
import random
import time
import json
from typing import Dict, Any, List, Optional, Tuple, Union
from datetime import datetime, timedelta

from ..utils.logger import get_logger
from ..models.message_models import Message
from ..models import ChatStream
from ..exceptions import MessageProcessError

class WillingnessChecker:
    """
    回应意愿检查器，负责判断机器人是否愿意回应特定消息
    
    基于情感状态、关系、上下文和规则等因素，决定是否回应以及如何回应消息。
    这个组件处于思维生成和回复生成中间，用于增加机器人的自然性和人格特质。
    """
    
    def __init__(self):
        """初始化回应意愿检查器"""
        self.logger = get_logger('linjing.core.willingness_checker')
        self.config = None
        self.emotion_manager = None
        self.relationship_manager = None
        
        # 基础意愿参数
        self.base_willingness = 0.7  # 基础回应意愿 (0-1)
        self.mood_influence = 0.2    # 心情对意愿的影响程度
        self.personality_weight = 0.3  # 性格对意愿的影响
        
        # 回应倾向
        self.response_bias = {
            "questions": 0.9,       # 问题
            "greetings": 0.8,       # 问候
            "opinions": 0.7,        # 观点
            "statements": 0.5,      # 陈述
            "commands": 0.4,        # 命令
            "irrelevant": 0.3,      # 不相关内容
            "offensive": -0.5       # 攻击性内容
        }
        
        # 特定关键词触发
        self.trigger_keywords = {
            "林镜": 0.9,             # 自己的名字
            "谢谢": 0.8,             # 感谢
            "帮忙": 0.7,             # 请求帮助
            "喜欢": 0.6,             # 喜好表达
            "讨厌": 0.6,             # 厌恶表达
            "为什么": 0.8,            # 疑问
            "怎么样": 0.7,            # 询问意见
            "觉得": 0.6              # 征求看法
        }
        
        # 情绪对应的回应意愿修正
        self.emotion_willingness_modifiers = {
            "joy": 0.2,             # 喜悦增加意愿
            "sadness": -0.2,        # 悲伤降低意愿
            "anger": -0.3,          # 愤怒降低意愿
            "fear": -0.1,           # 恐惧略微降低意愿
            "surprise": 0.1,        # 惊讶略微增加意愿
            "disgust": -0.3,        # 厌恶降低意愿
            "trust": 0.3,           # 信任增加意愿
            "anticipation": 0.2,    # 期待增加意愿
            "neutral": 0            # 中性不影响
        }
        
        # 回应态度配置
        self.attitude_config = {
            "friendly": 0.7,        # 友好态度的基础比例
            "neutral": 0.2,         # 中性态度的基础比例
            "reserved": 0.1,        # 保留态度的基础比例
            "emotion_influence": 0.4 # 情绪对态度的影响程度
        }
        
        # 冷却和限流
        self.last_responses = {}     # 上次回应时间记录
        self.cooldown_periods = {
            "normal": 5,            # 普通消息冷却期（秒）
            "low_priority": 30,     # 低优先级消息冷却期（秒）
            "group": 15             # 群组消息冷却期（秒）
        }
        self.response_quota = {      # 回应配额限制
            "per_user": {
                "limit": 20,        # 每用户配额
                "period": 3600      # 周期（秒）
            },
            "total": {
                "limit": 100,       # 总配额
                "period": 3600      # 周期（秒）
            }
        }
        self.quota_usage = {
            "users": {},            # 用户使用量
            "total": 0,             # 总使用量
            "reset_time": datetime.now() + timedelta(seconds=3600)  # 重置时间
        }
    
    async def initialize(self) -> None:
        """初始化回应意愿检查器"""
        self.logger.info("初始化回应意愿检查器...")
        
        # 导入配置
        from ..config import async_get_config
        self.config = await async_get_config()
        
        if not self.config:
            raise MessageProcessError("无法获取配置信息")
        
        # 加载意愿配置
        willingness_config = self.config.get('willingness', {})
        self.base_willingness = willingness_config.get('base_level', 0.7)
        self.mood_influence = willingness_config.get('mood_influence', 0.2)
        self.personality_weight = willingness_config.get('personality_weight', 0.3)
        
        # 加载回应倾向配置
        response_bias = willingness_config.get('response_bias', {})
        if response_bias:
            self.response_bias.update(response_bias)
        
        # 加载关键词触发配置
        trigger_keywords = willingness_config.get('trigger_keywords', {})
        if trigger_keywords:
            self.trigger_keywords.update(trigger_keywords)
        
        # 加载情绪修正器配置
        emotion_modifiers = willingness_config.get('emotion_modifiers', {})
        if emotion_modifiers:
            self.emotion_willingness_modifiers.update(emotion_modifiers)
        
        # 加载冷却配置
        cooldown = willingness_config.get('cooldown', {})
        if cooldown:
            self.cooldown_periods.update(cooldown)
        
        # 加载配额配置
        quota = willingness_config.get('quota', {})
        if quota and 'per_user' in quota:
            self.response_quota['per_user'].update(quota['per_user'])
        if quota and 'total' in quota:
            self.response_quota['total'].update(quota['total'])
        
        # 重置配额使用情况
        self.quota_usage = {
            "users": {},
            "total": 0,
            "reset_time": datetime.now() + timedelta(seconds=self.response_quota['total']['period'])
        }
        
        # 启动配额重置任务
        asyncio.create_task(self._run_quota_reset())
        
        # 加载情绪管理器
        from ..emotion import get_emotion_manager
        self.emotion_manager = await get_emotion_manager()
        
        # 加载关系管理器
        from ..relationship import get_relationship_manager
        self.relationship_manager = await get_relationship_manager()
        
        self.logger.info(f"回应意愿检查器初始化完成，基础意愿: {self.base_willingness}")
    
    async def check_willingness(self, 
                             message: Message, 
                             thought_content: Dict[str, Any],
                             chat_stream: ChatStream) -> Tuple[bool, Dict[str, Any]]:
        """
        检查是否愿意回应消息
        
        Args:
            message: 接收到的消息
            thought_content: 思维生成的内容
            chat_stream: 聊天流
            
        Returns:
            Tuple[bool, Dict[str, Any]]: (是否愿意回应, 回应态度和原因)
        """
        # 获取消息信息
        sender_id = message.sender.user_id if message.sender else ""
        message_type = message.message_type
        message_content = message.content if hasattr(message, 'content') else ""
        is_group = message_type == "group"
        
        # 计算基础回应意愿
        willingness_score = self.base_willingness
        
        # 检查冷却期
        if not await self._check_cooldown(sender_id, message_type):
            self.logger.debug(f"用户 {sender_id} 处于冷却期，降低回应意愿")
            willingness_score -= 0.3
        
        # 检查配额
        if not await self._check_quota(sender_id):
            self.logger.debug(f"用户 {sender_id} 或总体已达到配额限制，降低回应意愿")
            willingness_score -= 0.4
        
        # 根据消息内容类型调整意愿
        content_type = thought_content.get("intent", {}).get("type", "statements")
        if content_type in self.response_bias:
            willingness_score += self.response_bias[content_type]
            self.logger.debug(f"消息内容类型为 {content_type}，意愿调整为 {willingness_score}")
        
        # 根据关键词检查
        # 将MessageContent对象转换为字符串
        content_text = ""
        if hasattr(message_content, 'raw_content') and message_content.raw_content:
            content_text = message_content.raw_content
        elif hasattr(message_content, 'get_plain_text'):
            content_text = message_content.get_plain_text()
        else:
            content_text = str(message_content)
            
        keyword_bonus = await self._check_keywords(content_text)
        willingness_score += keyword_bonus
        
        # 根据情绪状态调整意愿
        emotion_modifier = await self._get_emotion_modifier()
        willingness_score += emotion_modifier
        
        # 根据关系调整意愿
        relationship_modifier = await self._get_relationship_modifier(sender_id)
        willingness_score += relationship_modifier
        
        # 对群聊和私聊消息区别对待
        if is_group:
            # 群聊回应意愿默认降低
            willingness_score -= 0.1
            
            # 检查是否@自己或者回复自己
            at_self = message.is_at_me if hasattr(message, 'is_at_me') else False
            reply_to_self = (hasattr(message, 'reply') and message.reply and 
                             hasattr(message.reply, 'sender') and 
                             message.reply.sender.is_self)
            
            if at_self or reply_to_self:
                # 如果@自己或回复自己，大幅提高回应意愿
                willingness_score += 0.5
                self.logger.debug(f"消息@或回复自己，意愿大幅提高: {willingness_score}")
        else:
            # 私聊默认提高回应意愿
            willingness_score += 0.1
        
        # 考虑聊天活跃度
        activity_modifier = await self._evaluate_chat_activity(chat_stream)
        willingness_score += activity_modifier
        
        # 随机波动（增加一点随机性）
        random_factor = random.uniform(-0.05, 0.05)
        willingness_score += random_factor
        
        # 确保意愿分数在合理范围内
        willingness_score = max(0.0, min(1.0, willingness_score))
        
        # 确定是否回应
        will_respond = False
        response_threshold = 0.5  # 基础回应阈值
        
        # 特殊情况强制回应
        force_respond = False
        
        # @自己或回复自己时强制回应
        at_self = message.is_at_me if hasattr(message, 'is_at_me') else False
        reply_to_self = (hasattr(message, 'reply') and message.reply and 
                         hasattr(message.reply, 'sender') and 
                         message.reply.sender.is_self)
        
        if at_self or reply_to_self:
            force_respond = True
            self.logger.debug("@自己或回复自己，强制回应")
        
        # 特定意图强制回应（如问题、请求等）
        intent_type = thought_content.get("intent", {}).get("type", "")
        important_intents = ["questions", "requests", "help_seeking", "greeting_to_me"]
        if intent_type in important_intents:
            force_respond = True
            self.logger.debug(f"重要意图 {intent_type}，强制回应")
        
        # 判断最终是否回应
        if force_respond or willingness_score >= response_threshold:
            will_respond = True
            
            # 更新冷却期和配额
            if will_respond:
                await self._update_response_record(sender_id, message_type)
        
        # 确定回应态度
        attitude = await self._determine_attitude(willingness_score, thought_content)
        
        # 构建回应原因
        reason = {
            "score": willingness_score,
            "base_willingness": self.base_willingness,
            "emotion_modifier": emotion_modifier,
            "relationship_modifier": relationship_modifier,
            "keyword_bonus": keyword_bonus,
            "content_type": content_type,
            "is_group": is_group,
            "force_respond": force_respond,
            "random_factor": random_factor,
            "activity_modifier": activity_modifier
        }
        
        self.logger.info(f"意愿检查结果: {'愿意' if will_respond else '不愿意'} 回应, 分数: {willingness_score:.2f}, 态度: {attitude}")
        
        return will_respond, {"attitude": attitude, "reason": reason}
    
    async def _check_keywords(self, content: str) -> float:
        """
        检查消息中是否包含触发关键词
        
        Args:
            content: 消息内容
            
        Returns:
            float: 关键词奖励分数
        """
        if not content:
            return 0.0
        
        bonus = 0.0
        for keyword, value in self.trigger_keywords.items():
            if keyword in content:
                bonus += value
                self.logger.debug(f"检测到关键词 '{keyword}'，奖励 {value}")
                
        # 限制最大奖励
        return min(0.5, bonus)
    
    async def _get_emotion_modifier(self) -> float:
        """
        获取情绪对回应意愿的影响
        
        Returns:
            float: 情绪修正值
        """
        if not self.emotion_manager:
            return 0.0
        
        try:
            # 获取当前情绪状态
            current_emotion = await self.emotion_manager.get_current_emotion()
            emotion_type = current_emotion.get("emotion", "neutral")
            intensity = current_emotion.get("intensity", 0.5)
            
            # 获取情绪对应的修正值
            base_modifier = self.emotion_willingness_modifiers.get(emotion_type, 0.0)
            
            # 根据强度调整修正值
            modifier = base_modifier * intensity
            
            self.logger.debug(f"情绪 {emotion_type} (强度: {intensity}) 对意愿的修正值: {modifier}")
            return modifier
            
        except Exception as e:
            self.logger.error(f"获取情绪修正值时出错: {e}")
            return 0.0
    
    async def _get_relationship_modifier(self, user_id: str) -> float:
        """
        获取与用户关系对回应意愿的影响
        
        Args:
            user_id: 用户ID
            
        Returns:
            float: 关系修正值
        """
        if not self.relationship_manager or not user_id:
            return 0.0
        
        try:
            # 获取与用户的关系
            relationship = await self.relationship_manager.get_relationship("self", user_id)
            
            if not relationship:
                return 0.0
            
            # 获取关系强度和印象
            strength = relationship.calculate_relationship_strength()
            impression = relationship.impressions.get("self", {})
            
            # 基于好感度调整意愿
            likability = impression.get("likability", 0.5)
            familiarity = impression.get("familiarity", 0.5)
            
            # 计算修正值 (好感度影响更大)
            modifier = (likability - 0.5) * 0.3 + (familiarity - 0.5) * 0.2
            
            self.logger.debug(f"与用户 {user_id} 的关系修正值: {modifier} (好感度: {likability}, 熟悉度: {familiarity})")
            return modifier
            
        except Exception as e:
            self.logger.error(f"获取关系修正值时出错: {e}")
            return 0.0
    
    async def _evaluate_chat_activity(self, chat_stream: ChatStream) -> float:
        """
        评估聊天活跃度对回应意愿的影响
        
        Args:
            chat_stream: 聊天流
            
        Returns:
            float: 活跃度修正值
        """
        try:
            # 获取最近消息数量
            recent_count = min(20, len(chat_stream.messages))
            if recent_count == 0:
                return 0.0
            
            # 计算近期自己的回复比例
            self_messages = 0
            for i in range(min(recent_count, len(chat_stream.messages))):
                msg = chat_stream.messages[-(i+1)]  # 从最新消息开始
                if hasattr(msg, 'sender') and msg.sender and msg.sender.is_self:
                    self_messages += 1
            
            # 如果自己最近发言过多，降低回应意愿
            self_ratio = self_messages / recent_count
            
            if self_ratio > 0.5:  # 如果自己发言超过50%
                modifier = -0.2 * (self_ratio - 0.5) * 2  # 将0.5-1.0映射到0.0-(-0.2)
            elif self_ratio < 0.2:  # 如果自己发言不足20%
                modifier = 0.1  # 适当提高回应意愿
            else:
                modifier = 0.0
            
            self.logger.debug(f"聊天活跃度修正值: {modifier} (自己发言比例: {self_ratio:.2f})")
            return modifier
            
        except Exception as e:
            self.logger.error(f"评估聊天活跃度时出错: {e}")
            return 0.0
    
    async def _determine_attitude(self, willingness_score: float, thought_content: Dict[str, Any]) -> str:
        """
        基于意愿分数和思维内容确定回应态度
        
        Args:
            willingness_score: 意愿分数
            thought_content: 思维内容
            
        Returns:
            str: 回应态度
        """
        # 获取当前情绪
        current_emotion = {"emotion": "neutral", "intensity": 0.5}
        if self.emotion_manager:
            try:
                current_emotion = await self.emotion_manager.get_current_emotion()
            except Exception as e:
                self.logger.error(f"获取当前情绪时出错: {e}")
        
        # 从思维内容获取情感反应
        emotional_response = thought_content.get("emotional_response", {})
        emotional_type = emotional_response.get("type", current_emotion.get("emotion", "neutral"))
        emotional_intensity = emotional_response.get("intensity", current_emotion.get("intensity", 0.5))
        
        # 基础态度分布
        attitude_weights = {
            "friendly": self.attitude_config["friendly"],
            "neutral": self.attitude_config["neutral"],
            "reserved": self.attitude_config["reserved"]
        }
        
        # 根据意愿分数调整态度
        if willingness_score > 0.8:
            # 高意愿，提高友好态度概率
            attitude_weights["friendly"] += 0.2
            attitude_weights["neutral"] -= 0.1
            attitude_weights["reserved"] -= 0.1
        elif willingness_score < 0.6:
            # 低意愿，提高保留态度概率
            attitude_weights["friendly"] -= 0.2
            attitude_weights["neutral"] -= 0.1
            attitude_weights["reserved"] += 0.3
        
        # 根据情绪类型调整态度
        emotion_influence = self.attitude_config["emotion_influence"]
        
        # 特定情绪对态度的影响
        emotion_attitude_map = {
            "joy": {"friendly": 0.3, "neutral": -0.1, "reserved": -0.2},
            "sadness": {"friendly": -0.2, "neutral": 0.0, "reserved": 0.2},
            "anger": {"friendly": -0.3, "neutral": -0.1, "reserved": 0.4},
            "fear": {"friendly": -0.2, "neutral": 0.0, "reserved": 0.2},
            "surprise": {"friendly": 0.1, "neutral": 0.0, "reserved": -0.1},
            "disgust": {"friendly": -0.3, "neutral": -0.1, "reserved": 0.4},
            "trust": {"friendly": 0.3, "neutral": 0.0, "reserved": -0.3},
            "anticipation": {"friendly": 0.2, "neutral": 0.0, "reserved": -0.2},
            "neutral": {"friendly": 0.0, "neutral": 0.1, "reserved": -0.1}
        }
        
        # 应用情绪影响
        if emotional_type in emotion_attitude_map:
            for attitude, modifier in emotion_attitude_map[emotional_type].items():
                attitude_weights[attitude] += modifier * emotional_intensity * emotion_influence
        
        # 确保权重为正并标准化
        total_weight = 0.0
        for attitude in attitude_weights:
            attitude_weights[attitude] = max(0.01, attitude_weights[attitude])  # 确保至少有0.01的概率
            total_weight += attitude_weights[attitude]
        
        for attitude in attitude_weights:
            attitude_weights[attitude] /= total_weight
        
        # 随机选择态度，基于权重
        attitudes = list(attitude_weights.keys())
        weights = [attitude_weights[a] for a in attitudes]
        
        selected_attitude = random.choices(attitudes, weights=weights, k=1)[0]
        
        self.logger.debug(f"选择的回应态度: {selected_attitude}, 权重: {attitude_weights}")
        return selected_attitude
    
    async def _check_cooldown(self, user_id: str, message_type: str) -> bool:
        """
        检查用户是否处于冷却期
        
        Args:
            user_id: 用户ID
            message_type: 消息类型
            
        Returns:
            bool: 是否通过冷却检查
        """
        now = time.time()
        
        # 获取冷却期时长
        cooldown_time = self.cooldown_periods.get("normal", 5)
        if message_type == "group":
            cooldown_time = self.cooldown_periods.get("group", 15)
        
        # 检查用户的上次回应时间
        if user_id in self.last_responses:
            last_time = self.last_responses[user_id]
            if now - last_time < cooldown_time:
                return False
        
        return True
    
    async def _check_quota(self, user_id: str) -> bool:
        """
        检查用户配额是否超限
        
        Args:
            user_id: 用户ID
            
        Returns:
            bool: 是否通过配额检查
        """
        # 检查是否需要重置配额
        now = datetime.now()
        if now > self.quota_usage["reset_time"]:
            self.quota_usage = {
                "users": {},
                "total": 0,
                "reset_time": now + timedelta(seconds=self.response_quota["total"]["period"])
            }
            return True
        
        # 检查总配额
        if self.quota_usage["total"] >= self.response_quota["total"]["limit"]:
            return False
        
        # 检查用户配额
        user_usage = self.quota_usage["users"].get(user_id, 0)
        if user_usage >= self.response_quota["per_user"]["limit"]:
            return False
        
        return True
    
    async def _update_response_record(self, user_id: str, message_type: str) -> None:
        """
        更新回应记录
        
        Args:
            user_id: 用户ID
            message_type: 消息类型
        """
        # 更新上次回应时间
        self.last_responses[user_id] = time.time()
        
        # 更新配额使用情况
        self.quota_usage["total"] += 1
        self.quota_usage["users"][user_id] = self.quota_usage["users"].get(user_id, 0) + 1
    
    async def _run_quota_reset(self) -> None:
        """运行配额重置任务"""
        self.logger.info("启动配额重置任务")
        
        while True:
            try:
                # 计算到下次重置时间的秒数
                now = datetime.now()
                if now < self.quota_usage["reset_time"]:
                    seconds_to_sleep = (self.quota_usage["reset_time"] - now).total_seconds()
                    await asyncio.sleep(seconds_to_sleep)
                
                # 重置配额
                reset_period = self.response_quota["total"]["period"]
                self.quota_usage = {
                    "users": {},
                    "total": 0,
                    "reset_time": datetime.now() + timedelta(seconds=reset_period)
                }
                self.logger.info(f"已重置回应配额，下次重置时间: {self.quota_usage['reset_time']}")
                
            except asyncio.CancelledError:
                self.logger.info("配额重置任务已取消")
                break
            except Exception as e:
                self.logger.error(f"配额重置任务出错: {e}")
                await asyncio.sleep(60)  # 错误后等待一分钟再尝试

# 单例实例
_willingness_checker = None

async def get_willingness_checker() -> WillingnessChecker:
    """
    获取回应意愿检查器单例实例
    
    Returns:
        WillingnessChecker: 回应意愿检查器实例
    """
    global _willingness_checker
    
    if _willingness_checker is None:
        _willingness_checker = WillingnessChecker()
        await _willingness_checker.initialize()
    
    return _willingness_checker