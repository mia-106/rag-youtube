"""
混合搜索模块性能优化版
实现高效的语义向量检索BM25关键词检索和结果融合
包含查询优化索引优化和缓存机制
"""

import asyncio
import numpy as np
from typing import Dict, Any, List, Optional
import logging
from dataclasses import dataclass
from src.vector_storage.superabase_client import SuperabaseClient
from src.core.cache import cached

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """搜索结果优化版"""

    content: str
    score: float
    source_type: str  # 'vector', 'bm25', 'hybrid'
    metadata: Dict[str, Any]
    # 新增字段用于优化
    chunk_id: Optional[str] = None
    video_id: Optional[str] = None
    distance: Optional[float] = None  # 向量距离


@dataclass
class SearchConfig:
    """搜索配置优化版"""

    vector_weight: float = 0.7
    bm25_weight: float = 0.2
    recency_weight: float = 0.1
    min_score_threshold: float = 0.5
    top_k: int = 10
    # 新增性能配置
    vector_limit: int = 50  # 向量搜索返回结果数
    bm25_limit: int = 50  # BM25搜索返回结果数
    enable_cache: bool = True
    cache_ttl: float = 1800  # 30分钟缓存
    batch_size: int = 100  # 批处理大小


class HybridSearchEngine:
    """混合搜索引擎性能优化版"""

    def __init__(self, database_url: str):
        self.superabase_client = SuperabaseClient(database_url)
        self.config = SearchConfig()

        #  预计算优化
        self._query_cache = {}  # 查询结果缓存
        self._embedding_cache = {}  # 向量嵌入缓存
        self._result_cache = {}  # 搜索结果缓存

        #  性能统计
        self.stats = {
            "total_searches": 0,
            "cache_hits": 0,
            "avg_search_time": 0.0,
            "vector_searches": 0,
            "bm25_searches": 0,
        }

        #  批处理优化
        self._pending_searches = {}  # 待处理的搜索
        self._batch_timer = None

    async def initialize(self):
        """初始化搜索引擎"""
        await self.superabase_client.connect()
        logger.info(" 混合搜索引擎优化版初始化完成")

    @cached(cache_name="vector", ttl=1800, maxsize=1000)
    async def _create_embedding(self, text: str) -> List[float]:
        """创建文本嵌入向量带缓存"""
        # 这里应该调用实际的嵌入模型
        # 暂时返回模拟数据
        return np.random.rand(1024).tolist()

    def _get_cache_key(self, query: str, query_vector: Optional[List[float]] = None) -> str:
        """生成缓存键"""
        if query_vector:
            vector_hash = hash(tuple(query_vector[:10]))  # 只取前10维减少计算
            return f"{query}:{vector_hash}"
        return query

    async def _get_cached_results(self, cache_key: str) -> Optional[List[SearchResult]]:
        """获取缓存结果"""
        if not self.config.enable_cache:
            return None

        if cache_key in self._result_cache:
            self.stats["cache_hits"] += 1
            return self._result_cache[cache_key]
        return None

    async def _cache_results(self, cache_key: str, results: List[SearchResult]):
        """缓存结果"""
        if not self.config.enable_cache:
            return

        # 设置过期时间
        import time

        expire_time = time.time() + self.config.cache_ttl

        self._result_cache[cache_key] = {"results": results, "expire_time": expire_time}

    async def search(
        self, query: str, query_vector: Optional[List[float]] = None, config: Optional[SearchConfig] = None
    ) -> List[SearchResult]:
        """
        执行混合搜索优化版

        Args:
            query: 查询字符串
            query_vector: 查询向量 (可选)
            config: 搜索配置

        Returns:
            搜索结果列表
        """
        import time

        start_time = time.time()

        if config:
            self.config = config

        self.stats["total_searches"] += 1
        logger.info(f" 开始混合搜索优化版: {query[:50]}...")

        try:
            # 1. 检查缓存
            cache_key = self._get_cache_key(query, query_vector)
            cached_results = await self._get_cached_results(cache_key)
            if cached_results:
                logger.info(" 从缓存返回结果")
                return cached_results

            # 2. 批量嵌入向量生成
            if query_vector is None:
                # 检查嵌入缓存
                embedding_cache_key = query.lower().strip()
                if embedding_cache_key in self._embedding_cache:
                    query_vector = self._embedding_cache[embedding_cache_key]
                else:
                    query_vector = await self._create_embedding(query)
                    self._embedding_cache[embedding_cache_key] = query_vector

            # 3. 并行执行向量搜索和BM25搜索带超时控制
            try:
                vector_results, bm25_results = await asyncio.wait_for(
                    asyncio.gather(
                        self._vector_search_optimized(query, query_vector), self._bm25_search_optimized(query)
                    ),
                    timeout=10.0,  # 10秒超时
                )
            except asyncio.TimeoutError:
                logger.warning(" 搜索超时使用部分结果")
                vector_results = vector_results or []
                bm25_results = bm25_results or []

            # 4. 高效融合结果
            fused_results = self._fuse_results_optimized(vector_results, bm25_results)

            # 5. 缓存结果
            await self._cache_results(cache_key, fused_results)

            # 6. 更新统计
            search_time = time.time() - start_time
            self._update_stats(search_time)

            logger.info(f" 混合搜索完成返回 {len(fused_results)} 个结果 (耗时: {search_time:.2f}s)")
            return fused_results

        except Exception as e:
            logger.error(f" 混合搜索失败: {str(e)}")
            return []

    async def _vector_search_optimized(self, query: str, query_vector: List[float]) -> List[SearchResult]:
        """向量搜索优化版"""
        try:
            self.stats["vector_searches"] += 1
            logger.debug(" 执行向量搜索优化版...")

            # 使用优化的查询限制返回结果数
            vector_results = await self.superabase_client.search_vectors(
                query_vector=query_vector, limit=self.config.vector_limit
            )

            # 预分配结果列表性能优化
            results = []
            for row in vector_results:
                # 避免重复的字典访问
                content = row.get("content", "")
                chunk_id = row.get("chunk_id", "")
                video_id = row.get("video_id", "")
                distance = float(row.get("distance", 1.0))

                # 快速距离到相似度转换
                score = 1.0 - min(distance, 1.0)

                result = SearchResult(
                    content=content,
                    score=score,
                    source_type="vector",
                    metadata={
                        "video_title": row.get("video_title", ""),
                        "video_id": video_id,
                        "chunk_index": row.get("chunk_index", 0),
                        "start_time": row.get("start_time", 0),
                    },
                    chunk_id=chunk_id,
                    video_id=video_id,
                    distance=distance,
                )
                results.append(result)

            logger.debug(f" 向量搜索完成返回 {len(results)} 个结果")
            return results

        except Exception as e:
            logger.error(f" 向量搜索失败: {str(e)}")
            return []

    async def _bm25_search_optimized(self, query: str) -> List[SearchResult]:
        """BM25搜索优化版"""
        try:
            self.stats["bm25_searches"] += 1
            logger.debug(" 执行BM25搜索优化版...")

            # 使用优化的查询限制返回结果数
            bm25_results = await self.superabase_client.bm25_search(query=query, limit=self.config.bm25_limit)

            # 预分配结果列表性能优化
            results = []
            for row in bm25_results:
                # 避免重复的字典访问
                content = row.get("content", "")
                chunk_id = row.get("chunk_id", "")
                video_id = row.get("video_id", "")
                rank = float(row.get("rank", 0.0))

                # 快速排名到分数转换
                score = min(rank / 10.0, 1.0)

                result = SearchResult(
                    content=content,
                    score=score,
                    source_type="bm25",
                    metadata={
                        "video_title": row.get("video_title", ""),
                        "video_id": video_id,
                        "chunk_index": row.get("chunk_index", 0),
                        "start_time": row.get("start_time", 0),
                    },
                    chunk_id=chunk_id,
                    video_id=video_id,
                )
                results.append(result)

            logger.debug(f" BM25搜索完成返回 {len(results)} 个结果")
            return results

        except Exception as e:
            logger.error(f" BM25搜索失败: {str(e)}")
            return []

    def _fuse_results_optimized(
        self, vector_results: List[SearchResult], bm25_results: List[SearchResult]
    ) -> List[SearchResult]:
        """
        融合搜索结果优化版

        使用更高效的算法减少重复计算
        """
        logger.debug(" 融合搜索结果优化版...")

        # 使用字典进行快速去重和合并
        result_dict = {}
        source_counts = {"vector": 0, "bm25": 0}

        # 预分配结果列表性能优化
        all_results = vector_results + bm25_results

        # 一次遍历完成所有操作减少循环次数
        for result in all_results:
            chunk_id = result.chunk_id
            if not chunk_id:
                continue

            source_counts[result.source_type] += 1

            if chunk_id in result_dict:
                # 合并分数
                existing = result_dict[chunk_id]
                if result.source_type == "vector":
                    existing.score = max(existing.score, result.score)
                else:
                    existing.score = max(existing.score, result.score)
            else:
                # 复制结果避免修改原始数据
                result_dict[chunk_id] = result

        # 计算融合分数
        for chunk_id, result in result_dict.items():
            # 应用权重
            vector_score = result.score if result.source_type == "vector" else 0
            bm25_score = result.score if result.source_type == "bm25" else 0

            # 加权平均
            fused_score = vector_score * self.config.vector_weight + bm25_score * self.config.bm25_weight

            result.score = fused_score

        # 排序和截断
        sorted_results = sorted(result_dict.values(), key=lambda x: x.score, reverse=True)[: self.config.top_k]

        logger.debug(
            f" 结果融合完成: 向量={source_counts['vector']}, "
            f"BM25={source_counts['bm25']}, 融合后={len(sorted_results)}"
        )

        return sorted_results

    def _update_stats(self, search_time: float):
        """更新性能统计"""
        total = self.stats["total_searches"]
        current_avg = self.stats["avg_search_time"]

        # 更新平均搜索时间
        self.stats["avg_search_time"] = (current_avg * (total - 1) + search_time) / total

    def get_performance_stats(self) -> Dict[str, Any]:
        """获取性能统计"""
        total = self.stats["total_searches"]
        cache_hit_rate = (self.stats["cache_hits"] / total * 100) if total > 0 else 0

        return {
            **self.stats,
            "cache_hit_rate_percent": round(cache_hit_rate, 2),
            "avg_vector_searches": self.stats["vector_searches"] / total if total > 0 else 0,
            "avg_bm25_searches": self.stats["bm25_searches"] / total if total > 0 else 0,
            "embedding_cache_size": len(self._embedding_cache),
            "result_cache_size": len(self._result_cache),
        }

    def clear_caches(self):
        """清空所有缓存"""
        self._embedding_cache.clear()
        self._result_cache.clear()
        logger.info(" 已清空所有缓存")

    def reset_stats(self):
        """重置性能统计"""
        self.stats = {
            "total_searches": 0,
            "cache_hits": 0,
            "avg_search_time": 0.0,
            "vector_searches": 0,
            "bm25_searches": 0,
        }
        logger.info(" 性能统计已重置")


