#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import json
import uuid
import hashlib
import time
from typing import Dict, Any, List, Optional, Union, Tuple
from datetime import datetime, timezone

from utils.logger import get_logger


class StorageUtils:
    """存储工具类，提供通用的存储相关工具函数"""
    
    def __init__(self):
        """初始化存储工具类"""
        self.logger = get_logger("StorageUtils")
    
    @staticmethod
    def generate_id() -> str:
        """生成唯一ID
        
        Returns:
            str: 唯一ID
        """
        return str(uuid.uuid4())
    
    @staticmethod
    def generate_hash(data: Union[str, bytes, Dict[str, Any]]) -> str:
        """根据数据生成哈希字符串
        
        Args:
            data: 要哈希的数据，可以是字符串、字节或字典
            
        Returns:
            str: 哈希字符串
        """
        if isinstance(data, dict):
            # 字典需要先序列化为JSON字符串，确保顺序一致
            data = json.dumps(data, sort_keys=True)
        
        if isinstance(data, str):
            data = data.encode('utf-8')
            
        return hashlib.sha256(data).hexdigest()
    
    @staticmethod
    def timestamp_now() -> float:
        """获取当前时间戳
        
        Returns:
            float: 当前时间戳（秒）
        """
        return time.time()
    
    @staticmethod
    def datetime_now() -> datetime:
        """获取当前UTC时间
        
        Returns:
            datetime: 当前UTC时间
        """
        return datetime.now(timezone.utc)
    
    @staticmethod
    def datetime_to_str(dt: datetime) -> str:
        """将datetime转换为ISO格式字符串
        
        Args:
            dt: datetime对象
            
        Returns:
            str: ISO格式字符串
        """
        return dt.isoformat()
    
    @staticmethod
    def str_to_datetime(dt_str: str) -> Optional[datetime]:
        """将ISO格式字符串转换为datetime
        
        Args:
            dt_str: ISO格式字符串
            
        Returns:
            datetime: datetime对象，解析失败则返回None
        """
        try:
            return datetime.fromisoformat(dt_str)
        except ValueError:
            return None
    
    @staticmethod
    def ensure_dir(directory: str) -> None:
        """确保目录存在，不存在则创建
        
        Args:
            directory: 目录路径
        """
        if not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
    
    @staticmethod
    def file_exists(filepath: str) -> bool:
        """检查文件是否存在
        
        Args:
            filepath: 文件路径
            
        Returns:
            bool: 文件是否存在
        """
        return os.path.isfile(filepath)
    
    @staticmethod
    def dir_exists(directory: str) -> bool:
        """检查目录是否存在
        
        Args:
            directory: 目录路径
            
        Returns:
            bool: 目录是否存在
        """
        return os.path.isdir(directory)
    
    @staticmethod
    def save_json(data: Dict[str, Any], filepath: str) -> bool:
        """将数据保存为JSON文件
        
        Args:
            data: 要保存的数据
            filepath: 保存路径
            
        Returns:
            bool: 是否保存成功
        """
        try:
            # 确保目录存在
            directory = os.path.dirname(filepath)
            if directory and not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)
                
            # 保存文件
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            return False
    
    @staticmethod
    def load_json(filepath: str) -> Optional[Dict[str, Any]]:
        """从JSON文件加载数据
        
        Args:
            filepath: 文件路径
            
        Returns:
            Dict[str, Any]: 加载的数据，加载失败则返回None
        """
        try:
            if not os.path.isfile(filepath):
                return None
                
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            return None
    
    @staticmethod
    def append_to_file(content: str, filepath: str) -> bool:
        """追加内容到文件
        
        Args:
            content: 要追加的内容
            filepath: 文件路径
            
        Returns:
            bool: 是否成功
        """
        try:
            # 确保目录存在
            directory = os.path.dirname(filepath)
            if directory and not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)
                
            # 追加内容
            with open(filepath, 'a', encoding='utf-8') as f:
                f.write(content)
            return True
        except Exception as e:
            return False
    
    @staticmethod
    def read_file(filepath: str) -> Optional[str]:
        """读取文件内容
        
        Args:
            filepath: 文件路径
            
        Returns:
            str: 文件内容，读取失败则返回None
        """
        try:
            if not os.path.isfile(filepath):
                return None
                
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            return None
    
    @staticmethod
    def write_file(content: str, filepath: str) -> bool:
        """写入内容到文件
        
        Args:
            content: 要写入的内容
            filepath: 文件路径
            
        Returns:
            bool: 是否成功
        """
        try:
            # 确保目录存在
            directory = os.path.dirname(filepath)
            if directory and not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)
                
            # 写入内容
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        except Exception as e:
            return False
    
    @staticmethod
    def deep_update(d: Dict[str, Any], u: Dict[str, Any]) -> Dict[str, Any]:
        """深度更新字典
        
        Args:
            d: 原字典
            u: 要更新的内容
            
        Returns:
            Dict[str, Any]: 更新后的字典
        """
        for k, v in u.items():
            if isinstance(v, dict) and k in d and isinstance(d[k], dict):
                d[k] = StorageUtils.deep_update(d[k], v)
            else:
                d[k] = v
        return d
    
    @staticmethod
    def filter_dict(d: Dict[str, Any], keys: List[str]) -> Dict[str, Any]:
        """只保留字典中的指定键
        
        Args:
            d: 原字典
            keys: 要保留的键列表
            
        Returns:
            Dict[str, Any]: 过滤后的字典
        """
        return {k: v for k, v in d.items() if k in keys}
    
    @staticmethod
    def exclude_keys(d: Dict[str, Any], keys: List[str]) -> Dict[str, Any]:
        """从字典中排除指定键
        
        Args:
            d: 原字典
            keys: 要排除的键列表
            
        Returns:
            Dict[str, Any]: 过滤后的字典
        """
        return {k: v for k, v in d.items() if k not in keys}
    
    @staticmethod
    def flatten_dict(d: Dict[str, Any], parent_key: str = '', sep: str = '.') -> Dict[str, Any]:
        """扁平化嵌套字典
        
        Args:
            d: 嵌套字典
            parent_key: 父键前缀
            sep: 键分隔符
            
        Returns:
            Dict[str, Any]: 扁平化后的字典
        """
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(StorageUtils.flatten_dict(v, new_key, sep).items())
            else:
                items.append((new_key, v))
        return dict(items)
    
    @staticmethod
    def unflatten_dict(d: Dict[str, Any], sep: str = '.') -> Dict[str, Any]:
        """将扁平化字典还原为嵌套字典
        
        Args:
            d: 扁平化字典
            sep: 键分隔符
            
        Returns:
            Dict[str, Any]: 嵌套字典
        """
        result = {}
        for k, v in d.items():
            parts = k.split(sep)
            
            # 逐层创建嵌套字典
            current = result
            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]
                
            # 设置叶子节点值
            current[parts[-1]] = v
            
        return result