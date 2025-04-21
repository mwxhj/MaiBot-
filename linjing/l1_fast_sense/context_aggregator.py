# linjing/l1_fast_sense/context_aggregator.py
import asyncio
import time
import json # 导入 json
from typing import Dict, Any, List, Optional

# 导入 redis.asyncio
try:
    import redis.asyncio as redis
except ImportError:
    redis = None
    print("错误: 未找到 'redis' 库 (需要版本 >= 4.2)。请运行 'pip install redis>=4.2.0rc1'。ContextAggregator 将无法工作。")

from linjing.utils.logger import get_logger

logger = get_logger(__name__)

# 假设未来会有一个存储接口或客户端
# from ..storage import FastContextStorage # 示例

class ContextAggregator:
    """
    L1 上下文聚合器。
    使用 Redis 从快速存储中获取与当前事件相关的少量、关键的上下文摘要。
    """
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化 ContextAggregator (Redis 版本)。

        Args:
            config: 配置字典，应包含 Redis 连接信息 (host, port, db, password)。
                    例如:
                    {
                        "redis_host": "localhost",
                        "redis_port": 6379,
                        "redis_db": 0,
                        "redis_password": null, # or your password
                        "l1_context_cache_max_len": 10, # 缓存长度
                        "l1_context_key_prefix": "l1ctx:", # Redis key 前缀
                        "user_activity_window_sec": 60 # 用于活跃度检查的时间窗口 (秒)
                    }
        """
        self.config = config or {}
        self.redis_client: Optional[redis.Redis] = None
        self._key_prefix = self.config.get("l1_context_key_prefix", "l1ctx:")
        # 每个会话缓存最近 N 条记录
        self._cache_max_len = int(self.config.get("l1_context_cache_max_len", 10))
        # 用户活跃度检查时间窗口
        self._activity_window = int(self.config.get("user_activity_window_sec", 60))

        if redis:
            try:
                redis_host = self.config.get("redis_host", "localhost")
                redis_port = int(self.config.get("redis_port", 6379))
                redis_db = int(self.config.get("redis_db", 0))
                redis_password = self.config.get("redis_password", None)

                # 创建异步 Redis 连接池
                self.redis_pool = redis.ConnectionPool(
                    host=redis_host,
                    port=redis_port,
                    db=redis_db,
                    password=redis_password,
                    decode_responses=True # 自动解码响应为字符串
                )
                self.redis_client = redis.Redis(connection_pool=self.redis_pool)
                logger.info(f"ContextAggregator 初始化完成，连接到 Redis: {redis_host}:{redis_port}/{redis_db}")
                # 可以添加一个 ping 测试连接
                # asyncio.create_task(self._test_redis_connection())
            except Exception as e:
                logger.error(f"连接 Redis 时出错: {e}", exc_info=True)
                self.redis_client = None # 确保客户端设为 None
        else:
             logger.error("Redis 库未安装，ContextAggregator 将无法工作。")


    async def _test_redis_connection(self):
        """测试 Redis 连接"""
        if not self.redis_client: return
        try:
            if await self.redis_client.ping():
                 logger.info("成功 Ping Redis 服务器。")
            else:
                 logger.warning("Ping Redis 服务器失败。")
        except Exception as e:
            logger.error(f"测试 Redis 连接时出错: {e}")


    async def update_context(self, session_id: str, raw_event: Dict[str, Any]):
        """
        使用原始事件更新 Redis 中的上下文列表。

        Args:
            session_id: 会话 ID。
            raw_event: 刚处理完的原始事件字典。
        """
        if not self.redis_client or self._cache_max_len <= 0:
            # logger.trace("Redis 未连接或缓存禁用，跳过上下文更新。")
            return

        redis_key = f"{self._key_prefix}{session_id}"
        user_id = raw_event.get("user_id")

        # 提取需要存储的摘要信息
        text = raw_event.get("raw_message") or raw_event.get("message", "")
        if isinstance(text, list):
             text = "".join(str(seg.get("data", {}).get("text", "")) if isinstance(seg, dict) and seg.get("type") == "text" else "" for seg in text)
        if not isinstance(text, str):
             text = str(text)

        # 使用更少的信息以减少存储大小
        event_summary = {
            "u": str(user_id) if user_id else "unk", # user_id 缩写
            "t": text[:100], # 限制文本长度
            "ts": raw_event.get("time", time.time()), # timestamp
            "mid": raw_event.get("message_id") # message_id
        }

        try:
            # 将摘要序列化为 JSON 字符串
            serialized_summary = json.dumps(event_summary, ensure_ascii=False)

            # 使用 Redis Pipeline 提高效率
            async with self.redis_client.pipeline(transaction=True) as pipe:
                # LPUSH 将新条目添加到列表头部
                await pipe.lpush(redis_key, serialized_summary)
                # LTRIM 保留列表指定长度 (0 到 max_len-1)，移除旧条目
                await pipe.ltrim(redis_key, 0, self._cache_max_len - 1)
                # 执行 Pipeline
                results = await pipe.execute()
                # logger.trace(f"Redis LPUSH/LTRIM results for {redis_key}: {results}")

            # 更新用户活跃度时间戳 (简单方法，使用 SET)
            if user_id:
                 activity_key = f"{self._key_prefix}user_activity:{user_id}:{session_id}"
                 # 设置键值，并设置过期时间
                 await self.redis_client.setex(activity_key, self._activity_window * 2, time.time()) # 稍微延长过期时间

            logger.trace(f"更新了 Redis Session '{redis_key}' 的 L1 上下文缓存。")

        except json.JSONDecodeError as e:
             logger.error(f"序列化事件摘要时出错 for {redis_key}: {e}", exc_info=True)
        except redis.RedisError as e:
            logger.error(f"与 Redis 交互时出错 for {redis_key}: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"更新 Redis 上下文时发生未知错误 for {redis_key}: {e}", exc_info=True)


    async def get_summary(self, session_id: str, current_event_id: Optional[Any] = None) -> Dict[str, Any]:
        """
        从 Redis 获取指定会话的上下文摘要。

        Args:
            session_id: 会话 ID。
            current_event_id: 当前正在处理的事件 ID (可选, 用于避免包含自身)。

        Returns:
            包含上下文摘要信息的字典。
        """
        if not self.redis_client or self._cache_max_len <= 0:
             return {"recent_messages": [], "last_interaction_time": None, "user_flags": []}

        redis_key = f"{self._key_prefix}{session_id}"
        recent_messages_summary = []
        last_interaction_time = None
        user_flags = []

        try:
            # LRANGE 获取列表中的所有条目 (最多 max_len 条)
            # 注意：获取比 max_len 稍多一点，以防当前事件恰好在列表末尾
            serialized_summaries = await self.redis_client.lrange(redis_key, 0, self._cache_max_len)

            if serialized_summaries:
                processed_count = 0
                for serialized in serialized_summaries:
                    if processed_count >= self._cache_max_len: # 确保最多返回 max_len 条
                        break
                    try:
                        msg = json.loads(serialized)
                        # 过滤掉当前事件
                        if msg.get("mid") == current_event_id:
                            continue

                        # 格式化摘要
                        text_summary = msg.get("t", "")
                        recent_messages_summary.append({
                            "user": msg.get("u", "unknown"),
                            "text_summary": (text_summary[:15] + "...") if len(text_summary) > 15 else text_summary,
                            "timestamp": msg.get("ts")
                        })
                        processed_count += 1
                    except json.JSONDecodeError:
                        logger.warning(f"无法解析 Redis 中存储的 JSON 摘要: {serialized}")
                    except Exception as e_inner:
                         logger.warning(f"处理单条 Redis 摘要时出错: {e_inner}")

                # 获取第一个（最新的）有效消息的时间戳
                if recent_messages_summary:
                    last_interaction_time = recent_messages_summary[0].get("timestamp")

            # 检查用户活跃度标记 (简单示例)
            last_user_id = recent_messages_summary[0].get("user") if recent_messages_summary else None
            if last_user_id and last_user_id != 'unknown':
                 is_frequent = await self._is_frequent(last_user_id, session_id)
                 if is_frequent:
                     user_flags.append("frequent_interactor")

        except redis.RedisError as e:
            logger.error(f"从 Redis 获取摘要时出错 for {redis_key}: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"获取 Redis 摘要时发生未知错误 for {redis_key}: {e}", exc_info=True)


        summary = {
             "recent_messages": recent_messages_summary,
             "last_interaction_time": last_interaction_time,
             "user_flags": user_flags
        }
        logger.debug(f"ContextAggregator 从 Redis 获取到的摘要 ({len(recent_messages_summary)} 条): {summary}")
        return summary

    async def _is_frequent(self, user_id: str, session_id: str) -> bool:
        """
        (示例) 检查用户在给定会话中是否近期活跃。
        简单实现：检查 Redis 中是否存在对应的活跃度时间戳 key。
        """
        if not self.redis_client: return False
        activity_key = f"{self._key_prefix}user_activity:{user_id}:{session_id}"
        try:
            # 简单地检查 key 是否存在
            exists = await self.redis_client.exists(activity_key)
            if exists:
                 # 可以进一步检查时间戳是否在窗口内，但 EXPIRE 已经处理了大部分情况
                 # last_active_time = await self.redis_client.get(activity_key)
                 # if last_active_time and (time.time() - float(last_active_time)) < self._activity_window:
                 #      return True
                 return True # 只要键存在（未过期）就认为是活跃的
            return False
        except redis.RedisError as e:
             logger.error(f"检查用户活跃度时出错 for {activity_key}: {e}")
             return False
        except Exception as e:
             logger.error(f"检查用户活跃度时发生未知错误 for {activity_key}: {e}")
             return False

    # 示例: 判断用户是否频繁交互的内部方法 (需要具体实现)
    # def _is_frequent(self, user_id: str, session_id: str) -> bool:
    #     # TODO: 实现判断逻辑, e.g., 检查短时间内发言次数
    #     return False 