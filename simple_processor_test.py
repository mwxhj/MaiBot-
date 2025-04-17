#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
简单测试BaseProcessor的优先级参数
"""

import asyncio
import sys
import os
import logging
from typing import Dict, Any, Optional

# 配置日志
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

from linjing.processors.base_processor import BaseProcessor

class SimpleProcessor(BaseProcessor):
    """简单处理器，仅用于测试"""
    
    name = "simple_processor"
    description = "简单测试处理器"
    version = "1.0.0"
    
    async def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """处理方法"""
        print(f"处理器优先级: {self.priority}")
        return context

def test_processor_init():
    """测试处理器初始化"""
    # 不带优先级参数
    processor1 = SimpleProcessor()
    print(f"处理器1名称: {processor1.get_name()}")
    print(f"处理器1优先级: {processor1.priority}")
    
    # 带优先级参数
    processor2 = SimpleProcessor(priority=100)
    print(f"处理器2名称: {processor2.get_name()}")
    print(f"处理器2优先级: {processor2.priority}")
    
    # 带配置和优先级参数
    processor3 = SimpleProcessor(config={"enabled": False}, priority=200)
    print(f"处理器3名称: {processor3.get_name()}")
    print(f"处理器3优先级: {processor3.priority}")
    print(f"处理器3是否启用: {processor3.is_enabled()}")
    
    print("\n测试完成!")

if __name__ == "__main__":
    test_processor_init() 