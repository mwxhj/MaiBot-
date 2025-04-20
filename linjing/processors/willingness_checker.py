#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
意愿检查器模块 (Willingness Checker)
在生成内心想法后，决定是否适合将其表达出来。
"""

# import json # 在此文件中未使用
from typing import Any, Dict, Optional # <--- 移除未使用的 List

from linjing.processors.base_processor import BaseProcessor
from linjing.processors.message_context import MessageContext
from linjing.processors.processor_registry import ProcessorRegistry
from linjing.utils.logger import get_logger
# from linjing import ConfigManager # ConfigManager 在此文件未使用
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
        self.personality = None # 预期由 LinjingBot 设置 (当前未实现)
        # 从传入的配置中获取 willingness_checker 处理器的 prompt 模板
        # 预期 config 结构: {"prompts": {"willingness_checker": {"check_prompt": "..."}}}
        self.prompt_template = self.config.get("prompts", {}).get(self.name, {}).get("check_prompt", "") # 使用 self.name 获取对应配置
        if not self.prompt_template:
             logger.error(f"未能从配置中加载 {self.name} check_prompt 模板！")
             self.prompt_template = "错误：缺少 {self.name} Prompt 模板。"
        # 是否在被 @ 时跳过检查的配置
        self.skip_on_mention = self.config.get("skip_on_mention", True)
        # 默认意愿（如果 LLM 调用失败或解析失败）
        self.default_willingness = self.config.get("default_willingness", True)
        # 获取机器人QQ号用于判断 @ (从处理器配置获取，需要确保配置中存在)
        # TODO: 考虑更健壮的方式获取 bot_qq，例如从全局配置或 Bot 实例
        self.bot_qq = str(self.config.get("bot_qq", "unknown")) # 尝试从处理器自身配置获取
        if self.bot_qq == "unknown":
             logger.warning(f"未能从 {self.name} 配置中获取 'bot_qq'，@提及检查可能不准确。")

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

        # --- 检查是否需要跳过意愿检查 ---
        # 1. 如果配置了 skip_on_mention 且机器人被直接 @
        is_mentioned = False
        if self.skip_on_mention and self.bot_qq != "unknown" and hasattr(context.message, 'segments'):
             for segment in context.message.segments:
                 # 检查消息段是否是 at 类型，并且 at 的 QQ 号是机器人自己
                 if segment.type == "at" and str(segment.data.get("qq")) == self.bot_qq:
                     is_mentioned = True
                     logger.info(f"检测到机器人被提及 (QQ: {self.bot_qq})。")
                     break
        
        if is_mentioned:
            logger.info("机器人被直接提及，跳过意愿检查。")
            context.set_state("is_willing_to_reply", True)
            return context

        # --- 获取构建 Prompt 所需的信息 ---
        # 格式化当前情绪状态
        emotion_text = self._format_emotion(context)
        # 格式化 ReadAir 分析结果 (简化版)
        air_analysis = self._format_air_analysis(context)
        # 获取人格原则文本 (依赖于 LinjingBot 正确加载并传递)
        # TODO: 修复 LinjingBot 中的配置加载逻辑
        personality_text = self.config.get("personality_text", "错误：人格原则文本未加载！")
        # 格式化近期对话历史
        history_text = self._format_history(context)

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
                max_tokens=self.config.get("llm_max_tokens", 100), # 从配置读取 token 限制
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

            # 使用 .format 填充模板占位符
            # 注意：确保模板中的占位符名称与这里的关键字参数完全匹配
            # Prompt 模板需要: {character_name}, {current_mind_info}, {mood_prompt}, {air_analysis}, {personality_text}, {history_text}, {relation_prompt_all}
            prompt = self.prompt_template.format(
                character_name=character_name,
                current_mind_info=thought,         # 对应 {current_mind_info}
                mood_prompt=emotion_text,         # 对应 {mood_prompt}
                air_analysis=air_analysis,         # 对应 {air_analysis}
                personality_text=personality_text, # 对应 {personality_text}
                history_text=history_text,         # 对应 {history_text}
                relation_prompt_all=""             # 对应 {relation_prompt_all} (TODO: 实现关系获取)
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
            # 获取角色 ("用户" 或 "我")
            is_user = msg.get_meta("is_user", False) # 使用 get_meta 获取元信息
            role = "用户" if is_user else f"我 ({self.name})" # 使用 self.name
            # 获取消息文本
            try:
                 content = msg.extract_plain_text()
            except AttributeError:
                 content = str(msg)
            history_text += f"{role}: {content}\n"
        return history_text.strip() or "无相关历史对话"

    # TODO: 考虑将此方法与 ThoughtGenerator 中的版本统一到工具类
    def _format_emotion(self, context: MessageContext) -> str:
        """格式化情绪状态，与 ThoughtGenerator._format_emotion 类似"""
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

    # TODO: 考虑将此方法与 ThoughtGenerator 中的版本统一到工具类，或确保差异是故意的
    def _format_air_analysis(self, context: MessageContext) -> str:
         """格式化 ReadAir 分析结果 (简化版)，与 ThoughtGenerator._format_air_analysis 不同"""
         analysis = context.get_state("read_air_analysis")
         if not analysis or not isinstance(analysis, dict):
             return "无对话分析"
         
         # 只提取关键信息用于意愿判断
         intent = analysis.get("intent", {}).get("primary", "未知")
         emotions = analysis.get("emotion", {})
         emotion_summary = ", ".join([f"{k}({v:.1f})" for k, v in emotions.items() if isinstance(v, (int, float)) and v > 0.4]) or "中性"
         expectation = analysis.get("social_context", {}).get("expectation", "未知")
         
         return f"初步分析：意图({intent}), 情感({emotion_summary}), 社交期望({expectation})"


    # 移除此方法，因为 personality_text 应从配置获取
    # def _format_personality(self) -> str:
    #     # ... (代码已移除) ...