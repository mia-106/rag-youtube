"""
检索策略集成模块
整合混合搜索重排序和优化功能
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
import logging
from src.retrieval.hybrid_search import OptimizedHybridSearch, SearchConfig
from src.retrieval.optimization import RetrievalOptimizer

logger = logging.getLogger(__name__)


class AdvancedRetrievalSystem:
    """高级检索系统"""

    def __init__(self, database_url: str, cohere_api_key: Optional[str] = None, cache_size: int = 10000):
        self.database_url = database_url
        self.cohere_api_key = cohere_api_key
        self.search_engine = OptimizedHybridSearch(database_url, cohere_api_key)
        self.optimizer = RetrievalOptimizer(database_url, cache_size)
        self.default_config = SearchConfig()

    async def initialize(self):
        """初始化系统"""
        await self.search_engine.initialize()
        logger.info(" 高级检索系统初始化完成")

    async def search(
        self,
        query: str,
        use_cache: bool = True,
        use_rerank: bool = True,
        config: Optional[SearchConfig] = None,
        return_metadata: bool = True,
    ) -> Dict[str, Any]:
        """
        执行高级检索

        Args:
            query: 查询字符串
            use_cache: 是否使用缓存
            use_rerank: 是否使用重排序
            config: 搜索配置
            return_metadata: 是否返回元数据

        Returns:
            检索结果字典
        """
        start_time = datetime.now()

        try:
            logger.info(f" 开始高级检索: {query[:50]}...")

            # 准备配置
            search_config = config or self.default_config
            config_dict = {
                "vector_weight": search_config.vector_weight,
                "bm25_weight": search_config.bm25_weight,
                "recency_weight": search_config.recency_weight,
                "min_score_threshold": search_config.min_score_threshold,
                "top_k": search_config.top_k,
                "use_rerank": use_rerank,
            }

            # 定义搜索函数
            async def perform_search(q, cfg):
                return await self.search_engine.search_with_rerank(q, use_rerank=use_rerank, config=cfg)

            # 执行优化搜索
            if use_cache:
                results = await self.optimizer.optimize_search(query, perform_search, config_dict)
            else:
                results = await perform_search(query, search_config)

            # 格式化结果
            end_time = datetime.now()
            response_time = (end_time - start_time).total_seconds()

            # 准备响应
            response = {
                "query": query,
                "results": [
                    {
                        "content": result.content,
                        "score": result.score,
                        "source_type": result.source_type,
                        "metadata": result.metadata,
                    }
                    for result in results
                ],
                "total_results": len(results),
                "response_time": response_time,
            }

            if return_metadata:
                response["metadata"] = {
                    "config": config_dict,
                    "cache_enabled": use_cache,
                    "rerank_enabled": use_rerank,
                    "search_engine": "hybrid_optimized",
                    "timestamp": start_time.isoformat(),
                }

            logger.info(f" 检索完成: {len(results)} 个结果耗时 {response_time:.3f}s")
            return response

        except Exception as e:
            logger.error(f" 高级检索失败: {str(e)}")
            return {
                "query": query,
                "results": [],
                "total_results": 0,
                "error": str(e),
                "response_time": (datetime.now() - start_time).total_seconds(),
            }

    async def batch_search(
        self,
        queries: List[str],
        use_cache: bool = True,
        use_rerank: bool = True,
        config: Optional[SearchConfig] = None,
        return_metadata: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        执行批量检索

        Args:
            queries: 查询列表
            use_cache: 是否使用缓存
            use_rerank: 是否使用重排序
            config: 搜索配置
            return_metadata: 是否返回元数据

        Returns:
            检索结果列表
        """
        start_time = datetime.now()

        try:
            logger.info(f" 开始批量检索: {len(queries)} 个查询")

            # 准备配置
            search_config = config or self.default_config
            config_dict = {
                "vector_weight": search_config.vector_weight,
                "bm25_weight": search_config.bm25_weight,
                "recency_weight": search_config.recency_weight,
                "min_score_threshold": search_config.min_score_threshold,
                "top_k": search_config.top_k,
                "use_rerank": use_rerank,
            }

            # 定义搜索函数
            async def perform_search(q, cfg):
                return await self.search_engine.search_with_rerank(q, use_rerank=use_rerank, config=cfg)

            # 执行优化批量搜索
            if use_cache:
                all_results = await self.optimizer.optimize_batch(queries, perform_search, config_dict)
            else:
                all_results = []
                for query in queries:
                    results = await perform_search(query, search_config)
                    all_results.append(results)

            # 格式化结果
            end_time = datetime.now()
            total_time = (end_time - start_time).total_seconds()

            # 准备响应列表
            responses = []
            for query, results in zip(queries, all_results):
                response = {
                    "query": query,
                    "results": [
                        {
                            "content": result.content,
                            "score": result.score,
                            "source_type": result.source_type,
                            "metadata": result.metadata,
                        }
                        for result in results
                    ],
                    "total_results": len(results),
                    "response_time": total_time / len(queries),  # 平均时间
                }

                if return_metadata:
                    response["metadata"] = {
                        "config": config_dict,
                        "cache_enabled": use_cache,
                        "rerank_enabled": use_rerank,
                        "search_engine": "hybrid_optimized",
                        "timestamp": start_time.isoformat(),
                    }

                responses.append(response)

            logger.info(f" 批量检索完成: {len(responses)} 个查询总耗时 {total_time:.3f}s")
            return responses

        except Exception as e:
            logger.error(f" 批量检索失败: {str(e)}")
            return [{"query": query, "results": [], "total_results": 0, "error": str(e)} for query in queries]

    def update_search_weights(self, vector_weight: float, bm25_weight: float, recency_weight: float = 0.1):
        """动态调整搜索权重"""
        self.search_engine.update_weights(vector_weight, bm25_weight, recency_weight)

    def get_system_statistics(self) -> Dict[str, Any]:
        """获取系统统计信息"""
        optimization_stats = self.optimizer.get_optimization_statistics()
        performance_stats = self.search_engine.get_performance_stats()

        return {
            "system": {
                "search_engine": "advanced_retrieval",
                "version": "1.0.0",
                "initialized_at": datetime.now().isoformat(),
            },
            "search_engine": performance_stats,
            "optimization": optimization_stats,
        }

    def clear_cache(self):
        """清空缓存"""
        self.optimizer.clear_cache()
        logger.info(" 检索缓存已清空")

    def clear_metrics(self):
        """清空性能指标"""
        self.optimizer.clear_metrics()
        logger.info(" 性能指标已清空")


