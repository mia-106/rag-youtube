"""
混合搜索模块
实现语义向量检索BM25关键词检索和结果融合
"""

import asyncio
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
import logging
from dataclasses import dataclass
from src.core.config import settings
from src.vector_storage.superabase_client import SuperabaseClient
from src.vector_storage.pgvector_handler import PGVectorHandler

# 环境自适应：根据 RUN_MODE 决定使用本地模型还是 API
USE_PRODUCTION_MODE = settings.RUN_MODE == "production"

if USE_PRODUCTION_MODE:
    # 生产模式：使用 Cohere Rerank API
    try:
        from langchain_cohere import CohereRerank
        RERANKER_AVAILABLE = True
    except ImportError:
        RERANKER_AVAILABLE = False
        logger.warning("Cohere not available, skipping reranker")
else:
    # 开发模式：使用本地 BGE Reranker
    from src.retrieval.reranker import BGEReranker

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """搜索结果"""

    content: str
    score: float
    source_type: str  # 'vector', 'bm25', 'hybrid'
    metadata: Dict[str, Any]


@dataclass
class SearchConfig:
    """搜索配置"""

    vector_weight: float = 0.7  # RRF模式下不使用
    bm25_weight: float = 0.2  # RRF模式下不使用
    recency_weight: float = 0.1
    min_score_threshold: float = 0.0  # RRF分数较小默认设为0
    top_k: int = settings.HYBRID_SEARCH_TOP_K  # 增加Top-K以供Reranker精排


