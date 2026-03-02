"""
计算优化模块
消除重复计算提高系统性能
包含缓存批处理惰性求值并行计算等技术
"""

import asyncio
import functools
import time
from typing import Any, Dict, List, Optional, Callable, Generic, TypeVar
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import logging


logger = logging.getLogger(__name__)

T = TypeVar("T")
R = TypeVar("R")


@dataclass
class ComputationResult:
    """计算结果"""

    value: Any
    computation_time: float
    cache_hit: bool = False
    timestamp: float = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()


class BatchProcessor(Generic[T, R]):
    """批处理器"""

    def __init__(self, processor_func: Callable[[List[T]], List[R]], batch_size: int = 100, max_wait_time: float = 1.0):
        self.processor_func = processor_func
        self.batch_size = batch_size
        self.max_wait_time = max_wait_time

        self._pending_items: List[T] = []
        self._pending_futures: List[asyncio.Future] = []
        self._batch_timer = None
        self._lock = asyncio.Lock()

    async def process(self, item: T) -> R:
        """处理单个项目批处理"""
        future = asyncio.Future()

        async with self._lock:
            self._pending_items.append(item)
            self._pending_futures.append(future)

            # 如果批次已满立即处理
            if len(self._pending_items) >= self.batch_size:
                await self._process_batch()
            elif self._batch_timer is None:
                # 启动定时器
                self._batch_timer = asyncio.create_task(self._batch_timer_task())

        return await future

    async def _process_batch(self):
        """处理当前批次"""
        if not self._pending_items:
            return

        # 获取待处理项目
        items = self._pending_items.copy()
        futures = self._pending_futures.copy()

        # 清空待处理队列
        self._pending_items.clear()
        self._pending_futures.clear()
        self._batch_timer = None

        # 在后台线程中处理
        try:
            results = await asyncio.get_event_loop().run_in_executor(None, self.processor_func, items)

            # 设置结果
            for future, result in zip(futures, results):
                future.set_result(result)

        except Exception as e:
            # 设置异常
            for future in futures:
                future.set_exception(e)

    async def _batch_timer_task(self):
        """批次定时器任务"""
        await asyncio.sleep(self.max_wait_time)

        async with self._lock:
            if self._pending_items:
                await self._process_batch()

    async def flush(self):
        """强制处理所有待处理项目"""
        async with self._lock:
            if self._pending_items:
                await self._process_batch()


class LazyValue(Generic[T]):
    """惰性值"""

    def __init__(self, factory: Callable[[], T]):
        self.factory = factory
        self._value = None
        self._computed = False

    def get(self) -> T:
        """获取值惰性计算"""
        if not self._computed:
            self._value = self.factory()
            self._computed = True
        return self._value

    def reset(self):
        """重置下次访问时重新计算"""
        self._value = None
        self._computed = False


class MemoizationCache:
    """记忆化缓存"""

    def __init__(self, maxsize: int = 128):
        self.maxsize = maxsize
        self._cache = {}
        self._access_order = []
        self._lock = asyncio.Lock()

    async def get(self, key: Any) -> Optional[Any]:
        """获取缓存值"""
        async with self._lock:
            if key in self._cache:
                # 更新访问顺序
                self._access_order.remove(key)
                self._access_order.append(key)
                return self._cache[key]
            return None

    async def set(self, key: Any, value: Any):
        """设置缓存值"""
        async with self._lock:
            # 如果缓存已满删除最久未使用的项
            if len(self._cache) >= self.maxsize:
                oldest_key = self._access_order.pop(0)
                del self._cache[oldest_key]

            # 添加新项
            self._cache[key] = value
            self._access_order.append(key)

    async def clear(self):
        """清空缓存"""
        async with self._lock:
            self._cache.clear()
            self._access_order.clear()


class ParallelProcessor:
    """并行处理器"""

    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self.thread_executor = ThreadPoolExecutor(max_workers=max_workers)
        self.process_executor = ProcessPoolExecutor(max_workers=max_workers)

    async def map_async(self, func: Callable[[T], R], items: List[T], use_process: bool = False) -> List[R]:
        """异步映射"""
        executor = self.process_executor if use_process else self.thread_executor

        tasks = [asyncio.get_event_loop().run_in_executor(executor, func, item) for item in items]

        return await asyncio.gather(*tasks)

    async def map_with_limit(self, func: Callable[[T], R], items: List[T], limit: int = 10) -> List[R]:
        """带限制的异步映射"""
        semaphore = asyncio.Semaphore(limit)

        async def limited_func(item):
            async with semaphore:
                return await asyncio.get_event_loop().run_in_executor(None, func, item)

        tasks = [limited_func(item) for item in items]
        return await asyncio.gather(*tasks)

    def shutdown(self):
        """关闭处理器"""
        self.thread_executor.shutdown(wait=True)
        self.process_executor.shutdown(wait=True)


