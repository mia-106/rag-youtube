"""
缓存模块
提供LRU缓存TTL缓存等多种缓存策略
支持异步操作和线程安全
"""

import asyncio
import time
import json
import hashlib
from typing import Any, Optional, Callable, Generic, TypeVar, Dict
from dataclasses import dataclass
from collections import OrderedDict
from functools import wraps
import logging

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class CacheEntry:
    """缓存条目"""

    value: Any
    timestamp: float
    ttl: Optional[float] = None
    access_count: int = 0
    last_access: float = 0

    def is_expired(self) -> bool:
        """检查是否过期"""
        if self.ttl is None:
            return False
        return time.time() - self.timestamp > self.ttl

    def update_access(self):
        """更新访问信息"""
        self.access_count += 1
        self.last_access = time.time()


class BaseCache(Generic[T]):
    """缓存基类"""

    def __init__(self, maxsize: int = 1000):
        self.maxsize = maxsize
        self._cache: Dict[str, CacheEntry] = OrderedDict()
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[T]:
        """获取缓存值"""
        async with self._lock:
            if key not in self._cache:
                return None

            entry = self._cache[key]

            # 检查是否过期
            if entry.is_expired():
                del self._cache[key]
                return None

            # 更新访问信息
            entry.update_access()
            return entry.value

    async def set(self, key: str, value: T, ttl: Optional[float] = None) -> None:
        """设置缓存值"""
        async with self._lock:
            # 如果缓存已满删除最旧的条目
            if len(self._cache) >= self.maxsize:
                await self._evict_lru()

            # 创建新条目
            entry = CacheEntry(value=value, timestamp=time.time(), ttl=ttl)
            entry.update_access()

            # 存储条目
            self._cache[key] = entry

    async def delete(self, key: str) -> bool:
        """删除缓存值"""
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    async def clear(self) -> None:
        """清空缓存"""
        async with self._lock:
            self._cache.clear()

    async def _evict_lru(self) -> None:
        """删除最久未使用的条目"""
        if not self._cache:
            return

        # 找到最久未访问的条目
        oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k].last_access)
        del self._cache[oldest_key]

    def size(self) -> int:
        """获取缓存大小"""
        return len(self._cache)

    def stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        total_access = sum(entry.access_count for entry in self._cache.values())
        expired_count = sum(1 for entry in self._cache.values() if entry.is_expired())

        return {
            "size": self.size(),
            "maxsize": self.maxsize,
            "total_access": total_access,
            "expired_entries": expired_count,
            "hit_ratio": 0.0,  # 将在实际使用中计算
        }


class LRUCache(BaseCache[T]):
    """LRU缓存实现"""

    def __init__(self, maxsize: int = 1000):
        super().__init__(maxsize)

    async def get(self, key: str) -> Optional[T]:
        """获取缓存值移动到末尾"""
        async with self._lock:
            if key not in self._cache:
                return None

            entry = self._cache[key]

            # 检查是否过期
            if entry.is_expired():
                del self._cache[key]
                return None

            # 移动到末尾最最近使用
            del self._cache[key]
            entry.update_access()
            self._cache[key] = entry

            return entry.value


class TTLCache(BaseCache[T]):
    """TTL缓存实现"""

    def __init__(self, maxsize: int = 1000, default_ttl: float = 3600):
        super().__init__(maxsize)
        self.default_ttl = default_ttl

    async def set(self, key: str, value: T, ttl: Optional[float] = None) -> None:
        """设置缓存值使用TTL"""
        await super().set(key, value, ttl or self.default_ttl)

    async def cleanup_expired(self) -> int:
        """清理过期的缓存条目"""
        async with self._lock:
            expired_keys = [key for key, entry in self._cache.items() if entry.is_expired()]
            for key in expired_keys:
                del self._cache[key]
            return len(expired_keys)


class CacheManager:
    """缓存管理器"""

    def __init__(self):
        self._caches: Dict[str, BaseCache] = {}
        self._default_cache = None

    def register_cache(self, name: str, cache: BaseCache) -> None:
        """注册缓存"""
        self._caches[name] = cache
        if self._default_cache is None:
            self._default_cache = cache

    def get_cache(self, name: str) -> Optional[BaseCache]:
        """获取缓存"""
        return self._caches.get(name)

    async def cleanup_all(self) -> Dict[str, int]:
        """清理所有缓存的过期条目"""
        results = {}
        for name, cache in self._caches.items():
            if isinstance(cache, TTLCache):
                results[name] = await cache.cleanup_expired()
            else:
                results[name] = 0
        return results

    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """获取所有缓存的统计信息"""
        return {name: cache.stats() for name, cache in self._caches.items()}


