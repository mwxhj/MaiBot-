#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Redis缓存模块
提供异步Redis缓存操作接口
"""

import json
import logging
import aioredis
from typing import Any, Dict, List, Optional, Set, Union, Tuple
import pickle


class RedisCache:
    """Redis缓存管理器，提供异步操作接口"""
    
    def __init__(self, config: Dict[str, Any]):
        """
        初始化Redis缓存管理器
        
        Args:
            config: Redis配置字典
                {
                    "host": "localhost",
                    "port": 6379,
                    "password": None,
                    "db": 0,
                    "encoding": "utf-8",
                    "max_connections": 10,
                    "socket_timeout": 5
                }
        """
        self.config = config
        self.host = config.get("host", "localhost")
        self.port = config.get("port", 6379)
        self.password = config.get("password")
        self.db = config.get("db", 0)
        self.encoding = config.get("encoding", "utf-8")
        self.max_connections = config.get("max_connections", 10)
        self.socket_timeout = config.get("socket_timeout", 5)
        
        # 初始化连接为None，在connect方法中创建
        self.redis = None
        self.logger = logging.getLogger("redis")
        self.connected = False
    
    async def connect(self) -> bool:
        """
        连接到Redis服务器
        
        Returns:
            bool: 连接是否成功
        """
        try:
            connection_kwargs = {
                "host": self.host,
                "port": self.port,
                "db": self.db,
                "encoding": self.encoding,
                "password": self.password,
                "maxsize": self.max_connections,
                "timeout": self.socket_timeout
            }
            
            # 移除None值
            connection_kwargs = {k: v for k, v in connection_kwargs.items() if v is not None}
            
            # 创建连接
            self.redis = await aioredis.create_redis_pool(**connection_kwargs)
            self.connected = True
            self.logger.info(f"已连接到Redis: {self.host}:{self.port}/{self.db}")
            return True
            
        except Exception as e:
            self.logger.error(f"连接Redis失败: {str(e)}")
            self.connected = False
            return False
    
    async def close(self) -> None:
        """关闭Redis连接"""
        if self.redis:
            self.redis.close()
            await self.redis.wait_closed()
            self.redis = None
            self.connected = False
            self.logger.info("Redis连接已关闭")
    
    async def ping(self) -> bool:
        """
        测试Redis连接
        
        Returns:
            bool: 连接是否正常
        """
        if not self.redis:
            return False
        
        try:
            result = await self.redis.ping()
            return result == b"PONG"
        except Exception as e:
            self.logger.error(f"Redis ping失败: {str(e)}")
            return False

    # 字符串操作
    async def set(self, key: str, value: Any, expire: int = None, nx: bool = False, xx: bool = False) -> bool:
        """
        设置键值对
        
        Args:
            key: 键名
            value: 值(字符串、数字、字典、列表等)
            expire: 过期时间(秒)
            nx: 如果为True，则只在键不存在时才设置
            xx: 如果为True，则只在键已存在时才设置
            
        Returns:
            bool: 是否设置成功
        """
        if not self.redis:
            await self.connect()
        
        try:
            # 对复杂类型进行序列化
            if not isinstance(value, (str, int, float, bytes)):
                value = json.dumps(value)
            
            # 设置参数
            params = {}
            if expire:
                params["expire"] = expire
            if nx:
                params["exist"] = aioredis.SET_IF_NOT_EXIST
            if xx:
                params["exist"] = aioredis.SET_IF_EXIST
            
            # 设置值
            result = await self.redis.set(key, value, **params)
            return result is True
        
        except Exception as e:
            self.logger.error(f"设置键值对失败 - {key}: {str(e)}")
            return False
    
    async def get(self, key: str, default: Any = None) -> Any:
        """
        获取键值
        
        Args:
            key: 键名
            default: 默认值，如果键不存在则返回
            
        Returns:
            Any: 键对应的值或默认值
        """
        if not self.redis:
            await self.connect()
        
        try:
            value = await self.redis.get(key)
            if value is None:
                return default
            
            # 尝试解析JSON
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                # 如果不是JSON格式，则尝试解码为字符串
                if isinstance(value, bytes):
                    return value.decode(self.encoding)
                return value
        
        except Exception as e:
            self.logger.error(f"获取键值失败 - {key}: {str(e)}")
            return default
    
    async def delete(self, *keys) -> int:
        """
        删除一个或多个键
        
        Args:
            *keys: 要删除的键名
            
        Returns:
            int: 成功删除的键数量
        """
        if not self.redis:
            await self.connect()
        
        try:
            if not keys:
                return 0
            return await self.redis.delete(*keys)
        
        except Exception as e:
            self.logger.error(f"删除键失败: {str(e)}")
            return 0
    
    async def exists(self, key: str) -> bool:
        """
        检查键是否存在
        
        Args:
            key: 键名
            
        Returns:
            bool: 键是否存在
        """
        if not self.redis:
            await self.connect()
        
        try:
            return await self.redis.exists(key) == 1
        
        except Exception as e:
            self.logger.error(f"检查键存在失败 - {key}: {str(e)}")
            return False
    
    async def expire(self, key: str, seconds: int) -> bool:
        """
        设置键的过期时间
        
        Args:
            key: 键名
            seconds: 过期秒数
            
        Returns:
            bool: 是否设置成功
        """
        if not self.redis:
            await self.connect()
        
        try:
            return await self.redis.expire(key, seconds) == 1
        
        except Exception as e:
            self.logger.error(f"设置过期时间失败 - {key}: {str(e)}")
            return False
    
    async def ttl(self, key: str) -> int:
        """
        获取键的剩余生存时间
        
        Args:
            key: 键名
            
        Returns:
            int: 剩余秒数，-1表示永不过期，-2表示键不存在
        """
        if not self.redis:
            await self.connect()
        
        try:
            return await self.redis.ttl(key)
        
        except Exception as e:
            self.logger.error(f"获取剩余时间失败 - {key}: {str(e)}")
            return -2
    
    # 哈希表操作
    async def hset(self, key: str, field: str, value: Any) -> bool:
        """
        设置哈希表字段值
        
        Args:
            key: 键名
            field: 字段名
            value: 字段值
            
        Returns:
            bool: 操作是否成功
        """
        if not self.redis:
            await self.connect()
        
        try:
            # 对复杂类型进行序列化
            if not isinstance(value, (str, int, float, bytes)):
                value = json.dumps(value)
            
            # Python API中，hset返回整数(新添加的字段数量，0或1)
            return await self.redis.hset(key, field, value) >= 0
        
        except Exception as e:
            self.logger.error(f"设置哈希字段失败 - {key}.{field}: {str(e)}")
            return False
    
    async def hget(self, key: str, field: str, default: Any = None) -> Any:
        """
        获取哈希表字段值
        
        Args:
            key: 键名
            field: 字段名
            default: 默认值，如果字段不存在则返回
            
        Returns:
            Any: 字段值或默认值
        """
        if not self.redis:
            await self.connect()
        
        try:
            value = await self.redis.hget(key, field)
            if value is None:
                return default
            
            # 尝试解析JSON
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                # 如果不是JSON格式，则尝试解码为字符串
                if isinstance(value, bytes):
                    return value.decode(self.encoding)
                return value
        
        except Exception as e:
            self.logger.error(f"获取哈希字段失败 - {key}.{field}: {str(e)}")
            return default
    
    async def hmset(self, key: str, mapping: Dict[str, Any]) -> bool:
        """
        批量设置哈希表字段
        
        Args:
            key: 键名
            mapping: 字段名到字段值的映射
            
        Returns:
            bool: 操作是否成功
        """
        if not self.redis:
            await self.connect()
        
        try:
            # 对复杂类型进行序列化
            processed_mapping = {}
            for field, value in mapping.items():
                if not isinstance(value, (str, int, float, bytes)):
                    processed_mapping[field] = json.dumps(value)
                else:
                    processed_mapping[field] = value
            
            # Python API中，hmset返回布尔值
            return await self.redis.hmset_dict(key, processed_mapping)
        
        except Exception as e:
            self.logger.error(f"批量设置哈希字段失败 - {key}: {str(e)}")
            return False
    
    async def hmget(self, key: str, fields: List[str]) -> Dict[str, Any]:
        """
        批量获取哈希表字段
        
        Args:
            key: 键名
            fields: 字段名列表
            
        Returns:
            Dict[str, Any]: 字段名到字段值的映射
        """
        if not self.redis:
            await self.connect()
        
        try:
            values = await self.redis.hmget(key, *fields)
            result = {}
            
            for field, value in zip(fields, values):
                if value is None:
                    result[field] = None
                    continue
                
                # 尝试解析JSON
                try:
                    result[field] = json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    # 如果不是JSON格式，则尝试解码为字符串
                    if isinstance(value, bytes):
                        result[field] = value.decode(self.encoding)
                    else:
                        result[field] = value
            
            return result
        
        except Exception as e:
            self.logger.error(f"批量获取哈希字段失败 - {key}: {str(e)}")
            return {}
    
    async def hgetall(self, key: str) -> Dict[str, Any]:
        """
        获取哈希表所有字段
        
        Args:
            key: 键名
            
        Returns:
            Dict[str, Any]: 所有字段名到字段值的映射
        """
        if not self.redis:
            await self.connect()
        
        try:
            values = await self.redis.hgetall(key)
            result = {}
            
            for field, value in values.items():
                # 解码字段名
                if isinstance(field, bytes):
                    field = field.decode(self.encoding)
                
                # 尝试解析JSON
                try:
                    result[field] = json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    # 如果不是JSON格式，则尝试解码为字符串
                    if isinstance(value, bytes):
                        result[field] = value.decode(self.encoding)
                    else:
                        result[field] = value
            
            return result
        
        except Exception as e:
            self.logger.error(f"获取哈希所有字段失败 - {key}: {str(e)}")
            return {}
    
    async def hdel(self, key: str, *fields) -> int:
        """
        删除哈希表字段
        
        Args:
            key: 键名
            *fields: 要删除的字段名
            
        Returns:
            int: 成功删除的字段数量
        """
        if not self.redis:
            await self.connect()
        
        try:
            if not fields:
                return 0
            return await self.redis.hdel(key, *fields)
        
        except Exception as e:
            self.logger.error(f"删除哈希字段失败 - {key}: {str(e)}")
            return 0
    
    async def hexists(self, key: str, field: str) -> bool:
        """
        检查哈希表字段是否存在
        
        Args:
            key: 键名
            field: 字段名
            
        Returns:
            bool: 字段是否存在
        """
        if not self.redis:
            await self.connect()
        
        try:
            return await self.redis.hexists(key, field)
        
        except Exception as e:
            self.logger.error(f"检查哈希字段存在失败 - {key}.{field}: {str(e)}")
            return False
    
    # 列表操作
    async def lpush(self, key: str, *values) -> int:
        """
        将值推入列表左侧
        
        Args:
            key: 键名
            *values: 要推入的值
            
        Returns:
            int: 操作后列表长度
        """
        if not self.redis:
            await self.connect()
        
        try:
            # 对复杂类型进行序列化
            processed_values = []
            for value in values:
                if not isinstance(value, (str, int, float, bytes)):
                    processed_values.append(json.dumps(value))
                else:
                    processed_values.append(value)
            
            return await self.redis.lpush(key, *processed_values)
        
        except Exception as e:
            self.logger.error(f"列表左推失败 - {key}: {str(e)}")
            return 0
    
    async def rpush(self, key: str, *values) -> int:
        """
        将值推入列表右侧
        
        Args:
            key: 键名
            *values: 要推入的值
            
        Returns:
            int: 操作后列表长度
        """
        if not self.redis:
            await self.connect()
        
        try:
            # 对复杂类型进行序列化
            processed_values = []
            for value in values:
                if not isinstance(value, (str, int, float, bytes)):
                    processed_values.append(json.dumps(value))
                else:
                    processed_values.append(value)
            
            return await self.redis.rpush(key, *processed_values)
        
        except Exception as e:
            self.logger.error(f"列表右推失败 - {key}: {str(e)}")
            return 0
    
    async def lpop(self, key: str) -> Any:
        """
        从列表左侧弹出值
        
        Args:
            key: 键名
            
        Returns:
            Any: 弹出的值，如果列表为空则返回None
        """
        if not self.redis:
            await self.connect()
        
        try:
            value = await self.redis.lpop(key)
            if value is None:
                return None
            
            # 尝试解析JSON
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                # 如果不是JSON格式，则尝试解码为字符串
                if isinstance(value, bytes):
                    return value.decode(self.encoding)
                return value
        
        except Exception as e:
            self.logger.error(f"列表左弹失败 - {key}: {str(e)}")
            return None
    
    async def rpop(self, key: str) -> Any:
        """
        从列表右侧弹出值
        
        Args:
            key: 键名
            
        Returns:
            Any: 弹出的值，如果列表为空则返回None
        """
        if not self.redis:
            await self.connect()
        
        try:
            value = await self.redis.rpop(key)
            if value is None:
                return None
            
            # 尝试解析JSON
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                # 如果不是JSON格式，则尝试解码为字符串
                if isinstance(value, bytes):
                    return value.decode(self.encoding)
                return value
        
        except Exception as e:
            self.logger.error(f"列表右弹失败 - {key}: {str(e)}")
            return None
    
    async def lrange(self, key: str, start: int, end: int) -> List[Any]:
        """
        获取列表范围内的元素
        
        Args:
            key: 键名
            start: 起始索引
            end: 结束索引，-1表示最后一个元素
            
        Returns:
            List[Any]: 范围内的元素列表
        """
        if not self.redis:
            await self.connect()
        
        try:
            values = await self.redis.lrange(key, start, end)
            result = []
            
            for value in values:
                # 尝试解析JSON
                try:
                    result.append(json.loads(value))
                except (json.JSONDecodeError, TypeError):
                    # 如果不是JSON格式，则尝试解码为字符串
                    if isinstance(value, bytes):
                        result.append(value.decode(self.encoding))
                    else:
                        result.append(value)
            
            return result
        
        except Exception as e:
            self.logger.error(f"获取列表范围失败 - {key}: {str(e)}")
            return []
    
    async def llen(self, key: str) -> int:
        """
        获取列表长度
        
        Args:
            key: 键名
            
        Returns:
            int: 列表长度
        """
        if not self.redis:
            await self.connect()
        
        try:
            return await self.redis.llen(key)
        
        except Exception as e:
            self.logger.error(f"获取列表长度失败 - {key}: {str(e)}")
            return 0
    
    # 集合操作
    async def sadd(self, key: str, *members) -> int:
        """
        向集合添加成员
        
        Args:
            key: 键名
            *members: 要添加的成员
            
        Returns:
            int: 添加的成员数量
        """
        if not self.redis:
            await self.connect()
        
        try:
            # 对复杂类型进行序列化
            processed_members = []
            for member in members:
                if not isinstance(member, (str, int, float, bytes)):
                    processed_members.append(json.dumps(member))
                else:
                    processed_members.append(member)
            
            return await self.redis.sadd(key, *processed_members)
        
        except Exception as e:
            self.logger.error(f"集合添加成员失败 - {key}: {str(e)}")
            return 0
    
    async def smembers(self, key: str) -> Set[Any]:
        """
        获取集合所有成员
        
        Args:
            key: 键名
            
        Returns:
            Set[Any]: 成员集合
        """
        if not self.redis:
            await self.connect()
        
        try:
            members = await self.redis.smembers(key)
            result = set()
            
            for member in members:
                # 尝试解析JSON
                try:
                    result.add(json.loads(member))
                except (json.JSONDecodeError, TypeError):
                    # 如果不是JSON格式，则尝试解码为字符串
                    if isinstance(member, bytes):
                        result.add(member.decode(self.encoding))
                    else:
                        result.add(member)
            
            return result
        
        except Exception as e:
            self.logger.error(f"获取集合成员失败 - {key}: {str(e)}")
            return set()
    
    async def srem(self, key: str, *members) -> int:
        """
        从集合移除成员
        
        Args:
            key: 键名
            *members: 要移除的成员
            
        Returns:
            int: 移除的成员数量
        """
        if not self.redis:
            await self.connect()
        
        try:
            # 对复杂类型进行序列化
            processed_members = []
            for member in members:
                if not isinstance(member, (str, int, float, bytes)):
                    processed_members.append(json.dumps(member))
                else:
                    processed_members.append(member)
            
            return await self.redis.srem(key, *processed_members)
        
        except Exception as e:
            self.logger.error(f"集合移除成员失败 - {key}: {str(e)}")
            return 0
    
    async def sismember(self, key: str, member: Any) -> bool:
        """
        检查成员是否在集合中
        
        Args:
            key: 键名
            member: 要检查的成员
            
        Returns:
            bool: 成员是否在集合中
        """
        if not self.redis:
            await self.connect()
        
        try:
            # 对复杂类型进行序列化
            if not isinstance(member, (str, int, float, bytes)):
                member = json.dumps(member)
            
            return await self.redis.sismember(key, member)
        
        except Exception as e:
            self.logger.error(f"检查集合成员失败 - {key}: {str(e)}")
            return False
    
    async def scard(self, key: str) -> int:
        """
        获取集合成员数量
        
        Args:
            key: 键名
            
        Returns:
            int: 成员数量
        """
        if not self.redis:
            await self.connect()
        
        try:
            return await self.redis.scard(key)
        
        except Exception as e:
            self.logger.error(f"获取集合大小失败 - {key}: {str(e)}")
            return 0
    
    # 有序集合操作
    async def zadd(self, key: str, score: float, member: Any) -> int:
        """
        向有序集合添加成员
        
        Args:
            key: 键名
            score: 分数
            member: 成员
            
        Returns:
            int: 添加的成员数量
        """
        if not self.redis:
            await self.connect()
        
        try:
            # 对复杂类型进行序列化
            if not isinstance(member, (str, int, float, bytes)):
                member = json.dumps(member)
            
            return await self.redis.zadd(key, score, member)
        
        except Exception as e:
            self.logger.error(f"有序集合添加成员失败 - {key}: {str(e)}")
            return 0
    
    async def zadd_multiple(self, key: str, members: Dict[Any, float]) -> int:
        """
        向有序集合批量添加成员
        
        Args:
            key: 键名
            members: 成员到分数的映射
            
        Returns:
            int: 添加的成员数量
        """
        if not self.redis:
            await self.connect()
        
        try:
            # 对复杂类型进行序列化
            processed_members = {}
            for member, score in members.items():
                if not isinstance(member, (str, int, float, bytes)):
                    processed_members[json.dumps(member)] = score
                else:
                    processed_members[member] = score
            
            # 转换为Redis API要求的格式
            args = []
            for member, score in processed_members.items():
                args.append(score)
                args.append(member)
            
            return await self.redis.zadd(key, *args)
        
        except Exception as e:
            self.logger.error(f"有序集合批量添加成员失败 - {key}: {str(e)}")
            return 0
    
    async def zrange(self, key: str, start: int, end: int, with_scores: bool = False) -> Union[List[Any], List[Tuple[Any, float]]]:
        """
        获取有序集合范围内的成员
        
        Args:
            key: 键名
            start: 起始索引
            end: 结束索引，-1表示最后一个元素
            with_scores: 是否包含分数
            
        Returns:
            Union[List[Any], List[Tuple[Any, float]]]: 成员列表或(成员,分数)元组列表
        """
        if not self.redis:
            await self.connect()
        
        try:
            values = await self.redis.zrange(key, start, end, with_scores=with_scores)
            
            if not with_scores:
                # 只有成员的情况
                result = []
                for value in values:
                    # 尝试解析JSON
                    try:
                        result.append(json.loads(value))
                    except (json.JSONDecodeError, TypeError):
                        # 如果不是JSON格式，则尝试解码为字符串
                        if isinstance(value, bytes):
                            result.append(value.decode(self.encoding))
                        else:
                            result.append(value)
                return result
            else:
                # 成员和分数的情况
                result = []
                for i in range(0, len(values), 2):
                    member = values[i]
                    score = float(values[i+1])
                    
                    # 尝试解析JSON
                    try:
                        member = json.loads(member)
                    except (json.JSONDecodeError, TypeError):
                        # 如果不是JSON格式，则尝试解码为字符串
                        if isinstance(member, bytes):
                            member = member.decode(self.encoding)
                    
                    result.append((member, score))
                return result
        
        except Exception as e:
            self.logger.error(f"获取有序集合范围失败 - {key}: {str(e)}")
            return []
    
    async def zrem(self, key: str, *members) -> int:
        """
        从有序集合移除成员
        
        Args:
            key: 键名
            *members: 要移除的成员
            
        Returns:
            int: 移除的成员数量
        """
        if not self.redis:
            await self.connect()
        
        try:
            # 对复杂类型进行序列化
            processed_members = []
            for member in members:
                if not isinstance(member, (str, int, float, bytes)):
                    processed_members.append(json.dumps(member))
                else:
                    processed_members.append(member)
            
            return await self.redis.zrem(key, *processed_members)
        
        except Exception as e:
            self.logger.error(f"有序集合移除成员失败 - {key}: {str(e)}")
            return 0
    
    async def zcard(self, key: str) -> int:
        """
        获取有序集合成员数量
        
        Args:
            key: 键名
            
        Returns:
            int: 成员数量
        """
        if not self.redis:
            await self.connect()
        
        try:
            return await self.redis.zcard(key)
        
        except Exception as e:
            self.logger.error(f"获取有序集合大小失败 - {key}: {str(e)}")
            return 0
    
    # 高级功能 - 二进制数据
    async def set_pickle(self, key: str, value: Any, expire: int = None) -> bool:
        """
        使用pickle序列化存储Python对象
        
        Args:
            key: 键名
            value: 任意Python对象
            expire: 过期时间(秒)
            
        Returns:
            bool: 是否成功
        """
        if not self.redis:
            await self.connect()
        
        try:
            # 序列化对象
            pickled_value = pickle.dumps(value)
            
            # 设置参数
            params = {}
            if expire:
                params["expire"] = expire
            
            # 设置值
            result = await self.redis.set(f"pickle:{key}", pickled_value, **params)
            return result is True
        
        except Exception as e:
            self.logger.error(f"pickle存储失败 - {key}: {str(e)}")
            return False
    
    async def get_pickle(self, key: str, default: Any = None) -> Any:
        """
        获取并反序列化pickle对象
        
        Args:
            key: 键名
            default: 默认值，如果键不存在则返回
            
        Returns:
            Any: 反序列化后的Python对象
        """
        if not self.redis:
            await self.connect()
        
        try:
            value = await self.redis.get(f"pickle:{key}")
            if value is None:
                return default
            
            # 反序列化
            return pickle.loads(value)
        
        except Exception as e:
            self.logger.error(f"pickle获取失败 - {key}: {str(e)}")
            return default
    
    # 批量操作
    async def pipeline(self):
        """
        创建管道以执行批量操作
        
        Returns:
            Pipeline: Redis管道对象
        """
        if not self.redis:
            await self.connect()
        
        return self.redis.pipeline()
    
    async def execute_pipeline(self, pipeline) -> List[Any]:
        """
        执行管道操作
        
        Args:
            pipeline: Redis管道对象
            
        Returns:
            List[Any]: 结果列表
        """
        try:
            return await pipeline.execute()
        
        except Exception as e:
            self.logger.error(f"执行管道操作失败: {str(e)}")
            return [] 