#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
资源锁管理器，提供对共享资源的细粒度锁控制。
实现辅助策略：Locking
"""

import asyncio
import time
from enum import Enum, auto
from typing import Dict, Any, Set, Optional
from contextlib import asynccontextmanager

from ..utils.logger import get_logger

logger = get_logger(__name__)

class ResourceType(Enum):
    """资源类型枚举"""
    MEMORY = auto()  # 记忆系统
    EMOTION = auto()  # 情绪系统
    SESSION = auto()  # 会话状态
    DATABASE = auto()  # 数据库
    VECTOR_DB = auto() # 向量数据库

class LockType(Enum):
    """锁类型枚举"""
    READ = auto()  # 读锁
    WRITE = auto()  # 写锁

class ResourceLockManager:
    """
    资源锁管理器，提供对共享资源的细粒度锁控制
    使用读写锁模式，允许多个读操作并发，但写操作需要独占
    """
    def __init__(self, lock_timeout: float = 30.0):
        # 资源锁字典
        self.locks: Dict[ResourceType, asyncio.Lock] = {}
        # 资源读写锁字典
        self.rw_locks: Dict[ResourceType, Dict[str, Any]] = {}
        # 锁定超时时间（秒）
        self.lock_timeout = lock_timeout
        # 初始化资源锁
        self._init_locks()
        # 用于统计和监控的数据
        self.stats = {
            resource_type: {
                "total_read_locks": 0,
                "total_write_locks": 0,
                "active_readers": 0,
                "active_writers": 0,
                "read_wait_time_total": 0.0,
                "write_wait_time_total": 0.0,
                "read_hold_time_total": 0.0,
                "write_hold_time_total": 0.0,
                "last_read_time": 0,
                "last_write_time": 0,
            }
            for resource_type in ResourceType
        }
        self.running = False
        self.log_task = None
    
    def _init_locks(self) -> None:
        """初始化所有资源锁"""
        for resource_type in ResourceType:
            self.locks[resource_type] = asyncio.Lock()
            self.rw_locks[resource_type] = {
                "readers": 0,  # 当前读取器数量
                "readers_waiting": 0,  # 等待中的读取器数量
                "writers_waiting": 0,  # 等待中的写入器数量
                "writer_active": False,  # 是否有活跃的写入器
                "read_event": asyncio.Event(),  # 读取事件
                "write_event": asyncio.Event(),  # 写入事件
                "lock": asyncio.Lock(),  # 内部锁
            }
            # 初始状态下，读取事件是置位的（可以读取）
            self.rw_locks[resource_type]["read_event"].set()
    
    @asynccontextmanager
    async def lock(self, resource_type: ResourceType) -> None:
        """
        获取指定资源的互斥锁
        
        Args:
            resource_type: 资源类型
            
        Yields:
            无返回值，使用 async with 语法获取锁
        """
        lock = self.locks.get(resource_type)
        if not lock:
            logger.error(f"尝试锁定未知资源类型: {resource_type}")
            yield
            return
        
        locked = False
        start_time = time.time()
        lock_id = f"{resource_type.name}_{id(lock)}_{int(start_time * 1000) % 10000}"
        
        try:
            logger.info(f"[锁 {lock_id}] 尝试获取资源 {resource_type.name} 的互斥锁")
            locked = await asyncio.wait_for(lock.acquire(), timeout=self.lock_timeout)
            acquire_time = time.time() - start_time
            logger.info(f"[锁 {lock_id}] 已获取资源 {resource_type.name} 的互斥锁，耗时: {acquire_time:.3f}秒")
            
            lock_start = time.time()
            yield
            lock_duration = time.time() - lock_start
            logger.info(f"[锁 {lock_id}] 资源 {resource_type.name} 的锁操作完成，持有时间: {lock_duration:.3f}秒")
        except asyncio.TimeoutError:
            logger.error(f"[锁 {lock_id}] 获取资源 {resource_type.name} 互斥锁超时 (>{self.lock_timeout}秒)")
            yield
        finally:
            if locked and lock.locked():
                lock.release()
                total_time = time.time() - start_time
                logger.info(f"[锁 {lock_id}] 已释放资源 {resource_type.name} 的互斥锁，总耗时: {total_time:.3f}秒")
    
    @asynccontextmanager
    async def read_lock(self, resource_type: ResourceType) -> None:
        """
        获取指定资源的读锁
        多个读锁可以同时持有，但与写锁互斥
        
        Args:
            resource_type: 资源类型
            
        Yields:
            无返回值，使用 async with 语法获取锁
        """
        rw_lock = self.rw_locks.get(resource_type)
        if not rw_lock:
            logger.error(f"尝试读锁定未知资源类型: {resource_type}")
            yield
            return
        
        start_time = time.time()
        lock_id = f"R_{resource_type.name}_{int(start_time * 1000) % 10000}"
        
        # 获取内部锁
        logger.info(f"[读锁 {lock_id}] 正在等待读取资源 {resource_type.name}")
        
        async with rw_lock["lock"]:
            rw_lock["readers_waiting"] += 1
            logger.debug(f"[读锁 {lock_id}] 读取等待计数增加，当前: {rw_lock['readers_waiting']}")
        
        # 等待读取事件（当没有写入器时）
        try:
            logger.info(f"[读锁 {lock_id}] 等待获取资源 {resource_type.name} 的读锁")
            await asyncio.wait_for(rw_lock["read_event"].wait(), timeout=self.lock_timeout)
            
            # 再次获取内部锁更新状态
            async with rw_lock["lock"]:
                rw_lock["readers_waiting"] -= 1
                rw_lock["readers"] += 1
                acquire_time = time.time() - start_time
                # 更新统计数据
                self.stats[resource_type]["total_read_locks"] += 1
                self.stats[resource_type]["active_readers"] += 1
                self.stats[resource_type]["read_wait_time_total"] += acquire_time
                self.stats[resource_type]["last_read_time"] = int(time.time())
                
                logger.info(f"[读锁 {lock_id}] 已获取资源 {resource_type.name} 的读锁，当前读取器数量: {rw_lock['readers']}，耗时: {acquire_time:.3f}秒")
            
            lock_start = time.time()
            try:
                yield
            finally:
                lock_duration = time.time() - lock_start
                logger.info(f"[读锁 {lock_id}] 资源 {resource_type.name} 的读锁操作完成，持有时间: {lock_duration:.3f}秒")
                
                # 更新统计数据
                self.stats[resource_type]["read_hold_time_total"] += lock_duration
                
                # 释放读锁
                async with rw_lock["lock"]:
                    rw_lock["readers"] -= 1
                    # 更新统计
                    self.stats[resource_type]["active_readers"] -= 1
                    
                    total_time = time.time() - start_time
                    logger.info(f"[读锁 {lock_id}] 已释放资源 {resource_type.name} 的读锁，剩余读取器数量: {rw_lock['readers']}，总耗时: {total_time:.3f}秒")
                    
                    # 如果没有更多读取器且有写入器等待，则设置写入事件
                    if rw_lock["readers"] == 0 and rw_lock["writers_waiting"] > 0:
                        logger.info(f"[读锁 {lock_id}] 没有更多读取器且有写入器等待，触发写入事件")
                        rw_lock["write_event"].set()
        
        except asyncio.TimeoutError:
            # 超时情况下，减少等待计数
            async with rw_lock["lock"]:
                rw_lock["readers_waiting"] -= 1
            logger.error(f"[读锁 {lock_id}] 获取资源 {resource_type.name} 读锁超时 (>{self.lock_timeout}秒)")
            yield
    
    @asynccontextmanager
    async def write_lock(self, resource_type: ResourceType) -> None:
        """
        获取指定资源的写锁
        写锁是独占的，与其他任何锁互斥
        
        Args:
            resource_type: 资源类型
            
        Yields:
            无返回值，使用 async with 语法获取锁
        """
        rw_lock = self.rw_locks.get(resource_type)
        if not rw_lock:
            logger.error(f"尝试写锁定未知资源类型: {resource_type}")
            yield
            return
        
        start_time = time.time()
        lock_id = f"W_{resource_type.name}_{int(start_time * 1000) % 10000}"
        
        logger.info(f"[写锁 {lock_id}] 正在等待写入资源 {resource_type.name}")
        
        # 获取内部锁并更新等待状态
        async with rw_lock["lock"]:
            rw_lock["writers_waiting"] += 1
            logger.debug(f"[写锁 {lock_id}] 写入等待计数增加，当前: {rw_lock['writers_waiting']}")
            
            # 如果已有读取器或写入器，清除写入事件等待
            if rw_lock["readers"] > 0 or rw_lock["writer_active"]:
                logger.debug(f"[写锁 {lock_id}] 当前有 {rw_lock['readers']} 个读取器，写入器活跃: {rw_lock['writer_active']}，清除写入事件")
                rw_lock["write_event"].clear()
            else:
                logger.debug(f"[写锁 {lock_id}] 没有读取器或活跃写入器，设置写入事件")
                rw_lock["write_event"].set()
            
            # 如果有写入器在等待，清除读取事件防止新的读取器进入
            if rw_lock["writers_waiting"] > 0:
                logger.debug(f"[写锁 {lock_id}] 有 {rw_lock['writers_waiting']} 个写入器在等待，清除读取事件")
                rw_lock["read_event"].clear()
        
        try:
            # 等待写入事件
            logger.info(f"[写锁 {lock_id}] 等待获取资源 {resource_type.name} 的写锁")
            await asyncio.wait_for(rw_lock["write_event"].wait(), timeout=self.lock_timeout)
            
            # 获取内部锁更新状态
            async with rw_lock["lock"]:
                rw_lock["writers_waiting"] -= 1
                rw_lock["writer_active"] = True
                # 确保读取事件清除（防止新读取器进入）
                rw_lock["read_event"].clear()
                # 清除写入事件（防止其他写入器进入）
                rw_lock["write_event"].clear()
                
                acquire_time = time.time() - start_time
                # 更新统计数据
                self.stats[resource_type]["total_write_locks"] += 1
                self.stats[resource_type]["active_writers"] += 1
                self.stats[resource_type]["write_wait_time_total"] += acquire_time
                self.stats[resource_type]["last_write_time"] = int(time.time())
                
                logger.info(f"[写锁 {lock_id}] 已获取资源 {resource_type.name} 的写锁，耗时: {acquire_time:.3f}秒")
            
            lock_start = time.time()
            try:
                yield
            finally:
                lock_duration = time.time() - lock_start
                logger.info(f"[写锁 {lock_id}] 资源 {resource_type.name} 的写锁操作完成，持有时间: {lock_duration:.3f}秒")
                
                # 更新统计数据
                self.stats[resource_type]["write_hold_time_total"] += lock_duration
                
                # 释放写锁
                async with rw_lock["lock"]:
                    rw_lock["writer_active"] = False
                    # 更新统计
                    self.stats[resource_type]["active_writers"] -= 1
                    
                    total_time = time.time() - start_time
                    logger.info(f"[写锁 {lock_id}] 已释放资源 {resource_type.name} 的写锁，总耗时: {total_time:.3f}秒")
                    
                    # 如果有写入器在等待，优先让写入器获得锁
                    if rw_lock["writers_waiting"] > 0:
                        logger.info(f"[写锁 {lock_id}] 有 {rw_lock['writers_waiting']} 个写入器在等待，触发写入事件")
                        rw_lock["write_event"].set()
                    else:
                        # 否则允许读取器获得锁
                        logger.info(f"[写锁 {lock_id}] 没有写入器在等待，有 {rw_lock['readers_waiting']} 个读取器在等待，触发读取事件")
                        rw_lock["read_event"].set()
        
        except asyncio.TimeoutError:
            # 超时情况下，减少等待计数
            async with rw_lock["lock"]:
                rw_lock["writers_waiting"] -= 1
            logger.error(f"[写锁 {lock_id}] 获取资源 {resource_type.name} 写锁超时 (>{self.lock_timeout}秒)")
            yield
    
    def start(self) -> None:
        """启动锁管理器，开始记录锁状态"""
        if self.running:
            logger.warning("锁管理器已在运行")
            return
        
        self.running = True
        logger.info("启动锁管理器")
        # 启动定期状态日志任务
        self.log_task = asyncio.create_task(self._log_status_periodically())
    
    async def stop(self) -> None:
        """停止锁管理器"""
        if not self.running:
            return
        
        self.running = False
        
        # 取消日志任务
        if self.log_task and not self.log_task.done():
            self.log_task.cancel()
            try:
                await self.log_task
            except asyncio.CancelledError:
                pass
        
        logger.info("锁管理器已停止")
    
    async def _log_status_periodically(self) -> None:
        """定期记录锁状态"""
        try:
            while self.running:
                self.log_lock_status()
                await asyncio.sleep(30)  # 每30秒记录一次状态
        except asyncio.CancelledError:
            logger.info("定期记录锁状态任务已取消")
        except Exception as e:
            logger.error(f"定期记录锁状态任务出错: {e}", exc_info=True)
    
    def log_lock_status(self) -> None:
        """记录当前所有锁的状态"""
        try:
            any_active = False
            
            # 首先检查是否有活跃的锁
            for resource_type in ResourceType:
                rw_lock = self.rw_locks.get(resource_type)
                if not rw_lock:
                    continue
                
                if (rw_lock["readers"] > 0 or rw_lock["writer_active"] or 
                    rw_lock["readers_waiting"] > 0 or rw_lock["writers_waiting"] > 0):
                    any_active = True
                    break
            
            # 如果没有活跃锁，只记录简要信息
            if not any_active:
                logger.info("资源锁状态: 所有资源空闲")
                return
            
            # 记录详细状态
            logger.info("资源锁状态:")
            for resource_type in ResourceType:
                rw_lock = self.rw_locks.get(resource_type)
                if not rw_lock:
                    continue
                
                # 获取锁的基本信息
                readers = rw_lock["readers"]
                readers_waiting = rw_lock["readers_waiting"]
                writers_waiting = rw_lock["writers_waiting"]
                writer_active = rw_lock["writer_active"]
                
                # 只记录有活动的资源
                if readers > 0 or writer_active or readers_waiting > 0 or writers_waiting > 0:
                    status = []
                    if readers > 0:
                        status.append(f"{readers} 个读取器活跃")
                    if writer_active:
                        status.append("写入器活跃")
                    if readers_waiting > 0:
                        status.append(f"{readers_waiting} 个读取器等待")
                    if writers_waiting > 0:
                        status.append(f"{writers_waiting} 个写入器等待")
                    
                    logger.info(f"  - {resource_type.name}: {', '.join(status)}")
                    
                    # 记录统计数据
                    stats = self.stats[resource_type]
                    logger.debug(f"    统计: 总读锁: {stats['total_read_locks']}, "
                                 f"总写锁: {stats['total_write_locks']}, "
                                 f"平均读等待: {stats['read_wait_time_total'] / max(1, stats['total_read_locks']):.3f}秒, "
                                 f"平均写等待: {stats['write_wait_time_total'] / max(1, stats['total_write_locks']):.3f}秒")
        except Exception as e:
            logger.error(f"记录锁状态时出错: {e}", exc_info=True)

class EasyResourceLock:
    """简化版资源锁，提供对共享资源的基本锁定"""
    
    def __init__(self):
        # 资源锁字典
        self.locks: Dict[ResourceType, asyncio.Lock] = {}
        # 锁定超时时间（秒）
        self.lock_timeout: float = 30.0
        # 初始化资源锁
        for resource_type in ResourceType:
            self.locks[resource_type] = asyncio.Lock()
        
        # 统计数据
        self.stats = {
            resource_type: {
                "total_locks": 0,
                "active_locks": 0,
                "wait_time_total": 0.0,
                "hold_time_total": 0.0,
                "last_lock_time": 0,
            }
            for resource_type in ResourceType
        }
        self.running = False
        self.log_task = None
    
    @asynccontextmanager
    async def lock(self, resource_type: ResourceType) -> None:
        """
        获取指定资源的锁
        
        Args:
            resource_type: 资源类型
            
        Yields:
            无返回值，使用 async with 语法获取锁
        """
        lock = self.locks.get(resource_type)
        if not lock:
            logger.error(f"尝试锁定未知资源类型: {resource_type}")
            yield
            return
        
        locked = False
        start_time = time.time()
        lock_id = f"{resource_type.name}_{id(lock)}_{int(start_time * 1000) % 10000}"
        
        try:
            logger.info(f"[锁 {lock_id}] 尝试获取资源 {resource_type.name} 的锁")
            locked = await asyncio.wait_for(lock.acquire(), timeout=self.lock_timeout)
            acquire_time = time.time() - start_time
            
            # 更新统计数据
            self.stats[resource_type]["total_locks"] += 1
            self.stats[resource_type]["active_locks"] += 1
            self.stats[resource_type]["wait_time_total"] += acquire_time
            self.stats[resource_type]["last_lock_time"] = int(time.time())
            
            logger.info(f"[锁 {lock_id}] 已获取资源 {resource_type.name} 的锁，耗时: {acquire_time:.3f}秒")
            
            lock_start = time.time()
            yield
            lock_duration = time.time() - lock_start
            
            # 更新统计数据
            self.stats[resource_type]["hold_time_total"] += lock_duration
            
            logger.info(f"[锁 {lock_id}] 资源 {resource_type.name} 的锁操作完成，持有时间: {lock_duration:.3f}秒")
        except asyncio.TimeoutError:
            logger.error(f"[锁 {lock_id}] 获取资源 {resource_type.name} 锁超时 (>{self.lock_timeout}秒)")
            yield
        finally:
            if locked and lock.locked():
                # 更新统计数据
                self.stats[resource_type]["active_locks"] -= 1
                
                lock.release()
                total_time = time.time() - start_time
                logger.info(f"[锁 {lock_id}] 已释放资源 {resource_type.name} 的锁，总耗时: {total_time:.3f}秒")
    
    def start(self) -> None:
        """启动锁管理器，开始记录锁状态"""
        if self.running:
            logger.warning("锁管理器已在运行")
            return
        
        self.running = True
        logger.info("启动简化版锁管理器")
        # 启动定期状态日志任务
        self.log_task = asyncio.create_task(self._log_status_periodically())
    
    async def stop(self) -> None:
        """停止锁管理器"""
        if not self.running:
            return
        
        self.running = False
        
        # 取消日志任务
        if self.log_task and not self.log_task.done():
            self.log_task.cancel()
            try:
                await self.log_task
            except asyncio.CancelledError:
                pass
        
        logger.info("简化版锁管理器已停止")
    
    async def _log_status_periodically(self) -> None:
        """定期记录锁状态"""
        try:
            while self.running:
                self.log_lock_status()
                await asyncio.sleep(30)  # 每30秒记录一次状态
        except asyncio.CancelledError:
            logger.info("定期记录锁状态任务已取消")
        except Exception as e:
            logger.error(f"定期记录锁状态任务出错: {e}", exc_info=True)
    
    def log_lock_status(self) -> None:
        """记录当前所有锁的状态"""
        try:
            any_active = False
            
            # 检查是否有活跃的锁
            for resource_type in ResourceType:
                lock = self.locks.get(resource_type)
                if not lock:
                    continue
                
                if lock.locked() or self.stats[resource_type]["active_locks"] > 0:
                    any_active = True
                    break
            
            # 如果没有活跃锁，只记录简要信息
            if not any_active:
                logger.info("简化版资源锁状态: 所有资源空闲")
                return
            
            # 记录详细状态
            logger.info("简化版资源锁状态:")
            for resource_type in ResourceType:
                lock = self.locks.get(resource_type)
                if not lock:
                    continue
                
                # 只记录有活动的资源
                if lock.locked() or self.stats[resource_type]["active_locks"] > 0:
                    stats = self.stats[resource_type]
                    logger.info(f"  - {resource_type.name}: {'锁定中' if lock.locked() else '未锁定'}, "
                               f"活跃锁: {stats['active_locks']}")
                    logger.debug(f"    统计: 总锁定次数: {stats['total_locks']}, "
                                f"平均等待时间: {stats['wait_time_total'] / max(1, stats['total_locks']):.3f}秒, "
                                f"平均持有时间: {stats['hold_time_total'] / max(1, stats['total_locks']):.3f}秒")
        except Exception as e:
            logger.error(f"记录锁状态时出错: {e}", exc_info=True) 