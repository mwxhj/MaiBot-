#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
林镜(LingJing) - 用户数据模型
"""

from typing import Dict, Any, List, Optional, Set
from datetime import datetime
from dataclasses import dataclass, field

from ..constants import PermissionLevel

@dataclass
class UserProfile:
    """用户个人资料"""
    nickname: str = ""
    avatar: str = ""
    bio: str = ""
    gender: str = "unknown"
    age: Optional[int] = None
    location: str = ""
    interests: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'nickname': self.nickname,
            'avatar': self.avatar,
            'bio': self.bio,
            'gender': self.gender,
            'age': self.age,
            'location': self.location,
            'interests': self.interests,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UserProfile':
        """从字典创建用户个人资料"""
        profile = cls(
            nickname=data.get('nickname', ''),
            avatar=data.get('avatar', ''),
            bio=data.get('bio', ''),
            gender=data.get('gender', 'unknown'),
            age=data.get('age'),
            location=data.get('location', ''),
            interests=data.get('interests', []),
        )
        
        # 解析日期时间
        created_at = data.get('created_at')
        if created_at:
            profile.created_at = datetime.fromisoformat(created_at)
        
        updated_at = data.get('updated_at')
        if updated_at:
            profile.updated_at = datetime.fromisoformat(updated_at)
        
        return profile

@dataclass
class User:
    """用户"""
    id: int
    platform: str = "qq"
    permission_level: int = PermissionLevel.USER
    name: str = ""
    profile: UserProfile = field(default_factory=UserProfile)
    groups: Set[int] = field(default_factory=set)
    is_active: bool = True
    last_active: datetime = field(default_factory=datetime.now)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'id': self.id,
            'platform': self.platform,
            'permission_level': self.permission_level,
            'name': self.name,
            'profile': self.profile.to_dict(),
            'groups': list(self.groups),
            'is_active': self.is_active,
            'last_active': self.last_active.isoformat(),
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'metadata': self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'User':
        """从字典创建用户"""
        user = cls(
            id=data.get('id', 0),
            platform=data.get('platform', 'qq'),
            permission_level=data.get('permission_level', PermissionLevel.USER),
            name=data.get('name', ''),
            profile=UserProfile.from_dict(data.get('profile', {})),
            groups=set(data.get('groups', [])),
            is_active=data.get('is_active', True),
            metadata=data.get('metadata', {}),
        )
        
        # 解析日期时间
        last_active = data.get('last_active')
        if last_active:
            user.last_active = datetime.fromisoformat(last_active)
        
        created_at = data.get('created_at')
        if created_at:
            user.created_at = datetime.fromisoformat(created_at)
        
        updated_at = data.get('updated_at')
        if updated_at:
            user.updated_at = datetime.fromisoformat(updated_at)
        
        return user
    
    def update_last_active(self) -> None:
        """更新最后活跃时间"""
        self.last_active = datetime.now()
        self.updated_at = datetime.now()
    
    def add_group(self, group_id: int) -> None:
        """
        添加用户所在的群
        
        Args:
            group_id: 群ID
        """
        self.groups.add(group_id)
        self.updated_at = datetime.now()
    
    def remove_group(self, group_id: int) -> None:
        """
        移除用户所在的群
        
        Args:
            group_id: 群ID
        """
        if group_id in self.groups:
            self.groups.remove(group_id)
            self.updated_at = datetime.now()
    
    def is_in_group(self, group_id: int) -> bool:
        """
        检查用户是否在指定群中
        
        Args:
            group_id: 群ID
            
        Returns:
            是否在群中
        """
        return group_id in self.groups
    
    def is_admin(self) -> bool:
        """
        检查用户是否为管理员
        
        Returns:
            是否为管理员
        """
        return self.permission_level >= PermissionLevel.ADMIN
    
    def is_master(self) -> bool:
        """
        检查用户是否为主人
        
        Returns:
            是否为主人
        """
        return self.permission_level >= PermissionLevel.MASTER
    
    def is_banned(self) -> bool:
        """
        检查用户是否被禁用
        
        Returns:
            是否被禁用
        """
        return self.permission_level <= PermissionLevel.BANNED
    
    def set_permission_level(self, level: int) -> None:
        """
        设置用户权限级别
        
        Args:
            level: 权限级别
        """
        self.permission_level = level
        self.updated_at = datetime.now()
    
    def get_metadata(self, key: str, default: Any = None) -> Any:
        """
        获取元数据
        
        Args:
            key: 键
            default: 默认值
            
        Returns:
            元数据值
        """
        return self.metadata.get(key, default)
    
    def set_metadata(self, key: str, value: Any) -> None:
        """
        设置元数据
        
        Args:
            key: 键
            value: 值
        """
        self.metadata[key] = value
        self.updated_at = datetime.now()
    
    def remove_metadata(self, key: str) -> None:
        """
        移除元数据
        
        Args:
            key: 键
        """
        if key in self.metadata:
            del self.metadata[key]
            self.updated_at = datetime.now()
            
    def update_profile(self, profile_data: Dict[str, Any]) -> None:
        """
        更新用户个人资料
        
        Args:
            profile_data: 个人资料数据
        """
        # 更新个人资料字段
        for key, value in profile_data.items():
            if hasattr(self.profile, key):
                setattr(self.profile, key, value)
        
        # 更新时间
        self.profile.updated_at = datetime.now()
        self.updated_at = datetime.now() 