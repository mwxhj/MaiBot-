#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
意愿检查器模块 (Willingness Checker)
在生成内心想法后，决定是否适合将其表达出来。
"""

import json
from typing import Any, Dict, List, Optional

from linjing.processors.base_processor import BaseProcessor
from linjing.processors.message_context import MessageContext
from linjing.processors.processor_registry import ProcessorRegistry
from linjing.utils.logger import get_logger
from linjing.adapters.message_types import MessageSegment # 导入 MessageSegment 用于检查 @

# 获取日志记录器
logger = get_logger(__name__)

@ProcessorRegistry.register()
class WillingnessChecker(BaseProcessor):
    """
    意愿检查器，判断是否适合表达生成的内心想法。
    相当于对机器人自己进行一次“读空气”。
    """

    name = "willingness_checker"
    description = "意愿检查器，判断是否适合表达内心想法"
    version = "1.0.0"

    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        """
        初始化意愿检查器
        """
        super().__init__(name=name, config=config)
        self.llm_manager = None
        self.personality = None
        # 从配置加载 Prompt 模板
        # 注意：这里假设 config 字典包含了加载后的 prompts 数据
        self.prompt_template = config.get("prompts", {}).get(self.name, {}).get("check_prompt", "")
        if not self.prompt_template:
             logger.error(f"未能从配置中加载 {self.name} check_prompt 模板！")
             self.prompt_template = "错误：缺少 {self.name} Prompt 模板。"
        # 是否在被 @ 时跳过检查的配置
        self.skip_on_mention = self.config.get("skip_on_mention", True)
        # 默认意愿（如果 LLM 调用失败或解析失败）
        self.default_willingness = self.config.get("default_willingness", True)
        # 获取机器人QQ号用于判断 @
        self.bot_qq = str(config.get("bot", {}).get("qq", "unknown")) # 从 bot 配置块获取 QQ

    def set_llm_manager(self, llm_manager: Any) -> None:
        self.llm_manager = llm_manager

    def set_personality(self, personality: Any) -> None:
        self.personality = personality

    async def process(self, context: MessageContext) -> MessageContext:
        """
        处理消息上下文，判断表达意愿
        """
        if not self.llm_manager:
            logger.warning("LLM管理器未设置，跳过意愿检查")
            context.set_state("is_willing_to_reply", self.default_willingness)
            return context

        thought = context.get_state("thought")
        if not thought:
            logger.debug("未找到思考结果，跳过意愿检查")
            context.set_state("is_willing_to_reply", self.default_willingness) # 没有思考，默认愿意（或根据需要调整）
            return context

        # 检查是否被直接 @
        is_mentioned = False
        if self.skip_on_mention and hasattr(context.message, 'segments'):
            if self.bot_qq == "unknown":
                 logger.warning("未在配置中找到 bot.qq，无法准确判断 @ 提及。")
            else:
                 for segment in context.message.segments:
                     if segment.type == "at" and str(segment.data.get("qq")) == self.bot_qq:
                         is_mentioned = True
                         logger.info(f"检测到机器人被提及 (QQ: {self.bot_qq})。")
                         break
        
        if is_mentioned:
            logger.info("机器人被直接提及，跳过意愿检查。")
            context.set_state("is_willing_to_reply", True)
            return context

        # 获取所需上下文信息
        emotion_text = self._format_emotion(context)
        air_analysis = self._format_air_analysis(context)
        personality_text = self._format_personality()
        history_text = self._format_history(context) # 获取历史记录

        # 构建 Prompt
        prompt = self._build_check_prompt(
            thought=thought,
            emotion_text=emotion_text,
            air_analysis=air_analysis,
            personality_text=personality_text,
            history_text=history_text # 传递历史记录
        )

        if "错误：" in prompt: # 检查构建 prompt 是否出错
             logger.error("构建意愿检查 Prompt 失败，使用默认意愿。")
             context.set_state("is_willing_to_reply", self.default_willingness)
             return context

        # 调用 LLM 进行判断
        try:
            logger.debug(f"意愿检查 Prompt (发送给 LLM):\n--- PROMPT START ---\n{prompt}\n--- PROMPT END ---") # 记录 Prompt
            response, metadata = await self.llm_manager.generate_text(
                prompt,
                max_tokens=100, # 判断意愿通常不需要很长回复
                task="willingness_check" # 定义新的任务类型
            )
            
            # 解析 LLM 响应 (期望返回 "true" 或 "false" 字符串)
            decision_str = response.strip().lower()
            # 增加对肯定/否定词的判断，提高鲁棒性
            is_willing = decision_str == "true" or decision_str in ["是", "愿意", "可以", "适合"] 
            logger.debug(f"意愿检查 LLM 响应: '{decision_str}', 解析结果: {is_willing}")
            context.set_state("is_willing_to_reply", is_willing)

        except Exception as e:
            logger.error(f"意愿检查 LLM 调用失败: {e}", exc_info=True)
            context.set_state("is_willing_to_reply", self.default_willingness) # 出错时使用默认值

        return context

    def _build_check_prompt(self, thought: str, emotion_text: str, air_analysis: str, personality_text: str, history_text: str) -> str:
        """构建意愿检查提示词"""
        try:
            # 确保从 self.config 获取最新的 prompts 数据
            current_prompts = self.config.get("prompts", {})
            self.prompt_template = current_prompts.get(self.name, {}).get("check_prompt", self.prompt_template)

            if not self.prompt_template or "错误：" in self.prompt_template:
                 logger.error(f"WillingnessChecker Prompt 模板无效或未加载，无法构建 Prompt。")
                 return f"错误：{self.name} Prompt 模板无效。"

            # 获取角色名
            character_name = getattr(self.personality, 'name', '林静') if self.personality else '林静'

            prompt = self.prompt_template.format(
                character_name=character_name,
                thought=thought,
                emotion=emotion_text,
                air_analysis=air_analysis,
                personality=personality_text,
                history=history_text # 添加历史记录到格式化
            )
            return prompt
        except KeyError as e:
             logger.error(f"构建 {self.name} Prompt 时缺少占位符: {e}。模板: {self.prompt_template}")
             return f"错误：构建 Prompt 失败，缺少占位符 {e}。"
        except Exception as e:
             logger.error(f"构建 {self.name} Prompt 时发生未知错误: {e}", exc_info=True)
             return "错误：构建 Prompt 时发生未知错误。"

    # 复用 ThoughtGenerator 中的格式化方法 (或者将它们移到 utils)
    def _format_history(self, context: MessageContext) -> str:
        # (与 ThoughtGenerator._format_history 类似，需要访问 context.history)
        history_text = ""
        max_history = self.config.get("max_history_for_willingness", 3) # 可以配置不同的历史长度
        recent_history = context.history[-max_history:] if context.history else []
        for msg in recent_history:
            # 尝试获取角色，如果失败则默认为 "未知"
            role = "用户" if getattr(msg, 'get_meta', lambda k, d: d)("is_user", False) else "我"
            # 尝试提取文本，如果失败则使用字符串表示
            try:
                 content = msg.extract_plain_text()
            except AttributeError:
                 content = str(msg)
            history_text += f"{role}: {content}\n"
        return history_text.strip() or "无相关历史对话"

    def _format_emotion(self, context: MessageContext) -> str:
        # (与 ThoughtGenerator._format_emotion 类似)
        emotion_dict = context.get_state("emotion")
        if not emotion_dict or not isinstance(emotion_dict, dict):
            return "情绪平静"
        emotion_text = ""
        dimensions = emotion_dict.get("dimensions")
        if isinstance(dimensions, dict):
            for emotion, intensity in dimensions.items():
                if isinstance(intensity, (int, float)) and intensity > 0.3:
                    emotion_text += f"{emotion}: {intensity:.2f}, "
        return emotion_text.strip(", ") or "情绪平静"

    def _format_air_analysis(self, context: MessageContext) -> str:
         # (与 ThoughtGenerator._format_air_analysis 类似，但可能需要简化)
         analysis = context.get_state("read_air_analysis")
         if not analysis or not isinstance(analysis, dict):
             return "无对话分析"
         
         # 只提取关键信息用于意愿判断
         intent = analysis.get("intent", {}).get("primary", "未知")
         emotions = analysis.get("emotion", {})
         emotion_summary = ", ".join([f"{k}({v:.1f})" for k, v in emotions.items() if isinstance(v, (int, float)) and v > 0.4]) or "中性"
         expectation = analysis.get("social_context", {}).get("expectation", "未知")
         
         return f"初步分析：意图({intent}), 情感({emotion_summary}), 社交期望({expectation})"


    def _format_personality(self) -> str:
        # (与 ThoughtGenerator._format_personality 类似)
        if not self.personality:
            return "性格平和"
        try:
            if hasattr(self.personality, "to_prompt_format"):
                # 尝试调用简短格式，如果不支持则回退
                try:
                    return self.personality.to_prompt_format(short=True) 
                except TypeError:
                    return self.personality.to_prompt_format()
            traits_text = ""
            if hasattr(self.personality, "traits") and isinstance(self.personality.traits, dict):
                traits_text = ", ".join([f"{k}:{v:.1f}" for k, v in self.personality.traits.items()])
            return traits_text or "性格平和"
        except Exception as e:
            logger.error(f"格式化人格特点失败: {e}", exc_info=True)
            return "性格平和"