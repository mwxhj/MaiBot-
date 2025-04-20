#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
响应生成器模块，负责根据上下文和思考过程生成最终的回复消息。
"""

import logging
import random
from typing import Any, Dict, List, Optional # <--- 移除未使用的 Union

from linjing.adapters.message_types import Message, MessageSegment
from linjing.processors.base_processor import BaseProcessor
from linjing.processors.message_context import MessageContext
from linjing.processors.processor_registry import ProcessorRegistry
# from linjing.processors.base_processor import BaseProcessor as Processor # <--- 别名 Processor 未使用

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
        name: str, # 添加 name 参数
        config: Dict[str, Any],
        # priority: int = 300, # <--- 移除未使用的 priority 参数
    ) -> None:
        """
        初始化响应生成器。

        Args:
            name: 处理器名称。
            config: 配置字典，包含生成回复所需的参数。
        """
        # 调用父类的 __init__，并传递 name 和 config
        super().__init__(name=name, config=config) # 显式传递 name 和 config
        self.llm_manager = None
        self.personality = None # 预期由 LinjingBot 设置 (当前未实现)

        # --- 从处理器配置 (self.config) 加载参数 ---
        # 加载 Prompt 模板
        prompts_config = self.config.get("prompts", {}).get(self.name, {}) # 使用 self.name 获取对应配置
        self.response_prompt_template = prompts_config.get("response_prompt", "")
        self.fallback_prompt_template = prompts_config.get("fallback_prompt", "")

        # 加载其他配置项
        self.max_history = self.config.get("max_history", 5) # 用于格式化历史记录
        self.fallback_responses = self.config.get("fallback_responses", [ # LLM 失败时的备用回复列表
            "抱歉，我没能完全理解您的意思，能请您再说明一下吗？",
            "不好意思，我没太明白您的意思，可以请您换个方式表达吗？",
            "抱歉，我可能理解有误，您能再详细说明一下您的需求吗？",
        ])
        self.error_responses = self.config.get("error_responses", [ # 内部错误时的回复列表
            "抱歉，我遇到了一些技术问题，无法正常回复您的消息。",
            "对不起，处理您的请求时出现了错误，请稍后再试。",
        ])
        self.default_emoji = self.config.get("default_emoji", "😊") # 添加风格化表情时使用
        self.response_template = self.config.get("response_template", "{response}") # 回复包装模板
        self.use_multimodal = self.config.get("use_multimodal", True) # 是否处理多模态内容
        self.style_factor = self.config.get("style_factor", 0.8) # 添加风格元素的概率因子

        # 获取角色名 (优先从处理器配置获取，其次尝试从全局配置，最后默认)
        # TODO: 确认 character_name 的最佳获取方式 (全局配置 vs 处理器配置)
        self.character_name = self.config.get("character_name") # 尝试从处理器配置获取
        if not self.character_name:
             global_config = self.config.get("global_config", {}) # 假设全局配置通过 'global_config' 键传递
             self.character_name = global_config.get("bot", {}).get("name", "灵镜") # 尝试从全局获取


        if not self.response_prompt_template:
             logger.error("未能从配置中加载 ResponseComposer response_prompt 模板！")
             self.response_prompt_template = "错误：缺少 ResponseComposer 回复 Prompt 模板。"
        if not self.fallback_prompt_template:
             logger.error("未能从配置中加载 ResponseComposer fallback_prompt 模板！")
             self.fallback_prompt_template = "错误：缺少 ResponseComposer 备用 Prompt 模板。"
        logger.debug(f"{name} max_history 设置为: {self.max_history}")


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

            # 在使用 reply 创建 MessageSegment 之前，记录它的原始值和类型
            logger.debug(f"原始回复内容 (来自 _generate_response): {repr(reply)}")
            logger.debug(f"原始回复内容的类型: {type(reply)}")

            # 将生成的回复添加到上下文
            reply_message = Message()
            # 确保 reply 是字符串类型再创建 Text Segment，否则记录错误并使用空字符串
            if isinstance(reply, str):
                reply_message.append(MessageSegment.text(reply))
            else:
                logger.error(f"_generate_response 返回了非字符串类型: {type(reply)}，内容: {repr(reply)}。将使用空文本。")
                reply_message.append(MessageSegment.text("")) # 使用空字符串避免后续错误
            
            logger.debug("准备检查并添加多模态内容...")
            # 如果配置允许且上下文中存在多模态内容，则添加到回复消息中
            if self.use_multimodal and context.get_state("multimodal_content"):
                await self._add_multimodal_content(reply_message, context)
            logger.debug("多模态内容处理完毕 (如果需要)。")
            
            # 在设置响应之前，详细记录将要设置的 reply_message 内容
            reply_text_for_log = reply_message.extract_plain_text() # 提取纯文本内容用于日志
            logger.debug(f"最终生成的回复消息对象 (纯文本): '{reply_text_for_log}'") # 记录纯文本
            logger.debug(f"最终生成的回复消息对象 (完整结构): {reply_message}") # 记录完整结构

            logger.debug(f"准备将回复对象设置到 context: {reply_message}") # 保留原有日志
            # 使用 create_response 来设置最终响应，而不是 set_state
            context.create_response(reply_message)
            # 保留 set_state 以防其他地方可能用到，但主要依赖 create_response
            context.set_state("reply", reply_message)
            # 使用提取的纯文本更新日志信息
            logger.info(f"已生成回复并设置到 context: {reply_text_for_log[:50]}{'...' if len(reply_text_for_log) > 50 else ''}")
            
        except Exception as e:
            logger.error(f"生成回复时出错: {e}", exc_info=True)
            # 发生错误时，也使用 create_response 设置错误回复
            error_reply_message = Message(MessageSegment.text(self._generate_error_response()))
            context.create_response(error_reply_message)
            # 同时保留错误状态
            context.set_state("reply", error_reply_message)

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
        # **新增：记录发送给 LLM (chat 任务) 的完整提示词**
        logger.debug(f"构建的回复生成提示词 (发送给 LLM):\n--- PROMPT START ---\n{prompt}\n--- PROMPT END ---")

        # 如果有LLM管理器，使用LLM生成回复
        if self.llm_manager:
            try:
                response, metadata = await self.llm_manager.generate_text(
                    prompt,
                    task="chat",  # 回复生成是对话任务
                    max_tokens=self.config.get("max_tokens", 1000) # 从配置读取 token 限制
                )
                # **新增：记录从 LLM (chat 任务) 返回的原始响应**
                logger.debug(f"LLM 返回的原始回复文本: {repr(response)}")

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
        构建用于生成回复的提示词，适配新的 current_mind_info JSON 输入和 v12_style_guide。
        
        Args:
            context: 消息上下文
            thought: 思考结果 (现在应为 current_mind_info JSON 字符串)
            
        Returns:
            格式化后的提示词
        """
        # 获取历史记录
        history_list = context.history if hasattr(context, 'history') else []
        history = self._format_history(history_list)
        
        # 获取用户消息文本
        user_message_text = context.message.extract_plain_text() if hasattr(context, 'message') else ""

        # 获取风格指南 (依赖于 LinjingBot 正确加载并传递)
        # TODO: 修复 LinjingBot 中的配置加载逻辑
        v12_style_guide = self.config.get("v12_style_guide", "错误：风格指南未加载！")

        # 获取关系信息 (当前为 TODO)
        relation_prompt_all = ""  # TODO: 从 MemoryManager 获取

        # 获取当前情绪状态 (当前为 TODO)
        mood_prompt = self._format_emotion(context) # 复用格式化方法，可能需要调整
        
        try:
            # 确保从 self.config 获取最新的 prompts 数据
            current_prompts = self.config.get("prompts", {})
            self.response_prompt_template = current_prompts.get("response_composer", {}).get("response_prompt", self.response_prompt_template)

            if not self.response_prompt_template or "错误：" in self.response_prompt_template:
                 logger.error("ResponseComposer response_prompt 模板无效或未加载，无法构建 Prompt。")
                 return "错误：ResponseComposer response_prompt 模板无效。"

            prompt = self.response_prompt_template.format(
                history=history,
                user_identifier=context.message.get_meta("user_display_name") or str(context.user_id),
                message_content=user_message_text,
                current_mind_info=thought,  # 现在传入完整的 JSON 字符串
                v12_style_guide=v12_style_guide,       # 对应 {v12_style_guide}
                relation_prompt_all=relation_prompt_all, # 对应 {relation_prompt_all} (TODO)
                mood_prompt=mood_prompt,               # 对应 {mood_prompt} (TODO)
                character_name=self.character_name     # 对应 {character_name}
            )
        except KeyError as e:
             logger.error(f"构建 ResponseComposer response_prompt 时缺少占位符: {e}。模板: {self.response_prompt_template}")
             prompt = f"错误：构建 Prompt 失败，缺少占位符 {e}。"
        except Exception as e:
             logger.error(f"构建 ResponseComposer response_prompt 时发生未知错误: {e}", exc_info=True)
             prompt = "错误：构建 Prompt 时发生未知错误。"

        return prompt

    def _format_history(self, history: List[Dict[str, Any]]) -> str:
        """
        格式化历史对话记录，确保与read_air和thought_generator格式一致。
        
        Args:
            history: 历史对话列表
            
        Returns:
            格式化后的历史对话文本
        """
        if not history:
            return "无历史对话"
        
        formatted_history = []
        # 使用 self.max_history 限制历史记录长度
        for msg in history[-self.max_history:]:
            # 统一处理 Message 对象
            if isinstance(msg, Message):
                 is_user = msg.get_meta("is_user", False)
                 role = "用户" if is_user else f"我 ({self.character_name})"
                 user_identifier = msg.get_meta("user_display_name") or str(msg.user_id)
                 if is_user:
                     role = f"用户 ({user_identifier})"
                 content = msg.extract_plain_text()
                 formatted_history.append(f"{role}: {content}")
            # 兼容旧的字典格式 (以防万一)
            elif isinstance(msg, dict):
                 if "user" in msg:
                     user_identifier = msg.get("user_identifier", "用户")
                     formatted_history.append(f"用户 ({user_identifier}): {msg['user']}")
                 elif msg.get("role") == "user":
                     user_identifier = msg.get("user_identifier", "用户")
                     formatted_history.append(f"用户 ({user_identifier}): {msg['content']}")
                 elif "bot" in msg:
                     formatted_history.append(f"我 ({self.character_name}): {msg['bot']}")
                 elif msg.get("role") == "bot":
                     formatted_history.append(f"我 ({self.character_name}): {msg['content']}")
        
        return "\n".join(formatted_history)

    # 移除已弃用的 _format_personality_traits 方法
    # def _format_personality_traits(self) -> str:
    #     """
    #     格式化人格特质 (已弃用)。
    #     """
    #     return "友好、乐于助人"

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
        
        # --- 添加风格化元素 (基于概率和配置) ---
        # 注意：当前 self.personality 为 None，此部分逻辑无效。
        # 需要修复 LinjingBot 中的配置加载和传递。
        # 假设 personality 对象未来会提供 get_preference 方法。
        if self.personality and random.random() < self.style_factor:
            try:
                # 获取 emoji 使用倾向 (假设方法存在)
                emoji_tendency = self.personality.get_preference("emoji_usage", 0.0)
                # 根据倾向随机决定是否添加表情 (乘以 0.5 降低频率)
                if emoji_tendency > 0.1 and random.random() < (emoji_tendency * 0.5):
                     # 使用配置的默认表情
                     formatted_response += f" {self.default_emoji}"

                # TODO: 实现或移除添加短语的逻辑 (当前 personality 无此功能)
                # phrase_tendency = self.personality.get_preference("phrase_usage", 0.0)
                # if phrase_tendency > 0.1 and random.random() < phrase_tendency:
                #     phrases = self.personality.get_phrases() # 假设方法存在
                #     if phrases:
                #         formatted_response += f" {random.choice(phrases)}"
            except AttributeError as e:
                 logger.warning(f"尝试访问 personality 对象的属性或方法失败: {e}。跳过风格化。")
            except Exception as e:
                 logger.error(f"添加风格化元素时出错: {e}", exc_info=True)
        
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
        
        # 尝试从 thought 字符串中提取标记为 "回复:", "答案:", "结论:" 的行
        # 这是一个简单的启发式方法，可能不够健壮
        for line in lines:
            # 跳过常见的思考过程标记行
            if line.startswith(("思考:", "分析:", "推理:", "计划:", "#", "//")):
                continue
            # 提取标记为回复的行
            if line.startswith(("回复:", "答案:", "结论:")):
                # 取冒号后的内容
                response_lines.append(line.split(":", 1)[-1].strip())
            # 保留其他非空、非注释的行作为可能的回复内容
            elif line:
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
                # **修改：从配置加载模板并格式化**
                try:
                    # 确保从 self.config 获取最新的 prompts 数据
                    current_prompts = self.config.get("prompts", {})
                    self.fallback_prompt_template = current_prompts.get("response_composer", {}).get("fallback_prompt", self.fallback_prompt_template) # 更新模板

                    if not self.fallback_prompt_template or "错误：" in self.fallback_prompt_template:
                         logger.error("ResponseComposer fallback_prompt 模板无效或未加载，无法构建 Prompt。")
                         # 如果模板加载失败，直接返回同步生成的备用回复
                         return self._generate_fallback_response_sync()

                    prompt = self.fallback_prompt_template.format(
                        user_message=user_message,
                        character_name=self.character_name
                    )
                except KeyError as e:
                     logger.error(f"构建 ResponseComposer fallback_prompt 时缺少占位符: {e}。模板: {self.fallback_prompt_template}")
                     return self._generate_fallback_response_sync() # 模板错误时回退
                except Exception as e:
                     logger.error(f"构建 ResponseComposer fallback_prompt 时发生未知错误: {e}", exc_info=True)
                     return self._generate_fallback_response_sync() # 未知错误时回退

                # **新增：记录备用回复的提示词**
                logger.debug(f"构建的备用回复提示词 (发送给 LLM):\n--- PROMPT START ---\n{prompt}\n--- PROMPT END ---")

                response, metadata = await self.llm_manager.generate_text(
                    prompt,
                    task="chat",  # 备用回复也是对话任务
                    max_tokens=self.config.get("max_tokens", 1000) # 从配置读取 token 限制
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
        同步方式从预定义的列表中随机选择一个备用回复。

        Returns:
            备用回复文本。
        """
        # 使用从配置中读取的 fallback_responses 列表
        if not self.fallback_responses:
             # 如果配置为空，提供一个硬编码的默认值
             logger.warning("配置中未找到 fallback_responses，使用硬编码的默认回复。")
             return "抱歉，我不太明白您的意思。"
        return random.choice(self.fallback_responses)

    def _generate_error_response(self) -> str:
        """
        发生技术错误时生成错误回复。

        Returns:
            错误回复文本
        """
        # 使用从配置中读取的 error_responses 列表
        if not self.error_responses:
             # 如果配置为空，提供一个硬编码的默认值
             logger.warning("配置中未找到 error_responses，使用硬编码的默认回复。")
             return "抱歉，处理时遇到问题。"
        return random.choice(self.error_responses)

    async def _add_multimodal_content(self, message: Message, context: MessageContext) -> None:
        """
        向回复中添加多模态内容（如图片、音频等）。

        Args:
            message: 回复消息
            context: 消息上下文
        """
        # 从 context state 获取由其他处理器可能添加的多模态内容列表
        multimodal_content = context.get_state("multimodal_content", []) # 默认为空列表

        if not multimodal_content:
             logger.debug("上下文中没有多模态内容需要添加。")
             return # 没有内容则直接返回

        logger.debug(f"开始处理 {len(multimodal_content)} 个多模态内容项...")
        for item in multimodal_content:
            # 确保 item 是字典并且包含 type 和 data
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
