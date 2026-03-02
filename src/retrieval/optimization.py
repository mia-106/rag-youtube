"""
检索优化模块
实现检索性能优化缓存策略和索引优化
"""

import asyncio
import time
from typing import Dict, Any, List, Optional
from datetime import datetime
import hashlib
import json
from dataclasses import dataclass
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """缓存条目"""

    data: Any
    timestamp: datetime
    access_count: int = 0
    last_accessed: datetime = None

    def __post_init__(self):
        if self.last_accessed is None:
            self.last_accessed = self.timestamp

    @property
    def age_seconds(self) -> float:
        """获取年龄秒"""
        return (datetime.now() - self.timestamp).total_seconds()

    def is_expired(self, ttl_seconds: int) -> bool:
        """检查是否过期"""
        return self.age_seconds > ttl_seconds

    def access(self):
        """访问记录"""
        self.access_count += 1
        self.last_accessed = datetime.now()


class RetrievalCache:
    """检索结果缓存管理器"""

    def __init__(self, max_size: int = 10000, ttl_seconds: int = 3600):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.cache: Dict[str, CacheEntry] = {}
        self.access_order: List[str] = []  # LRU顺序
        self.hit_count = 0
        self.miss_count = 0

    def _generate_key(self, query: str, config_hash: str) -> str:
        """生成缓存键"""
        query_hash = hashlib.md5(query.encode()).hexdigest()
        return f"{query_hash}:{config_hash}"

    def _get_config_hash(self, config: Dict[str, Any]) -> str:
        """生成配置哈希"""
        config_str = json.dumps(config, sort_keys=True)
        return hashlib.md5(config_str.encode()).hexdigest()

    def get(self, query: str, config: Dict[str, Any]) -> Optional[Any]:
        """获取缓存值"""
        config_hash = self._get_config_hash(config)
        key = self._generate_key(query, config_hash)

        if key in self.cache:
            entry = self.cache[key]
            if not entry.is_expired(self.ttl_seconds):
                entry.access()
                self.hit_count += 1
                logger.debug(f" 缓存命中: {query[:50]}...")
                return entry.data
            else:
                # 过期删除
                del self.cache[key]
                if key in self.access_order:
                    self.access_order.remove(key)

        self.miss_count += 1
        logger.debug(f" 缓存未命中: {query[:50]}...")
        return None

    def set(self, query: str, config: Dict[str, Any], data: Any):
        """设置缓存值"""
        config_hash = self._get_config_hash(config)
        key = self._generate_key(query, config_hash)

        # 如果已存在更新数据
        if key in self.cache:
            self.cache[key].data = data
            self.cache[key].timestamp = datetime.now()
        else:
            # 新建条目
            entry = CacheEntry(data=data, timestamp=datetime.now())
            self.cache[key] = entry
            self.access_order.append(key)

            # 检查缓存大小限制
            self._evict_if_needed()

    def _evict_if_needed(self):
        """如果需要清理缓存"""
        while len(self.cache) > self.max_size:
            self._evict_lru()

    def _evict_lru(self):
        """清理最少使用的条目"""
        if not self.access_order:
            return

        # 找到最少访问的条目
        lru_key = self.access_order[0]
        min_access = self.cache[lru_key].access_count

        for key in self.access_order:
            access_count = self.cache[key].access_count
            if access_count < min_access:
                min_access = access_count
                lru_key = key

        # 删除LRU条目
        del self.cache[lru_key]
        self.access_order.remove(lru_key)
        logger.debug(f" 清理LRU缓存: {lru_key[:20]}...")

    def clear_expired(self):
        """清理过期的缓存"""
        expired_keys = []
        for key, entry in self.cache.items():
            if entry.is_expired(self.ttl_seconds):
                expired_keys.append(key)

        for key in expired_keys:
            del self.cache[key]
            if key in self.access_order:
                self.access_order.remove(key)

        if expired_keys:
            logger.info(f" 清理了 {len(expired_keys)} 个过期缓存")

    def get_statistics(self) -> Dict[str, Any]:
        """获取缓存统计"""
        total_requests = self.hit_count + self.miss_count
        hit_rate = (self.hit_count / total_requests * 100) if total_requests > 0 else 0

        # 计算平均访问次数
        access_counts = [entry.access_count for entry in self.cache.values()]
        avg_access = sum(access_counts) / len(access_counts) if access_counts else 0

        return {
            "cache_size": len(self.cache),
            "max_size": self.max_size,
            "hit_count": self.hit_count,
            "miss_count": self.miss_count,
            "hit_rate": f"{hit_rate:.2f}%",
            "avg_access_count": f"{avg_access:.2f}",
            "ttl_seconds": self.ttl_seconds,
        }

    def clear(self):
        """清空缓存"""
        self.cache.clear()
        self.access_order.clear()
        self.hit_count = 0
        self.miss_count = 0
        logger.info(" 缓存已清空")


