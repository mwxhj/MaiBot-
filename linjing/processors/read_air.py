#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
读空气处理器模块，用于理解对话语境和隐含意图。
"读空气"是指能够理解对话中未明确表达的情感、意图和社交期望。
"""

import json
from typing import Any, Dict, List, Optional, Tuple

from linjing.adapters import Message
from linjing.processors.base_processor import BaseProcessor
from linjing.processors.message_context import MessageContext
from linjing.processors.processor_registry import ProcessorRegistry
from linjing.utils.logger import get_logger

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
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化读空气处理器
        
        Args:
            config: 处理器配置
        """
        super().__init__(config)
        
        # 置信度阈值，低于此值的分析结果将被忽略
        self.confidence_threshold = self.config.get("confidence_threshold", 0.6)
        
        # 最大历史消息数量
        self.max_history = self.config.get("max_history", 10)
        
        # LLM 管理器，用于调用语言模型
        self.llm_manager = None
    
    def set_llm_manager(self, llm_manager: Any) -> None:
        """
        设置LLM管理器
        
        Args:
            llm_manager: LLM管理器实例
        """
        self.llm_manager = llm_manager
    
    async def process(self, context: MessageContext) -> MessageContext:
        """
        处理消息上下文，分析对话语境和隐含意图
        
        Args:
            context: 消息上下文
            
        Returns:
            处理后的消息上下文
        """
        # 检查LLM管理器是否已设置
        if not self.llm_manager:
            logger.warning("LLM管理器未设置，跳过读空气处理")
            return context
        
        # 获取消息文本和历史
        message_text = context.message.extract_plain_text()
        history = self._prepare_history(context)
        
        # 记录处理信息
        context.log_processor(
            self.name, 
            f"分析消息: '{message_text[:50]}{'...' if len(message_text) > 50 else ''}'"
        )
        
        try:
            # 分析消息的情感、意图和社交期望
            analysis = await self._analyze_message(message_text, history)
            
            # 如果分析成功，将结果添加到上下文
            if analysis:
                context.set_state("read_air_analysis", analysis)
                
                # 记录主要分析结果
                intent = analysis.get("intent", {})
                emotion = analysis.get("emotion", {})
                social = analysis.get("social_context", {})
                
                intent_summary = f"意图: {intent.get('primary', '未知')} "
                intent_summary += f"({intent.get('confidence', 0):.2f})"
                
                emotion_summary = "情感: " + ", ".join(
                    [f"{k}: {v:.2f}" for k, v in emotion.items() 
                     if v > self.confidence_threshold]
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
            logger.error(f"读空气处理失败: {str(e)}", exc_info=True)
            context.log_processor(self.name, f"处理失败: {str(e)}")
        
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
        
        # 限制历史消息数量
        recent_history = context.history[-self.max_history:] if context.history else []
        
        # 格式化历史消息
        for msg in recent_history:
            history.append({
                "role": "user" if msg.get_meta("is_user", False) else "bot",
                "content": msg.extract_plain_text(),
                "timestamp": msg.timestamp() or 0
            })
        
        return history
    
    async def _analyze_message(
        self, message: str, history: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        分析消息的情感、意图和社交期望
        
        Args:
            message: 消息文本
            history: 历史消息列表
            
        Returns:
            分析结果，包含情感、意图和社交期望
        """
        if not message.strip():
            return None
        
        # 构建提示词
        prompt = self._build_analysis_prompt(message, history)
        
        try:
            # 调用LLM进行分析，指定任务类型为read_air以使用合适的模型
            response, metadata = await self.llm_manager.generate_text(
                prompt, 
                max_tokens=800,
                task="read_air"  # 使用任务路由机制选择合适的模型
            )
            
            # 记录使用的模型信息
            router_info = metadata.get("router_info", {})
            if router_info:
                model_id = router_info.get("model_id")
                logger.debug(f"读空气分析使用模型: {model_id}")
            
            # 解析JSON响应
            return self._parse_analysis_response(response)
        
        except Exception as e:
            logger.error(f"消息分析失败: {str(e)}", exc_info=True)
            return None
    
    def _build_analysis_prompt(self, message: str, history: List[Dict[str, Any]]) -> str:
        """
        构建分析提示词
        
        Args:
            message: 消息文本
            history: 历史消息列表
            
        Returns:
            分析提示词
        """
        # 将历史消息格式化为文本
        history_text = ""
        for i, msg in enumerate(history):
            role = "用户" if msg["role"] == "user" else "机器人"
            history_text += f"{role}: {msg['content']}\n"
        
        # 构建提示词
        prompt = f"""作为一个擅长理解对话语境的AI，请分析以下消息的情感、意图和社交期望。

历史对话:
{history_text}

当前消息:
用户: {message}

请分析以下内容并以JSON格式返回:
1. 情感(emotion): 识别消息中表达的主要情感(例如: 快乐、悲伤、愤怒、恐惧、惊讶等)，并给出置信度(0-1)
2. 意图(intent): 识别用户的主要意图和次要意图，并给出置信度
3. 社交期望(social_context): 分析用户的社交期望，例如是否期望同理心、解决问题、信息分享等
4. 隐含信息(implicit): 捕捉消息中未明确表达但可能隐含的信息

格式示例:
```json
{
  "emotion": {
    "happy": 0.8,
    "anxious": 0.3
  },
  "intent": {
    "primary": "寻求信息",
    "secondary": "表达担忧",
    "confidence": 0.85
  },
  "social_context": {
    "expectation": "希望得到准确信息并减轻焦虑",
    "relationship_building": true
  },
  "implicit": {
    "concerns": ["担心结果", "缺乏信息"],
    "confidence": 0.7
  }
}
```

请确保返回JSON格式正确，不要包含额外的解释或文本。"""

        return prompt
    
    def _parse_analysis_response(self, response: str) -> Optional[Dict[str, Any]]:
        """
        解析LLM分析响应
        
        Args:
            response: LLM响应文本
            
        Returns:
            解析后的分析结果
        """
        try:
            # 尝试提取JSON部分
            if "```json" in response:
                json_content = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_content = response.split("```")[1].strip()
            else:
                json_content = response.strip()
            
            # 解析JSON
            analysis = json.loads(json_content)
            return analysis
        
        except (json.JSONDecodeError, IndexError) as e:
            logger.error(f"解析分析响应失败: {str(e)}\nResponse: {response}")
            return None 