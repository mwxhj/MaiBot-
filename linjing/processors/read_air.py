#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
读空气处理器模块，用于理解对话语境和隐含意图。
"读空气"是指能够理解对话中未明确表达的情感、意图和社交期望。
"""

import json
from typing import Any, Dict, List, Optional # <--- 移除未使用的 Tuple

# from linjing.adapters import Message # <--- Message 类在此文件未直接使用
from linjing.processors.base_processor import BaseProcessor
from linjing.processors.message_context import MessageContext
from linjing.processors.processor_registry import ProcessorRegistry
from linjing.utils.logger import get_logger
# from linjing.constants import ProcessorName # <--- ProcessorName 在此文件未直接使用

# 获取日志记录器
logger = get_logger(__name__)


@ProcessorRegistry.register()
class ReadAirProcessor(BaseProcessor):
    """
    读空气处理器，理解对话语境和隐含意图。
    分析消息的情感、意图以及社交期望，并添加到上下文中。
    """
    
    name = "read_air"
    description = "读空气处理器，理解对话语境和隐含意图"
    version = "1.0.0"
    
    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None): # 添加 name 参数
        """
        初始化读空气处理器
        
        Args:
            name: 处理器名称
            config: 处理器配置
        """
        # 调用父类 __init__ 时传递 name 和 config
        super().__init__(name=name, config=config)
        
        # **修改：从处理器特定配置读取 confidence_threshold**
        # 注意：self.config 是传递给处理器的配置字典，通常来自 config.yaml 的 processors.<processor_name> 部分
        self.confidence_threshold = self.config.get("confidence_threshold", 0.6)
        logger.debug(f"{self.name} confidence_threshold 设置为: {self.confidence_threshold}")
        
        # **修改：从处理器特定配置读取 max_history**
        self.max_history = self.config.get("max_history", 10)
        logger.debug(f"{self.name} max_history 设置为: {self.max_history}")
        
        # LLM 管理器，用于调用语言模型
        self.llm_manager = None
        # **新增：存储 Prompt 模板**
        # 从传入的配置中获取 read_air 处理器的 prompt 模板
        # 预期 config 结构: {"prompts": {"read_air": {"analysis_prompt": "..."}}}
        # self.config 是传递给处理器的配置字典, prompts 已被注入到 self.config['prompts']
        self.prompt_template = self.config.get("prompts", {}).get("analysis_prompt", "") # 直接从 prompts 获取
        if not self.prompt_template:
             logger.error(f"未能从配置 {self.name} 中加载 prompts.analysis_prompt 模板！将无法生成分析。")
             # 可以选择抛出异常或设置一个默认的错误提示
             # raise ValueError("Missing required prompt template: prompts.read_air.analysis_prompt")
             self.prompt_template = "错误：缺少 ReadAir 分析 Prompt 模板。" # 提供一个错误提示

    def set_llm_manager(self, llm_manager: Any) -> None:
        """
        设置LLM管理器
        
        Args:
            llm_manager: LLM管理器实例
        """
        self.llm_manager = llm_manager
    
    async def process(self, context: MessageContext) -> MessageContext:
        """
        处理消息，分析情感、意图和社交期望，并添加到上下文。
        注意：自V12起，此方法返回更详细的分析结果。
        
        Args:
            context: 消息上下文，包含当前消息和历史记录。
            
        Returns:
            添加了分析结果的消息上下文。
        """
        # 获取消息对象
        message = context.message
        
        # 提取明文文本
        message_text = message.extract_plain_text() if hasattr(message, 'extract_plain_text') else str(message)
        
        # 检查消息是否包含图片
        contains_image = False
        image_urls = []
        if hasattr(message, 'segments') and isinstance(message.segments, list):
            for segment in message.segments:
                segment_type = getattr(segment, 'type', None)
                segment_data = getattr(segment, 'data', {})
                # 检查是否为图片类型
                if segment_type and segment_type.name == "IMAGE":
                    contains_image = True
                    if "url" in segment_data:
                        image_urls.append(segment_data["url"])
                    logger.debug(f"读空气处理器检测到图片: {segment_data.get('url', '无URL')}")
        
        # 记录图片信息
        if contains_image:
            context.set_state("contains_image", True)
            context.set_state("image_urls", image_urls)
            logger.info(f"消息包含图片，总数: {len(image_urls)}")
            # 如果消息只有图片没有文本，添加提示信息
            if not message_text.strip():
                message_text = "[用户发送了一张图片，无文字说明]"
        
        # 获取历史消息用于分析
        history = self._prepare_history(context)
        
        try:
            # 分析消息的情感、意图和社交期望
            analysis = await self._analyze_message(context, message_text)
            
            # 如果分析成功，将结果添加到上下文
            if analysis:
                context.set_state("read_air_analysis", analysis)
                # **新增：将 should_reply 存入 context state**
                should_reply = analysis.get("should_reply", True) # 从解析结果获取，默认为 True
                context.set_state("should_reply", should_reply)
                logger.debug(f"读空气分析结果 - 是否应回复: {should_reply}")

                # 记录主要分析结果
                intent = analysis.get("intent", {})
                emotion = analysis.get("emotion", {})
                social = analysis.get("social_context", {})
                
                intent_summary = f"意图: {intent.get('primary', '未知')} "
                intent_summary += f"({intent.get('confidence', 0):.2f})"
                
                emotion_summary = "情感: " + ", ".join(
                    # **修改：使用 self.confidence_threshold**
                    # 同时添加类型检查以提高健壮性
                    [f"{k}: {v:.2f}" for k, v in emotion.items()
                     if isinstance(v, (int, float)) and v > self.confidence_threshold]
                )
                
                social_summary = "社交期望: " + (
                    social.get("expectation", "无明确期望")
                )
                
                context.log_processor(self.name, intent_summary)
                context.log_processor(self.name, emotion_summary)
                context.log_processor(self.name, social_summary)
            else:
                context.log_processor(self.name, "无法分析消息")
        
        except Exception as e:
            # 修改日志记录方式，避免 f-string 格式化问题
            try:
                context_dict_str = json.dumps(context.to_dict(), indent=2, ensure_ascii=False, default=str)
                logger.error(f"读空气处理失败 - 输入数据:\n{context_dict_str}", exc_info=True)
            except Exception as log_e:
                 logger.error(f"记录读空气失败日志时出错: {log_e}", exc_info=True) # 记录原始错误和日志记录错误
            context.log_processor(self.name, f"处理失败: {type(e).__name__} - {str(e)}")
        
        return context
    
    def _prepare_history(self, context: MessageContext) -> List[Dict[str, Any]]:
        """
        准备历史消息用于分析
        
        Args:
            context: 消息上下文
            
        Returns:
            格式化的历史消息列表
        """
        history = []
        
        # **修改：使用 self.max_history**
        recent_history = context.history[-self.max_history:] if context.history else []
        
        # 格式化历史消息
        for msg in recent_history:
            user_identifier = msg.get_meta("user_display_name") or str(msg.user_id)
            history.append({
                "role": "user" if msg.get_meta("is_user", False) else "bot",
                "content": msg.extract_plain_text(),
                "timestamp": msg.timestamp() or 0,
                "user_identifier": user_identifier
            })
        
        return history
    
    async def _analyze_message(
        self, context: MessageContext, message: str
    ) -> Optional[Dict[str, Any]]:
        """
        调用 LLM 分析消息的情感、意图和社交期望。

        Args:
            context: 当前消息上下文 (用于获取历史和用户信息)
            message: 需要分析的消息文本。

        Returns:
            分析结果字典，或在失败时返回 None。
        """
        if not message.strip():
            logger.debug("空消息，跳过分析")
            return None

        # 获取用户标识符(优先使用昵称，没有则用ID) - 从 context 获取
        user_identifier = context.message.get_meta("user_display_name") or str(context.user_id)
        # 准备历史记录 - 从 context 获取
        history_for_prompt = self._prepare_history(context)

        # 检查消息是否包含图片
        contains_image = context.get_state("contains_image", False)
        image_urls = context.get_state("image_urls", [])
        
        # 添加图片信息到消息文本
        if contains_image and image_urls:
            message = f"{message}\n[注意:此消息包含 {len(image_urls)} 张图片]"

        # 构建提示词 - 传递 context 以便 _build_analysis_prompt 获取历史
        prompt = self._build_analysis_prompt(context, message, user_identifier)
        
        try:
            # 调用LLM进行分析，指定任务类型为read_air以使用合适的模型
            response, metadata = await self.llm_manager.generate_text(
                prompt,
                max_tokens=self.config.get("llm_max_tokens", 1000), # 从配置读取 token 限制
                task=ProcessorName.READ_AIR  # 使用任务路由机制选择合适的模型
            )
            
            # 记录使用的模型信息
            router_info = metadata.get("router_info", {})
            if router_info:
                model_id = router_info.get("model_id")
                logger.debug(f"读空气分析使用模型: {model_id}")
            
            # 解析JSON响应
            analysis = self._parse_analysis_response(response)
            
            # 如果包含图片，添加图片分析标记
            if contains_image and analysis:
                if "metadata" not in analysis:
                    analysis["metadata"] = {}
                analysis["metadata"]["contains_image"] = True
                analysis["metadata"]["image_count"] = len(image_urls)
            
            return analysis
        
        except Exception as e:
            logger.error(f"消息分析失败: {str(e)}", exc_info=True)
            return None
    
    def _build_analysis_prompt(self, context: MessageContext, message: str, user_identifier: str = "用户") -> str:
        """
        根据模板和当前上下文构建用于 LLM 分析的提示词。

        Args:
            context: 当前消息上下文 (用于获取历史记录)。
            message: 当前需要分析的消息文本。
            user_identifier: 当前消息发送者的标识符。

        Returns:
            构建好的分析提示词字符串。
        """
        # 从 context 准备历史消息文本
        history_list = self._prepare_history(context) # 调用内部方法获取格式化历史
        history_text = ""
        for msg in history_list:
            # 使用 self.name 获取机器人名字
            role = f"用户 ({msg.get('user_identifier', '用户')})" if msg["role"] == "user" else f"我 ({self.name})"
            history_text += f"{role}: {msg['content']}\n"
        
        # 从配置加载模板并格式化
        try:
            current_prompts = self.config.get("prompts", {})
            self.prompt_template = current_prompts.get("read_air", {}).get("analysis_prompt", self.prompt_template)

            if not self.prompt_template or "错误：" in self.prompt_template:
                 logger.error("ReadAir Prompt 模板无效或未加载，无法构建 Prompt。")
                 return "错误：ReadAir Prompt 模板无效。"

            prompt = self.prompt_template.format(
                history_text=history_text,
                user_identifier=user_identifier,
                message_content=message
            )
            # YAML 加载时会处理 {{ 和 }}，所以不需要额外转义
        except KeyError as e:
             logger.error(f"构建 ReadAir Prompt 时缺少占位符: {e}。模板: {self.prompt_template}")
             # 返回一个错误提示或默认 Prompt
             prompt = f"错误：构建 Prompt 失败，缺少占位符 {e}。"
        except Exception as e:
             logger.error(f"构建 ReadAir Prompt 时发生未知错误: {e}", exc_info=True)
             prompt = "错误：构建 Prompt 时发生未知错误。"

        return prompt
    
    def _parse_analysis_response(self, response: str) -> Optional[Dict[str, Any]]:
        """
        解析LLM分析响应，适配新的JSON结构
        
        Args:
            response: LLM响应文本
            
        Returns:
            解析后的分析结果字典，包含完整的分析结构
        """
        try:
            # 尝试从 LLM 响应中提取 JSON 内容 (可能包含在代码块中)
            json_content = response.strip()
            if json_content.startswith("```json"):
                json_content = json_content[len("```json"):].strip()
            if json_content.startswith("```"): # 处理普通代码块
                json_content = json_content[len("```"):].strip()
            if json_content.endswith("```"):
                json_content = json_content[:-len("```")].strip()

            # 确保提取的内容看起来像 JSON (简单的检查)
            if not (json_content.startswith('{') and json_content.endswith('}')):
                 logger.warning(f"提取的分析内容不像有效的 JSON: {json_content[:100]}...")
                 # 可以尝试直接解析，或者返回 None
                 # return None # 如果严格要求格式

            # 解析JSON
            
            # 解析JSON
            analysis = json.loads(json_content)
            
            # 验证基本结构
            if not isinstance(analysis, dict):
                raise ValueError("分析结果不是有效的JSON对象")
                
            # 确保关键字段存在
            required_sections = [
                "message_metadata",
                "linguistic_profile",
                "cognitive_emotional_state",
                "communicative_intent",
                "logical_argument_analysis",
                "social_context_assessment",
                "v12_trigger_scan_results"
            ]
            
            for section in required_sections:
                if section not in analysis:
                    logger.warning(f"分析结果缺少关键部分: {section}")
                    analysis[section] = {}  # 提供空字典作为默认值
                    
            # 确保触发器扫描结果存在
            triggers = analysis["v12_trigger_scan_results"]
            required_triggers = [
                "triggers_linjing_disrespect_sensitivity",
                "triggers_linjing_logical_fallacy_sensitivity",
                "triggers_linjing_provocation_sensitivity",
                "triggers_linjing_personal_attack_sensitivity",
                "triggers_linjing_misinformation_sensitivity",
                "triggers_linjing_fairness_sensitivity",
                "triggers_linjing_ai_identity_sensitivity"
            ]
            
            for trigger in required_triggers:
                if trigger not in triggers:
                    logger.warning(f"分析结果缺少V12触发器: {trigger}")
                    triggers[trigger] = False  # 默认为未触发
                    
            # 添加should_reply字段（从recommended_engagement推断）
            if "overall_assessment" in analysis:
                engagement = analysis["overall_assessment"].get("recommended_engagement", "address_directly")
                analysis["should_reply"] = engagement != "ignore"
            else:
                analysis["should_reply"] = True
                
            return analysis
            
        except json.JSONDecodeError as e:
            logger.error(f"解析分析响应失败: JSON格式错误\nError: {str(e)}\nResponse: {response}")
        except Exception as e:
            logger.error(f"解析分析响应时发生意外错误: {type(e).__name__}\nError: {str(e)}\nResponse: {response}")
            
        return None

    # --- 新增：格式化关系信息 ---
    async def _format_relationship(self, context: MessageContext) -> str:
        """
        从 MemoryManager 获取关系摘要并格式化为 Prompt 字符串。

        Args:
            context: 当前消息上下文。

        Returns:
            格式化后的关系信息字符串，或在出错/无信息时返回提示。
        """
        # 直接使用 self.memory_manager
        if not self.memory_manager:
            logger.warning("无法获取关系信息：memory_manager 未设置。")
            return "关系信息：未知"

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