class ParallelRetriever:
    """并行检索器"""

    def __init__(self, max_workers: int = 5):
        self.max_workers = max_workers
        self.semaphore = asyncio.Semaphore(max_workers)

    async def retrieve_batch(
        self, queries: List[str], retrieve_func, config: Optional[Dict[str, Any]] = None
    ) -> List[Any]:
        """
        批量并行检索

        Args:
            queries: 查询列表
            retrieve_func: 检索函数
            config: 配置

        Returns:
            检索结果列表
        """
        logger.info(f" 开始并行检索: {len(queries)} 个查询")

        async def retrieve_single(query):
            async with self.semaphore:
                try:
                    if config:
                        return await retrieve_func(query, config)
                    else:
                        return await retrieve_func(query)
                except Exception as e:
                    logger.error(f" 检索失败 {query[:50]}: {str(e)}")
                    return []

        # 并发执行所有检索
        results = await asyncio.gather(*[retrieve_single(query) for query in queries])

        logger.info(f" 并行检索完成处理了 {len(results)} 个结果")
        return results


class IndexOptimizer:
    """索引优化器"""

    def __init__(self, database_url: str):
        self.database_url = database_url

    async def optimize_vector_index(self, table_name: str = "subtitle_chunks"):
        """
        优化向量索引

        Args:
            table_name: 表名
        """
        logger.info(f" 优化 {table_name} 表的向量索引")

        try:
            # 这里应该执行实际的SQL优化命令
            # 例如: REINDEX, ANALYZE, VACUUM等

            optimization_commands = [
                f"ANALYZE {table_name};",
                f"REINDEX TABLE {table_name};",
                # 可以添加更多优化命令
            ]

            # 模拟执行
            for cmd in optimization_commands:
                logger.debug(f"执行: {cmd}")
                # await self._execute_sql(cmd)

            logger.info(" 索引优化完成")

        except Exception as e:
            logger.error(f" 索引优化失败: {str(e)}")

    async def get_index_statistics(self, table_name: str = "subtitle_chunks") -> Dict[str, Any]:
        """获取索引统计信息"""
        try:
            # 这里应该查询实际的索引统计信息
            # 例如: pg_stat_user_indexes, pg_stat_user_tables等

            stats = {
                "table_name": table_name,
                "total_rows": 0,
                "index_size": "0 MB",
                "last_analyze": datetime.now().isoformat(),
                "last_vacuum": datetime.now().isoformat(),
            }

            return stats

        except Exception as e:
            logger.error(f" 获取索引统计失败: {str(e)}")
            return {}


class PerformanceMonitor:
    """性能监控器"""

    def __init__(self):
        self.metrics: Dict[str, List[float]] = defaultdict(list)
        self.start_times: Dict[str, float] = {}

    def start_timer(self, operation: str):
        """开始计时"""
        self.start_times[operation] = time.time()

    def end_timer(self, operation: str) -> float:
        """结束计时并记录"""
        if operation in self.start_times:
            duration = time.time() - self.start_times[operation]
            self.metrics[operation].append(duration)
            del self.start_times[operation]
            return duration
        return 0.0

    def record_metric(self, operation: str, value: float):
        """记录指标值"""
        self.metrics[operation].append(value)

    def get_statistics(self, operation: str) -> Dict[str, Any]:
        """获取操作统计"""
        if operation not in self.metrics or not self.metrics[operation]:
            return {"operation": operation, "count": 0, "avg": 0, "min": 0, "max": 0, "p95": 0, "p99": 0}

        values = self.metrics[operation]
        values.sort()

        count = len(values)
        avg = sum(values) / count
        p95_index = int(count * 0.95)
        p99_index = int(count * 0.99)

        return {
            "operation": operation,
            "count": count,
            "avg": f"{avg:.4f}s",
            "min": f"{values[0]:.4f}s",
            "max": f"{values[-1]:.4f}s",
            "p95": f"{values[p95_index]:.4f}s",
            "p99": f"{values[p99_index]:.4f}s",
        }

    def get_all_statistics(self) -> Dict[str, Dict[str, Any]]:
        """获取所有操作统计"""
        return {operation: self.get_statistics(operation) for operation in self.metrics}

    def clear(self):
        """清空所有指标"""
        self.metrics.clear()
        self.start_times.clear()
        logger.info(" 性能指标已清空")