# 全局缓存管理器实例
cache_manager = CacheManager()


def cache_key_generator(*args, **kwargs) -> str:
    """生成缓存键"""
    # 合并所有参数
    key_data = {"args": args, "kwargs": sorted(kwargs.items())}

    # 序列化为JSON
    key_json = json.dumps(key_data, default=str, sort_keys=True)

    # 生成MD5哈希
    return hashlib.md5(key_json.encode()).hexdigest()


def cached(
    cache_name: str = "default", ttl: Optional[float] = None, key_func: Optional[Callable] = None, maxsize: int = 1000
):
    """
    缓存装饰器

    Args:
        cache_name: 缓存名称
        ttl: 生存时间秒
        key_func: 自定义键生成函数
        maxsize: 缓存最大大小
    """

    def decorator(func: Callable) -> Callable:
        # 获取或创建缓存
        cache = cache_manager.get_cache(cache_name)
        if cache is None:
            # 创建新缓存
            cache = TTLCache(maxsize=maxsize, default_ttl=ttl or 3600)
            cache_manager.register_cache(cache_name, cache)

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # 生成缓存键
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = cache_key_generator(*args, **kwargs)

            # 尝试从缓存获取
            cached_result = await cache.get(cache_key)
            if cached_result is not None:
                logger.debug(f"缓存命中: {func.__name__}({cache_key})")
                return cached_result

            # 执行函数
            logger.debug(f"缓存未命中: {func.__name__}({cache_key})")
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            # 存储到缓存
            await cache.set(cache_key, result, ttl)

            return result

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # 对于同步函数暂时不支持缓存
            # 未来可以添加线程安全缓存
            return func(*args, **kwargs)

        # 根据函数类型返回包装器
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


# === 预定义缓存实例 ===
# API调用缓存
api_cache = TTLCache(maxsize=500, default_ttl=1800)  # 30分钟
cache_manager.register_cache("api", api_cache)

# 数据库查询缓存
db_cache = TTLCache(maxsize=200, default_ttl=600)  # 10分钟
cache_manager.register_cache("database", db_cache)

# 向量搜索缓存
vector_cache = TTLCache(maxsize=300, default_ttl=900)  # 15分钟
cache_manager.register_cache("vector", vector_cache)

# 嵌入向量缓存
embedding_cache = TTLCache(maxsize=1000, default_ttl=3600)  # 1小时
cache_manager.register_cache("embedding", embedding_cache)


# === 缓存工具函数 ===
async def get_cache_stats() -> Dict[str, Any]:
    """获取缓存统计信息"""
    return cache_manager.get_all_stats()


async def clear_all_caches() -> None:
    """清空所有缓存"""
    for cache in cache_manager._caches.values():
        await cache.clear()
    logger.info(" 所有缓存已清空")


async def cleanup_expired_caches() -> Dict[str, int]:
    """清理所有缓存的过期条目"""
    results = await cache_manager.cleanup_all()
    total_cleaned = sum(results.values())
    if total_cleaned > 0:
        logger.info(f" 清理了 {total_cleaned} 个过期缓存条目")
    return results


def invalidate_cache_by_pattern(pattern: str) -> int:
    """
    根据模式使缓存失效简单实现

    Args:
        pattern: 要匹配的键模式

    Returns:
        失效的条目数量
    """
    # 简单实现实际使用中可能需要更复杂的模式匹配
    count = 0
    for cache in cache_manager._caches.values():
        # 这里需要实现具体的模式匹配逻辑
        # 暂时返回0
        pass
    return count


# === 缓存监控任务 ===
async def cache_cleanup_task(interval: int = 3600):
    """
    定期清理过期缓存的任务

    Args:
        interval: 清理间隔秒
    """
    while True:
        await asyncio.sleep(interval)
        try:
            cleaned = await cleanup_expired_caches()
            logger.debug(f" 缓存清理完成: {cleaned}")
        except Exception as e:
            logger.error(f" 缓存清理失败: {e}")


# === 使用示例 ===
# @cached(cache_name="api", ttl=1800)
# async def fetch_data(url: str):
#     # 获取数据
#     pass

# @cached(cache_name="database", ttl=600)
# async def query_database(sql: str):
#     # 查询数据库
#     pass
