#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
令牌计数器模块。

提供了用于计算不同模型的令牌数的工具。
"""

import re
import logging
from typing import Dict, List, Optional, Tuple, Union, Any

try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False

from ..utils.logger import get_logger

logger = get_logger(__name__)


class TokenCounter:
    """
    令牌计数器类，用于计算不同模型的令牌数。
    
    支持多种模型和编码方式，包括OpenAI的各种模型。
    """
    
    # 默认支持的模型和其对应的编码
    MODEL_TO_ENCODING = {
        # GPT-4 模型
        "gpt-4": "cl100k_base",
        "gpt-4-0314": "cl100k_base",
        "gpt-4-0613": "cl100k_base",
        "gpt-4-32k": "cl100k_base",
        "gpt-4-32k-0314": "cl100k_base",
        "gpt-4-32k-0613": "cl100k_base",
        "gpt-4-turbo": "cl100k_base",
        "gpt-4-0125-preview": "cl100k_base",
        "gpt-4-1106-preview": "cl100k_base",
        "gpt-4-vision-preview": "cl100k_base",
        # GPT-3.5 模型
        "gpt-3.5-turbo": "cl100k_base",
        "gpt-3.5-turbo-0301": "cl100k_base",
        "gpt-3.5-turbo-0613": "cl100k_base",
        "gpt-3.5-turbo-1106": "cl100k_base",
        "gpt-3.5-turbo-0125": "cl100k_base",
        "gpt-3.5-turbo-16k": "cl100k_base",
        "gpt-3.5-turbo-16k-0613": "cl100k_base",
        "gpt-3.5-turbo-instruct": "cl100k_base",
        # 文本嵌入模型
        "text-embedding-ada-002": "cl100k_base",
        "text-embedding-3-small": "cl100k_base",
        "text-embedding-3-large": "cl100k_base",
        # 旧版GPT-3模型
        "text-davinci-003": "p50k_base",
        "text-davinci-002": "p50k_base",
        "text-davinci-001": "r50k_base",
        "text-curie-001": "r50k_base",
        "text-babbage-001": "r50k_base",
        "text-ada-001": "r50k_base",
        "davinci": "r50k_base",
        "curie": "r50k_base",
        "babbage": "r50k_base",
        "ada": "r50k_base",
        # 代码模型
        "code-davinci-002": "p50k_base",
        "code-davinci-001": "p50k_base",
        "code-cushman-002": "p50k_base",
        "code-cushman-001": "p50k_base",
        "davinci-codex": "p50k_base",
        "cushman-codex": "p50k_base",
        # 基础编码
        "cl100k_base": "cl100k_base",
        "p50k_base": "p50k_base",
        "r50k_base": "r50k_base"
    }
    
    # 默认支持的编码方式和其对应的每条消息开销
    ENCODING_TO_MESSAGE_OVERHEAD = {
        "cl100k_base": 3,  # 比如gpt-3.5-turbo和gpt-4
        "p50k_base": 3,    # 比如text-davinci-003
        "r50k_base": 3     # 比如davinci
    }
    
    # 消息格式开销
    MESSAGE_FORMAT_OVERHEAD = {
        "gpt-3.5-turbo": 3,
        "gpt-3.5-turbo-0301": 3,
        "gpt-3.5-turbo-0613": 3,
        "gpt-3.5-turbo-1106": 3,
        "gpt-3.5-turbo-0125": 3,
        "gpt-3.5-turbo-16k": 3,
        "gpt-3.5-turbo-16k-0613": 3,
        "gpt-4": 3,
        "gpt-4-0314": 3,
        "gpt-4-0613": 3,
        "gpt-4-32k": 3,
        "gpt-4-32k-0314": 3,
        "gpt-4-32k-0613": 3,
        "gpt-4-turbo": 3,
        "gpt-4-0125-preview": 3,
        "gpt-4-1106-preview": 3,
        "gpt-4-vision-preview": 3
    }
    
    def __init__(self, default_model: str = "gpt-3.5-turbo"):
        """
        初始化令牌计数器
        
        Args:
            default_model: 默认使用的模型名称
        """
        self.default_model = default_model
        self.encoders = {}
        self.fallback_encoder = None
        
        # 检查tiktoken是否可用
        if not TIKTOKEN_AVAILABLE:
            logger.warning("tiktoken未安装，将使用简单估算方法计算令牌")
        else:
            try:
                # 初始化默认编码器
                self._get_encoder(self.default_model)
            except Exception as e:
                logger.error(f"初始化默认编码器失败: {e}")
    
    def _get_encoder(self, model: str):
        """
        获取指定模型的编码器
        
        Args:
            model: 模型名称
            
        Returns:
            编码器对象
        """
        if not TIKTOKEN_AVAILABLE:
            return None
        
        # 如果已有缓存，则直接返回
        if model in self.encoders:
            return self.encoders[model]
        
        # 获取编码名称
        encoding_name = self.MODEL_TO_ENCODING.get(model)
        if not encoding_name:
            # 如果找不到对应编码，使用默认编码
            logger.warning(f"未知模型 '{model}'，使用默认编码 'cl100k_base'")
            encoding_name = "cl100k_base"
        
        try:
            # 创建编码器
            encoder = tiktoken.get_encoding(encoding_name)
            self.encoders[model] = encoder
            
            # 保存一个备用编码器
            if self.fallback_encoder is None:
                self.fallback_encoder = encoder
                
            return encoder
        except Exception as e:
            logger.error(f"获取编码器 '{encoding_name}' 失败: {e}")
            # 如果有备用编码器，使用备用
            if self.fallback_encoder is not None:
                return self.fallback_encoder
            # 否则尝试获取cl100k_base编码器
            try:
                return tiktoken.get_encoding("cl100k_base")
            except:
                logger.error("无法获取任何编码器，将使用估算方法")
                return None
    
    def count_tokens(self, text: str, model: Optional[str] = None) -> int:
        """
        计算文本的令牌数
        
        Args:
            text: 输入文本
            model: 模型名称，默认使用初始化时指定的模型
            
        Returns:
            令牌数
        """
        if not text:
            return 0
            
        model = model or self.default_model
        
        # 使用tiktoken计算
        if TIKTOKEN_AVAILABLE:
            encoder = self._get_encoder(model)
            if encoder:
                try:
                    tokens = encoder.encode(text)
                    return len(tokens)
                except Exception as e:
                    logger.error(f"计算令牌数失败，使用估算方法: {e}")
                    # 失败时回退到估算方法
        
        # 回退到简单估算方法
        return self._estimate_tokens(text)
    
    def count_message_tokens(self, messages: List[Dict[str, str]], model: Optional[str] = None) -> Tuple[int, Dict[str, int]]:
        """
        计算聊天消息的令牌数
        
        Args:
            messages: 聊天消息列表，每个消息包含role和content字段
            model: 模型名称，默认使用初始化时指定的模型
            
        Returns:
            总令牌数和详细统计信息的元组
        """
        if not messages:
            return 0, {}
            
        model = model or self.default_model
        
        # 获取每条消息的开销
        encoding_name = self.MODEL_TO_ENCODING.get(model, "cl100k_base")
        message_overhead = self.ENCODING_TO_MESSAGE_OVERHEAD.get(encoding_name, 3)
        
        # 计算每条消息的令牌数
        token_counts = {}
        total_tokens = 0
        
        # 根据消息格式计算令牌数
        # ChatGPT格式为: <|im_start|>role\ncontent<|im_end|>
        # 每条消息的开销为3个令牌(im_start, role, im_end)
        for i, message in enumerate(messages):
            role = message.get("role", "user")
            content = message.get("content", "")
            
            # 处理content可能是列表的情况（例如包含图像等多模态内容）
            if isinstance(content, list):
                content_tokens = 0
                for item in content:
                    if isinstance(item, str):
                        content_tokens += self.count_tokens(item, model)
                    elif isinstance(item, dict) and "text" in item:
                        content_tokens += self.count_tokens(item["text"], model)
                    # 图像等其他内容的token计算
                    elif isinstance(item, dict) and "type" in item and item["type"] == "image":
                        # 根据OpenAI的规则计算图像token
                        # 对于GPT-4 Vision模型，图像token取决于尺寸和质量
                        content_tokens += self._calculate_image_tokens(item, model)
            else:
                content_tokens = self.count_tokens(content, model)
            
            # 计算本条消息的令牌数
            role_tokens = self.count_tokens(role, model)
            message_tokens = role_tokens + content_tokens + message_overhead
            
            # 记录统计信息
            message_id = f"message_{i}_{role}"
            token_counts[message_id] = message_tokens
            total_tokens += message_tokens
        
        # 添加消息格式的额外开销（如果适用）
        format_overhead = self.MESSAGE_FORMAT_OVERHEAD.get(model, 0)
        if format_overhead > 0:
            total_tokens += format_overhead
            token_counts["format_overhead"] = format_overhead
        
        return total_tokens, token_counts
    
    def _calculate_image_tokens(self, image_item: Dict[str, Any], model: str) -> int:
        """
        计算图像的令牌数
        
        Args:
            image_item: 图像项，包含类型和可能的详细信息
            model: 模型名称
            
        Returns:
            估算的令牌数
        """
        # 默认值
        base_token_count = 85  # 基础token消耗
        
        # 如果不是支持图像的模型，返回基础值
        if not model.startswith("gpt-4-vision"):
            return base_token_count
        
        image_detail = image_item.get("detail", "auto")
        
        # 图像尺寸信息（如果有）
        width = image_item.get("width", 0)
        height = image_item.get("height", 0)
        
        # 根据OpenAI的规则，图片token计算取决于尺寸和详细程度
        # 参考：https://platform.openai.com/docs/guides/vision
        if image_detail == "high":
            # 高清模式：在一个平铺的512px网格上计算
            if width > 0 and height > 0:
                # 计算图像包含的512px瓦片数
                tiles = ((width + 511) // 512) * ((height + 511) // 512)
                return base_token_count + tiles * 765  # 每个瓦片约765个token
            return 850  # 默认高清图像估算
        elif image_detail == "low":
            return 65  # 低清图像估算
        else:  # auto或其他
            if width > 0 and height > 0:
                # 计算图像面积
                area = width * height
                # 小图使用low，大图使用high的简化版
                if area <= 512 * 512:
                    return 65  # 小图使用low
                else:
                    tiles = ((width + 511) // 512) * ((height + 511) // 512)
                    return base_token_count + tiles * 170  # 每个瓦片的简化计算
            return 450  # 中等质量估算
    
    def _estimate_tokens(self, text: str) -> int:
        """
        简单估算文本的令牌数（当tiktoken不可用时使用）
        
        基于经验规则：
        - 英文文本大约1个token为4个字符
        - 中文/日文/韩文等语言大约1个字符为1-2个token
        
        Args:
            text: 输入文本
            
        Returns:
            估算的令牌数
        """
        if not text:
            return 0
        
        # 计算不同类型字符的数量
        # 英文单词
        english_words = re.findall(r'\b[a-zA-Z0-9]+\b', text)
        english_word_count = len(english_words)
        english_char_count = sum(len(word) for word in english_words)
        
        # 标点符号
        punctuation_count = len(re.findall(r'[.,!?;:"\'\(\)\[\]\{\}]', text))
        
        # 中日韩字符
        cjk_char_count = len(re.findall(r'[\u4e00-\u9fff\u3040-\u30ff\u3400-\u4dbf\uac00-\ud7af]', text))
        
        # 空白字符
        whitespace_count = len(re.findall(r'\s', text))
        
        # 其他字符
        total_chars = len(text)
        other_char_count = total_chars - english_char_count - punctuation_count - cjk_char_count - whitespace_count
        
        # 使用更精确的估算规则
        # 英文单词: 平均每个单词约1.3个token
        english_word_tokens = english_word_count * 1.3
        
        # 标点符号: 每个约0.5个token
        punctuation_tokens = punctuation_count * 0.5
        
        # 中日韩字符: 每个字符约1.5个token
        cjk_tokens = cjk_char_count * 1.5
        
        # 空白字符: 约0.25个token每个
        whitespace_tokens = whitespace_count * 0.25
        
        # 其他字符: 约0.5-1个token每个字符
        other_tokens = other_char_count * 0.75
        
        # 总token估算
        estimated_tokens = english_word_tokens + punctuation_tokens + cjk_tokens + whitespace_tokens + other_tokens
        
        # 确保至少返回1个token
        return max(1, int(estimated_tokens))
    
    def register_model(self, model_name: str, encoding_name: str) -> None:
        """
        注册新的模型和其对应的编码
        
        Args:
            model_name: 模型名称
            encoding_name: 编码名称（如cl100k_base）
        """
        if not model_name or not encoding_name:
            logger.warning("模型名称和编码名称不能为空")
            return
            
        self.MODEL_TO_ENCODING[model_name] = encoding_name
        # 清除缓存以便重新创建编码器
        if model_name in self.encoders:
            del self.encoders[model_name]
        
        logger.debug(f"注册模型 '{model_name}' 使用编码 '{encoding_name}'")
    
    def get_model_context_size(self, model: Optional[str] = None) -> int:
        """
        获取模型的最大上下文大小
        
        Args:
            model: 模型名称，默认使用初始化时指定的模型
            
        Returns:
            最大上下文大小（token数）
        """
        model = model or self.default_model
        
        # 常见模型的上下文大小，更新至2023年最新信息
        context_sizes = {
            # GPT-4
            "gpt-4": 8192,
            "gpt-4-0314": 8192,
            "gpt-4-0613": 8192,
            "gpt-4-32k": 32768,
            "gpt-4-32k-0314": 32768,
            "gpt-4-32k-0613": 32768,
            "gpt-4-turbo": 128000,  # 最新版
            "gpt-4-0125-preview": 128000,
            "gpt-4-1106-preview": 128000,
            "gpt-4-vision-preview": 128000,
            # GPT-3.5
            "gpt-3.5-turbo": 16385,  # 更新为最新版
            "gpt-3.5-turbo-0301": 4096,
            "gpt-3.5-turbo-0613": 4096,
            "gpt-3.5-turbo-1106": 16385,
            "gpt-3.5-turbo-0125": 16385,
            "gpt-3.5-turbo-16k": 16385,
            "gpt-3.5-turbo-16k-0613": 16385,
            "gpt-3.5-turbo-instruct": 4096,
            # 旧版GPT-3
            "text-davinci-003": 4097,
            "text-davinci-002": 4097,
            "text-davinci-001": 2049,
            "text-curie-001": 2049,
            "text-babbage-001": 2049,
            "text-ada-001": 2049,
            "davinci": 2049,
            "curie": 2049,
            "babbage": 2049,
            "ada": 2049,
            # Claude模型
            "claude-instant-1": 100000,
            "claude-1": 100000,
            "claude-2": 100000,
            "claude-2.1": 200000,
            "claude-3-opus": 200000,
            "claude-3-sonnet": 200000,
            "claude-3-haiku": 200000
        }
        
        # 返回模型的上下文大小，如果未知则返回默认值
        return context_sizes.get(model, 4096)
    
    def truncate_text_to_token_limit(self, text: str, limit: int, model: Optional[str] = None) -> str:
        """
        将文本截断到指定的令牌限制
        
        Args:
            text: 输入文本
            limit: 令牌限制
            model: 模型名称，默认使用初始化时指定的模型
            
        Returns:
            截断后的文本
        """
        if not text:
            return ""
            
        if limit <= 0:
            logger.warning("令牌限制必须大于0，返回空字符串")
            return ""
            
        # 检查是否需要截断
        token_count = self.count_tokens(text, model)
        if token_count <= limit:
            return text
            
        model = model or self.default_model
        
        # 使用tiktoken进行精确截断
        if TIKTOKEN_AVAILABLE:
            encoder = self._get_encoder(model)
            if encoder:
                try:
                    tokens = encoder.encode(text)
                    truncated_tokens = tokens[:limit]
                    return encoder.decode(truncated_tokens)
                except Exception as e:
                    logger.error(f"使用tiktoken截断文本失败，将使用估算方法: {e}")
        
        # 使用二分查找策略进行截断
        return self._binary_search_truncate(text, limit, model)
    
    def _binary_search_truncate(self, text: str, limit: int, model: str) -> str:
        """
        使用二分查找策略将文本截断到令牌限制
        
        Args:
            text: 输入文本
            limit: 令牌限制
            model: 模型名称
            
        Returns:
            截断后的文本
        """
        # 初始估算字符比例
        ratio = len(text) / self.count_tokens(text, model)
        estimated_chars = int(limit * ratio * 0.9)  # 预留10%的余量
        
        # 二分查找合适的截断位置
        low, high = 0, len(text)
        best_length = 0
        
        while low <= high:
            mid = (low + high) // 2
            truncated = text[:mid]
            tokens = self.count_tokens(truncated, model)
            
            if tokens <= limit:
                best_length = mid
                low = mid + 1
            else:
                high = mid - 1
        
        # 确保不会截断UTF-8多字节字符
        truncated = text[:best_length]
        
        # 如果是中文等语言，尝试在标点符号处截断以获得更自然的结果
        cjk_punctuation = r'[\u3000-\u303F\uFF00-\uFF1F]'  # 常见中文标点符号范围
        last_punc_match = list(re.finditer(cjk_punctuation, truncated[-50:]))
        
        if last_punc_match:
            # 在最后50个字符中找到标点符号，在标点后截断
            last_punc_pos = last_punc_match[-1].end() + len(truncated) - 50
            if last_punc_pos > 0:
                truncated = text[:last_punc_pos]
        
        return truncated 