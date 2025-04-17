#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
安全工具模块，提供加密、解密和安全检查功能。
"""

import re
import os
import base64
import hashlib
import secrets
import warnings
from typing import Any, Dict, List, Optional, Tuple, Union

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

# 敏感信息模式
_SENSITIVE_PATTERNS = [
    r'\b(?:\d[ -]*?){13,16}\b',  # 信用卡号
    r'\b(?:\d{3}[ -]*?){3}\d{4}\b',  # 社会安全号
    r'(?:\d{1,3}\.){3}\d{1,3}',  # IP地址
    r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',  # 电子邮件
]

def generate_key() -> bytes:
    """
    生成一个新的加密密钥
    
    Returns:
        加密密钥
    """
    return Fernet.generate_key()

def derive_key(password: str, salt: Optional[bytes] = None) -> Tuple[bytes, bytes]:
    """
    从密码派生加密密钥
    
    Args:
        password: 密码
        salt: 盐值（如果为None，则生成新的盐值）
        
    Returns:
        (密钥, 盐值) 元组
    """
    if salt is None:
        salt = os.urandom(16)
    
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    return key, salt

def encrypt(data: str, key: bytes) -> str:
    """
    使用Fernet对称加密算法加密数据
    
    Args:
        data: 要加密的数据
        key: 加密密钥
        
    Returns:
        加密后的数据（Base64编码）
    """
    f = Fernet(key)
    return f.encrypt(data.encode()).decode()

def decrypt(encrypted_data: str, key: bytes) -> str:
    """
    解密Fernet加密的数据
    
    Args:
        encrypted_data: 加密后的数据（Base64编码）
        key: 加密密钥
        
    Returns:
        解密后的数据
    """
    f = Fernet(key)
    return f.decrypt(encrypted_data.encode()).decode()

def hash_password(password: str) -> Tuple[str, str]:
    """
    安全地哈希密码
    
    Args:
        password: 明文密码
        
    Returns:
        (哈希密码, 盐值) 元组
    """
    # 生成随机盐值
    salt = secrets.token_hex(16)
    
    # 结合盐值进行哈希
    pwdhash = hashlib.pbkdf2_hmac(
        'sha256', 
        password.encode(), 
        salt.encode(), 
        100000
    ).hex()
    
    return pwdhash, salt

def verify_password(password: str, stored_hash: str, salt: str) -> bool:
    """
    验证密码是否匹配存储的哈希值
    
    Args:
        password: 待验证的密码
        stored_hash: 存储的哈希值
        salt: 盐值
        
    Returns:
        密码是否匹配
    """
    # 计算哈希
    pwdhash = hashlib.pbkdf2_hmac(
        'sha256', 
        password.encode(), 
        salt.encode(), 
        100000
    ).hex()
    
    # 比较哈希值
    return pwdhash == stored_hash

def mask_sensitive_data(text: str, mask_char: str = '*') -> str:
    """
    掩盖文本中的敏感信息
    
    Args:
        text: 输入文本
        mask_char: 用于掩盖的字符
        
    Returns:
        掩盖敏感信息后的文本
    """
    masked_text = text
    
    for pattern in _SENSITIVE_PATTERNS:
        regex = re.compile(pattern)
        matches = regex.finditer(masked_text)
        
        # 从后向前替换，避免替换后的偏移问题
        matches = list(matches)
        for match in reversed(matches):
            start, end = match.span()
            # 保留前两个和后两个字符
            if end - start > 4:
                masked = masked_text[start:start+2] + mask_char * (end - start - 4) + masked_text[end-2:end]
            else:
                masked = mask_char * (end - start)
            
            masked_text = masked_text[:start] + masked + masked_text[end:]
    
    return masked_text

def contains_sensitive_data(text: str) -> bool:
    """
    检查文本是否包含敏感信息
    
    Args:
        text: 输入文本
        
    Returns:
        是否包含敏感信息
    """
    for pattern in _SENSITIVE_PATTERNS:
        if re.search(pattern, text):
            return True
    
    return False

def generate_strong_password(length: int = 16) -> str:
    """
    生成强密码
    
    Args:
        length: 密码长度
        
    Returns:
        生成的密码
    """
    if length < 8:
        warnings.warn("密码长度应至少为8个字符", UserWarning)
        length = max(8, length)
    
    # 确保包含大小写字母、数字和特殊字符
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()-_=+[]{}|;:,.<>?/"
    
    # 生成随机密码
    password = ''.join(secrets.choice(alphabet) for _ in range(length))
    
    return password

def is_safe_url(url: str) -> bool:
    """
    检查URL是否安全（不包含危险协议）
    
    Args:
        url: URL字符串
        
    Returns:
        URL是否安全
    """
    # 检查URL协议
    dangerous_protocols = ['javascript:', 'data:', 'vbscript:', 'file:']
    lower_url = url.lower()
    
    for protocol in dangerous_protocols:
        if lower_url.startswith(protocol):
            return False
    
    # 基本URL格式检查
    url_pattern = r'^(https?:\/\/)?([\da-z\.-]+)\.([a-z\.]{2,6})([\/\w \.-]*)*\/?$'
    if not re.match(url_pattern, url):
        return False
    
    return True

def sanitize_input(text: str) -> str:
    """
    清理用户输入，防止XSS攻击
    
    Args:
        text: 用户输入文本
        
    Returns:
        清理后的文本
    """
    # 替换特殊字符
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    text = text.replace('"', '&quot;')
    text = text.replace("'", '&#x27;')
    text = text.replace('/', '&#x2F;')
    
    return text 