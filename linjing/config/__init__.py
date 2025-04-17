#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
配置模块初始化文件，提供Config类用于加载YAML配置。
"""

import os
import yaml
import logging
import json
from typing import Dict, Any, Optional, List
from pathlib import Path

# 尝试加载环境变量
try:
    from dotenv import load_dotenv
    # 尝试加载.env文件
    project_root = Path(__file__).parents[2]  # 项目根目录 (MaiBot-)
    env_path = project_root / '.env'
    if env_path.exists():
        load_dotenv(str(env_path))
        print(f"已从 {env_path} 加载环境变量")
except ImportError:
    pass  # 如果没有安装dotenv，忽略错误

class Config:
    """配置类，用于加载YAML配置文件"""
    
    def __init__(self):
        """初始化配置对象"""
        self.config = {}
    
    def load_from_file(self, filepath):
        """从文件加载配置"""
        try:
            with open(filepath, 'r', encoding='utf-8') as file:
                if filepath.endswith('.yaml') or filepath.endswith('.yml'):
                    self.config = yaml.safe_load(file)
                elif filepath.endswith('.json'):
                    self.config = json.load(file)
                else:
                    logging.error(f"不支持的配置文件格式: {filepath}")
                    return False
                
            logging.info(f"成功加载配置文件: {filepath}")
            return True
        except Exception as e:
            logging.error(f"加载配置文件失败: {e}")
            return False
    
    def get(self, key_path, default=None):
        """
        获取配置项
        
        Args:
            key_path: 配置项路径，如 "llm.providers.openai.api_key"
            default: 默认值
            
        Returns:
            配置项的值
        """
        keys = key_path.split(".")
        config = self.config
        
        for key in keys:
            if isinstance(config, dict) and key in config:
                config = config[key]
            else:
                return default
        
        return config
    
    def set(self, key_path, value):
        """
        设置配置项
        
        Args:
            key_path: 配置项路径
            value: 配置项的值
        """
        keys = key_path.split(".")
        config = self.config
        
        # 遍历路径直到倒数第二级
        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]
        
        # 设置最后一级的值
        config[keys[-1]] = value


class ConfigManager:
    """配置管理器，用于加载和访问配置项"""
    
    def __init__(self, config_dir: str = "config"):
        """
        初始化配置管理器
        
        Args:
            config_dir: 配置文件目录
        """
        self.config_dir = config_dir
        self.config: Dict[str, Any] = {}
        
        # 确定配置文件路径
        project_root = Path(__file__).parents[2]  # 项目根目录 (MaiBot-)
        yaml_config_path = project_root / "config.yaml"
        default_config_path = os.path.join(config_dir, "default_config.json")
        user_config_path = os.path.join(config_dir, "user_config.json")
        
        # 尝试加载YAML配置
        if yaml_config_path.exists():
            try:
                with open(yaml_config_path, "r", encoding="utf-8") as f:
                    self.config = yaml.safe_load(f)
                    logging.info(f"已加载YAML配置: {yaml_config_path}")
            except Exception as e:
                logging.error(f"加载YAML配置失败: {e}")
                self.config = {}
        else:
            # 回退到JSON配置
            try:
                with open(default_config_path, "r", encoding="utf-8") as f:
                    self.config = json.load(f)
                logging.info(f"已加载默认JSON配置: {default_config_path}")
            except FileNotFoundError:
                logging.error(f"默认配置文件不存在: {default_config_path}")
                self.config = {}
            
            # 加载用户配置（如果存在）
            try:
                with open(user_config_path, "r", encoding="utf-8") as f:
                    user_config = json.load(f)
                    # 递归合并配置
                    self._merge_config(self.config, user_config)
                logging.info(f"已加载用户JSON配置: {user_config_path}")
            except FileNotFoundError:
                logging.warning(f"用户配置文件不存在: {user_config_path}")
        
        # 从环境变量覆盖一些敏感配置
        self._override_from_env()
        
        # 设置日志级别
        log_level = self.get("bot.log_level", "INFO")
        logging.basicConfig(level=getattr(logging, log_level))
    
    def _merge_config(self, base: Dict[str, Any], override: Dict[str, Any]) -> None:
        """
        递归合并配置
        
        Args:
            base: 基础配置
            override: 覆盖配置
        """
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_config(base[key], value)
            else:
                base[key] = value
    
    def _override_from_env(self) -> None:
        """从环境变量覆盖配置项"""
        # 获取环境变量中的密钥
        openai_api_key = os.getenv("OPENAI_API_KEY")
        openai_api_base = os.getenv("OPENAI_API_BASE")
        openai_org_id = os.getenv("OPENAI_ORG_ID")
        azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")
        azure_resource_name = os.getenv("AZURE_RESOURCE_NAME")
        azure_api_base = os.getenv("AZURE_API_BASE")
        azure_deployment_name = os.getenv("AZURE_DEPLOYMENT_NAME")
        azure_embedding_deployment = os.getenv("AZURE_EMBEDDING_DEPLOYMENT")
        azure_api_version = os.getenv("AZURE_API_VERSION")
        
        # 确保llm和providers存在
        if "llm" not in self.config:
            self.config["llm"] = {}
        
        if "providers" not in self.config["llm"]:
            self.config["llm"]["providers"] = []
        
        # 获取providers列表
        providers = self.config["llm"]["providers"]
        if not isinstance(providers, list):
            logging.error("配置中的llm.providers不是列表类型")
            return
            
        # 更新OpenAI提供商配置
        if openai_api_key:
            # 查找OpenAI提供商
            openai_provider = None
            openai_provider_index = -1
            for i, provider in enumerate(providers):
                if isinstance(provider, dict) and provider.get("type") == "openai":
                    openai_provider = provider
                    openai_provider_index = i
                    break
            
            # 如果找到OpenAI提供商，更新它
            if openai_provider:
                providers[openai_provider_index]["api_key"] = openai_api_key
                if openai_api_base:
                    providers[openai_provider_index]["api_base"] = openai_api_base
                if openai_org_id:
                    providers[openai_provider_index]["organization"] = openai_org_id
                logging.info("已更新OpenAI提供商配置")
            
            # 更新模型路由器配置
            for i, provider in enumerate(providers):
                if isinstance(provider, dict) and provider.get("type") == "model_router" and provider.get("provider_type") == "openai":
                    if "shared_config" in provider:
                        provider["shared_config"]["api_key"] = openai_api_key
                        if openai_api_base:
                            provider["shared_config"]["api_base"] = openai_api_base
                        if openai_org_id:
                            provider["shared_config"]["organization"] = openai_org_id
                        logging.info("已更新模型路由器中的OpenAI配置")
        
        # 更新Azure提供商配置
        if azure_api_key:
            # 查找Azure提供商
            azure_provider = None
            azure_provider_index = -1
            for i, provider in enumerate(providers):
                if isinstance(provider, dict) and provider.get("type") == "azure":
                    azure_provider = provider
                    azure_provider_index = i
                    break
            
            # 如果找到Azure提供商，更新它
            if azure_provider:
                providers[azure_provider_index]["api_key"] = azure_api_key
                
                if azure_resource_name:
                    providers[azure_provider_index]["resource_name"] = azure_resource_name
                
                if azure_api_base:
                    if "{resource_name}" in azure_api_base and azure_resource_name:
                        azure_api_base = azure_api_base.replace("{resource_name}", azure_resource_name)
                    providers[azure_provider_index]["api_base"] = azure_api_base
                
                if azure_deployment_name:
                    providers[azure_provider_index]["deployment_name"] = azure_deployment_name
                
                if azure_embedding_deployment:
                    providers[azure_provider_index]["embedding_deployment"] = azure_embedding_deployment
                
                if azure_api_version:
                    providers[azure_provider_index]["api_version"] = azure_api_version
                
                logging.info("已更新Azure提供商配置")
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        获取配置项
        
        Args:
            key_path: 配置项路径，如 "llm.providers.openai.api_key"
            default: 默认值
            
        Returns:
            配置项的值
        """
        keys = key_path.split(".")
        config = self.config
        
        for key in keys:
            if isinstance(config, dict) and key in config:
                config = config[key]
            else:
                return default
        
        return config
    
    def set(self, key_path: str, value: Any) -> None:
        """
        设置配置项
        
        Args:
            key_path: 配置项路径
            value: 配置项的值
        """
        keys = key_path.split(".")
        config = self.config
        
        # 处理特殊情况：providers是列表
        if "providers" in keys and keys[0] == "llm" and len(keys) > 2:
            provider_type = keys[2]  # 例如"openai"、"azure"
            provider_field = keys[3] if len(keys) > 3 else None  # 例如"api_key"
            
            if "llm" not in config:
                config["llm"] = {}
            
            if "providers" not in config["llm"]:
                config["llm"]["providers"] = []
            
            providers = config["llm"]["providers"]
            if not isinstance(providers, list):
                logging.error("配置中的llm.providers不是列表类型")
                return
            
            # 查找指定类型的提供商
            found = False
            for provider in providers:
                if isinstance(provider, dict) and provider.get("type") == provider_type:
                    if provider_field:
                        provider[provider_field] = value
                    found = True
                    break
            
            # 如果未找到，创建一个新的提供商
            if not found and provider_field:
                new_provider = {"type": provider_type, provider_field: value}
                providers.append(new_provider)
            
            return
        
        # 标准情况处理
        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            elif not isinstance(config[key], dict):
                # 如果当前节点不是字典，则替换为字典
                config[key] = {}
            config = config[key]
        
        # 设置最后一级的值
        config[keys[-1]] = value
    
    def save_user_config(self) -> bool:
        """
        保存用户配置
        
        Returns:
            保存是否成功
        """
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(os.path.join(self.config_dir, "user_config.json")), exist_ok=True)
            
            with open(os.path.join(self.config_dir, "user_config.json"), "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            logging.error(f"保存用户配置失败: {str(e)}")
            return False

    def find_provider_by_id(self, provider_id: str) -> Optional[Dict[str, Any]]:
        """
        根据ID查找提供商
        
        Args:
            provider_id: 提供商ID
            
        Returns:
            提供商配置，如果未找到则返回None
        """
        providers = self.config.get("llm", {}).get("providers", [])
        if not isinstance(providers, list):
            return None
            
        for provider in providers:
            if isinstance(provider, dict) and provider.get("id") == provider_id:
                return provider
                
        return None

    def update_provider(self, provider_id: str, **updates) -> bool:
        """
        更新指定ID的提供商配置
        
        Args:
            provider_id: 提供商ID
            **updates: 要更新的配置项
            
        Returns:
            是否成功更新
        """
        providers = self.config.get("llm", {}).get("providers", [])
        if not isinstance(providers, list):
            return False
            
        for i, provider in enumerate(providers):
            if isinstance(provider, dict) and provider.get("id") == provider_id:
                # 更新配置
                for key, value in updates.items():
                    provider[key] = value
                return True
                
        return False


# 全局配置实例
config_manager = ConfigManager() 