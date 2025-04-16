#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
林镜(LingJing) - 运行脚本
"""

import asyncio
from linjing.main import main

if __name__ == "__main__":
    print("启动林镜(LingJing)...")
    asyncio.run(main()) 