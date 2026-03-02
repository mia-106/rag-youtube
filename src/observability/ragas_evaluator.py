"""
RAGAS评估模块
集成RAGAS框架进行检索增强生成的量化评估
"""

import asyncio
from typing import Dict, Any, List, Optional, cast
from datetime import datetime
import logging
from dataclasses import dataclass

# RAGAS相关导入
try:
    from ragas import evaluate
    from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall, answer_similarity
    from ragas.dataset import Dataset

    RAGAS_AVAILABLE = True
except ImportError:
    RAGAS_AVAILABLE = False
    logging.warning(" RAGAS未安装将使用模拟评估")

logger = logging.getLogger(__name__)


@dataclass
class EvaluationQuestion:
    """评估问题"""

    question: str
    ground_truth: str
    answer: Optional[str] = None
    contexts: Optional[List[str]] = None
    retrieved_contexts: Optional[List[str]] = None


@dataclass
class EvaluationResult:
    """评估结果"""

    question: str
    answer: str
    contexts: List[str]
    metrics: Dict[str, float]
    overall_score: float
    timestamp: str


class RAGASEvaluator:
    """RAGAS评估器"""

    def __init__(self):
        self.evaluation_history: List[EvaluationResult] = []
        self.custom_metrics = {}

        if not RAGAS_AVAILABLE:
            logger.warning(" RAGAS未安装使用模拟评估")

    async def evaluate_single(
        self, question: str, answer: str, contexts: List[str], ground_truth: Optional[str] = None
    ) -> EvaluationResult:
        """
        评估单个问答对

        Args:
            question: 问题
            answer: 答案
            contexts: 上下文列表
            ground_truth: 真实答案可选

        Returns:
            评估结果
        """
        try:
            logger.info(f" 评估问题: {question[:50]}...")

            if RAGAS_AVAILABLE:
                # 使用真实的RAGAS评估
                result = await self._evaluate_with_ragas(question, answer, contexts, ground_truth)
            else:
                # 使用模拟评估
                result = await self._evaluate_simulation(question, answer, contexts, ground_truth)

            self.evaluation_history.append(result)
            logger.info(f" 评估完成: {question[:50]}...")

            return result

        except Exception as e:
            logger.error(f" 评估失败: {str(e)}")
            # 返回默认结果
            return EvaluationResult(
                question=question,
                answer=answer,
                contexts=contexts,
                metrics={
                    "faithfulness": 0.0,
                    "answer_relevancy": 0.0,
                    "context_precision": 0.0,
                    "context_recall": 0.0,
                    "answer_similarity": 0.0,
                },
                overall_score=0.0,
                timestamp=datetime.now().isoformat(),
            )

    async def _evaluate_with_ragas(
        self, question: str, answer: str, contexts: List[str], ground_truth: Optional[str] = None
    ) -> EvaluationResult:
        """使用RAGAS进行评估"""
        try:
            # 构建评估数据
            data = {"question": [question], "answer": [answer], "contexts": [contexts]}

            if ground_truth:
                data["ground_truth"] = [ground_truth]

            # 创建数据集
            dataset = Dataset.from_dict(data)

            # 执行评估
            result = evaluate(
                dataset,
                metrics=[faithfulness, answer_relevancy, context_precision, context_recall, answer_similarity],
            )

            # 提取评估分数
            scores = cast(Dict[str, Any], result.to_dict())
            metrics = {
                "faithfulness": scores.get("faithfulness", [0.0])[0],
                "answer_relevancy": scores.get("answer_relevancy", [0.0])[0],
                "context_precision": scores.get("context_precision", [0.0])[0],
                "context_recall": scores.get("context_recall", [0.0])[0],
                "answer_similarity": scores.get("answer_similarity", [0.0])[0],
            }

            # 计算总体分数
            overall_score = sum(metrics.values()) / len(metrics)

            return EvaluationResult(
                question=question,
                answer=answer,
                contexts=contexts,
                metrics=metrics,
                overall_score=overall_score,
                timestamp=datetime.now().isoformat(),
            )

        except Exception as e:
            logger.error(f" RAGAS评估失败: {str(e)}")
            # 回退到模拟评估
            return await self._evaluate_simulation(question, answer, contexts, ground_truth)

    async def _evaluate_simulation(
        self, question: str, answer: str, contexts: List[str], ground_truth: Optional[str] = None
    ) -> EvaluationResult:
        """模拟评估当RAGAS不可用时"""
        try:
            # 简化的模拟评估逻辑
            import random

            random.seed(42)  # 固定种子保证一致性

            # 计算基础指标
            answer_length = len(answer)
            context_count = len(contexts)

            # 模拟忠实度评估
            faithfulness_score = min(1.0, answer_length / 1000)

            # 模拟答案相关性
            relevancy_score = min(1.0, len(question.split()) / 10)

            # 模拟上下文精度
            precision_score = min(1.0, context_count / 5)

            # 模拟上下文召回
            recall_score = min(1.0, context_count / 3)

            # 模拟答案相似度
            similarity_score = min(1.0, answer_length / 500)

            metrics = {
                "faithfulness": faithfulness_score,
                "answer_relevancy": relevancy_score,
                "context_precision": precision_score,
                "context_recall": recall_score,
                "answer_similarity": similarity_score,
            }

            # 计算总体分数
            overall_score = sum(metrics.values()) / len(metrics)

            return EvaluationResult(
                question=question,
                answer=answer,
                contexts=contexts,
                metrics=metrics,
                overall_score=overall_score,
                timestamp=datetime.now().isoformat(),
            )

        except Exception as e:
            logger.error(f" 模拟评估失败: {str(e)}")
            raise

    async def evaluate_batch(self, evaluations: List[EvaluationQuestion]) -> List[EvaluationResult]:
        """
        批量评估

        Args:
            evaluations: 评估问题列表

        Returns:
            评估结果列表
        """
        logger.info(f" 开始批量评估: {len(evaluations)} 个问题")

        results = []
        for eval_question in evaluations:
            result = await self.evaluate_single(
                question=eval_question.question,
                answer=eval_question.answer or "",
                contexts=eval_question.contexts or [],
                ground_truth=eval_question.ground_truth,
            )
            results.append(result)

        logger.info(f" 批量评估完成: {len(results)} 个结果")
        return results

    def calculate_aggregate_metrics(self, results: List[EvaluationResult]) -> Dict[str, Any]:
        """
        计算聚合指标

        Args:
            results: 评估结果列表

        Returns:
            聚合指标字典
        """
        try:
            if not results:
                return {}

            # 计算各指标的统计信息
            metrics_summary = {}
            metric_names = [
                "faithfulness",
                "answer_relevancy",
                "context_precision",
                "context_recall",
                "answer_similarity",
                "overall_score",
            ]

            for metric_name in metric_names:
                scores = [result.metrics.get(metric_name, 0.0) for result in results]
                metrics_summary[metric_name] = {
                    "mean": sum(scores) / len(scores),
                    "min": min(scores),
                    "max": max(scores),
                    "std": self._calculate_std(scores),
                }

            # 计算总体统计
            total_evaluations = len(results)
            successful_evaluations = sum(1 for r in results if r.overall_score > 0)

            aggregate_metrics = {
                "total_evaluations": total_evaluations,
                "successful_evaluations": successful_evaluations,
                "success_rate": (successful_evaluations / total_evaluations * 100) if total_evaluations > 0 else 0,
                "metrics_summary": metrics_summary,
                "evaluation_timestamp": datetime.now().isoformat(),
            }

            logger.info(f" 聚合指标计算完成: {total_evaluations} 个评估")
            return aggregate_metrics

        except Exception as e:
            logger.error(f" 聚合指标计算失败: {str(e)}")
            return {}

    def _calculate_std(self, scores: List[float]) -> float:
        """计算标准差"""
        if len(scores) <= 1:
            return 0.0

        mean = sum(scores) / len(scores)
        variance = sum((x - mean) ** 2 for x in scores) / (len(scores) - 1)
        return variance**0.5

    async def generate_evaluation_report(
        self, results: List[EvaluationResult], output_path: Optional[str] = None
    ) -> str:
        """
        生成评估报告

        Args:
            results: 评估结果列表
            output_path: 输出路径可选

        Returns:
            报告内容
        """
        try:
            # 计算聚合指标
            aggregate_metrics = self.calculate_aggregate_metrics(results)

            # 生成报告
            report_lines = [
                "# RAGAS评估报告",
                f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "",
                "## 总体统计",
                f"- 评估总数: {aggregate_metrics.get('total_evaluations', 0)}",
                f"- 成功评估: {aggregate_metrics.get('successful_evaluations', 0)}",
                f"- 成功率: {aggregate_metrics.get('success_rate', 0):.2f}%",
                "",
                "## 指标统计",
                "",
            ]

            # 添加指标统计
            metrics_summary = aggregate_metrics.get("metrics_summary", {})
            for metric_name, stats in metrics_summary.items():
                report_lines.extend(
                    [
                        f"### {metric_name}",
                        f"- 平均值: {stats['mean']:.3f}",
                        f"- 最小值: {stats['min']:.3f}",
                        f"- 最大值: {stats['max']:.3f}",
                        f"- 标准差: {stats['std']:.3f}",
                        "",
                    ]
                )

            # 添加详细结果
            report_lines.extend(["## 详细结果", ""])

            for result in results:
                report_lines.extend(
                    [
                        f"### 问题: {result.question}",
                        f"答案长度: {len(result.answer)} 字符",
                        f"上下文数量: {len(result.contexts)}",
                        "",
                        "**指标分数:**",
                    ]
                )

                for metric_name, score in result.metrics.items():
                    report_lines.append(f"- {metric_name}: {score:.3f}")

                report_lines.extend([f"**总体分数:** {result.overall_score:.3f}", ""])

            report_content = "\n".join(report_lines)

            # 保存报告
            if output_path:
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(report_content)
                logger.info(f" 评估报告已保存: {output_path}")

            return report_content

        except Exception as e:
            logger.error(f" 评估报告生成失败: {str(e)}")
            return ""

    def get_evaluation_history(self) -> List[EvaluationResult]:
        """获取评估历史"""
        return self.evaluation_history

    def clear_history(self):
        """清空评估历史"""
        self.evaluation_history.clear()
        logger.info(" 评估历史已清空")


