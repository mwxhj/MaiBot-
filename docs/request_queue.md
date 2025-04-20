# 请求队列机制设计文档

## 概述

请求队列机制是MaiBot框架中的一个核心组件，用于管理和处理高并发请求场景。它提供了基于类型的资源隔离、优先级队列管理、请求超时与取消、资源限制与自动回收等功能，同时支持详细的运行状态监控。

## 设计目标

1. **资源隔离**：不同类型的请求使用不同的队列处理，避免相互干扰
2. **并发控制**：限制每种类型的请求并发数量，避免资源过度消耗
3. **优先级支持**：高优先级请求优先处理，保证重要操作及时执行
4. **超时处理**：自动处理长时间未完成的请求，避免资源泄漏
5. **状态监控**：提供详细的队列状态信息，便于监控和调试
6. **类型安全**：通过泛型支持，提供更好的类型安全保障
7. **可扩展性**：灵活的设计使其能够适应各种使用场景

## 核心组件

### 请求状态 (RequestStatus)

定义请求的生命周期状态：

- `PENDING`：等待处理
- `PROCESSING`：处理中
- `COMPLETED`：已完成
- `FAILED`：失败
- `CANCELLED`：已取消
- `TIMEOUT`：超时

### 队列类型 (RequestQueueType)

预定义的请求队列类型：

- `DEFAULT`：默认队列
- `MESSAGE`：消息处理队列
- `API`：API调用队列
- `DATABASE`：数据库操作队列
- `MEDIA`：媒体处理队列
- `FILE`：文件操作队列
- `NETWORK`：网络请求队列

### 请求任务 (RequestTask)

表示一个要处理的请求：

- 包含请求ID、类型、数据、元数据等基本信息
- 记录创建时间、开始处理时间、完成时间等时间戳
- 支持请求优先级和超时时间设置
- 提供状态转换方法（标记开始、完成、失败等）
- 使用Future存储结果，支持异步等待

### 类型化请求队列 (TypedRequestQueue)

特定类型请求的处理队列：

- 按优先级排序处理请求
- 支持并发处理多个请求
- 自动处理超时请求
- 提供队列状态监控

### 请求队列管理器 (RequestQueueManager)

管理不同类型的请求队列：

- 根据需要创建并缓存不同类型的队列
- 提供统一的请求添加接口
- 支持请求取消操作
- 定期清理空闲队列
- 提供全局状态监控

## 使用方法

### 基本用法

```python
import asyncio
from linjing.concurrent import RequestQueueManager, RequestQueueType

# 创建一个处理函数
async def process_data(data):
    # 处理数据的逻辑
    await asyncio.sleep(1)  # 模拟处理时间
    return {"result": f"处理完成: {data}"}

async def main():
    # 创建请求队列管理器
    manager = RequestQueueManager()
    
    # 启动管理器
    await manager.start()
    
    try:
        # 添加请求到队列
        task = await manager.add_request(
            queue_type=RequestQueueType.API,
            data={"id": 1, "value": "test"},
            processor=process_data,
            priority=0,  # 优先级，数字越小优先级越高
            timeout=10.0  # 10秒超时
        )
        
        # 等待结果
        result = await task.future
        print(f"处理结果: {result}")
        
    finally:
        # 停止管理器
        await manager.stop()

if __name__ == "__main__":
    asyncio.run(main())
```

### 处理大量请求

```python
import asyncio
from linjing.concurrent import RequestQueueManager, RequestQueueType

async def process_batch_requests():
    manager = RequestQueueManager(
        default_concurrent=10,  # 允许10个并发处理
        default_queue_size=100  # 队列最大大小为100
    )
    
    await manager.start()
    
    try:
        # 创建多个请求任务
        tasks = []
        for i in range(50):
            task = await manager.add_request(
                queue_type=RequestQueueType.DATABASE,
                data={"query": f"SELECT * FROM table WHERE id = {i}"},
                processor=lambda data: asyncio.sleep(0.5) and {"rows": [1, 2, 3]},
                priority=i % 5  # 使用不同优先级
            )
            tasks.append(task)
        
        # 等待所有任务完成
        results = await asyncio.gather(*[t.future for t in tasks])
        
        print(f"所有请求已完成，结果数: {len(results)}")
        
    finally:
        await manager.stop()
```

