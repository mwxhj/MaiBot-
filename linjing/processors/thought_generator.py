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
        prompts_config = self.config.get("prompts", {})
        self.thinking_template = ""
        
        if prompts_config:
            # 尝试获取思考提示词模板
            self.thinking_template = prompts_config.get("thinking_prompt", "")
            if self.thinking_template:
                logger.debug(f"{self.name} 成功加载 thinking_prompt 模板 (长度: {len(self.thinking_template)})")
            else:
                logger.error(f"{self.name} 无法从配置中找到 thinking_prompt 模板!")
        
        if not self.thinking_template:
            logger.error(f"未能从配置 {self.name} 中加载 prompts.thinking_prompt 模板！将无法生成思考。")
            # 提供一个错误提示作为默认值
            self.thinking_template = "错误：缺少 ThoughtGenerator 思考 Prompt 模板。"

        # LLM 管理器，用于调用语言模型
        self.llm_manager = None
        # 记忆管理器，用于获取关系信息和存储思考
        self.memory_manager = None
        
        # 人格系统
        self.personality = None
    
    def set_llm_manager(self, llm_manager: Any) -> None:
        """
        设置LLM管理器
        
        Args:
            llm_manager: LLM管理器实例
        """
        self.llm_manager = llm_manager

    def set_memory_manager(self, memory_manager: Any) -> None:
        """设置记忆管理器实例"""
        self.memory_manager = memory_manager
        logger.debug(f"{self.name} memory_manager 设置成功。")

    # 移除 set_personality 方法，人格原则文本现在通过 config 注入
    # def set_personality(self, personality: Any) -> None:
    #     """
    #     设置人格系统
    #     """
    #     self.personality = personality
    
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

    # 修改为 async def
    async def _generate_thought(self, context: MessageContext) -> Optional[str]:
        """
        生成内部思考
        
        Args:
            context: 消息上下文
            
        Returns:
            生成的思考内容
        """
        # 构建提示词 (确认已修改)
        prompt = await self._build_thinking_prompt(context)

        try:
            # 调用LLM生成思考，使用任务路由选择合适的模型
            thought, metadata = await self.llm_manager.generate_text(
                prompt,
                max_tokens=self.config.get("max_tokens", 1000), # 从配置读取 token 限制
                task=self.name  # 使用处理器名称作为任务类型
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
    
    # 修改为 async def
    async def _build_thinking_prompt(self, context: MessageContext) -> str:
        """
        构建思考提示词
        
        Args:
            context: 消息上下文
            
        Returns:
            思考提示词
        """
        import json # Import json module here
        
        # 获取消息文本
        message_text = context.message.extract_plain_text()
        
        # --- 准备 Prompt 所需的上下文信息 ---
        # 格式化近期对话历史
        history_text = self._format_history(context)
        # 格式化检索到的相关记忆
        memories_text = self._format_memories(context)
        # 格式化当前情绪状态 (用于 mood_prompt)
        mood_prompt = self._format_emotion(context) # 注意: _format_emotion 可能需要调整以输出更适合 Prompt 的格式
        # 格式化 ReadAir 的分析结果 (获取 Python 对象)
        air_analysis = self._format_air_analysis(context)
        # 获取人格原则文本 (由 LinjingBot 注入到 self.config)
        personality_text = self.config.get("personality_text", "错误：人格原则文本未在配置中找到！")
        if "错误：" in personality_text:
             logger.error("未能从配置中获取 personality_text！Prompt 将不完整。")

        # 获取关系信息摘要 (确认已修改)
        relation_prompt_all = await self._format_relationship(context)

        # --- 新增：将 air_analysis 对象转换为 JSON 字符串 ---
        air_analysis_json_str = "{}" # Default to empty JSON object string
        if isinstance(air_analysis, dict):
            try:
                # Convert the Python dict to a JSON string
                air_analysis_json_str = json.dumps(air_analysis, ensure_ascii=False, indent=2)
            except TypeError as e:
                 logger.error(f"无法将 air_analysis 字典转换为 JSON 字符串: {e}")
                 air_analysis_json_str = f'{{"error": "Failed to serialize air_analysis: {str(e)}"}}'
        elif air_analysis: # If it's not a dict but not None/empty, log a warning
            logger.warning(f"_format_air_analysis 返回的不是字典，而是: {type(air_analysis)}")
            air_analysis_json_str = f'{{"error": "Invalid air_analysis type: {type(air_analysis).__name__}"}}'
        # --- JSON 转换结束 ---

        # 构建思考提示词
        depth_description = ["简单", "一般", "详细", "深入", "非常深入"][min(self.thinking_depth, 4)]
        
        try:
            # 直接使用在 __init__ 中加载好的 self.thinking_template
            if not self.thinking_template or "错误：" in self.thinking_template:
                 logger.error(f"ThoughtGenerator Prompt 模板无效或未加载 (来自 __init__)，无法构建 Prompt。")
                 return "错误：ThoughtGenerator Prompt 模板无效。"

            # 获取角色名 (尝试从 global_config 获取，如果 LinjingBot 传递了的话)
            global_config = self.config.get("global_config", {})
            character_name = global_config.get("bot", {}).get("name", "林静") # 默认 '林静'

            prompt = self.thinking_template.format(
                character_name=character_name,
                user_identifier=context.message.get_meta("user_display_name") or str(context.user_id),
                message_content=message_text,
                history_text=history_text,
                memories_text=memories_text,
                mood_prompt=mood_prompt,
                relation_prompt_all=relation_prompt_all,
                air_analysis=air_analysis_json_str, # 使用 JSON 字符串
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
                # 修复：使用get_user_id方法或get_meta获取user_id
                user_id = msg.get_user_id() if hasattr(msg, 'get_user_id') else msg.get_meta("user_id", "unknown")
                user_identifier = msg.get_meta("user_display_name") or str(user_id)
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
        # 从全局配置中获取情绪显著性阈值
        # global_config 是在 LinjingBot._init_processors 中注入的
        global_config = self.config.get("global_config", {})
        significant_threshold = global_config.get("emotion", {}).get("vad_model", {}).get("significant_threshold", 0.3)
        logger.debug(f"使用情绪显著性阈值: {significant_threshold}")

        # 从字典中获取 VAD 维度值
        # 注意：EmotionManager 现在存储的是 VAD 值，键名是 valence, arousal, dominance
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
            emotion_text = ", ".join(significant_emotions)
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
            分析结果字典，或在出错时返回 None 或空字典。
        """
        # 从 context state 获取由 ReadAirProcessor 设置的分析结果字典
        analysis = context.get_state("read_air_analysis")
        logger.debug(f"获取到的'读空气'分析结果: {analysis}")
        
        # 只返回获取到的字典，或者在无效时返回 None 或空字典
        if not analysis or not isinstance(analysis, dict):
            logger.warning(f"无效的'读空气'分析结果类型: {type(analysis)}，返回 None")
            return None # 或者 return {} 如果下游期望字典

        # 直接返回获取到的字典对象
        return analysis
    
    # --- 新增：格式化关系信息 ---
    # 修改为 async def (确认已修改)
    async def _format_relationship(self, context: MessageContext) -> str:
        """
        从 MemoryManager 获取关系摘要并格式化为 Prompt 字符串。

        Args:
            context: 当前消息上下文。

        Returns:
            格式化后的关系信息字符串，或在出错/无信息时返回提示。
        """
        # 先检查 memory_manager 是否已设置
        if not hasattr(self, "memory_manager") or self.memory_manager is None:
            logger.warning("无法获取关系信息：memory_manager 未设置。")
            return "关系信息：未知（记忆系统未就绪）"

        try:
            # 从 MemoryManager 获取基本关系摘要
            relationship_summary = await self.memory_manager.get_user_relationship_summary(context.user_id)
            
            # 准备关系信息组件
            parts = []
            
            # 1. 基本交互信息
            count = relationship_summary.get("interaction_count", 0)
            first_ts = relationship_summary.get("first_interaction_ts")
            last_ts = relationship_summary.get("last_interaction_ts")
            tags = relationship_summary.get("tags", [])

            parts.append(f"交互次数: {count}")
            
            if first_ts:
                 import datetime
                 first_dt = datetime.datetime.fromtimestamp(first_ts).strftime('%Y-%m-%d')
                 parts.append(f"初次交互: {first_dt}")
                 
            if last_ts:
                 import datetime
                 last_dt = datetime.datetime.fromtimestamp(last_ts).strftime('%Y-%m-%d %H:%M')
                 parts.append(f"上次交互: {last_dt}")
                 
            if tags:
                 parts.append(f"用户标签: {', '.join(tags)}")
                 
            # 2. 交互频率（如果数据足够）
            if first_ts and last_ts and count > 3:
                duration_days = max(1, (last_ts - first_ts) / (24 * 3600))
                if duration_days > 1:  # 至少有超过一天的交互历史
                    frequency = count / duration_days
                    if frequency > 10:
                        parts.append("互动频率: 非常频繁")
                    elif frequency > 5:
                        parts.append("互动频率: 频繁")
                    elif frequency > 1:
                        parts.append("互动频率: 一般")
                    else:
                        parts.append("互动频率: 偶尔")
            
            # 3. 关系紧密度（基于互动频率和总次数的综合评估）
            if count > 0:
                if count > 50:
                    parts.append("关系评估: 密切")
                elif count > 20:
                    parts.append("关系评估: 熟悉")
                elif count > 5:
                    parts.append("关系评估: 认识")
                else:
                    parts.append("关系评估: 初步接触")
            
            # 组合所有信息
            relationship_str = "关系信息：" + "; ".join(parts)
            return relationship_str

        except Exception as e:
            logger.error(f"获取或格式化用户 {context.user_id} 关系信息失败: {e}", exc_info=True)
            return "关系信息：获取失败"

    async def _save_thought_to_memory(self, context: MessageContext, thought: str) -> None:
        """
        将生成的思考内容 (current_mind_info JSON) 保存为知识记忆。

        Args:
            context: 当前消息上下文 (需要包含 memory_manager)。
            thought: 生成的思考内容字符串 (预期为 JSON)。
        """
        try:
            # 先检查 memory_manager 是否已设置
            if not hasattr(self, "memory_manager") or self.memory_manager is None:
                logger.warning("无法保存思考：memory_manager 未设置。")
                return
            
            # 使用 add_knowledge_memory 存储思考
            await self.memory_manager.add_knowledge_memory(
                content=thought, # 直接存储 JSON 字符串
                category="internal_thought", # 指定类别
                source=self.name, # 来源是本处理器
                importance=self.thought_importance, # 使用配置的重要性
                # 可以添加更多元数据，例如关联的消息 ID
                metadata={
                    "user_id": context.user_id,
                    "session_id": context.session_id,
                    "message_id": context.message.get_id() if hasattr(context.message, 'get_id') else None
                }
                # 思考通常不需要向量化，所以不传递 embedding
            )
            logger.debug("思考已保存到记忆 (类型: knowledge, 类别: internal_thought)")
        except Exception as e:
            logger.error(f"保存思考到记忆失败: {str(e)}", exc_info=True)
            # 失败不影响主流程，只记录日志
