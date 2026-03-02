"""
LangGraph工作流
实现Agentic RAG的核心工作流思考-检索-验证-回答闭环
"""

from typing import Dict, Any, List
from datetime import datetime
import logging
from src.core.deepseek_client import DeepSeekClient
from src.agent_workflow.state_manager import AgentState, AgentStatus, state_manager
from src.agent_workflow.self_reflection_agent import SelfReflectionAgent
from src.agent_workflow.text_to_sql import TextToSQL
from src.vector_storage.superabase_client import SuperabaseClient

logger = logging.getLogger(__name__)


class AgenticRAGWorkflow:
    """Agentic RAG工作流"""

    def __init__(self, database_url: str):
        self.deepseek_client = DeepSeekClient()
        self.reflection_agent = SelfReflectionAgent()
        self.text_to_sql = TextToSQL(database_url)
        self.vector_client = SuperabaseClient()
        self.state_manager = state_manager

    async def process_question(self, question: str, session_id: str) -> Dict[str, Any]:
        """
        处理用户问题的主要入口

        Args:
            question: 用户问题
            session_id: 会话ID

        Returns:
            处理结果字典
        """
        start_time = datetime.now()
        logger.info(f" 开始处理问题: {question[:100]}... (session: {session_id})")

        try:
            # 1. 创建初始状态
            state = self.state_manager.create_initial_state(question, session_id)
            logger.info(f" 创建初始状态: {session_id}")

            # 2. 思考阶段
            state = await self._thinking_phase(state)
            if state.status == AgentStatus.FAILED:
                return self._format_response(state)

            # 3. 检索阶段
            state = await self._retrieval_phase(state)
            if state.status == AgentStatus.FAILED:
                return self._format_response(state)

            # 4. 评估阶段
            state = await self._evaluation_phase(state)
            if state.status == AgentStatus.FAILED:
                return self._format_response(state)

            # 5. 反思阶段如果需要
            while state.can_reflect() and not state.sufficient:
                state = await self._reflection_phase(state)
                if state.status == AgentStatus.FAILED:
                    break

                # 重新检索
                state = await self._retrieval_phase(state)
                if state.status == AgentStatus.FAILED:
                    break

                # 重新评估
                state = await self._evaluation_phase(state)
                if state.status == AgentStatus.FAILED:
                    break

            # 6. 回答阶段
            if state.status != AgentStatus.FAILED:
                state = await self._answer_phase(state)

            # 计算总时间
            end_time = datetime.now()
            state.total_time = (end_time - start_time).total_seconds()

            # 返回结果
            return self._format_response(state)

        except Exception as e:
            logger.error(f" 工作流执行失败: {str(e)}")
            error_state = AgentState(question=question, session_id=session_id)
            error_state.set_error(str(e))
            return self._format_response(error_state)

    async def _thinking_phase(self, state: AgentState) -> AgentState:
        """思考阶段"""
        logger.info(" 进入思考阶段...")

        try:
            # 更新状态
            state.status = AgentStatus.THINKING
            state.updated_at = datetime.now()

            # 分析问题并生成查询策略
            context = f"问题{state.question}\n时间{datetime.now().isoformat()}"
            await self.deepseek_client.generate_thought(context=context, question=state.question)

            state.query_strategy = "混合检索策略向量+关键词"
            state.original_query = state.question
            state.current_query = state.question

            # 更新状态
            state.thinking_time = 0.5  # 简化计算
            state.status = AgentStatus.THINKING

            logger.info(" 思考阶段完成")
            return state

        except Exception as e:
            logger.error(f" 思考阶段失败: {str(e)}")
            state.set_error(f"思考阶段失败: {str(e)}")
            return state

    async def _retrieval_phase(self, state: AgentState) -> AgentState:
        """检索阶段"""
        logger.info(f" 进入检索阶段: {state.current_query}")

        try:
            # 更新状态
            state.status = AgentStatus.RETRIEVING
            state.updated_at = datetime.now()

            start_time = datetime.now()

            # 1. 检查是否是统计查询
            if self._is_statistical_query(state.current_query):
                # 使用Text-to-SQL
                sql_result = await self._handle_statistical_query(state)
                if sql_result.get("success"):
                    state.retrieval_results = [sql_result]
                    state.retrieval_metadata = {
                        "type": "sql",
                        "query": sql_result.get("sql_generation", {}).get("sql_query", ""),
                        "row_count": sql_result.get("execution", {}).get("row_count", 0),
                    }
            else:
                # 使用向量检索
                await self.vector_client.connect()

                # 生成查询向量
                from src.vector_storage.pgvector_handler import PGVectorHandler

                vector_handler = PGVectorHandler()
                query_vector = await vector_handler.create_embedding(state.current_query)

                # 执行混合检索
                retrieval_results = await self._hybrid_search(state.current_query, query_vector)

                state.retrieval_results = retrieval_results
                state.retrieval_metadata = {
                    "type": "hybrid",
                    "query_vector": query_vector,
                    "result_count": len(retrieval_results),
                }

            # 计算检索时间
            end_time = datetime.now()
            state.retrieval_time = (end_time - start_time).total_seconds()

            logger.info(f" 检索阶段完成返回 {len(state.retrieval_results)} 个结果")
            return state

        except Exception as e:
            logger.error(f" 检索阶段失败: {str(e)}")
            state.set_error(f"检索阶段失败: {str(e)}")
            return state

    async def _evaluation_phase(self, state: AgentState) -> AgentState:
        """评估阶段"""
        logger.info(" 进入评估阶段...")

        try:
            # 更新状态
            state.status = AgentStatus.EVALUATING
            state.updated_at = datetime.now()

            start_time = datetime.now()

            # 构建上下文
            context = self._build_context(state.retrieval_results)

            # 评估检索充足性
            evaluation_details = await self.reflection_agent.evaluate_retrieval_sufficiency(
                context=context, question=state.question, current_state=state.to_dict()
            )

            # 更新状态
            state.evaluation_score = evaluation_details.get("overall_score", 0.0)
            state.evaluation_details = evaluation_details
            state.sufficient = evaluation_details.get("sufficient", False)
            state.evaluation_feedback = evaluation_details.get("analysis", "")

            # 计算评估时间
            end_time = datetime.now()
            state.evaluation_time = (end_time - start_time).total_seconds()

            logger.info(f" 评估阶段完成得分: {state.evaluation_score:.3f}")
            return state

        except Exception as e:
            logger.error(f" 评估阶段失败: {str(e)}")
            state.set_error(f"评估阶段失败: {str(e)}")
            return state

    async def _reflection_phase(self, state: AgentState) -> AgentState:
        """反思阶段"""
        logger.info(" 进入反思阶段...")

        try:
            # 更新状态
            state.status = AgentStatus.REFLECTING
            state.updated_at = datetime.now()

            # 生成反思
            context = self._build_context(state.retrieval_results)
            reflection_result = await self.reflection_agent.reflect_on_process(
                question=state.question,
                context=context,
                answer="",  # 还没有答案
                evaluation_score=state.evaluation_score,
                reflection_count=state.reflection_count,
            )

            # 生成改进建议
            improvement_suggestions = await self.reflection_agent.suggest_improvements(
                question=state.question, context=context, answer="", evaluation_details=state.evaluation_details
            )

            # 更新状态
            state.add_reflection(reflection_result.get("reflection_text", ""))
            for suggestion in improvement_suggestions:
                state.add_improvement_suggestion(suggestion)

            # 如果还没有优化查询生成新的
            if not state.optimized_queries:
                optimized_queries = await self.reflection_agent.generate_enhanced_query(
                    original_question=state.original_query,
                    context=context,
                    evaluation_details=state.evaluation_details,
                    previous_queries=[state.current_query],
                )
                state.optimized_queries = optimized_queries
                state.current_query = optimized_queries[0] if optimized_queries else state.current_query

            logger.info(f" 反思阶段完成反思次数: {state.reflection_count}")
            return state

        except Exception as e:
            logger.error(f" 反思阶段失败: {str(e)}")
            state.set_error(f"反思阶段失败: {str(e)}")
            return state

    async def _answer_phase(self, state: AgentState) -> AgentState:
        """回答阶段"""
        logger.info(" 进入回答阶段...")

        try:
            # 更新状态
            state.status = AgentStatus.ANSWERING
            state.updated_at = datetime.now()

            # 构建上下文
            context = self._build_context(state.retrieval_results)

            # 检查是否是统计查询
            if state.retrieval_metadata.get("type") == "sql":
                # 处理SQL结果
                sql_result = state.retrieval_results[0] if state.retrieval_results else {}
                final_answer = self._format_sql_answer(sql_result, state.question)
                confidence_score = 0.95  # SQL查询通常很准确
            else:
                # 生成自然语言答案
                final_answer = await self.deepseek_client.generate_answer(
                    context=context, question=state.question, answer_style="detailed"
                )
                confidence_score = state.evaluation_score

            # 生成最终评估
            final_assessment = await self.reflection_agent.generate_final_assessment(
                question=state.question,
                context=context,
                answer=final_answer,
                evaluation_score=state.evaluation_score,
                reflection_notes=state.reflection_notes,
            )

            # 更新状态
            state.final_answer = final_answer
            state.confidence_score = final_assessment.get("confidence_score", confidence_score)
            state.answer_metadata = final_assessment
            state.status = AgentStatus.COMPLETED

            logger.info(" 回答阶段完成")
            return state

        except Exception as e:
            logger.error(f" 回答阶段失败: {str(e)}")
            state.set_error(f"回答阶段失败: {str(e)}")
            return state

    async def _hybrid_search(self, query: str, query_vector: List[float]) -> List[Dict[str, Any]]:
        """执行混合搜索"""
        try:
            # 1. 向量搜索
            vector_results = await self.vector_client.search_vectors(query_vector=query_vector, limit=50)

            # 2. BM25搜索
            bm25_results = await self.vector_client.bm25_search(query=query, limit=50)

            # 3. 融合结果简化实现
            combined_results = []

            # 添加向量搜索结果
            for result in vector_results[:25]:
                result["search_type"] = "vector"
                result["score"] = 1.0 - float(result.get("distance", 0.5))  # 转换为相似度
                combined_results.append(result)

            # 添加BM25搜索结果
            for result in bm25_results[:25]:
                result["search_type"] = "bm25"
                result["score"] = float(result.get("rank", 0.5))
                combined_results.append(result)

            # 按分数排序
            combined_results.sort(key=lambda x: x["score"], reverse=True)

            # 去重并返回Top-10
            seen_ids = set()
            unique_results = []
            for result in combined_results:
                chunk_id = result.get("id")
                if chunk_id not in seen_ids:
                    seen_ids.add(chunk_id)
                    unique_results.append(result)
                if len(unique_results) >= 10:
                    break

            return unique_results

        except Exception as e:
            logger.error(f" 混合搜索失败: {str(e)}")
            return []

    def _is_statistical_query(self, query: str) -> bool:
        """判断是否是统计查询"""
        statistical_keywords = [
            "统计",
            "分析",
            "数量",
            "数量",
            "最高",
            "最低",
            "平均",
            "总计",
            "多少",
            "几个",
            "排名",
            "排序",
            "前",
            "后",
            "最多",
            "最少",
            "count",
            "sum",
            "avg",
            "max",
            "min",
            "total",
            "number",
            "how many",
        ]

        query_lower = query.lower()
        return any(keyword.lower() in query_lower for keyword in statistical_keywords)

    async def _handle_statistical_query(self, state: AgentState) -> Dict[str, Any]:
        """处理统计查询"""
        try:
            # 获取表信息
            await self.text_to_sql.get_table_info()

            # 生成SQL查询
            sql_result = await self.text_to_sql.generate_statistical_query(
                question=state.current_query, data_type="video"
            )

            return sql_result

        except Exception as e:
            logger.error(f" 统计查询处理失败: {str(e)}")
            return {"success": False, "error": str(e)}

    def _build_context(self, retrieval_results: List[Dict[str, Any]]) -> str:
        """构建上下文"""
        if not retrieval_results:
            return "未检索到相关信息"

        context_parts = []
        for i, result in enumerate(retrieval_results[:5], 1):
            if result.get("search_type") == "sql":
                context_parts.append(f"[SQL结果 {i}]\n{self._format_sql_context(result)}")
            else:
                content = result.get("content", "")
                video_title = result.get("video_title", "未知视频")
                start_time = result.get("start_time", 0)
                context_parts.append(f"[{i}] 视频{video_title}\n时间{start_time}秒\n内容{content[:300]}...")

        return "\n\n".join(context_parts)

    def _format_sql_context(self, sql_result: Dict[str, Any]) -> str:
        """格式化SQL查询上下文"""
        execution = sql_result.get("execution", {})
        if not execution.get("success"):
            return "SQL查询失败"

        data = execution.get("data", [])
        if not data:
            return "查询无结果"

        # 构建结果摘要
        summary_parts = []
        for row in data[:3]:  # 只显示前3行
            summary_parts.append(str(row))

        return "SQL查询结果\n" + "\n".join(summary_parts)

    def _format_sql_answer(self, sql_result: Dict[str, Any], question: str) -> str:
        """格式化SQL答案"""
        if not sql_result.get("success"):
            return f"抱歉查询失败{sql_result.get('error', '未知错误')}"

        execution = sql_result.get("execution", {})
        data = execution.get("data", [])
        summary = sql_result.get("summary", "")

        if not data:
            return "查询无结果"

        answer = f"根据数据分析{summary}\n\n"
        answer += "详细结果\n"

        for i, row in enumerate(data[:5], 1):
            answer += f"{i}. {row}\n"

        if len(data) > 5:
            answer += f"\n... 共{len(data)}条记录"

        return answer

    def _format_response(self, state: AgentState) -> Dict[str, Any]:
        """格式化响应"""
        return {
            "session_id": state.session_id,
            "question": state.question,
            "answer": state.final_answer,
            "confidence": state.confidence_score,
            "status": state.status.value,
            "evaluation_score": state.evaluation_score,
            "sufficient": state.sufficient,
            "reflection_count": state.reflection_count,
            "optimized_queries": state.optimized_queries,
            "retrieval_count": len(state.retrieval_results),
            "performance": {
                "total_time": state.total_time,
                "retrieval_time": state.retrieval_time,
                "thinking_time": state.thinking_time,
                "evaluation_time": state.evaluation_time,
            },
            "metadata": {
                "query_strategy": state.query_strategy,
                "answer_metadata": state.answer_metadata,
                "evaluation_details": state.evaluation_details,
            },
            "error": state.error_message if state.error_message else None,
        }


def test_agentic_workflow():
    """测试Agentic工作流"""
    print(" 测试Agentic工作流...")
    print("  注意: 需要完整的数据库连接才能测试")

    # 创建工作流实例
    workflow = AgenticRAGWorkflow("postgresql://user:pass@localhost/db")

    print(" 工作流实例创建成功")

    # 测试问题类型识别
    print("\n 测试问题类型识别...")
    test_questions = ["什么是Python", "播放量最高的视频有哪些", "去年平均播放量是多少"]

    for question in test_questions:
        is_stat = workflow._is_statistical_query(question)
        print(f"  {question} -> {'统计查询' if is_stat else '普通查询'}")

    print("\n 工作流测试完成")


if __name__ == "__main__":
    test_agentic_workflow()
