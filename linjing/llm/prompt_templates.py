#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
提示词模板模块。

提供了用于创建和管理LLM提示词模板的工具。
"""

import re
import json
import logging
from string import Formatter
from typing import Dict, List, Any, Set, Optional, Union

from ..utils.logger import get_logger

logger = get_logger(__name__)


class PromptTemplate:
    """
    提示词模板类，用于创建和格式化提示词。
    
    支持变量替换、条件逻辑和格式化功能。
    """
    
    def __init__(self, template: str, required_vars: Optional[List[str]] = None):
        """
        初始化提示词模板
        
        Args:
            template: 模板字符串，包含{variable}形式的变量
            required_vars: 必需的变量列表，如果未提供则自动检测
        """
        self.template = template
        self._formatter = Formatter()
        
        # 提取所有变量名
        self._variables = set()
        for _, var_name, _, _ in self._formatter.parse(template):
            if var_name is not None:
                # 处理格式化规范，例如{var:.2f}
                base_var = var_name.split('.')[0].split('[')[0].split(':')[0]
                if base_var:  # 排除空变量名
                    self._variables.add(base_var)
        
        # 设置必需变量
        if required_vars is not None:
            self.required_vars = set(required_vars)
        else:
            self.required_vars = self._variables
    
    def format(self, **kwargs) -> str:
        """
        使用提供的变量格式化模板
        
        Args:
            **kwargs: 变量键值对
            
        Returns:
            格式化后的字符串
            
        Raises:
            ValueError: 缺少必需变量时抛出
        """
        # 验证必需变量
        missing_vars = self.required_vars - set(kwargs.keys())
        if missing_vars:
            raise ValueError(f"缺少必需变量: {', '.join(missing_vars)}")
        
        try:
            # 处理条件块
            template = self._process_conditionals(self.template, kwargs)
            # 处理循环块
            template = self._process_loops(template, kwargs)
            # 格式化最终模板
            return template.format(**kwargs)
        except KeyError as e:
            logger.error(f"格式化模板时缺少变量: {e}")
            raise ValueError(f"格式化模板时缺少变量: {e}")
        except Exception as e:
            logger.error(f"格式化模板出错: {e}")
            raise ValueError(f"格式化模板出错: {e}")
    
    def validate_vars(self, variables: Dict[str, Any]) -> bool:
        """
        验证变量是否满足模板需求
        
        Args:
            variables: 变量字典
            
        Returns:
            是否所有必需变量都存在
        """
        for var in self.required_vars:
            if var not in variables:
                return False
        return True
    
    def get_variables(self) -> Set[str]:
        """
        获取模板中的所有变量
        
        Returns:
            变量名集合
        """
        return self._variables
    
    def get_required_variables(self) -> Set[str]:
        """
        获取模板中的必需变量
        
        Returns:
            必需变量名集合
        """
        return self.required_vars
    
    def _process_conditionals(self, template: str, variables: Dict[str, Any]) -> str:
        """
        处理模板中的条件块
        
        条件格式: {%if condition%}...{%elif condition%}...{%else%}...{%endif%}
        
        Args:
            template: 原始模板
            variables: 变量字典
            
        Returns:
            处理后的模板
        """
        # 正则表达式匹配条件块
        pattern = r'\{%if\s+(.+?)%\}(.*?)(?:\{%else%\}(.*?))??\{%endif%\}'
        
        def evaluate_condition(condition: str) -> bool:
            """评估条件表达式"""
            try:
                # 替换变量名为字典引用
                condition_vars = set(re.findall(r'\b([a-zA-Z_][a-zA-Z0-9_]*)\b', condition))
                eval_str = condition
                
                for var in condition_vars:
                    if var in variables:
                        # 替换变量为其JSON表示
                        var_json = json.dumps(variables[var])
                        # 在条件表达式中替换变量
                        eval_str = re.sub(rf'\b{var}\b', var_json, eval_str)
                
                # 使用eval评估条件
                return bool(eval(eval_str))
            except Exception as e:
                logger.error(f"评估条件 '{condition}' 出错: {e}")
                return False
        
        # 处理嵌套条件
        while re.search(pattern, template, re.DOTALL):
            template = re.sub(
                pattern,
                lambda m: m.group(2) if evaluate_condition(m.group(1)) else (m.group(3) if m.group(3) else ''),
                template,
                flags=re.DOTALL
            )
        
        return template
    
    def _process_loops(self, template: str, variables: Dict[str, Any]) -> str:
        """
        处理模板中的循环块
        
        循环格式: {%for item in items%}...{%endfor%}
        
        Args:
            template: 原始模板
            variables: 变量字典
            
        Returns:
            处理后的模板
        """
        # 正则表达式匹配循环块
        pattern = r'\{%for\s+([a-zA-Z_][a-zA-Z0-9_]*)\s+in\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*%\}(.*?)\{%endfor%\}'
        
        def process_loop(match):
            item_var = match.group(1)
            collection_var = match.group(2)
            loop_content = match.group(3)
            
            if collection_var not in variables:
                logger.warning(f"循环集合变量 '{collection_var}' 不存在")
                return ""
            
            collection = variables[collection_var]
            if not isinstance(collection, (list, tuple, set)):
                logger.warning(f"循环变量 '{collection_var}' 不是可迭代的集合")
                return ""
            
            # 处理循环体
            result = []
            for item in collection:
                # 创建临时变量上下文
                temp_vars = {**variables, item_var: item}
                # 递归处理条件块
                processed = self._process_conditionals(loop_content, temp_vars)
                # 格式化循环内容
                try:
                    result.append(processed.format(**temp_vars))
                except KeyError as e:
                    logger.warning(f"循环格式化出错: {e}")
                    result.append(processed)
            
            return ''.join(result)
        
        # 处理所有循环，支持嵌套
        while re.search(pattern, template, re.DOTALL):
            template = re.sub(pattern, process_loop, template, flags=re.DOTALL)
        
        return template
    
    def __str__(self) -> str:
        """字符串表示"""
        return f"PromptTemplate(vars={len(self._variables)}, required={len(self.required_vars)})"


class PromptManager:
    """
    提示词模板管理器，用于管理多个提示词模板。
    """
    
    def __init__(self):
        """初始化提示词模板管理器"""
        self.templates: Dict[str, PromptTemplate] = {}
    
    def add_template(self, name: str, template: Union[str, PromptTemplate], required_vars: Optional[List[str]] = None) -> None:
        """
        添加提示词模板
        
        Args:
            name: 模板名称
            template: 模板字符串或PromptTemplate实例
            required_vars: 必需的变量列表，对于字符串模板有效
        """
        if isinstance(template, str):
            self.templates[name] = PromptTemplate(template, required_vars)
        else:
            self.templates[name] = template
        
        logger.debug(f"添加模板 '{name}'，变量: {len(self.templates[name].get_variables())}")
    
    def get_template(self, name: str) -> Optional[PromptTemplate]:
        """
        获取指定名称的模板
        
        Args:
            name: 模板名称
            
        Returns:
            PromptTemplate实例，不存在则返回None
        """
        return self.templates.get(name)
    
    def format(self, name: str, **kwargs) -> str:
        """
        使用指定模板格式化提示词
        
        Args:
            name: 模板名称
            **kwargs: 变量键值对
            
        Returns:
            格式化后的字符串
            
        Raises:
            ValueError: 模板不存在或格式化错误时抛出
        """
        if name not in self.templates:
            raise ValueError(f"模板 '{name}' 不存在")
        
        return self.templates[name].format(**kwargs)
    
    def list_templates(self) -> List[str]:
        """
        列出所有可用的模板名称
        
        Returns:
            模板名称列表
        """
        return list(self.templates.keys()) 