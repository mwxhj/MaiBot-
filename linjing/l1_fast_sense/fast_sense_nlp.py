# linjing/l1_fast_sense/fast_sense_nlp.py
import asyncio
import json
import re # 导入 re
from typing import Dict, Any, List, Optional

# 假设 L3 使用的 LLM 接口和 Prompt Assembler
# from ..llm.llm_interface import LLMInterface # 假设存在
# from ..processors.prompt_assembler import PromptAssembler # 假设存在
# 暂时使用 Any 作为类型提示占位符
LLMInterface = Any
PromptAssembler = Any

from linjing.utils.logger import get_logger

logger = get_logger(__name__)

class FastSenseNLPModule:
    """
    L1 轻量级 NLP 分析模块 (基于 LLM 实现)。
    负责调用 LLM 快速提取文本的基础特征。
    """
    def __init__(self,
                 llm_interface: LLMInterface,
                 prompt_assembler: PromptAssembler,
                 config: Optional[Dict[str, Any]] = None):
        """
        初始化 FastSenseNLPModule (LLM 版本)。

        Args:
            llm_interface: 用于调用 LLM 的接口实例。
            prompt_assembler: 用于组装 Prompt 的实例。
            config: 可选的配置字典，可包含 L1 使用的 LLM 模型名称等。
        """
        self.llm_interface = llm_interface
        self.prompt_assembler = prompt_assembler
        self.config = config or {}
        self.l1_model_name = self.config.get("l1_llm_model", "default_fast_model") # 假设配置中指定 L1 模型
        self.prompt_key = "fast_sense_processor.analysis_prompt" # 定义使用的 Prompt Key
        logger.info(f"FastSenseNLPModule (LLM Version) 初始化完成，使用模型: {self.l1_model_name}")

    async def process(self, text: str) -> Dict[str, Any]:
        """
        处理输入的文本，通过调用 LLM 执行快速 NLP 分析。

        Args:
            text: 需要分析的原始文本字符串。

        Returns:
            一个包含 LLM 分析结果的字典，结构尽量符合 L1 Prompt 的要求
            (例如，返回 `routing_assessment` 中 `basic_analysis` 部分的内容)。
            如果 LLM 调用失败或解析错误，返回空字典或包含错误信息的字典。
        """
        logger.debug(f"FastSenseNLPModule (LLM) 开始处理文本 (长度: {len(text)}): '{text[:50]}...'")
        if not text or not text.strip():
            logger.debug("输入文本为空，返回空结果。")
            return {}

        try:
            # 1. 准备 Prompt 上下文数据
            # 注意：当前只传递了文本。如果 L1 Prompt 严格需要 history_snippet 等，
            # 需要修改此处的 context_data 或由 FastSenseProcessor 提供。
            context_data = {
                "message_batch_or_single": text, # 映射到 Prompt 中的变量
                # "history_snippet": "...", # 占位符 - 需要实现获取逻辑
                # "sender_basic_info": {} # 占位符 - 需要实现获取逻辑
            }

            # 2. 组装 Prompt
            prompt = self.prompt_assembler.assemble(self.prompt_key, context_data)
            if not prompt:
                logger.error(f"无法为 key '{self.prompt_key}' 组装 Prompt。")
                return {"error": "Prompt assembly failed"}

            logger.trace(f"组装好的 L1 分析 Prompt:\n{prompt}") # Trace 级别记录完整 Prompt

            # 3. 调用 LLM
            # 注意：llm_interface.invoke 可能需要传入 model_name 和其他配置
            llm_config = self.config.get("l1_llm_config", {}) # 获取 L1 LLM 的特定配置
            llm_response_str = await self.llm_interface.invoke(
                prompt=prompt,
                model_name=self.l1_model_name,
                config=llm_config # 传递 L1 特定配置
                # 可能还需要指定 stop sequences 或 max_tokens 来控制输出
            )

            if not llm_response_str:
                logger.error("LLM 调用没有返回任何内容。")
                return {"error": "LLM invocation returned empty response"}

            logger.trace(f"LLM 返回的原始字符串:\n{llm_response_str}")

            # 4. 解析 LLM 返回的 JSON
            # 尝试从返回的字符串中提取 JSON 部分 (LLM 可能在 JSON 前后包含其他文本)
            json_match = re.search(r'\{.*\}', llm_response_str, re.DOTALL)
            if not json_match:
                 logger.error(f"无法从 LLM 响应中提取 JSON: {llm_response_str}")
                 return {"error": "Failed to extract JSON from LLM response"}

            analysis_results_json = json_match.group(0)

            try:
                analysis_results = json.loads(analysis_results_json)
                logger.debug(f"成功解析 LLM 返回的 JSON: {analysis_results}")

                # 5. 提取需要的分析结果 (例如 basic_analysis 部分)
                # 根据 prompts.yaml 中 L1 Prompt 的输出格式要求调整
                basic_analysis = analysis_results.get("basic_analysis", {})
                # 也可以返回整个 analysis_results，让 FastSenseProcessor 选择需要的部分
                # return analysis_results
                return basic_analysis # 返回 basic_analysis 部分

            except json.JSONDecodeError as json_e:
                logger.error(f"解析 LLM 返回的 JSON 时失败: {json_e}\n原始 JSON 字符串: {analysis_results_json}", exc_info=True)
                return {"error": "JSON decode failed", "raw_json": analysis_results_json}

        except Exception as e:
            logger.error(f"FastSenseNLPModule (LLM) 处理文本时发生未知错误: {e}", exc_info=True)
            return {"error": f"Unknown error during processing: {e}"} 