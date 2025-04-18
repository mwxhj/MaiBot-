#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
思考生成器模块，用于生成机器人的内部思考过程。
包括对用户消息的理解、知识检索、思考逻辑和情绪反应等。
"""

from typing import Any, Dict, List, Optional, Tuple, Union

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
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化思考生成器
        
        Args:
            config: 处理器配置
        """
        super().__init__(config)
        
        # 思考深度，影响思考的详细程度
        self.thinking_depth = self.config.get("thinking_depth", 3)
        
        # 是否保存思考结果到记忆
        self.save_to_memory = self.config.get("save_to_memory", True)
        
        # 思考模板
        self.thinking_template = self.config.get("thinking_template", None)
        
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
                max_tokens=1000,
                task="creative"  # 思考生成是创意任务，使用高质量模型
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
        
        # 获取历史消息
        history_text = self._format_history(context)
        
        # 获取记忆摘要
        memories_text = self._format_memories(context)
        
        # 获取情感状态
        emotion_text = self._format_emotion(context)
        
        # 获取"读空气"分析结果
        air_analysis = self._format_air_analysis(context)
        
        # 获取人格描述
        personality_text = self._format_personality()
        
        # 构建思考提示词
        depth_description = ["简单", "一般", "详细", "深入", "非常深入"][min(self.thinking_depth, 4)]
        
        # 使用配置的模板或默认模板
        if self.thinking_template:
            prompt = self.thinking_template.format(
                message=message_text,
                history=history_text,
                memories=memories_text,
                emotion=emotion_text,
                air_analysis=air_analysis,
                personality=personality_text,
                depth=depth_description
            )
        else:
            prompt = f"""作为一个名为林静的AI助手，你需要根据用户的消息生成你的内部思考过程。这个思考过程应该反映你如何理解和处理信息，以及你的个性特点如何影响你的思考。

### 基本信息
- 用户消息: "{message_text}"
- 对话历史:
{history_text}

### 你的记忆
{memories_text}

### 你的情绪状态
{emotion_text}

### 对当前消息的分析
{air_analysis}

### 你的人格特点
{personality_text}

现在，请以{depth_description}的思考深度，生成你对这条消息的内部思考过程。思考应该包括:
1. 你对消息的理解和解读
2. 与你记忆中的相关信息联系
3. 考虑用户可能的意图和期望
4. 你的情感反应和直觉
5. 可能的回应方向和策略

保持真实自然的思考流程，展现你的个性特点。不需要按固定格式输出，而是模拟真实的思考过程。"""
        
        return prompt
    
    def _format_history(self, context: MessageContext) -> str:
        """
        格式化历史消息
        
        Args:
            context: 消息上下文
            
        Returns:
            格式化的历史消息文本
        """
        history_text = ""
        
        # 获取最近的历史消息
        max_history = self.config.get("max_history", 5)
        recent_history = context.history[-max_history:] if context.history else []
        
        # 格式化历史消息
        for msg in recent_history:
            role = "用户" if msg.get_meta("is_user", False) else "我"
            content = msg.extract_plain_text()
            history_text += f"{role}: {content}\n"
        
        return history_text.strip() or "无历史对话"
    
    def _format_memories(self, context: MessageContext) -> str:
        """
        格式化记忆内容
        
        Args:
            context: 消息上下文
            
        Returns:
            格式化的记忆文本
        """
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
        格式化情绪状态
        
        Args:
            context: 消息上下文
            
        Returns:
            格式化的情绪状态文本
        """
        if not context.emotion_state:
            return "情绪平静"
        logger.debug(f"格式化情绪状态: {context.emotion_state}") # 添加日志
        emotion_text = ""
        for emotion, intensity in context.emotion_state.items():
            # 添加类型检查和日志
            if isinstance(intensity, (int, float)): 
                if intensity > 0.3:  # 只显示强度较高的情绪
                    emotion_text += f"{emotion}: {intensity:.2f}, "
            else:
                 logger.warning(f"情绪强度不是数字类型: emotion={emotion}, type={type(intensity)}, value={intensity}")

        return emotion_text.strip(", ") or "情绪平静"
    
    def _format_air_analysis(self, context: MessageContext) -> str:
        """
        格式化"读空气"分析结果
        
        Args:
            context: 消息上下文
            
        Returns:
            格式化的分析结果文本
        """
        analysis = context.get_state("read_air_analysis")
        logger.debug(f"格式化'读空气'分析结果: {analysis}") # 添加日志
        if not analysis or not isinstance(analysis, dict): # 检查 analysis 是否为字典
            logger.warning(f"无效的'读空气'分析结果类型: {type(analysis)}")
            return "无对话分析"

        result = ""

        # 格式化意图
        intent = analysis.get("intent", {})
        if isinstance(intent, dict): # 确保 intent 是字典
            primary = intent.get("primary", "未知")
            secondary = intent.get("secondary", "无")
            confidence = intent.get("confidence", 0)
            # 检查 confidence 类型
            if isinstance(confidence, (int, float)):
                 result += f"用户意图: 主要-{primary}, 次要-{secondary} (置信度: {confidence:.2f})\n"
            else:
                 logger.warning(f"意图置信度不是数字类型: type={type(confidence)}, value={confidence}")
                 result += f"用户意图: 主要-{primary}, 次要-{secondary} (置信度: N/A)\n"
        else:
             logger.warning(f"无效的意图类型: {type(intent)}")

        # 格式化情感
        emotion = analysis.get("emotion", {})
        if isinstance(emotion, dict): # 确保 emotion 是字典
            emotions_list = []
            for k, v in emotion.items():
                 # 检查情感值类型
                 if isinstance(v, (int, float)):
                     if v > 0.3:
                         emotions_list.append(f"{k}: {v:.2f}")
                 else:
                     logger.warning(f"分析中的情感值不是数字类型: key={k}, type={type(v)}, value={v}")
            emotions_str = ", ".join(emotions_list)
            result += f"用户情感: {emotions_str or '中性'}\n"
        else:
            logger.warning(f"无效的情感类型: {type(emotion)}")


        # 格式化社交期望
        social = analysis.get("social_context", {})
        if social:
            expectation = social.get("expectation", "无明确期望")
            result += f"社交期望: {expectation}\n"
        
        # 格式化隐含信息
        implicit = analysis.get("implicit", {})
        if implicit:
            concerns = implicit.get("concerns", [])
            concerns_str = ", ".join(concerns) if concerns else "无"
            result += f"隐含信息: {concerns_str}\n"
        
        return result.strip() or "无对话分析"
    
    def _format_personality(self) -> str:
        """
        格式化人格特点
        
        Returns:
            格式化的人格特点文本
        """
        if not self.personality:
            return "性格平和，乐于助人"
        
        try:
            # 如果人格系统实现了to_prompt_format方法，则使用该方法
            if hasattr(self.personality, "to_prompt_format"):
                return self.personality.to_prompt_format()
            
            # 否则尝试获取特质
            traits_text = ""
            if hasattr(self.personality, "traits") and isinstance(self.personality.traits, dict): # 确保 traits 是字典
                logger.debug(f"格式化人格特质: {self.personality.traits}") # 添加日志
                for trait, value in self.personality.traits.items():
                    # 检查特质值类型
                    if isinstance(value, (int, float)):
                        traits_text += f"{trait}: {value:.2f}, "
                    else:
                        logger.warning(f"人格特质值不是数字类型: trait={trait}, type={type(value)}, value={value}")
            elif hasattr(self.personality, "traits"):
                 logger.warning(f"无效的人格特质类型: {type(self.personality.traits)}")


            # 获取兴趣
            interests_text = ""
            if hasattr(self.personality, "interests") and self.personality.interests:
                interests_text = "兴趣: " + ", ".join(self.personality.interests)
            
            return (traits_text.strip(", ") + "\n" + interests_text).strip() or "性格平和，乐于助人"
            
        except Exception as e:
            logger.error(f"格式化人格特点失败: {str(e)}", exc_info=True)
            return "性格平和，乐于助人"
    
    async def _save_thought_to_memory(self, context: MessageContext, thought: str) -> None:
        """
        保存思考内容到记忆
        
        Args:
            context: 消息上下文
            thought: 思考内容
        """
        try:
            if hasattr(context, "memory_manager") and context.memory_manager:
                # 创建思考记忆
                importance = self.config.get("thought_importance", 0.5)
                await context.memory_manager.store_memory(
                    content=thought,
                    memory_type="thought",
                    importance=importance,
                    user_id=context.user_id,
                    associated_message=context.message
                )
                logger.debug("思考已保存到记忆")
        except Exception as e:
            logger.error(f"保存思考到记忆失败: {str(e)}", exc_info=True)
            # 失败不影响主流程，只记录日志