class ComputationOptimizer:
    """计算优化器"""

    def __init__(self):
        self.memo_cache = MemoizationCache(maxsize=256)
        self.batch_processors: Dict[str, BatchProcessor] = {}
        self.lazy_values: Dict[str, LazyValue] = {}
        self.parallel_processor = ParallelProcessor()

        # 性能统计
        self.stats = {"total_computations": 0, "cache_hits": 0, "batch_computations": 0, "parallel_computations": 0}

    async def memoize(self, func: Callable, key_func: Optional[Callable] = None) -> Callable:
        """创建记忆化函数"""

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # 生成缓存键
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = (args, tuple(sorted(kwargs.items())))

            # 尝试从缓存获取
            cached_result = await self.memo_cache.get(cache_key)
            if cached_result is not None:
                self.stats["cache_hits"] += 1
                return cached_result

            # 执行计算
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = await asyncio.get_event_loop().run_in_executor(None, func, *args, **kwargs)

            # 缓存结果
            await self.memo_cache.set(cache_key, result)
            self.stats["total_computations"] += 1

            return result

        return wrapper

    def create_batch_processor(
        self, name: str, processor_func: Callable, batch_size: int = 100, max_wait_time: float = 1.0
    ) -> BatchProcessor:
        """创建批处理器"""
        processor = BatchProcessor(processor_func, batch_size, max_wait_time)
        self.batch_processors[name] = processor
        return processor

    def add_lazy_value(self, name: str, factory: Callable):
        """添加惰性值"""
        self.lazy_values[name] = LazyValue(factory)

    def get_lazy_value(self, name: str) -> Any:
        """获取惰性值"""
        if name not in self.lazy_values:
            raise KeyError(f"惰性值 '{name}' 不存在")

        return self.lazy_values[name].get()

    async def parallel_map(
        self, func: Callable, items: List[Any], use_process: bool = False, limit: Optional[int] = None
    ) -> List[Any]:
        """并行映射"""
        if limit:
            result = await self.parallel_processor.map_with_limit(func, items, limit)
        else:
            result = await self.parallel_processor.map_async(func, items, use_process)

        self.stats["parallel_computations"] += len(items)
        return result

    def get_optimization_stats(self) -> Dict[str, Any]:
        """获取优化统计"""
        total = self.stats["total_computations"]
        cache_hit_rate = (self.stats["cache_hits"] / total * 100) if total > 0 else 0

        return {
            **self.stats,
            "cache_hit_rate_percent": round(cache_hit_rate, 2),
            "memo_cache_size": len(self.memo_cache._cache),
            "lazy_values_count": len(self.lazy_values),
            "batch_processors_count": len(self.batch_processors),
        }

    async def flush_all_batches(self):
        """刷新所有批次"""
        for processor in self.batch_processors.values():
            await processor.flush()

    async def clear_all_caches(self):
        """清空所有缓存"""
        await self.memo_cache.clear()
        for lazy_value in self.lazy_values.values():
            lazy_value.reset()
        self.stats = {"total_computations": 0, "cache_hits": 0, "batch_computations": 0, "parallel_computations": 0}


# === 装饰器 ===
def batch_process(batch_size: int = 100, max_wait_time: float = 1.0, processor_name: Optional[str] = None):
    """批处理装饰器"""

    def decorator(func):
        if not hasattr(func, "_batch_processor"):
            # 创建批处理器
            resolved_name = processor_name or f"{func.__module__}.{func.__name__}"
            processor = BatchProcessor(func, batch_size, max_wait_time)
            func._batch_processor = processor
            func._batch_processor_name = resolved_name

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # 如果是异步函数使用批处理器
            if asyncio.iscoroutinefunction(func):
                processor = func._batch_processor
                # 假设第一个参数是要处理的项目
                if args:
                    return await processor.process(args[0])
                else:
                    return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)

        # 添加刷新方法
        async def flush():
            if hasattr(func, "_batch_processor"):
                await func._batch_processor.flush()

        wrapper.flush = flush
        return wrapper

    return decorator


def parallel_execute(limit: Optional[int] = None):
    """并行执行装饰器"""

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(items: List[Any]):
            if not items:
                return []

            # 如果是单个函数并行执行多个项目
            if asyncio.iscoroutinefunction(func):
                if limit:
                    semaphore = asyncio.Semaphore(limit)
                    tasks = [semaphore.wait(func(item)) for item in items]
                    return await asyncio.gather(*tasks)
                else:
                    return await asyncio.gather(*[func(item) for item in items])
            else:
                # 同步函数使用线程池
                executor = ThreadPoolExecutor(max_workers=limit or 4)
                loop = asyncio.get_event_loop()
                tasks = [loop.run_in_executor(executor, func, item) for item in items]
                return await asyncio.gather(*tasks)

        return wrapper

    return decorator


# === 全局优化器实例 ===
computation_optimizer = ComputationOptimizer()


# === 使用示例 ===
# # 记忆化
# @computation_optimizer.memoize
# async def expensive_computation(x: int) -> int:
#     await asyncio.sleep(1)  # 模拟耗时计算
#     return x * x

# # 批处理
# @batch_process(batch_size=50, max_wait_time=0.5)
# def process_item(item: int) -> str:
#     return f"processed_{item}"

# # 并行执行
# @parallel_execute(limit=10)
# async def process_parallel(item: int) -> str:
#     await asyncio.sleep(0.1)
#     return f"parallel_{item}"

# # 惰性值
# computation_optimizer.add_lazy_value(
#     "config_data",
#     lambda: load_expensive_config()
# )
# config = computation_optimizer.get_lazy_value("config_data")
