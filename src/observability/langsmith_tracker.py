"""
LangSmith追踪模块
集成LangSmith进行全链路追踪和监控
"""

import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging
from langsmith import Client, traceable
from src.core.config import settings

logger = logging.getLogger(__name__)


class LangSmithTracker:
    """LangSmith追踪器"""

    def __init__(self, project_name: Optional[str] = None):
        self.project_name = project_name or settings.LANGCHAIN_PROJECT
        self.client = None
        self.traces = []

        # 初始化LangSmith客户端
        if settings.LANGCHAIN_TRACING_V2:
            try:
                self.client = Client(api_key=settings.LANGCHAIN_API_KEY, project_name=self.project_name)
                logger.info(" LangSmith客户端初始化成功")
            except Exception as e:
                logger.warning(f" LangSmith初始化失败: {str(e)}")
                self.client = None

    @traceable(name="YouTube RAG Workflow")
    async def trace_workflow(self, workflow_id: str, question: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        追踪工作流

        Args:
            workflow_id: 工作流ID
            question: 用户问题
            metadata: 元数据

        Returns:
            追踪ID
        """
        try:
            if not self.client:
                logger.warning(" LangSmith客户端未初始化")
                return ""

            logger.info(f" 开始追踪工作流: {workflow_id}")
            return workflow_id

        except Exception as e:
            logger.error(f" 工作流追踪失败: {str(e)}")
            return ""

    async def trace_thinking_phase(
        self, workflow_id: str, question: str, thinking_content: str, metadata: Optional[Dict[str, Any]] = None
    ):
        """追踪思考阶段"""
        try:
            if not self.client:
                return

            logger.info(f" 追踪思考阶段: {workflow_id}")

            # 记录思考过程
            # 实际实现中可以使用LangSmith的Dataset和Example功能

        except Exception as e:
            logger.error(f" 思考阶段追踪失败: {str(e)}")

    async def trace_retrieval_phase(
        self, workflow_id: str, query: str, results: List[Dict[str, Any]], metadata: Optional[Dict[str, Any]] = None
    ):
        """追踪检索阶段"""
        try:
            if not self.client:
                return

            logger.info(f" 追踪检索阶段: {workflow_id}")

            retrieval_data = {
                "query": query,
                "result_count": len(results),
                "top_results": results[:3],  # 只记录前3个结果
                "metadata": metadata or {},
            }

            logger.debug(f"检索数据: {retrieval_data}")

        except Exception as e:
            logger.error(f" 检索阶段追踪失败: {str(e)}")

    async def trace_evaluation_phase(
        self, workflow_id: str, evaluation_score: float, sufficient: bool, evaluation_details: Dict[str, Any]
    ):
        """追踪评估阶段"""
        try:
            if not self.client:
                return

            logger.info(f" 追踪评估阶段: {workflow_id}")

            evaluation_data = {
                "evaluation_score": evaluation_score,
                "sufficient": sufficient,
                "evaluation_details": evaluation_details,
            }

            logger.debug(f"评估数据: {evaluation_data}")

        except Exception as e:
            logger.error(f" 评估阶段追踪失败: {str(e)}")

    async def trace_reflection_phase(
        self, workflow_id: str, reflection_count: int, reflection_notes: List[str], improvement_suggestions: List[str]
    ):
        """追踪反思阶段"""
        try:
            if not self.client:
                return

            logger.info(f" 追踪反思阶段: {workflow_id}")

            reflection_data = {
                "reflection_count": reflection_count,
                "reflection_notes": reflection_notes,
                "improvement_suggestions": improvement_suggestions,
            }

            logger.debug(f"反思数据: {reflection_data}")

        except Exception as e:
            logger.error(f" 反思阶段追踪失败: {str(e)}")

    async def trace_answer_phase(
        self,
        workflow_id: str,
        answer: str,
        confidence_score: float,
        response_time: float,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """追踪回答阶段"""
        try:
            if not self.client:
                return

            logger.info(f" 追踪回答阶段: {workflow_id}")

            answer_data = {
                "answer_length": len(answer),
                "confidence_score": confidence_score,
                "response_time": response_time,
                "metadata": metadata or {},
            }

            logger.debug(f"回答数据: {answer_data}")

        except Exception as e:
            logger.error(f" 回答阶段追踪失败: {str(e)}")

    async def trace_performance_metrics(self, workflow_id: str, metrics: Dict[str, float]):
        """追踪性能指标"""
        try:
            if not self.client:
                return

            logger.info(f" 追踪性能指标: {workflow_id}")

            performance_data = {"metrics": metrics, "timestamp": datetime.now().isoformat()}

            logger.debug(f"性能数据: {performance_data}")

        except Exception as e:
            logger.error(f" 性能指标追踪失败: {str(e)}")

    async def log_error(self, workflow_id: str, error: Exception, context: Dict[str, Any]):
        """记录错误"""
        try:
            if not self.client:
                return

            error_data = {
                "workflow_id": workflow_id,
                "error_type": type(error).__name__,
                "error_message": str(error),
                "context": context,
                "timestamp": datetime.now().isoformat(),
            }

            logger.error(f" 记录错误: {error_data}")

        except Exception as e:
            logger.error(f" 错误记录失败: {str(e)}")

    async def create_dataset(
        self, dataset_name: str, description: str, examples: List[Dict[str, Any]]
    ) -> Optional[str]:
        """创建数据集"""
        try:
            if not self.client:
                logger.warning(" LangSmith客户端未初始化")
                return None

            # 这里应该调用LangSmith API创建数据集
            # 实际实现中需要根据LangSmith的API文档调整

            logger.info(f" 创建数据集: {dataset_name}")
            return dataset_name

        except Exception as e:
            logger.error(f" 数据集创建失败: {str(e)}")
            return None

    async def add_example_to_dataset(
        self,
        dataset_name: str,
        input_text: str,
        expected_output: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """向数据集添加示例"""
        try:
            if not self.client:
                return

            example_data = {"input": input_text, "expected_output": expected_output, "metadata": metadata or {}}

            logger.debug(f"添加示例到数据集 {dataset_name}: {example_data}")

        except Exception as e:
            logger.error(f" 示例添加失败: {str(e)}")

    async def export_trace(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """导出追踪数据"""
        try:
            if not self.client:
                return None

            # 这里应该调用LangSmith API导出追踪数据
            trace_data = {"workflow_id": workflow_id, "exported_at": datetime.now().isoformat(), "traces": self.traces}

            logger.info(f" 导出追踪数据: {workflow_id}")
            return trace_data

        except Exception as e:
            logger.error(f" 追踪数据导出失败: {str(e)}")
            return None

    def get_tracking_statistics(self) -> Dict[str, Any]:
        """获取追踪统计信息"""
        return {
            "project_name": self.project_name,
            "client_initialized": self.client is not None,
            "total_traces": len(self.traces),
            "tracking_enabled": settings.LANGCHAIN_TRACING_V2,
        }


# 全局追踪器实例
langsmith_tracker = LangSmithTracker()


def test_langsmith_tracker():
    """测试LangSmith追踪器"""
    print(" 测试LangSmith追踪器...")

    # 创建追踪器
    tracker = LangSmithTracker(project_name="test_project")

    print(" LangSmith追踪器创建成功")

    # 测试基本功能
    print("\n 测试基本功能...")

    # 测试工作流追踪
    workflow_id = asyncio.run(tracker.trace_workflow(workflow_id="test_001", question="什么是Python"))
    print(f" 工作流追踪: {workflow_id}")

    # 测试性能指标追踪
    asyncio.run(
        tracker.trace_performance_metrics(
            workflow_id="test_001", metrics={"response_time": 1.5, "retrieval_time": 0.8, "evaluation_time": 0.2}
        )
    )
    print(" 性能指标追踪")

    # 测试统计信息
    print("\n 追踪统计:")
    stats = tracker.get_tracking_statistics()
    for key, value in stats.items():
        print(f"  {key}: {value}")

    print("\n 所有测试完成")


if __name__ == "__main__":
    test_langsmith_tracker()
