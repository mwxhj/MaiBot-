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
    相当于对机器人自己进行一次"读空气"。
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
        self.memory_manager = None
        self.personality = None # 预期由 LinjingBot 设置 (当前未实现)
        
        # 改进：从配置中获取 willingness_checker 处理器的 prompt 模板
        prompts_config = self.config.get("prompts", {})
        self.prompt_template = ""
        
        if prompts_config:
            # 尝试获取意愿检查提示词模板
            self.prompt_template = prompts_config.get("check_prompt", "")
            if self.prompt_template:
                logger.debug(f"{self.name} 成功加载 check_prompt 模板 (长度: {len(self.prompt_template)})")
            else:
                logger.error(f"{self.name} 无法从配置中找到 check_prompt 模板!")
        
        if not self.prompt_template:
             logger.error(f"未能从配置 {self.name} 中加载 prompts.check_prompt 模板！")
             self.prompt_template = f"错误：缺少 {self.name} Prompt 模板。"
         
        # 默认意愿（如果 LLM 调用失败或解析失败）
        self.default_willingness = self.config.get("default_willingness", True)
        # 获取机器人QQ号用于判断 @ (从处理器配置获取，需要确保配置中存在)
        # TODO: 考虑更健壮的方式获取 bot_qq，例如从全局配置或 Bot 实例
        self.bot_qq = str(self.config.get("bot_qq", "unknown")) # 尝试从处理器自身配置获取
        if self.bot_qq == "unknown":
             logger.warning(f"未能从 {self.name} 配置中获取 'bot_qq'，@提及检查可能不准确。")

    def set_llm_manager(self, llm_manager: Any) -> None:
        self.llm_manager = llm_manager

    def set_memory_manager(self, memory_manager: Any) -> None:
        """设置记忆管理器实例"""
        self.memory_manager = memory_manager
        logger.debug(f"{self.name} memory_manager 设置成功。")

    # 移除 set_personality 方法，人格原则文本现在通过 config 注入
    # def set_personality(self, personality: Any) -> None:
    #     self.personality = personality

    async def process(self, context: MessageContext) -> MessageContext:
        """
        检查是否愿意表达内心想法（回复消息）
        当前检查因素：1) 消息文本, 2) 思考过程, 3) 当前情绪, 4) 读空气分析
        
        Args:
            context: 消息上下文
            
        Returns:
            更新后的消息上下文
        """
        # 首先检查必要的依赖是否就绪
        if not self.llm_manager:
            logger.warning(f"{self.name} 没有设置 llm_manager，无法执行意愿检查，默认为愿意回复。")
            context.set_state("is_willing_to_reply", True)
            return context
            
        # 获取已生成的思考结果
        thought = context.get_state("thought")
        if not thought:
            logger.error("未找到思考结果，无法判断回复意愿，默认为愿意回复。")
            context.set_state("is_willing_to_reply", True)
            return context
            
        # 检查是否包含图片 (仅记录信息，不影响判断流程)
        contains_image = context.get_state("contains_image", False)
        if contains_image:
            image_count = len(context.get_state("image_urls", []))
            logger.info(f"检测到图片消息 ({image_count} 张图片)，将进行标准意愿检查。")

        # --- 获取构建 Prompt 所需的信息 ---
        # 格式化当前情绪状态
        emotion_text = self._format_emotion(context)
        # 格式化 ReadAir 分析结果 (简化版)
        air_analysis = self._format_air_analysis(context)
        # 获取人格原则文本 (由 LinjingBot 注入到 self.config)
        personality_text = self.config.get("personality_text", "错误：人格原则文本未在配置中找到！")
        if "错误：" in personality_text:
             logger.error("未能从配置中获取 personality_text！Prompt 将不完整。")
        # 格式化近期对话历史
        history_text = self._format_history(context)

        # 构建 Prompt, 传递 context 参数
        prompt = await self._build_check_prompt(
            thought=thought,
            emotion_text=emotion_text,
            air_analysis=air_analysis,
            personality_text=personality_text,
            history_text=history_text,
            context=context # 传递 context 用于获取关系信息
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
                task=self.name # 使用处理器名称作为任务类型
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

    async def _build_check_prompt(self, thought: str, emotion_text: str, air_analysis: str, personality_text: str, history_text: str, context: Optional[MessageContext] = None) -> str:
        """
        构建意愿检查提示词
        
        Args:
            thought: 思考结果
            emotion_text: 格式化的情绪状态文本
            air_analysis: 格式化的读空气分析文本
            personality_text: 人格原则文本
            history_text: 历史对话文本
            context: 可选的消息上下文，用于获取关系信息
            
        Returns:
            构建好的提示词
        """
        try:
            # 直接使用在 __init__ 中加载好的 self.prompt_template
            if not self.prompt_template or "错误：" in self.prompt_template:
                 logger.error(f"WillingnessChecker Prompt 模板无效或未加载 (来自 __init__)，无法构建 Prompt。")
                 return f"错误：{self.name} Prompt 模板无效。"

            # 获取角色名 (尝试从 global_config 获取)
            global_config = self.config.get("global_config", {})
            character_name = global_config.get("bot", {}).get("name", "林静") # 默认 '林静'
            
            # 获取关系信息
            relation_prompt_all = ""
            if context is not None and hasattr(self, "_format_relationship"):
                try:
                    relation_prompt_all = await self._format_relationship(context)
                    logger.debug(f"为意愿检查获取到关系信息: {relation_prompt_all}")
                except Exception as e:
                    logger.error(f"获取关系信息失败: {e}", exc_info=True)
                    relation_prompt_all = "关系信息获取失败"

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
                relation_prompt_all=relation_prompt_all  # 对应 {relation_prompt_all}
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

        # 从全局配置中获取情绪显著性阈值
        # global_config 是在 LinjingBot._init_processors 中注入的
        global_config = self.config.get("global_config", {})
        significant_threshold = global_config.get("emotion", {}).get("vad_model", {}).get("significant_threshold", 0.3)
        logger.debug(f"使用情绪显著性阈值: {significant_threshold}")

        # 从字典中获取 VAD 维度值
        valence = emotion_dict.get("valence", 0.5)
        arousal = emotion_dict.get("arousal", 0.5)
        dominance = emotion_dict.get("dominance", 0.5)
        baseline_vad = global_config.get("emotion", {}).get("vad_model", {}).get("baseline_vad", [0.5, 0.3, 0.5])
        if len(baseline_vad) != 3: baseline_vad = [0.5, 0.3, 0.5] # 确保基线有效

        # 检查每个维度与基线的偏差是否超过阈值
        significant_emotions = []
        if abs(valence - baseline_vad[0]) > significant_threshold:
            significant_emotions.append(f"Valence={valence:.2f}")
        if abs(arousal - baseline_vad[1]) > significant_threshold:
            significant_emotions.append(f"Arousal={arousal:.2f}")
        if abs(dominance - baseline_vad[2]) > significant_threshold:
            significant_emotions.append(f"Dominance={dominance:.2f}")

        if significant_emotions:
            return ", ".join(significant_emotions)
        else:
            return "情绪平静"

    def _format_air_analysis(self, context: MessageContext) -> str:
         """格式化 ReadAir 分析结果，直接返回JSON字符串"""
         analysis = context.get_state("read_air_analysis")
         if not analysis or not isinstance(analysis, dict):
             return "无对话分析"
         
         try:
             # 直接将分析结果转换为JSON字符串
             import json
             result = json.dumps(analysis, ensure_ascii=False, indent=2)
             return result
         except Exception as e:
             logger.error(f"格式化分析结果为JSON时出错: {str(e)}", exc_info=True)
             return "无效的分析结果"

    # --- 新增：格式化关系信息 ---
    async def _format_relationship(self, context: MessageContext) -> str:
        """
        获取并格式化与用户的关系信息
        
        Args:
            context: 消息上下文
            
        Returns:
            格式化的关系信息字符串
        """
        # 先检查 memory_manager 是否已设置
        if not hasattr(self, "memory_manager") or self.memory_manager is None:
            logger.warning("无法获取关系信息：memory_manager 未设置。")
            return "关系信息：未知（记忆系统未就绪）"
        
        try:
            # 尝试使用 context.user_id 而不是 context.sender_id
            user_id = context.user_id
            if not user_id:
                # 如果 context.user_id 也没有，尝试回退到 message.sender.user_id
                if hasattr(context, 'message') and hasattr(context.message, 'sender') and hasattr(context.message.sender, 'user_id'):
                    user_id = context.message.sender.user_id
                
                if not user_id:
                    logger.warning("无法从 context.user_id 或 context.message.sender.user_id 获取用户 ID。")
                    return "用户ID未知，无法获取关系信息"
            
            logger.debug(f"尝试为用户 {user_id} 获取关系摘要。") # 添加日志确认 user_id
            # 从记忆管理器获取关系摘要
            relation_summary = await self.memory_manager.get_user_relationship_summary(user_id)
            if not relation_summary:
                # 修改日志级别为 debug，因为这不一定是错误
                logger.debug(f"与用户 {user_id} 尚无明确的关系记录。")
                return f"与用户 {user_id} 尚无明确的关系记录。"
            
            # 关系信息格式化
            relation_prompt = f"与用户 {user_id} 的关系信息如下:\n"
            
            # 添加亲密度信息
            closeness = relation_summary.get("亲密度", {})
            if closeness:
                value = closeness.get("value", 0)
                desc = closeness.get("description", "普通关系")
                trend = closeness.get("trend", "稳定")
                relation_prompt += f"- 亲密度: {value}/100 ({desc}, {trend})\n"
            
            # 添加关系描述
            description = relation_summary.get("关系描述", "无特殊关系")
            relation_prompt += f"- 关系描述: {description}\n"
            
            # 添加关键事件
            key_events = relation_summary.get("关键事件", [])
            if key_events:
                relation_prompt += "- 关键事件:\n"
                for event in key_events[:3]:  # 最多显示3个关键事件
                    date = event.get("date", "未知时间")
                    desc = event.get("description", "未记录")
                    relation_prompt += f"  * {date}: {desc}\n"
            
            # 添加记忆标签
            # memory_tags = relation_summary.get("记忆标签", [])
            # if memory_tags:
            #     tags_str = ", ".join(memory_tags[:5])  # 最多显示5个标签
            #     relation_prompt += f"- 记忆标签: {tags_str}\n"
            
            return relation_prompt
        except Exception as e:
            logger.error(f"格式化关系信息时出错: {str(e)}", exc_info=True)
            return "关系信息：获取失败"

    # 移除此方法，因为 personality_text 应从配置获取
    # def _format_personality(self) -> str:
    #     # ... (代码已移除) ...