class HybridSearchEngine:
    """混合搜索引擎"""

    def __init__(self, database_url: str):
        self.superabase_client = SuperabaseClient()
        self.vector_handler = PGVectorHandler()
        self.reranker = None
        self.config = SearchConfig()
        self.cache: Dict[str, List[SearchResult]] = {}

    async def initialize(self):
        """初始化搜索引擎"""
        await self.superabase_client.connect()
        await self.vector_handler.initialize()

        # 初始化 Reranker (根据环境选择本地模型或 API)
        if USE_PRODUCTION_MODE and RERANKER_AVAILABLE:
            try:
                logger.info("Using Cohere Rerank API")
                self.reranker = CohereRerank(
                    cohere_api_key=settings.COHERE_API_KEY,
                    model=settings.COHERE_MODEL,
                    top_n=settings.RERANK_TOP_K
                )
            except Exception as e:
                logger.warning(f"Cohere Reranker initialization failed: {e}")
        else:
            # 开发模式：使用本地 BGE Reranker
            try:
                self.reranker = await asyncio.to_thread(BGEReranker)
            except Exception as e:
                logger.warning(f"Local Reranker initialization failed: {e}")

        logger.info("Hybrid search engine initialized successfully")

    async def search(
        self,
        query: Union[str, List[str]],
        query_vector: Optional[List[float]] = None,
        config: Optional[SearchConfig] = None,
    ) -> List[SearchResult]:
        """
        执行混合搜索 (支持多路查询)
        """
        if config:
            self.config = config

        # 统一处理为列表
        queries = [query] if isinstance(query, str) else query
        main_query = queries[0]  # 用于重排序的基准查询

        logger.info(f"Hybrid search: {len(queries)} queries, Main: {main_query[:30]}...")

        try:
            # 1. 检查缓存
            if len(queries) == 1:
                cache_key = self._get_cache_key(main_query)
                if cache_key in self.cache:
                    return self.cache[cache_key]

            # 2. 并行执行所有查询
            search_tasks = []
            for i, q in enumerate(queries):
                if i == 0 and query_vector:
                    search_tasks.append(self._vector_search(q, query_vector))
                else:
                    search_tasks.append(self._execute_single_vector_search(q))
                search_tasks.append(self._bm25_search(q))
            # 执行所有搜索
            all_rankings = await asyncio.gather(*search_tasks)

            # 3. 融合结果 (RRF)
            fused_results = self._fuse_rankings(all_rankings)

            # 4. 重排序 (Rerank)
            final_results = await self._rerank_results(main_query, fused_results)

            # 5. 缓存结果
            if len(queries) == 1:
                self.cache[cache_key] = final_results

            return final_results

        except Exception as e:
            logger.error(f"Hybrid search failed: {str(e)}")
            return []

    async def _execute_single_vector_search(self, query: str) -> List[SearchResult]:
        """辅助方法生成向量并搜索"""
        try:
            vec = await self.vector_handler.create_embedding(query)
            return await self._vector_search(query, vec)
        except Exception as e:
            logger.error(f"Vector creation/search failed: {e}")
            return []

    def _fuse_rankings(self, rankings: List[List[SearchResult]]) -> List[SearchResult]:
        """
        通用 RRF 融合
        """
        k = 60
        doc_scores = {}
        doc_map = {}

        for ranking in rankings:
            for rank, result in enumerate(ranking):
                content_hash = hash(result.content)
                if content_hash not in doc_scores:
                    doc_scores[content_hash] = 0.0
                    doc_map[content_hash] = result

                doc_scores[content_hash] += 1.0 / (k + rank + 1)

        fused_results = []
        for content_hash, score in doc_scores.items():
            result = doc_map[content_hash]
            result.score = score
            result.source_type = "hybrid_rrf"
            fused_results.append(result)

        fused_results.sort(key=lambda x: x.score, reverse=True)
        return fused_results[: self.config.top_k]

    async def _rerank_results(self, query: str, results: List[SearchResult]) -> List[SearchResult]:
        """
        对搜索结果进行重排序
        """
        if not self.reranker or not results:
            return results

        rerank_inputs = []
        for r in results:
            meta = r.metadata
            title = meta.get("video_title", "")
            summary = meta.get("video_summary", "")
            content = r.content
            augmented_text = f"Title: {title}\nSummary: {summary}\nContent: {content}"
            rerank_inputs.append(augmented_text)

        # 使用异步方法运行重排序避免阻塞
        ranked_indices = await self.reranker.rerank_async(query, rerank_inputs, top_k=settings.RERANK_TOP_K)

        reranked_results = []
        for rank, (original_idx, score) in enumerate(ranked_indices, start=1):
            result = results[original_idx]
            result.score = score
            result.source_type = "hybrid_reranked"
            reranked_results.append(result)

        return reranked_results

    async def _vector_search(self, query: str, query_vector: List[float]) -> List[SearchResult]:
        """向量搜索"""
        try:
            vector_results = await self.superabase_client.search_vectors(query_vector=query_vector, limit=50)

            results = []
            for row in vector_results:
                content = row.get("content", "")
                distance = float(row.get("distance", 1.0))
                score = 1.0 / (1.0 + distance)

                result = SearchResult(
                    content=content,
                    score=score,
                    source_type="vector",
                    metadata={
                        "video_title": row.get("video_title", ""),
                        "video_id": row.get("video_id", ""),
                        "chunk_id": row.get("chunk_id", ""),
                        "start_time": row.get("start_time", 0),
                        "video_summary": row.get("video_summary", ""),
                    },
                )
                results.append(result)
            return results

        except Exception as e:
            logger.error(f"Vector search failed: {str(e)}")
            return []

    async def _bm25_search(self, query: str) -> List[SearchResult]:
        """BM25关键词搜索"""
        try:
            bm25_results = await self.superabase_client.bm25_search(query=query, limit=50)

            results = []
            for row in bm25_results:
                content = row.get("content", "")
                rank = float(row.get("rank", 0.0))
                score = min(1.0, rank / 10.0)

                result = SearchResult(
                    content=content,
                    score=score,
                    source_type="bm25",
                    metadata={
                        "video_title": row.get("video_title", ""),
                        "video_id": row.get("video_id", ""),
                        "chunk_id": row.get("chunk_id", ""),
                        "start_time": row.get("start_time", 0),
                        "video_summary": row.get("video_summary", ""),
                    },
                )
                results.append(result)
            return results

        except Exception as e:
            logger.error(f"BM25 search failed: {str(e)}")
            return []

    def _get_cache_key(self, query: str) -> str:
        return f"search:{hash(query)}"

    def update_config(self, config: SearchConfig):
        self.config = config

    def clear_cache(self):
        self.cache.clear()

    def get_search_statistics(self) -> Dict[str, Any]:
        return {
            "cache_size": len(self.cache),
            "config": {
                "top_k": self.config.top_k,
            },
            "last_updated": datetime.now().isoformat(),
        }


class ResultReranker:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key

    async def rerank(self, query: str, results: List[SearchResult], top_k: int = 5) -> List[SearchResult]:
        if not self.api_key or len(results) <= top_k:
            return results[:top_k]
        return results[:top_k]  # Placeholder


class OptimizedHybridSearch:
    def __init__(self, database_url: str, cohere_api_key: Optional[str] = None):
        self.hybrid_engine = HybridSearchEngine(database_url)
        self.reranker = ResultReranker(cohere_api_key)
        self.config = SearchConfig()

    async def initialize(self):
        await self.hybrid_engine.initialize()

    async def search_with_rerank(
        self, query: str, use_rerank: bool = True, config: Optional[SearchConfig] = None
    ) -> List[SearchResult]:
        results = await self.hybrid_engine.search(query, config=config)
        return results

    def update_weights(self, vector_weight: float, bm25_weight: float, recency_weight: float = 0.1) -> None:
        self.config.vector_weight = vector_weight
        self.config.bm25_weight = bm25_weight
        self.config.recency_weight = recency_weight
        self.hybrid_engine.update_config(self.config)

    def get_performance_stats(self) -> Dict[str, Any]:
        return self.hybrid_engine.get_search_statistics()


if __name__ == "__main__":
    pass