def test_ragas_evaluator():
    """测试RAGAS评估器"""
    print(" 测试RAGAS评估器...")

    # 创建评估器
    evaluator = RAGASEvaluator()

    print(" RAGAS评估器创建成功")

    # 测试单个评估
    print("\n 测试单个评估...")

    async def test_single():
        result = await evaluator.evaluate_single(
            question="什么是Python",
            answer="Python是一种编程语言",
            contexts=["Python是一种高级编程语言", "Python简单易学"],
        )

        print(" 单个评估完成")
        print(f"  问题: {result.question}")
        print(f"  总体分数: {result.overall_score:.3f}")
        print(f"  指标: {result.metrics}")

    asyncio.run(test_single())

    # 测试批量评估
    print("\n 测试批量评估...")

    async def test_batch():
        evaluations = [
            EvaluationQuestion(
                question="Python的特点是什么",
                answer="Python简单易学",
                contexts=["Python简单易学", "Python功能强大"],
                ground_truth="Python是一种简单易学的编程语言",
            ),
            EvaluationQuestion(
                question="JavaScript的用途",
                answer="用于Web开发",
                contexts=["JavaScript用于前端开发", "JavaScript也可以用于后端"],
                ground_truth="JavaScript主要用于Web开发",
            ),
        ]

        results = await evaluator.evaluate_batch(evaluations)

        print(f" 批量评估完成: {len(results)} 个结果")

        # 计算聚合指标
        aggregate = evaluator.calculate_aggregate_metrics(results)
        print(" 聚合指标:")
        for key, value in aggregate.items():
            if isinstance(value, dict):
                print(f"  {key}:")
                for subkey, subvalue in value.items():
                    if isinstance(subvalue, dict):
                        print(f"    {subkey}: {subvalue}")
            else:
                print(f"  {key}: {value}")

    asyncio.run(test_batch())

    # 测试报告生成
    print("\n 测试报告生成...")

    async def test_report():
        history = evaluator.get_evaluation_history()
        report = await evaluator.generate_evaluation_report(history, output_path="evaluation_report.md")
        print(f" 报告生成完成: {len(report)} 字符")

    asyncio.run(test_report())

    print("\n 所有测试完成")


if __name__ == "__main__":
    test_ragas_evaluator()
