# MaiBot-/linjing/config/__init__.py
"""
配置模块初始化文件。
将 config.py 中的主要对象暴露到包命名空间。
"""

from ..config import config_manager, get_log_directory # 从上级目录的 config.py 导入

__all__ = ['config_manager', 'get_log_directory']