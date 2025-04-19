#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
响应生成器模块，负责根据上下文和思考过程生成最终的回复消息。
"""

import logging
import random
from typing import Any, Dict, List, Optional, Union

from linjing.adapters.message_types import Message, MessageSegment
from linjing.processors.base_processor import BaseProcessor
from linjing.processors.message_context import MessageContext
from linjing.processors.processor_registry import ProcessorRegistry
from linjing.processors.base_processor import BaseProcessor as Processor

logger = logging.getLogger(__name__)


@ProcessorRegistry.register("response_composer")
class ResponseComposer(BaseProcessor):
    """
    响应生成器，根据上下文和思考结果生成最终回复消息。
    
    该处理器负责：
    1. 根据思考生成器的输出构建回复
    2. 格式化回复内容
    3. 添加适当的情感和风格元素
    4. 处理多模态内容（如图片、音频等）
    """

    def __init__(
        self,
        config: Dict[str, Any],
        priority: int = 300,
    ) -> None:
        """
        初始化响应生成器。

        Args:
            config: 配置字典，包含生成回复所需的参数
            priority: 处理器优先级，默认为300（执行顺序靠后）
        """
        super().__init__(config, priority)
        self.style_factor = config.get("style_factor", 0.8)
        self.character_name = config.get("character_name", "灵镜")
        self.response_template = config.get(
            "response_template", "{response}"
        )
        self.use_multimodal = config.get("use_multimodal", True)
        self.llm_manager = None
        self.personality = None

    def set_llm_manager(self, llm_manager: Any) -> None:
        """
        设置LLM管理器。

        Args:
            llm_manager: 语言模型管理器实例
        """
        self.llm_manager = llm_manager

    def set_personality(self, personality: Any) -> None:
        """
        设置人格配置。

        Args:
            personality: 人格配置实例
        """
        self.personality = personality

    async def process(self, context: MessageContext) -> MessageContext:
        """
        处理消息上下文，生成最终回复。

        Args:
            context: 消息上下文

        Returns:
            更新后的消息上下文，包含生成的回复
        """
        logger.info("开始生成回复消息")
        
        try:
            # 获取思考结果和相关上下文
            thought = context.get_state("thought", "")
            
            if not thought:
                logger.warning("未找到思考结果，将生成备用回复")
                reply = await self._generate_fallback_response(context)
            else:
                # 基于思考结果生成回复
                reply = await self._generate_response(context, thought)
            
            # 将生成的回复添加到上下文
            reply_message = Message()
            reply_message.append(MessageSegment.text(reply))
            
            # 如果需要添加多模态内容
            if self.use_multimodal and hasattr(context, "multimodal_content"):
                await self._add_multimodal_content(reply_message, context)
            
            context.set_state("reply", reply_message)
            logger.info(f"已生成回复: {reply[:50]}...")
            
        except Exception as e:
            logger.error(f"生成回复时出错: {e}", exc_info=True)
            context["reply"] = Message(MessageSegment.text(self._generate_error_response()))
        
        return context

    async def _generate_response(self, context: MessageContext, thought: str) -> str:
        """
        基于思考结果生成回复内容。

        Args:
            context: 消息上下文
            thought: 思考结果

        Returns:
            格式化后的回复文本
        """
        # 构建提示词
        prompt = self._build_prompt(context, thought)
        
        # 如果有LLM管理器，使用LLM生成回复
        if self.llm_manager:
            try:
                response, metadata = await self.llm_manager.generate_text(
                    prompt,
                    task="chat",  # 回复生成是对话任务
                    max_tokens=500
                )
                
                # 记录使用的模型信息
                router_info = metadata.get("router_info", {})
                if router_info:
                    model_id = router_info.get("model_id")
                    logger.debug(f"回复生成使用模型: {model_id}")
                
                return self._format_response(response)
            except Exception as e:
                logger.error(f"使用LLM生成回复失败: {e}", exc_info=True)
        
        # 否则，直接基于思考结果格式化回复
        return self._format_thought_as_response(thought)

    def _build_prompt(self, context: MessageContext, thought: str) -> str:
        """
        构建用于生成回复的提示词。

        Args:
            context: 消息上下文
            thought: 思考结果

        Returns:
            格式化后的提示词
        """
        # 获取历史记录
        history = self._format_history(context.get("history", []))
        
        # 获取人格特质
        traits = self._format_personality_traits()
        
        # 构建提示词模板
        prompt = (
            f"基于以下信息生成回复:\n\n"
            f"历史对话:\n{history}\n\n"
            f"用户消息: {context.get('message', '')}\n\n"
            f"内部思考: {thought}\n\n"
            f"人格特质: {traits}\n\n"
            f"请以{self.character_name}的身份生成自然、得体且符合人格特质的回复。"
            f"回复应直接面向用户，不要包含思考过程，回复应当是完整、流畅的中文语句。"
        )
        return prompt

    def _format_history(self, history: List[Dict[str, Any]]) -> str:
        """
        格式化历史对话记录。

        Args:
            history: 历史对话列表

        Returns:
            格式化后的历史对话文本
        """
        if not history:
            return "无历史对话"
        
        formatted_history = []
        for entry in history[-5:]:  # 只使用最近的5条对话
            if "user" in entry:
                formatted_history.append(f"用户: {entry['user']}")
            if "bot" in entry:
                formatted_history.append(f"{self.character_name}: {entry['bot']}")
        
        return "\n".join(formatted_history)

    def _format_personality_traits(self) -> str:
        """
        格式化人格特质。

        Returns:
            格式化后的人格特质文本
        """
        if not self.personality:
            return "友好、乐于助人"
        
        traits = self.personality.get("traits", [])
        if not traits:
            return "友好、乐于助人"
        
        return "、".join(traits)

    def _format_response(self, response: str) -> str:
        """
        格式化回复内容，添加风格和情感元素。

        Args:
            response: 原始回复内容

        Returns:
            格式化后的回复文本
        """
        # 清理回复内容
        response = response.strip()
        
        # 应用响应模板
        formatted_response = self.response_template.format(response=response)
        
        # 如果有人格设置，可以添加个性化表情或语气词
        if self.personality and random.random() < self.style_factor:
            emojis = self.personality.get("emojis", [])
            phrases = self.personality.get("phrases", [])
            
            if emojis and random.random() < 0.3:
                formatted_response += f" {random.choice(emojis)}"
            
            if phrases and random.random() < 0.2:
                formatted_response += f" {random.choice(phrases)}"
        
        return formatted_response

    def _format_thought_as_response(self, thought: str) -> str:
        """
        将思考结果格式化为回复。

        Args:
            thought: 思考结果

        Returns:
            格式化后的回复文本
        """
        # 从思考结果中提取有用信息
        lines = thought.strip().split("\n")
        response_lines = []
        
        for line in lines:
            # 跳过思考过程的标记行
            if line.startswith(("思考:", "分析:", "推理:", "计划:")):
                continue
            # 保留直接回答的行
            if line.startswith(("回复:", "答案:", "结论:")):
                response_lines.append(line.split(":", 1)[1].strip())
            # 保留有用的信息行
            elif line and not line.startswith(("#", "//")):
                response_lines.append(line)
        
        # 如果提取后没有有效内容，返回原始思考
        if not response_lines:
            # 清理思考内容，移除标记和无关内容
            cleaned_thought = thought.replace("思考:", "").replace("分析:", "").strip()
            return cleaned_thought
        
        response = "\n".join(response_lines)
        return self._format_response(response)

    async def _generate_fallback_response(self, context: MessageContext) -> str:
        """
        当无法理解用户意图时生成备用回复。

        Args:
            context: 消息上下文

        Returns:
            备用回复文本
        """
        # 如果有LLM管理器，尝试使用它生成备用回复
        if self.llm_manager:
            try:
                user_message = context.message.extract_plain_text() if hasattr(context, "message") else ""
                prompt = (
                    f"用户发送了以下消息，但我无法完全理解其意图:\n"
                    f"\"{user_message}\"\n\n"
                    f"请以{self.character_name}的身份生成一个礼貌的回复，询问用户能否更清楚地表达意图。"
                    f"回复应当是自然、友好的中文，不超过50个字。"
                )
                
                response, metadata = await self.llm_manager.generate_text(
                    prompt,
                    task="chat",  # 备用回复也是对话任务
                    max_tokens=100
                )
                
                # 记录使用的模型信息
                router_info = metadata.get("router_info", {})
                if router_info:
                    model_id = router_info.get("model_id")
                    logger.debug(f"备用回复生成使用模型: {model_id}")
                
                return self._format_response(response)
            except Exception as e:
                logger.error(f"使用LLM生成备用回复失败: {e}", exc_info=True)
        
        # 备用方案：使用预定义的回复
        return self._generate_fallback_response_sync()

    def _generate_fallback_response_sync(self) -> str:
        """
        同步方式生成备用回复。

        Returns:
            备用回复文本
        """
        fallback_responses = [
            "抱歉，我没能完全理解您的意思，能请您再说明一下吗？",
            "不好意思，我没太明白您的意思，可以请您换个方式表达吗？",
            "抱歉，我可能理解有误，您能再详细说明一下您的需求吗？",
            "对不起，我没有理解您的意图，请问您能更清楚地解释一下吗？",
            "不好意思，我似乎没有抓住您的重点，能否请您再解释一下？"
        ]
        return random.choice(fallback_responses)

    def _generate_error_response(self) -> str:
        """
        发生技术错误时生成错误回复。

        Returns:
            错误回复文本
        """
        error_responses = [
            "抱歉，我遇到了一些技术问题，无法正常回复您的消息。",
            "对不起，处理您的请求时出现了错误，请稍后再试。",
            "不好意思，系统暂时出现了故障，请稍候再尝试。",
            "抱歉，我现在无法处理您的请求，请稍后再试。",
            "对不起，我遇到了技术障碍，暂时无法回应您的问题。"
        ]
        return random.choice(error_responses)

    async def _add_multimodal_content(self, message: Message, context: MessageContext) -> None:
        """
        向回复中添加多模态内容（如图片、音频等）。

        Args:
            message: 回复消息
            context: 消息上下文
        """
        multimodal_content = context.get("multimodal_content", [])
        
        for item in multimodal_content:
            content_type = item.get("type")
            content_data = item.get("data")
            
            if not content_type or not content_data:
                continue
                
            if content_type == "image":
                message.append(MessageSegment.image(content_data))
            elif content_type == "audio":
                message.append(MessageSegment.audio(content_data))
            elif content_type == "video":
                message.append(MessageSegment.video(content_data))
            # 可以根据需要添加更多类型的多模态内容
            elif content_type == "file":
                message.append(MessageSegment.file(content_data))
            elif content_type == "location":
                message.append(MessageSegment.location(content_data))
            elif content_type == "at":
                message.append(MessageSegment.at(content_data))
