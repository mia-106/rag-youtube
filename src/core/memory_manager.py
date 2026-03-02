"""
内存优化模块
提供内存管理对象池垃圾回收优化等功能
减少内存使用和提高系统性能
"""

import asyncio
import gc
import psutil
import threading
import time
from typing import Any, Dict, List, Callable, Generic, TypeVar
from dataclasses import dataclass, field
from collections import deque
from weakref import WeakSet, WeakValueDictionary
import logging

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class MemoryStats:
    """内存统计信息"""

    rss: int  # 常驻内存
    vms: int  # 虚拟内存
    percent: float  # 内存使用百分比
    available: int  # 可用内存
    used: int  # 已使用内存
    timestamp: float = field(default_factory=time.time)


class ObjectPool(Generic[T]):
    """对象池实现"""

    def __init__(self, factory: Callable[[], T], maxsize: int = 100):
        self.factory = factory
        self.maxsize = maxsize
        self._pool = deque(maxlen=maxsize)
        self._in_use = WeakSet()

    def acquire(self) -> T:
        """获取对象"""
        try:
            return self._pool.popleft()
        except IndexError:
            return self.factory()

    def release(self, obj: T):
        """释放对象"""
        if len(self._pool) < self.maxsize:
            self._pool.append(obj)


class MemoryMonitor:
    """内存监控器"""

    def __init__(self, threshold_percent: float = 80.0):
        self.threshold_percent = threshold_percent
        self.stats_history = deque(maxlen=100)
        self.monitoring = False
        self._monitor_task = None

    def get_memory_stats(self) -> MemoryStats:
        """获取当前内存统计"""
        memory = psutil.virtual_memory()
        return MemoryStats(
            rss=psutil.Process().memory_info().rss,
            vms=psutil.Process().memory_info().vms,
            percent=memory.percent,
            available=memory.available,
            used=memory.used,
        )

    def start_monitoring(self, interval: float = 5.0):
        """开始内存监控"""
        if self.monitoring:
            return

        self.monitoring = True
        self._monitor_task = asyncio.create_task(self._monitor_loop(interval))
        logger.info(f" 内存监控已启动 (阈值: {self.threshold_percent}%)")

    async def stop_monitoring(self):
        """停止内存监控"""
        self.monitoring = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.info(" 内存监控已停止")

    async def _monitor_loop(self, interval: float):
        """监控循环"""
        while self.monitoring:
            try:
                stats = self.get_memory_stats()
                self.stats_history.append(stats)

                # 检查内存使用率
                if stats.percent >= self.threshold_percent:
                    logger.warning(f" 内存使用率过高: {stats.percent:.1f}% (阈值: {self.threshold_percent}%)")
                    await self._trigger_cleanup()

                await asyncio.sleep(interval)
            except Exception as e:
                logger.error(f" 内存监控出错: {e}")
                await asyncio.sleep(interval)

    async def _trigger_cleanup(self):
        """触发内存清理"""
        logger.info(" 触发内存清理...")
        gc.collect()

        # 可选释放一些缓存
        try:
            from src.core.cache import cleanup_expired_caches

            await cleanup_expired_caches()
        except Exception as e:
            logger.error(f" 清理缓存失败: {e}")


class MemoryEfficientList:
    """内存高效的列表实现"""

    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self._data = deque(maxlen=max_size)
        self._access_count = 0

    def append(self, item: Any):
        """添加项目"""
        self._data.append(item)

    def extend(self, items: List[Any]):
        """批量添加项目"""
        # 批量添加避免频繁的内存分配
        for item in items:
            if len(self._data) >= self.max_size:
                break
            self._data.append(item)

    def get_recent(self, n: int) -> List[Any]:
        """获取最近的n个项目"""
        return list(self._data)[-n:]

    def clear(self):
        """清空列表"""
        self._data.clear()


class MemoryTracker:
    """内存跟踪器"""

    def __init__(self):
        self.tracked_objects = WeakValueDictionary()
        self._lock = threading.Lock()

    def track(self, obj_id: str, obj: Any, size_estimate: int = 0):
        """跟踪对象"""
        with self._lock:
            self.tracked_objects[obj_id] = {"object": obj, "size_estimate": size_estimate, "created_at": time.time()}

    def untrack(self, obj_id: str):
        """取消跟踪"""
        with self._lock:
            if obj_id in self.tracked_objects:
                del self.tracked_objects[obj_id]

    def get_tracked_count(self) -> int:
        """获取跟踪对象数量"""
        return len(self.tracked_objects)

    def get_memory_usage(self) -> int:
        """获取内存使用估计"""
        return sum(info["size_estimate"] for info in self.tracked_objects.values())


