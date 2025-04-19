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
        # 注意：这里假设 config 字典包含了加载后的 prompts 数据
        self.thinking_template = config.get("prompts", {}).get("thought_generator", {}).get("thinking_prompt", "")
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
        
        # **修改：始终使用从配置加载的模板**
        try:
            # 确保从 self.config 获取最新的 prompts 数据
            current_prompts = self.config.get("prompts", {})
            self.thinking_template = current_prompts.get("thought_generator", {}).get("thinking_prompt", self.thinking_template) # 更新模板

            if not self.thinking_template or "错误：" in self.thinking_template:
                 logger.error("ThoughtGenerator Prompt 模板无效或未加载，无法构建 Prompt。")
                 return "错误：ThoughtGenerator Prompt 模板无效。"

            # 获取角色名，如果 personality 对象存在且有 name 属性
            character_name = getattr(self.personality, 'name', '林静') if self.personality else '林静'

            prompt = self.thinking_template.format(
                character_name=character_name, # 添加角色名
                user_identifier=context.message.get_meta("user_display_name") or str(context.user_id),
                message_content=message_text,
                history_text=history_text,
                memories_text=memories_text,
                emotion_text=emotion_text,
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
        格式化历史消息
        
        Args:
            context: 消息上下文
            
        Returns:
            格式化的历史消息文本
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
        # 从 context state 获取情绪字典
        emotion_dict = context.get_state("emotion")
        if not emotion_dict or not isinstance(emotion_dict, dict):
            return "情绪平静"

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
        格式化"读空气"分析结果
        
        Args:
            context: 消息上下文
            
        Returns:
            格式化的分析结果文本
        """
        analysis = context.get_state("read_air_analysis")
        logger.debug(f"格式化'读空气'分析结果: {analysis}") # 添加日志
        # 定义一个特殊的标记表示无法分析
        UNANALYZABLE_CONTENT_MARKER = "内容无法分析（可能是图片等非文本内容）"
        if not analysis or not isinstance(analysis, dict): # 检查 analysis 是否为字典
            logger.warning(f"无效的'读空气'分析结果类型: {type(analysis)}，使用占位符")
            # 返回特定标记而不是通用文本
            return UNANALYZABLE_CONTENT_MARKER

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
                # **修改：使用 self.thought_importance**
                await context.memory_manager.store_memory(
                    content=thought,
                    memory_type="thought",
                    importance=self.thought_importance, # 使用从配置读取的值
                    importance=importance,
                    user_id=context.user_id,
                    associated_message=context.message
                )
                logger.debug("思考已保存到记忆")
        except Exception as e:
            logger.error(f"保存思考到记忆失败: {str(e)}", exc_info=True)
            # 失败不影响主流程，只记录日志
