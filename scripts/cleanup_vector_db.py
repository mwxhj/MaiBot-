#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
向量数据库锁定清理工具

该脚本用于清理向量数据库的锁定状态，使得新实例能够成功连接。
"""

import os
import sys
import shutil
import logging
import time
from pathlib import Path

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def cleanup_vector_db(path, backup=True):
    """
    清理向量数据库锁定文件
    
    Args:
        path: 向量数据库路径
        backup: 是否创建备份
    """
    try:
        db_path = Path(path)
        if not db_path.exists():
            logger.warning(f"向量数据库路径不存在: {path}")
            return False
        
        # 检查是否为目录
        if not db_path.is_dir():
            logger.error(f"指定路径不是目录: {path}")
            return False
        
        lock_files = list(db_path.glob("*.lock"))
        if not lock_files:
            logger.info(f"未发现锁定文件在: {path}")
            return True
        
        # 备份
        if backup:
            backup_dir = db_path.parent / f"{db_path.name}_backup_{int(time.time())}"
            logger.info(f"创建备份目录: {backup_dir}")
            shutil.copytree(db_path, backup_dir)
        
        # 删除锁文件
        for lock_file in lock_files:
            logger.info(f"删除锁定文件: {lock_file}")
            lock_file.unlink(missing_ok=True)
        
        logger.info(f"成功清理向量数据库锁定文件: {path}")
        return True
    except Exception as e:
        logger.error(f"清理向量数据库锁定文件失败: {e}", exc_info=True)
        return False

def main():
    """主函数"""
    try:
        # 将当前目录添加到模块搜索路径
        sys.path.insert(0, os.path.abspath('.'))
        
        # 默认向量数据库路径
        default_path = "data/vector_db"
        
        # 解析命令行参数
        if len(sys.argv) > 1:
            vector_db_path = sys.argv[1]
            logger.info(f"使用命令行指定的向量数据库路径: {vector_db_path}")
        else:
            # 尝试从配置文件获取路径
            try:
                import yaml
                config_path = "config.yaml"
                if os.path.exists(config_path):
                    with open(config_path, 'r', encoding='utf-8') as f:
                        config = yaml.safe_load(f)
                    vector_db_path = config.get("storage", {}).get("vector_db", {}).get("path", default_path)
                    logger.info(f"从配置文件获取向量数据库路径: {vector_db_path}")
                else:
                    vector_db_path = default_path
                    logger.warning(f"配置文件不存在，使用默认路径: {vector_db_path}")
            except Exception as e:
                vector_db_path = default_path
                logger.warning(f"读取配置失败，使用默认路径: {vector_db_path}，错误: {e}")
        
        # 清理向量数据库
        success = cleanup_vector_db(vector_db_path)
        if success:
            logger.info("向量数据库锁定清理完成")
            return 0
        else:
            logger.error("向量数据库锁定清理失败")
            return 1
    except Exception as e:
        logger.error(f"程序执行失败: {e}", exc_info=True)
        return 1

if __name__ == "__main__":
    sys.exit(main()) 