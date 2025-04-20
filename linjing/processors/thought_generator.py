#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
思考生成器模块，用于生成机器人的内部思考过程。
包括对用户消息的理解、知识检索、思考逻辑和情绪反应等。
"""

from typing import Any, Dict, List, Optional # <--- 移除未使用的 Tuple, Union

from linjing.processors.base_processor import BaseProcessor
from linjing.processors.message_context import MessageContext
from linjing.processors.processor_registry import ProcessorRegistry
from linjing.utils.logger import get_logger

# 获取日志记录器
logger = get_logger(__name__)


@ProcessorRegistry.register()
class ThoughtGenerator(BaseProcessor):
    """
    思考生成器，生成机器人的内部思考过程。
    基于用户消息、历史对话、记忆和情感状态生成内部思考。
    """
    
    name = "thought_generator"
    description = "思考生成器，生成机器人的内部思考过程"
    version = "1.0.0"
    
    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None): # 添加 name 参数
        """
        初始化思考生成器
        
        Args:
            name: 处理器名称
            config: 处理器配置
        """
        # 调用父类 __init__ 时传递 name 和 config
        super().__init__(name=name, config=config)
        
        # **修改：从处理器特定配置读取 thinking_depth**
        # 注意：self.config 是传递给处理器的配置字典
        self.thinking_depth = self.config.get("thinking_depth", 3)
        logger.debug(f"{self.name} thinking_depth 设置为: {self.thinking_depth}")
        
        # **修改：从处理器特定配置读取 save_to_memory**
        self.save_to_memory = self.config.get("save_to_memory", True)
        logger.debug(f"{self.name} save_to_memory 设置为: {self.save_to_memory}")
        
        # **修改：从处理器特定配置读取 max_history**
        self.max_history = self.config.get("max_history", 5) # 用于 _format_history
        logger.debug(f"{self.name} max_history 设置为: {self.max_history}")

        # **修改：从处理器特定配置读取 thought_importance**
        self.thought_importance = self.config.get("thought_importance", 0.5) # 用于 _save_thought_to_memory
        logger.debug(f"{self.name} thought_importance 设置为: {self.thought_importance}")

        # **修改：从配置加载思考模板**
        # 从传入的配置中获取 thought_generator 处理器的 prompt 模板
        # 预期 config 结构: {"prompts": {"thought_generator": {"thinking_prompt": "..."}}}
        # self.config 是传递给处理器的配置字典
        self.thinking_template = self.config.get("prompts", {}).get(self.name, {}).get("thinking_prompt", "") # 使用 self.name 获取对应配置
        if not self.thinking_template:
             logger.error("未能从配置中加载 ThoughtGenerator thinking_prompt 模板！将无法生成思考。")
             self.thinking_template = "错误：缺少 ThoughtGenerator 思考 Prompt 模板。"

        # LLM 管理器，用于调用语言模型
        self.llm_manager = None
        
        # 人格系统
        self.personality = None
    
    def set_llm_manager(self, llm_manager: Any) -> None:
        """
        设置LLM管理器
        
        Args:
            llm_manager: LLM管理器实例
        """
        self.llm_manager = llm_manager
    
    def set_personality(self, personality: Any) -> None:
        """
        设置人格系统
        
        Args:
            personality: 人格系统实例
        """
        self.personality = personality
    
    async def process(self, context: MessageContext) -> MessageContext:
        """
        处理消息上下文，生成内部思考
        
        Args:
            context: 消息上下文
            
        Returns:
            处理后的消息上下文
        """
        # 检查LLM管理器是否已设置
        if not self.llm_manager:
            logger.warning("LLM管理器未设置，跳过思考生成")
            return context
        
        # 获取消息文本
        message_text = context.message.extract_plain_text()
        
        # 记录处理信息
        context.log_processor(
            self.name, 
            f"生成思考: '{message_text[:50]}{'...' if len(message_text) > 50 else ''}'"
        )
        
        try:
            # 生成内部思考
            thought = await self._generate_thought(context)
            
            # 将思考结果添加到上下文
            if thought:
                context.set_state("thought", thought)
                context.log_processor(self.name, f"思考生成成功 ({len(thought)} 字符)")
                
                # 保存思考到记忆
                if self.save_to_memory and hasattr(context, "memory_manager"):
                    await self._save_thought_to_memory(context, thought)
            else:
                context.log_processor(self.name, "无法生成思考")
        
        except Exception as e:
            logger.error(f"思考生成失败: {str(e)}", exc_info=True)
            context.log_processor(self.name, f"处理失败: {str(e)}")
        
        return context
    
    async def _generate_thought(self, context: MessageContext) -> Optional[str]:
        """
        生成内部思考
        
        Args:
            context: 消息上下文
            
        Returns:
            生成的思考内容
        """
        # 构建提示词
        prompt = self._build_thinking_prompt(context)
        
        try:
            # 调用LLM生成思考，使用任务路由选择合适的模型
            thought, metadata = await self.llm_manager.generate_text(
                prompt,
                max_tokens=self.config.get("max_tokens", 1000), # 从配置读取 token 限制
                task="thought_generation"  # 使用专门的任务类型
            )
            
            # 记录使用的模型信息
            router_info = metadata.get("router_info", {})
            if router_info:
                model_id = router_info.get("model_id")
                logger.debug(f"思考生成使用模型: {model_id}")
            
            return thought.strip()
        
        except Exception as e:
            logger.error(f"思考生成失败: {str(e)}", exc_info=True)
            return None
    
    def _build_thinking_prompt(self, context: MessageContext) -> str:
        """
        构建思考提示词
        
        Args:
            context: 消息上下文
            
        Returns:
            思考提示词
        """
        # 获取消息文本
        message_text = context.message.extract_plain_text()
        
        # --- 准备 Prompt 所需的上下文信息 ---
        # 格式化近期对话历史
        history_text = self._format_history(context)
        # 格式化检索到的相关记忆
        memories_text = self._format_memories(context)
        # 格式化当前情绪状态 (用于 mood_prompt)
        mood_prompt = self._format_emotion(context) # 注意: _format_emotion 可能需要调整以输出更适合 Prompt 的格式
        # 格式化 ReadAir 的分析结果 (JSON 字符串)
        air_analysis = self._format_air_analysis(context)
        # 获取人格原则文本 (依赖于 LinjingBot 正确加载并传递)
        # TODO: 修复 LinjingBot 中的配置加载逻辑，确保 personality_text 被正确传递
        personality_text = self.config.get("personality_text", "错误：人格原则文本未加载！")
        # 获取关系信息 (当前为 TODO)
        
        # 获取关系信息 (暂时使用空字符串，待实现)
        relation_prompt_all = ""  # TODO: 从 MemoryManager 获取
        
        # 构建思考提示词
        depth_description = ["简单", "一般", "详细", "深入", "非常深入"][min(self.thinking_depth, 4)]
        
        try:
            # 确保从 self.config 获取最新的 prompts 数据
            current_prompts = self.config.get("prompts", {})
            self.thinking_template = current_prompts.get("thought_generator", {}).get("thinking_prompt", self.thinking_template)

            if not self.thinking_template or "错误：" in self.thinking_template:
                 logger.error("ThoughtGenerator Prompt 模板无效或未加载，无法构建 Prompt。")
                 return "错误：ThoughtGenerator Prompt 模板无效。"

            # 获取角色名
            character_name = getattr(self.personality, 'name', '林静') if self.personality else '林静'

            prompt = self.thinking_template.format(
                character_name=character_name,
                user_identifier=context.message.get_meta("user_display_name") or str(context.user_id),
                message_content=message_text,
                history_text=history_text,
                memories_text=memories_text,
                mood_prompt=mood_prompt,
                relation_prompt_all=relation_prompt_all,
                air_analysis=air_analysis,
                personality_text=personality_text,
                depth_description=depth_description
            )
        except KeyError as e:
             logger.error(f"构建 ThoughtGenerator Prompt 时缺少占位符: {e}。模板: {self.thinking_template}")
             prompt = f"错误：构建 Prompt 失败，缺少占位符 {e}。"
        except Exception as e:
             logger.error(f"构建 ThoughtGenerator Prompt 时发生未知错误: {e}", exc_info=True)
             prompt = "错误：构建 Prompt 时发生未知错误。"

        return prompt
    
    def _format_history(self, context: MessageContext) -> str:
        """
        从 MessageContext 中提取并格式化最近的对话历史记录，用于 Prompt。

        Args:
            context: 当前消息上下文。

        Returns:
            格式化后的历史对话字符串，如果无历史则返回 "无历史对话"。
        """
        history_text = ""
        
        # **修改：使用 self.max_history**
        recent_history = context.history[-self.max_history:] if context.history else []
        
        # 格式化历史消息
        for msg in recent_history:
            if msg.get_meta("is_user", False):
                user_identifier = msg.get_meta("user_display_name") or str(msg.user_id)
                role = f"用户 ({user_identifier})"
            else:
                role = f"我 ({self.name})"
            content = msg.extract_plain_text()
            history_text += f"{role}: {content}\n"
        
        return history_text.strip() or "无历史对话"
    
    def _format_memories(self, context: MessageContext) -> str:
        """
        从 MessageContext 中提取并格式化检索到的相关记忆，用于 Prompt。

        Args:
            context: 当前消息上下文。

        Returns:
            格式化后的记忆列表字符串，如果无记忆则返回 "无相关记忆"。
        """
        # context.memories 预期是一个包含记忆对象的列表
        # (例如 MemoryManager.search_similar_memories 返回的字典列表)
        if not context.memories:
            return "无相关记忆"
        
        memories_text = ""
        for i, memory in enumerate(context.memories):
            if hasattr(memory, "content"):
                memories_text += f"- {memory.content}\n"
            elif isinstance(memory, dict) and "content" in memory:
                memories_text += f"- {memory['content']}\n"
            elif isinstance(memory, str):
                memories_text += f"- {memory}\n"
        
        return memories_text.strip() or "无相关记忆"
    
    def _format_emotion(self, context: MessageContext) -> str:
        """
        从 MessageContext 中提取并格式化当前的情绪状态，用于 Prompt。
        主要提取强度大于阈值的情绪维度。

        Args:
            context: 当前消息上下文。

        Returns:
            格式化后的情绪状态字符串，如果无明显情绪则返回 "情绪平静"。
        """
        # 从 context state 获取由 EmotionManager 设置的情绪字典
        emotion_dict = context.get_state("emotion")
        if not emotion_dict or not isinstance(emotion_dict, dict):
            logger.debug("未在上下文中找到有效的情绪状态字典")
            return "情绪平静" # 默认状态

        logger.debug(f"格式化情绪状态字典: {emotion_dict}")
        emotion_text = ""
        # 从字典中获取 dimensions
        dimensions = emotion_dict.get("dimensions")
        if isinstance(dimensions, dict):
            for emotion, intensity in dimensions.items():
                if isinstance(intensity, (int, float)):
                    if intensity > 0.3:
                        emotion_text += f"{emotion}: {intensity:.2f}, "
                else:
                    logger.warning(f"情绪强度不是数字类型: emotion={emotion}, type={type(intensity)}, value={intensity}")
        else:
             # 如果 emotion_dict 存在但没有 'dimensions' 或格式不对
             logger.warning(f"情绪状态字典中缺少 'dimensions' 或格式无效: {emotion_dict}")

        return emotion_text.strip(", ") or "情绪平静"
    
    def _format_air_analysis(self, context: MessageContext) -> str:
        """
        从 MessageContext 中提取 ReadAirProcessor 的分析结果 (预期为 JSON 字典)，
        并将其格式化为适合 Prompt 输入的 JSON 字符串。

        Args:
            context: 当前消息上下文。

        Returns:
            格式化后的分析结果 JSON 字符串，或在出错时返回错误提示。
        """
        # 从 context state 获取由 ReadAirProcessor 设置的分析结果字典
        analysis = context.get_state("read_air_analysis")
        logger.debug(f"获取到的'读空气'分析结果: {analysis}")
        
        # 定义无法分析的标记
        UNANALYZABLE_CONTENT_MARKER = "内容无法分析（可能是图片等非文本内容）"
        
        if not analysis or not isinstance(analysis, dict):
            logger.warning(f"无效的'读空气'分析结果类型: {type(analysis)}，使用占位符")
            return UNANALYZABLE_CONTENT_MARKER

        result = ""

        try:
            # 语言学特征
            ling = analysis.get("linguistic_profile", {})
            if ling:
                result += f"语言风格: {', '.join(ling.get('style_assessment', []))}\n"
                result += f"语域: {ling.get('register_assessment', '未知')}\n"
                result += f"关键主题: {', '.join(ling.get('key_topics', []))}\n"

            # 认知情绪状态
            ces = analysis.get("cognitive_emotional_state", {})
            if ces:
                dom_emo = ces.get("dominant_emotion", {})
                if dom_emo:
                    result += f"主要情绪: {dom_emo.get('type', '未知')} "
                    result += f"(效价: {dom_emo.get('valence', 0):.1f}, "
                    result += f"唤醒度: {dom_emo.get('arousal', 0):.1f})\n"
                
                sec_emos = ces.get("secondary_emotions", [])
                if sec_emos:
                    result += "次要情绪: " + ", ".join(
                        [f"{e.get('type', '?')}({e.get('confidence', 0):.1f})"
                         for e in sec_emos]) + "\n"
                
                result += f"认知意图: {', '.join(ces.get('cognitive_intent', []))}\n"

            # 沟通意图
            comm = analysis.get("communicative_intent", {})
            if comm:
                result += f"主要言语行为: {comm.get('primary_speech_act', '未知')}\n"
                result += f"期望回应: {', '.join(comm.get('expected_response_type', []))}\n"

            # 逻辑分析
            logic = analysis.get("logical_argument_analysis", {})
            if logic:
                if logic.get("contains_argument", False):
                    result += f"论证清晰度: {logic.get('argument_clarity', '未知')}\n"
                
                fallacies = logic.get("identified_fallacies", [])
                if fallacies:
                    result += "逻辑谬误: " + ", ".join(
                        [f"{f.get('type', '?')}({f.get('target', '')})"
                         for f in fallacies]) + "\n"
                
                result += f"隐含假设: {', '.join(logic.get('implicit_assumptions', []))}\n"

            # 社交语境
            social = analysis.get("social_context_assessment", {})
            if social:
                fta = social.get("face_threatening_act", {})
                if fta:
                    result += f"面子威胁: {'是' if fta.get('threatens_receiver_positive_face', False) else '否'}\n"
                    result += f"严重程度: {fta.get('severity', '未知')}\n"
                
                result += f"群体规范: {social.get('alignment_with_group_norms', '未知')}\n"
                result += f"关系影响: {social.get('potential_relationship_impact', '未知')}\n"

            # V12触发器
            triggers = analysis.get("v12_trigger_scan_results", {})
            if triggers:
                active_triggers = [k for k, v in triggers.items() if v is True]
                if active_triggers:
                    result += f"触发的V12敏感点: {', '.join(active_triggers)}\n"
                else:
                    result += "未触发V12敏感点\n"

            # 综合评估
            overall = analysis.get("overall_assessment", {})
            if overall:
                result += f"消息复杂度: {overall.get('message_complexity', '未知')}\n"
                result += f"潜在冲突等级: {overall.get('potential_conflict_level', '未知')}\n"
                result += f"建议互动方式: {overall.get('recommended_engagement', '未知')}\n"

        except Exception as e:
            logger.error(f"格式化分析结果时出错: {str(e)}", exc_info=True)
            return UNANALYZABLE_CONTENT_MARKER

        return result.strip() or "无详细分析结果"
    
    # 已移除弃用的 _format_personality 方法
    
    async def _save_thought_to_memory(self, context: MessageContext, thought: str) -> None:
        """
        将生成的思考内容保存到记忆库 (如果配置允许)。
        注意：当前 MemoryManager 没有通用的 store_memory 方法，此功能可能未完全实现。

        Args:
            context: 当前消息上下文 (需要包含 memory_manager)。
            thought: 生成的思考内容字符串。
        """
        try:
            # 检查 context 是否有关联的 memory_manager
            if hasattr(context, "memory_manager") and context.memory_manager:
                logger.warning("尝试调用 context.memory_manager.store_memory，但该方法可能不存在。")
                # TODO: 实现或替换为正确的记忆存储方法，例如 add_knowledge_memory
                # 可能需要将 thought 视为一种特殊的 knowledge
                # await context.memory_manager.add_knowledge_memory(
                #     content=thought,
                #     category="internal_thought",
                #     importance=self.thought_importance,
                #     metadata={"user_id": context.user_id, "session_id": context.session_id}
                # )
                # logger.debug("思考已尝试保存到记忆 (使用 add_knowledge_memory)")
            else:
                 logger.warning("无法保存思考：未在上下文中找到 memory_manager。")
        except Exception as e:
            logger.error(f"保存思考到记忆失败: {str(e)}", exc_info=True)
            # 失败不影响主流程，只记录日志