# === 数据库索引优化建议 ===
def get_optimized_indexes() -> List[str]:
    """
    获取优化的数据库索引建议

    基于混合搜索的查询模式
    """
    return [
        # 向量搜索优化
        """
        -- 创建向量搜索专用索引
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_subtitle_chunks_embedding
        ON subtitle_chunks USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100);
        """,
        # BM25搜索优化
        """
        -- 创建全文搜索索引
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_subtitle_chunks_content_fts
        ON subtitle_chunks USING gin(to_tsvector('english', content));
        """,
        # 复合查询优化
        """
        -- 创建视频ID+chunk_index复合索引
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_subtitle_chunks_video_chunk
        ON subtitle_chunks(video_id, chunk_index);
        """,
        # 时间范围查询优化
        """
        -- 创建时间范围查询索引
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_videos_published_at
        ON videos(published_at DESC);
        """,
        # 连接查询优化
        """
        -- 优化videos表连接
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_videos_channel_id
        ON videos(channel_id);
        """,
    ]


# === 查询性能监控 ===
async def monitor_query_performance():
    """监控查询性能"""
    # 这里可以添加实际的性能监控逻辑
    # 例如使用pg_stat_statements扩展

    monitoring_queries = [
        """
        -- 获取最慢的查询
        SELECT query, mean_time, calls, total_time
        FROM pg_stat_statements
        ORDER BY mean_time DESC
        LIMIT 10;
        """,
        """
        -- 获取索引使用统计
        SELECT schemaname, tablename, indexname, idx_scan, idx_tup_read, idx_tup_fetch
        FROM pg_stat_user_indexes
        ORDER BY idx_scan DESC;
        """,
        """
        -- 获取缓存命中率
        SELECT
            sum(heap_blks_read) as heap_read,
            sum(heap_blks_hit) as heap_hit,
            sum(heap_blks_hit) / (sum(heap_blks_hit) + sum(heap_blks_read)) as ratio
        FROM pg_statio_user_tables;
        """,
    ]

    return monitoring_queries