### 监控队列状态

```python
async def monitor_queues(manager, interval=5.0):
    """定期监控队列状态"""
    while True:
        status = await manager.get_status()
        
        print(f"总队列数: {status['total_queues']}")
        
        for queue_type, queue_info in status["queues"].items():
            print(f"队列 {queue_type}:")
            print(f"  - 等待请求: {queue_info['queue_size']}")
            print(f"  - 处理中: {queue_info['processing']}")
            print(f"  - 已处理: {queue_info['tasks_processed']}")
            print(f"  - 失败数: {queue_info['tasks_failed']}")
        
        print("-" * 50)
        
        await asyncio.sleep(interval)
```

## 最佳实践

1. **合理设置队列类型**：根据业务类型选择合适的队列类型，避免不同类型的请求相互影响。

2. **设置合理的优先级**：重要请求应设置较高的优先级（数值较小），确保优先处理。

3. **适当的超时时间**：根据操作复杂度设置合理的超时时间，避免资源长时间占用。

4. **资源限制**：设置合理的队列大小和并发数，避免系统资源过度消耗。

5. **异常处理**：请求处理函数应妥善处理异常，确保即使处理失败也能返回有意义的错误信息。

6. **状态监控**：定期检查队列状态，及时发现并解决潜在问题。

7. **取消未处理的请求**：在系统关闭或用户退出时，应考虑取消尚未处理的请求。

## 扩展与自定义

### 自定义队列类型

可以扩展`RequestQueueType`枚举添加自定义队列类型：

```python
from enum import Enum
from linjing.concurrent.request_queue import RequestQueueType

class CustomQueueType(Enum):
    VOICE_PROCESSING = "voice_processing"
    IMAGE_RECOGNITION = "image_recognition"
    LARGE_LANGUAGE_MODEL = "llm"

# 使用自定义队列类型
await manager.add_request(
    queue_type=CustomQueueType.VOICE_PROCESSING,
    data=voice_data,
    processor=process_voice
)
```

### 自定义处理策略

可以继承`TypedRequestQueue`类来实现自定义的请求处理策略：

```python
class CustomRequestQueue(TypedRequestQueue):
    async def process_queue(self) -> None:
        # 自定义处理逻辑
        pass
```

## 性能考虑

1. 请求队列机制主要适用于I/O密集型操作，如网络请求、数据库操作等。

2. 对于CPU密集型操作，应考虑使用进程池等其他并发机制。

3. 监控内存使用情况，确保队列中的请求数据不会占用过多内存。

4. 定期清理队列中的过期请求和已完成任务，避免内存泄漏。

## 与其他组件的集成

### 与MessageDebouncer集成

```python
from linjing.concurrent import MessageDebouncer, RequestQueueManager

# 在消息去重后处理请求
async def process_debounced_messages(messages, contexts):
    manager = RequestQueueManager()
    
    # 将合并后的消息加入处理队列
    task = await manager.add_request(
        queue_type=RequestQueueType.MESSAGE,
        data={"messages": messages, "contexts": contexts},
        processor=process_message_group
    )
    
    return await task.future
```

### 与ResourceLockManager集成

```python
from linjing.concurrent import ResourceLockManager, RequestQueueManager

# 在请求处理中使用资源锁
async def safe_db_operation(data):
    lock_manager = ResourceLockManager()
    
    # 获取资源锁
    async with await lock_manager.acquire_lock("database", "write"):
        # 执行数据库操作
        result = await perform_db_operation(data)
        return result

# 将安全的数据库操作加入请求队列
task = await request_manager.add_request(
    queue_type=RequestQueueType.DATABASE,
    data=db_data,
    processor=safe_db_operation
)
```

## 未来改进方向

1. **分布式支持**：扩展为分布式请求队列，支持跨进程、跨服务器的请求处理。

2. **持久化**：支持请求队列的持久化，保证系统重启后能够恢复未处理的请求。

3. **限流策略**：实现更复杂的限流策略，如令牌桶、漏桶等算法。

4. **批处理**：支持请求批处理，对类似请求进行批量处理以提高效率。

5. **更详细的监控**：提供更详细的性能指标和监控数据，便于系统调优。 