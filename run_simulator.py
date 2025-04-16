#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
启动林镜机器人模拟器
"""

import asyncio
from bot_simulator import main

if __name__ == "__main__":
    print("正在启动林镜机器人模拟器...")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n程序已终止")
    except Exception as e:
        print(f"\n启动失败：{e}")
        import traceback
        traceback.print_exc() 