class LazyLoader:
    """延迟加载器"""

    def __init__(self, loader_func: Callable[[], Any]):
        self.loader_func = loader_func
        self._loaded = False
        self._data = None

    def get(self) -> Any:
        """获取数据延迟加载"""
        if not self._loaded:
            self._data = self.loader_func()
            self._loaded = True
        return self._data

    def reset(self):
        """重置下次访问时重新加载"""
        self._loaded = False
        self._data = None


# 全局内存管理实例
memory_monitor = MemoryMonitor()
memory_tracker = MemoryTracker()


def optimize_garbage_collection():
    """优化垃圾回收设置"""
    # 调整GC阈值减少频繁回收
    gc.set_threshold(700, 10, 10)

    # 启用自动回收
    gc.enable()

    logger.info(" 垃圾回收已优化")


async def force_garbage_collection():
    """强制垃圾回收"""
    collected = gc.collect()
    logger.info(f" 垃圾回收完成回收了 {collected} 个对象")
    return collected


def get_memory_summary() -> Dict[str, Any]:
    """获取内存使用摘要"""
    process = psutil.Process()
    memory_info = process.memory_info()
    memory_percent = process.memory_percent()

    return {
        "rss_mb": round(memory_info.rss / 1024 / 1024, 2),
        "vms_mb": round(memory_info.vms / 1024 / 1024, 2),
        "percent": round(memory_percent, 2),
        "tracked_objects": memory_tracker.get_tracked_count(),
        "gc_counts": gc.get_count(),
    }


async def memory_optimization_task():
    """内存优化任务"""
    while True:
        try:
            # 每10分钟执行一次内存优化
            await asyncio.sleep(600)

            # 检查内存使用率
            stats = memory_monitor.get_memory_stats()
            if stats.percent >= memory_monitor.threshold_percent:
                logger.warning(f" 内存使用率过高: {stats.percent:.1f}%")
                await force_garbage_collection()

            # 定期清理过期缓存
            try:
                from src.core.cache import cleanup_expired_caches

                await cleanup_expired_caches()
            except Exception as e:
                logger.error(f" 清理缓存失败: {e}")

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f" 内存优化任务出错: {e}")


# === 上下文管理器 ===
class MemoryContext:
    """内存上下文管理器"""

    def __init__(self, enable_monitoring: bool = True):
        self.enable_monitoring = enable_monitoring
        self.initial_stats = None
        self.final_stats = None

    async def __aenter__(self):
        """进入上下文"""
        if self.enable_monitoring:
            self.initial_stats = memory_monitor.get_memory_stats()
            if not memory_monitor.monitoring:
                memory_monitor.start_monitoring()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """退出上下文"""
        if self.enable_monitoring:
            self.final_stats = memory_monitor.get_memory_stats()
            diff_rss = (self.final_stats.rss - self.initial_stats.rss) / 1024 / 1024
            logger.info(
                f" 内存使用变化: {diff_rss:+.2f} MB "
                f"({self.initial_stats.percent:.1f}%  {self.final_stats.percent:.1f}%)"
            )


# === 装饰器 ===
def memory_efficient(func: Callable) -> Callable:
    """内存高效装饰器"""

    def wrapper(*args, **kwargs):
        # 在函数执行前清理一次
        gc.collect()

        result = func(*args, **kwargs)

        # 在函数执行后清理一次
        gc.collect()

        return result

    return wrapper


def lazy_property(func: Callable) -> property:
    """延迟属性装饰器"""
    return property(LazyLoader(func).get)


# === 初始化 ===
def initialize_memory_management():
    """初始化内存管理"""
    # 优化垃圾回收
    optimize_garbage_collection()

    # 启动内存监控
    memory_monitor.start_monitoring()

    logger.info(" 内存管理系统已初始化")


# === 使用示例 ===
# with MemoryContext():
#     # 执行内存密集型操作
#     pass

# @memory_efficient
# def heavy_operation():
#     # 内存高效的函数
#     pass

# lazy_obj = LazyLoader(lambda: expensive_operation())
# result = lazy_obj.get()  # 只在第一次访问时执行
