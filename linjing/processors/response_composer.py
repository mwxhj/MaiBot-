#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
响应生成器模块，负责根据上下文和思考过程生成最终的回复消息。
"""

import logging
import random
from typing import Any, Dict, List, Optional, Tuple

from linjing.adapters.message_types import Message, MessageSegment
from linjing.processors.base_processor import BaseProcessor
from linjing.processors.message_context import MessageContext
from linjing.processors.processor_registry import ProcessorRegistry
from linjing.llm.llm_manager import LLMManager
from linjing.memory.memory_manager import MemoryManager
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
        self.llm_manager: Optional[LLMManager] = None
        self.memory_manager: Optional[MemoryManager] = None
        self.personality = None # 预期由 LinjingBot 设置 (当前未实现)

        # --- 从处理器配置 (self.config) 加载参数 ---
        # 加载 Prompt 模板 (prompts 已被注入到 self.config['prompts'])
        prompts_config = self.config.get("prompts", {}) # 直接获取 prompts 字典
        self.response_prompt_template = ""
        self.fallback_prompt_template = ""
        
        if prompts_config:
            # 尝试获取回复提示词模板
            self.response_prompt_template = prompts_config.get("response_prompt", "")
            if self.response_prompt_template:
                logger.debug(f"{self.name} 成功加载 response_prompt 模板 (长度: {len(self.response_prompt_template)})")
            else:
                logger.error(f"{self.name} 无法从配置中找到 response_prompt 模板!")
            
            # 尝试获取备用提示词模板
            self.fallback_prompt_template = prompts_config.get("fallback_prompt", "")
            if self.fallback_prompt_template:
                logger.debug(f"{self.name} 成功加载 fallback_prompt 模板 (长度: {len(self.fallback_prompt_template)})")
            else:
                logger.error(f"{self.name} 无法从配置中找到 fallback_prompt 模板!")

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
        self.max_tokens = self.config.get("max_tokens", 4096)
        self.temperature = self.config.get("temperature", 0.7)
        self.max_length = self.config.get("max_length", 500)
        self.format_response = self.config.get("format_response", True)
        self.filter_sensitive = self.config.get("filter_sensitive", True)
        logger.info(f"{name} 响应生成器已初始化，最大回复长度: {self.max_length} 字符")

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


    def set_llm_manager(self, llm_manager: LLMManager) -> None:
        """
        设置LLM管理器。

        Args:
            llm_manager: 语言模型管理器实例
        """
        self.llm_manager = llm_manager
        logger.debug(f"{self.name} LLM管理器已设置到 {self.name}")

    def set_memory_manager(self, memory_manager: MemoryManager) -> None:
        """设置记忆管理器"""
        self.memory_manager = memory_manager
        logger.debug(f"{self.name} 记忆管理器已设置到 {self.name}")

    # 已移除 set_personality 方法

    async def process(self, context: MessageContext) -> MessageContext:
        """
        处理消息上下文，生成最终回复。

        Args:
            context: 消息上下文

        Returns:
            更新后的消息上下文，包含生成的回复
        """
        print("!!! DEBUG PRINT: ResponseComposer process ENTERED !!!", flush=True) # 添加 print 标记
        logger.info("--- ResponseComposer process method entered ---") # 入口标记
        # --- 新增：使用 bind 记录输入的 thoughts/context ---
        # 假设核心想法/上下文存储在 context.get_state('thought') 或类似的结构化数据中
        # 需要确认 `thought` 的具体来源和格式，这里假设它是包含核心信息的 dict 或 JSON str
        thought_data = context.get_state("thought") 
        # 尝试获取传递给此处理器的完整 current_mind_info (如果存在)
        # 注意：这依赖于之前的处理器（如ThoughtGenerator）将它存储在context中
        current_mind_info = context.get_state("current_mind_info") # 假设键名为 current_mind_info
        
        if current_mind_info:
             # 优先记录完整的 current_mind_info
             logger.bind(thought_input=current_mind_info).debug("接收到上下文 (current_mind_info)")
        elif thought_data:
             # 如果没有完整的 mind info，记录 thought_data
             logger.bind(thought_input=thought_data).debug("接收到上下文 (thought_data)")
        else:
             # 如果两者都没有，记录一个警告
             logger.warning("ResponseComposer 未在 context 中找到 'thought' 或 'current_mind_info' 状态数据")
        # --- 日志记录结束 ---
        logger.info("开始生成回复消息")
        
        reply = None # 初始化 reply 变量
        reply_message = None # 初始化 reply_message 变量

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

            # --- Setting the response ---
            logger.debug(f"准备将回复对象设置到 context: {reply_message}") # 保留原有日志
            # This is the main way to set the response for the bot to send
            try:
                context.create_response(reply_message)
                logger.info(f"成功调用 context.create_response. context.response 类型: {type(context.response)}, 内容: {context.response}") # 检查调用后状态
            except Exception as cr_err:
                 logger.error(f"调用 context.create_response 时出错: {cr_err}", exc_info=True)
                 # 即使 create_response 失败，也尝试设置状态以供调试
            
            # This sets a state variable, might be redundant or used elsewhere
            logger.debug("尝试调用 context.set_state('reply', ...)") # 原日志保持 debug
            try:
                context.set_state("reply", reply_message)
                logger.debug("成功调用 context.set_state('reply').") # 原日志保持 debug
            except Exception as cs_err:
                logger.error(f"调用 context.set_state('reply') 时出错: {cs_err}", exc_info=True)
            
            # logger.info(f"已生成回复并设置到 context: {reply_text_for_log[:50]}{'...'} ") # 这行日志现在可能引起混淆，注释掉
            
        except Exception as e: # 这个 except 块捕获 process 方法的主要流程错误
            logger.error(f"生成回复时出错 (Outer Try Block): {e}", exc_info=True)
            context.set_state("reply_generation_error", True) # 设置错误标志

        print("!!! DEBUG PRINT: ResponseComposer process FINISHING !!!", flush=True) # 添加 print 标记
        logger.info("--- ResponseComposer process method finishing ---") # 出口标记
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
        prompt = await self._build_prompt(context, thought)
        # **新增：记录发送给 LLM (chat 任务) 的完整提示词**
        logger.debug(f"构建的回复生成提示词 (发送给 LLM):\n--- PROMPT START ---\n{prompt}\n--- PROMPT END ---")

        # 如果有LLM管理器，使用LLM生成回复
        if self.llm_manager:
            try:
                response, metadata = await self.llm_manager.generate_text(
                    prompt,
                    task=self.name,  # 使用处理器名称作为任务类型
                    max_tokens=self.max_tokens,
                    temperature=self.temperature
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

    async def _build_prompt(self, context: MessageContext, thought: str) -> str:
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

        # 获取风格指南 (由 LinjingBot 注入到 self.config)
        v12_style_guide = self.config.get("v12_style_guide", "错误：风格指南未在配置中找到！")
        if "错误：" in v12_style_guide:
             logger.error("未能从配置中获取 v12_style_guide！Prompt 将不完整。")

        # 尝试获取关系信息 (现在使用 await)
        relation_prompt_all = ""
        if hasattr(self, "_format_relationship"):
            try:
                # 直接 await 调用异步方法
                relation_prompt_all = await self._format_relationship(context)
                logger.debug(f"为响应生成获取到关系信息: {relation_prompt_all}")
            except Exception as e:
                logger.error(f"异步获取关系信息失败: {e}", exc_info=True)
                relation_prompt_all = "关系信息获取失败"

        # 获取当前情绪状态
        mood_prompt = self._format_emotion(context)
        
        # 获取对话目标 (处理缺失情况)
        chat_target = context.get_state("chat_target", "无特定目标") # 从 state 获取，提供默认值

        try:
            # 使用初始化时加载好的模板，避免运行时重新获取
            if not self.response_prompt_template or "错误：" in self.response_prompt_template:
                 logger.error("ResponseComposer response_prompt 模板无效或未加载，无法构建 Prompt。")
                 return "错误：ResponseComposer response_prompt 模板无效。"

            prompt_params = {
                "history": history,
                "user_identifier": context.message.get_meta("user_display_name") or str(context.user_id),
                "message_content": user_message_text,
                "current_mind_info": thought,  # 现在传入完整的 JSON 字符串
                "v12_style_guide": v12_style_guide,       # 对应 {v12_style_guide}
                "relation_prompt_all": relation_prompt_all, # 对应 {relation_prompt_all}
                "mood_prompt": mood_prompt,               # 对应 {mood_prompt}
                "character_name": self.character_name,     # 对应 {character_name}
                "chat_target": chat_target                # 对应 {chat_target}, Add chat_target
            }

            prompt = self.response_prompt_template.format(**prompt_params) # 使用 ** 解包

        except KeyError as e:
             # 现在 chat_target 已包含，检查是否有其他缺失
             logger.error(f"构建 ResponseComposer response_prompt 时缺少占位符: {e}。参数: {prompt_params.keys()} 模板: {self.response_prompt_template}")
             prompt = f"错误：构建 Prompt 失败，缺少占位符 {e}。"
        except Exception as e:
             logger.error(f"构建 ResponseComposer response_prompt 时发生未知错误: {e}", exc_info=True)
             prompt = "错误：构建 Prompt 时发生未知错误。"

        return prompt

    # TODO: 考虑将此方法与 ThoughtGenerator/WillingnessChecker 中的版本统一到工具类
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

    # 使用与 ThoughtGenerator 和 WillingnessChecker 统一的格式化逻辑
    def _format_history(self, history_list: List[Message]) -> str:
        """
        格式化历史消息列表，包含用户昵称和 ID
        """
        history_text = ""
        # --- 添加调试日志 ---\n        logger.debug(f\"--- ENTERING _format_history ---\")\n        logger.debug(f\"_format_history received history_list type: {type(history_list)}\")\n        if isinstance(history_list, list):\n            logger.debug(f\"_format_history history_list length: {len(history_list)}\")\n            try:\n                items_to_log = min(len(history_list), 2) # 只记录前几个，避免日志过长\n                for i in range(items_to_log):\n                    item = history_list[i]\n                    logger.debug(f\"_format_history item {i} type: {type(item)}\")\n            except Exception as log_err:\n                 logger.error(f\"Error logging history items: {log_err}\")\n        else:\n             logger.warning(f\"_format_history received non-list: {str(history_list)[:200]}...\")\n        # --- 调试日志结束 ---\n\n        # 使用 ResponseComposer 自身的 max_history 配置\n        # 这是 traceback 指向的行 (或附近)\n        try:\n             recent_history = history_list[-self.max_history:] if history_list else []\n             logger.debug(f\"Successfully sliced history_list (line 364 area)\") # 确认这行能成功执行\n        except AttributeError as e:\n             logger.error(f\"AttributeError occurred exactly at slicing (line 364 area)! history_list type: {type(history_list)}\", exc_info=True)\n             raise e # 重新抛出异常以便看到原始traceback\n        except Exception as e:\n             logger.error(f\"Unexpected error at slicing (line 364 area)! history_list type: {type(history_list)}\", exc_info=True)\n             raise e\n\n        for i, msg in enumerate(recent_history): # Add enumerate\n            # --- 添加循环内日志 ---\n            logger.debug(f\"_format_history loop {i}: msg type: {type(msg)}\")\n            # --- 循环内日志结束 ---

        # 使用 ResponseComposer 自身的 max_history 配置
        # 这是 traceback 指向的行 (或附近)
        try:
             recent_history = history_list[-self.max_history:] if history_list else []
             logger.debug(f"Successfully sliced history_list (line 364 area)") # 确认这行能成功执行
        except AttributeError as e:
             logger.error(f"AttributeError occurred exactly at slicing (line 364 area)! history_list type: {type(history_list)}", exc_info=True)
             raise e # 重新抛出异常以便看到原始traceback
        except Exception as e:
             logger.error(f"Unexpected error at slicing (line 364 area)! history_list type: {type(history_list)}", exc_info=True)
             raise e

        for i, msg in enumerate(recent_history): # Add enumerate
            # --- 添加循环内日志 ---\n            logger.debug(f\"_format_history loop {i}: msg type: {type(msg)}\")\n            # --- 循环内日志结束 ---
            logger.debug(f"_format_history loop {i}: msg type: {type(msg)}")
            # --- 循环内日志结束 ---
            is_user = msg.get_meta("is_user", False)
            try:
                 content = msg.extract_plain_text()
                 if not content: content = str(msg)
            except AttributeError:
                 content = str(msg)

            if is_user:
                user_id = None
                nickname = None
                if hasattr(msg, 'sender'):
                    user_id = getattr(msg.sender, 'user_id', None)
                    nickname = getattr(msg.sender, 'nickname', None)
                
                if nickname and user_id:
                    role = f"{nickname}({user_id})"
                elif nickname:
                    role = f"{nickname}"
                elif user_id:
                    role = f"({user_id})"
                else:
                    role = "未知用户"
            else:
                global_config = self.config.get("global_config", {}) if self.config else {}
                bot_config = global_config.get("bot", {}) if global_config else {}
                bot_name = bot_config.get("name", "林静")
                role = f"我 ({bot_name})"

            history_text += f"{role}: {content}\n"
        
        return history_text.strip() or "无相关历史对话" # <-- 修正：统一返回 "无相关历史对话"

    # 已移除弃用的 _format_personality_traits 方法

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
        # 注意：此处的风格化逻辑 (如添加 emoji) 依赖于 self.personality 对象，
        # 但目前 LinjingBot 未能正确加载和设置 self.personality。
        # 因此，这部分逻辑当前不会生效。
        # TODO: 在修复 LinjingBot 的 personality 加载后，重新审视此处的风格化逻辑，
        #       确保它与 V12 风格指南的严格要求 (特别是 Emoji 的极度克制原则) 一致。
        if self.personality and random.random() < self.style_factor:
             logger.warning("尝试添加风格化元素，但 self.personality 未设置或相关逻辑需要根据 V12 风格指南重构。")
             # 示例：如果未来 personality 对象可用，且 V12 允许在特定温和情绪下使用 Emoji
             # if should_add_emoji_based_on_mind_info_and_style_guide: # 需要额外的判断逻辑
             #    if random.random() < 0.2: # 降低概率
             #        formatted_response += f" {self.default_emoji}"
        
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
                # **修改：使用初始化时加载的模板**
                try:
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
                    task=self.name,  # 使用处理器名称作为任务类型
                    max_tokens=self.max_tokens,
                    temperature=self.temperature
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
        同步方式从配置的列表中随机选择一个备用回复。

        Returns:
            备用回复文本。
        """
        # 使用从 self.config 加载的 self.fallback_responses 列表
        if not self.fallback_responses:
             # 如果配置列表为空，提供一个最终的硬编码默认值
             logger.warning("配置中 fallback_responses 为空，使用硬编码的默认回复。")
             return "抱歉，我不太明白您的意思。"
        return random.choice(self.fallback_responses)

    def _generate_error_response(self) -> str:
        """
        发生技术错误时从配置的列表中随机选择一个错误回复。

        Returns:
            错误回复文本。
        """
        # 使用从 self.config 加载的 self.error_responses 列表
        if not self.error_responses:
             # 如果配置列表为空，提供一个最终的硬编码默认值
             logger.warning("配置中 error_responses 为空，使用硬编码的默认回复。")
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

    # --- 新增：格式化关系信息 ---
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