class RetrievalEvaluator:
    """检索质量评估器"""

    def __init__(self, retrieval_system: AdvancedRetrievalSystem):
        self.retrieval_system = retrieval_system

    async def evaluate_search_quality(self, test_queries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        评估搜索质量

        Args:
            test_queries: 测试查询列表 [{'query': '...', 'expected': [...]}]

        Returns:
            评估结果
        """
        logger.info(f" 开始评估搜索质量: {len(test_queries)} 个测试查询")

        try:
            total_queries = len(test_queries)
            successful_queries = 0
            total_results = 0
            avg_response_time = 0.0
            quality_scores = []

            for test_case in test_queries:
                query = test_case.get("query", "")

                # 执行搜索
                result = await self.retrieval_system.search(query)

                if result.get("results"):
                    successful_queries += 1
                    total_results += result["total_results"]
                    avg_response_time += result["response_time"]

                    # 计算质量分数 (简化实现)
                    quality_score = min(1.0, result["total_results"] / 10.0)
                    quality_scores.append(quality_score)

            # 计算总体指标
            success_rate = (successful_queries / total_queries * 100) if total_queries > 0 else 0
            avg_results_per_query = (total_results / successful_queries) if successful_queries > 0 else 0
            avg_quality_score = (sum(quality_scores) / len(quality_scores)) if quality_scores else 0
            avg_response_time = (avg_response_time / successful_queries) if successful_queries > 0 else 0

            evaluation_result = {
                "evaluation_timestamp": datetime.now().isoformat(),
                "total_queries": total_queries,
                "successful_queries": successful_queries,
                "success_rate": f"{success_rate:.2f}%",
                "avg_results_per_query": f"{avg_results_per_query:.2f}",
                "avg_quality_score": f"{avg_quality_score:.3f}",
                "avg_response_time": f"{avg_response_time:.3f}s",
                "quality_grade": self._get_quality_grade(avg_quality_score),
            }

            logger.info(f" 评估完成: 质量等级 {evaluation_result['quality_grade']}")
            return evaluation_result

        except Exception as e:
            logger.error(f" 搜索质量评估失败: {str(e)}")
            return {"error": str(e), "evaluation_timestamp": datetime.now().isoformat()}

    def _get_quality_grade(self, quality_score: float) -> str:
        """获取质量等级"""
        if quality_score >= 0.9:
            return "A+ (优秀)"
        elif quality_score >= 0.8:
            return "A (良好)"
        elif quality_score >= 0.7:
            return "B (中等)"
        elif quality_score >= 0.6:
            return "C (及格)"
        else:
            return "D (需改进)"

    async def benchmark_retrieval_performance(
        self, benchmark_queries: List[str], iterations: int = 3
    ) -> Dict[str, Any]:
        """
        基准测试检索性能

        Args:
            benchmark_queries: 基准查询列表
            iterations: 迭代次数

        Returns:
            基准测试结果
        """
        logger.info(f" 开始性能基准测试: {len(benchmark_queries)} 查询 x {iterations} 迭代")

        try:
            all_response_times = []

            for iteration in range(iterations):
                logger.info(f" 迭代 {iteration + 1}/{iterations}")

                iteration_times = []
                for query in benchmark_queries:
                    result = await self.retrieval_system.search(query)
                    iteration_times.append(result["response_time"])

                all_response_times.extend(iteration_times)

            # 计算统计指标
            all_response_times.sort()
            count = len(all_response_times)
            avg_time = sum(all_response_times) / count
            min_time = min(all_response_times)
            max_time = max(all_response_times)
            p95_index = int(count * 0.95)
            p99_index = int(count * 0.99)

            benchmark_result = {
                "benchmark_timestamp": datetime.now().isoformat(),
                "total_queries": len(benchmark_queries) * iterations,
                "iterations": iterations,
                "response_times": {
                    "avg": f"{avg_time:.3f}s",
                    "min": f"{min_time:.3f}s",
                    "max": f"{max_time:.3f}s",
                    "p95": f"{all_response_times[p95_index]:.3f}s",
                    "p99": f"{all_response_times[p99_index]:.3f}s",
                },
                "performance_grade": self._get_performance_grade(avg_time),
            }

            logger.info(f" 基准测试完成: 性能等级 {benchmark_result['performance_grade']}")
            return benchmark_result

        except Exception as e:
            logger.error(f" 基准测试失败: {str(e)}")
            return {"error": str(e), "benchmark_timestamp": datetime.now().isoformat()}

    def _get_performance_grade(self, avg_time: float) -> str:
        """获取性能等级"""
        if avg_time < 0.5:
            return "A+ (优秀)"
        elif avg_time < 1.0:
            return "A (良好)"
        elif avg_time < 2.0:
            return "B (中等)"
        elif avg_time < 5.0:
            return "C (及格)"
        else:
            return "D (需优化)"


def test_advanced_retrieval():
    """测试高级检索系统"""
    print(" 测试高级检索系统...")

    # 创建系统
    retrieval_system = AdvancedRetrievalSystem(
        database_url="postgresql://user:pass@localhost/db", cohere_api_key="test_key", cache_size=1000
    )

    print(" 高级检索系统创建成功")

    # 测试系统统计
    print("\n 系统统计:")
    stats = retrieval_system.get_system_statistics()
    for category, data in stats.items():
        print(f"  {category}:")
        for key, value in data.items():
            print(f"    {key}: {value}")

    # 测试权重调整
    print("\n 权重调整:")
    retrieval_system.update_search_weights(0.6, 0.3, 0.1)
    print(" 权重已调整")

    # 测试评估器
    print("\n 检索评估器:")
    RetrievalEvaluator(retrieval_system)
    print(" 评估器创建成功")

    print("\n 所有测试完成")


if __name__ == "__main__":
    test_advanced_retrieval()