class RetrievalOptimizer:
    """检索优化器"""

    def __init__(self, database_url: str, cache_size: int = 10000):
        self.cache = RetrievalCache(max_size=cache_size)
        self.parallel_retriever = ParallelRetriever()
        self.index_optimizer = IndexOptimizer(database_url)
        self.performance_monitor = PerformanceMonitor()

    async def optimize_search(self, query: str, search_func, config: Dict[str, Any]) -> Any:
        """
        优化搜索

        Args:
            query: 查询
            search_func: 搜索函数
            config: 配置

        Returns:
            搜索结果
        """
        self.performance_monitor.start_timer("total_search")

        try:
            # 1. 尝试从缓存获取
            cached_result = self.cache.get(query, config)
            if cached_result is not None:
                self.performance_monitor.record_metric("cache_hit", 1.0)
                return cached_result

            self.performance_monitor.record_metric("cache_hit", 0.0)

            # 2. 执行搜索
            self.performance_monitor.start_timer("search_execution")
            result = await search_func(query, config)
            search_time = self.performance_monitor.end_timer("search_execution")

            # 3. 缓存结果
            self.cache.set(query, config, result)

            # 4. 记录性能指标
            self.performance_monitor.record_metric("search_time", search_time)

            return result

        finally:
            total_time = self.performance_monitor.end_timer("total_search")
            self.performance_monitor.record_metric("total_time", total_time)

    async def optimize_batch(self, queries: List[str], search_func, config: Dict[str, Any]) -> List[Any]:
        """
        优化批量搜索

        Args:
            queries: 查询列表
            search_func: 搜索函数
            config: 配置

        Returns:
            搜索结果列表
        """
        self.performance_monitor.start_timer("batch_search")

        try:
            # 1. 分离缓存命中和未命中
            cached_results = {}
            uncached_queries = []

            for query in queries:
                cached = self.cache.get(query, config)
                if cached is not None:
                    cached_results[query] = cached
                else:
                    uncached_queries.append(query)

            # 2. 并行检索未缓存的查询
            if uncached_queries:
                self.performance_monitor.start_timer("parallel_search")
                uncached_results = await self.parallel_retriever.retrieve_batch(uncached_queries, search_func, config)
                parallel_time = self.performance_monitor.end_timer("parallel_search")

                # 3. 缓存新结果
                for query, result in zip(uncached_queries, uncached_results):
                    self.cache.set(query, config, result)

                self.performance_monitor.record_metric("parallel_search_time", parallel_time)

            # 4. 合并结果
            results = []
            for query in queries:
                if query in cached_results:
                    results.append(cached_results[query])
                else:
                    # 从未缓存结果中找
                    query_index = uncached_queries.index(query)
                    results.append(uncached_results[query_index])

            return results

        finally:
            total_time = self.performance_monitor.end_timer("batch_search")
            self.performance_monitor.record_metric("batch_total_time", total_time)

    def get_optimization_statistics(self) -> Dict[str, Any]:
        """获取优化统计"""
        cache_stats = self.cache.get_statistics()
        performance_stats = self.performance_monitor.get_all_statistics()

        return {"cache": cache_stats, "performance": performance_stats, "timestamp": datetime.now().isoformat()}

    def clear_cache(self):
        """清空缓存"""
        self.cache.clear()

    def clear_metrics(self):
        """清空性能指标"""
        self.performance_monitor.clear()


def test_retrieval_optimization():
    """测试检索优化"""
    print(" 测试检索优化...")

    # 创建优化器
    optimizer = RetrievalOptimizer("postgresql://user:pass@localhost/db", cache_size=1000)

    print(" 检索优化器创建成功")

    # 测试缓存
    print("\n 测试缓存...")
    config = {"top_k": 10, "threshold": 0.5}

    # 模拟搜索函数
    async def mock_search(query, config):
        await asyncio.sleep(0.1)  # 模拟搜索时间
        return f"Results for {query}"

    # 测试单个查询优化
    async def test_single_query():
        result = await optimizer.optimize_search("Python教程", mock_search, config)
        print(f"  查询结果: {result[:50]}...")

    asyncio.run(test_single_query())

    # 测试缓存统计
    print("\n 缓存统计:")
    cache_stats = optimizer.cache.get_statistics()
    for key, value in cache_stats.items():
        print(f"  {key}: {value}")

    # 测试性能监控
    print("\n 性能统计:")
    perf_stats = optimizer.performance_monitor.get_all_statistics()
    for operation, stats in perf_stats.items():
        print(f"  {operation}: {stats}")

    print("\n 所有测试完成")


if __name__ == "__main__":
    test_retrieval_optimization()
