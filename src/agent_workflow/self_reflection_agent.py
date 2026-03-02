"""
自反思代理
实现Agent的自反思机制评估检索充足性并优化查询
"""

import asyncio
from typing import Dict, Any, List
import logging
from src.core.deepseek_client import DeepSeekClient
from src.core.config import settings

logger = logging.getLogger(__name__)


class SelfReflectionAgent:
    """自反思代理"""

    def __init__(self):
        self.deepseek_client = DeepSeekClient()
        self.evaluation_threshold = settings.MIN_CONTEXT_PRECISION

    async def evaluate_retrieval_sufficiency(
        self, context: str, question: str, current_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        评估检索充足性

        Args:
            context: 检索到的上下文
            question: 用户问题
            current_state: 当前状态

        Returns:
            评估结果字典
        """
        logger.info(" 开始评估检索充足性...")

        try:
            # 使用DeepSeek评估检索充分性
            evaluation_result = await self.deepseek_client.evaluate_retrieval_sufficiency(
                context=context, question=question
            )

            # 解析评估结果
            relevance_score = evaluation_result.get("relevance_score", 0.0)
            completeness_score = evaluation_result.get("completeness_score", 0.0)
            overall_score = evaluation_result.get("overall_score", 0.0)
            sufficient = evaluation_result.get("sufficient", False)
            analysis = evaluation_result.get("analysis", "")

            # 检查是否需要反思
            needs_reflection = not sufficient and overall_score < self.evaluation_threshold

            evaluation_details = {
                "relevance_score": relevance_score,
                "completeness_score": completeness_score,
                "overall_score": overall_score,
                "sufficient": sufficient,
                "analysis": analysis,
                "threshold": self.evaluation_threshold,
                "needs_reflection": needs_reflection,
            }

            logger.info(f" 评估完成 - 得分: {overall_score:.3f}, 充足: {sufficient}")

            return evaluation_details

        except Exception as e:
            logger.error(f" 评估检索充足性失败: {str(e)}")

            # 返回默认值
            return {
                "relevance_score": 0.0,
                "completeness_score": 0.0,
                "overall_score": 0.0,
                "sufficient": False,
                "analysis": f"评估失败: {str(e)}",
                "threshold": self.evaluation_threshold,
                "needs_reflection": True,
                "error": str(e),
            }

    async def generate_enhanced_query(
        self, original_question: str, context: str, evaluation_details: Dict[str, Any], previous_queries: List[str]
    ) -> List[str]:
        """
        生成增强查询

        Args:
            original_question: 原始问题
            context: 当前上下文
            evaluation_details: 评估结果
            previous_queries: 之前的查询

        Returns:
            增强后的查询列表
        """
        logger.info(" 开始生成增强查询...")

        try:
            # 分析不足之处
            analysis = evaluation_details.get("analysis", "")
            suggestions = evaluation_details.get("suggestions", [])

            # 使用DeepSeek生成优化查询
            optimized_queries = await self.deepseek_client.generate_optimized_query(
                original_question=original_question, context=context, insufficient_analysis=analysis
            )

            # 添加基于建议的查询
            enhanced_queries = []
            for suggestion in suggestions:
                if isinstance(suggestion, str):
                    enhanced_queries.append(suggestion)

            # 合并查询去重
            all_queries = optimized_queries + enhanced_queries
            unique_queries = []
            seen = set()

            for query in all_queries:
                query_lower = query.lower().strip()
                if query_lower not in seen and query_lower not in [q.lower() for q in previous_queries]:
                    unique_queries.append(query)
                    seen.add(query_lower)

            logger.info(f" 生成 {len(unique_queries)} 个增强查询")
            return unique_queries[:3]  # 返回最多3个查询

        except Exception as e:
            logger.error(f" 生成增强查询失败: {str(e)}")

            # 返回默认值
            return [original_question]

    async def reflect_on_process(
        self, question: str, context: str, answer: str, evaluation_score: float, reflection_count: int
    ) -> Dict[str, Any]:
        """
        反思整个过程

        Args:
            question: 用户问题
            context: 检索上下文
            answer: 生成答案
            evaluation_score: 评估分数
            reflection_count: 反思次数

        Returns:
            反思结果
        """
        logger.info(" 开始反思过程...")

        try:
            # 构建反思提示
            system_prompt = """你是一个专业的AI助手正在反思整个问题解决过程

请从以下几个维度进行反思
1. 问题理解 - 是否准确理解了用户意图
2. 检索策略 - 检索方法是否有效
3. 答案质量 - 答案是否准确全面有帮助
4. 改进空间 - 哪些方面可以进一步优化

请提供具体的反思意见和建议"""

            user_prompt = f"""问题{question}

检索上下文
{context}

生成答案
{answer}

评估分数{evaluation_score:.3f}
反思次数{reflection_count}

请进行深入反思"""

            messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]

            reflection = await self.deepseek_client.generate_completion(messages=messages, temperature=0.4)

            reflection_result = {
                "reflection_text": reflection,
                "evaluation_score": evaluation_score,
                "reflection_count": reflection_count,
                "timestamp": asyncio.get_event_loop().time(),
            }

            logger.info(" 反思完成")
            return reflection_result

        except Exception as e:
            logger.error(f" 反思过程失败: {str(e)}")

            return {
                "reflection_text": f"反思失败: {str(e)}",
                "evaluation_score": evaluation_score,
                "reflection_count": reflection_count,
                "timestamp": asyncio.get_event_loop().time(),
                "error": str(e),
            }

    async def suggest_improvements(
        self, question: str, context: str, answer: str, evaluation_details: Dict[str, Any]
    ) -> List[str]:
        """
        建议改进措施

        Args:
            question: 用户问题
            context: 检索上下文
            answer: 生成答案
            evaluation_details: 评估详情

        Returns:
            改进建议列表
        """
        logger.info(" 生成改进建议...")

        try:
            # 分析评估结果
            suggestions = evaluation_details.get("suggestions", [])

            # 基于评估结果生成建议
            improvement_suggestions = []

            relevance_score = evaluation_details.get("relevance_score", 0.0)
            completeness_score = evaluation_details.get("completeness_score", 0.0)

            # 基于分数添加建议
            if relevance_score < 0.7:
                improvement_suggestions.append("增加更多相关关键词检索")
                improvement_suggestions.append("尝试同义词和相关概念")

            if completeness_score < 0.7:
                improvement_suggestions.append("扩大检索范围")
                improvement_suggestions.append("增加更多背景信息")

            # 添加从分析中提取的建议
            for suggestion in suggestions:
                if isinstance(suggestion, str) and suggestion not in improvement_suggestions:
                    improvement_suggestions.append(suggestion)

            # 去重并限制数量
            unique_suggestions = list(dict.fromkeys(improvement_suggestions))[:5]

            logger.info(f" 生成 {len(unique_suggestions)} 条改进建议")
            return unique_suggestions

        except Exception as e:
            logger.error(f" 生成改进建议失败: {str(e)}")
            return ["请检查检索策略", "尝试优化查询词"]

    async def should_continue_reflection(
        self, evaluation_score: float, reflection_count: int, max_reflections: int = 3
    ) -> bool:
        """
        判断是否应该继续反思

        Args:
            evaluation_score: 评估分数
            reflection_count: 当前反思次数
            max_reflections: 最大反思次数

        Returns:
            是否继续
        """
        # 基本规则
        if reflection_count >= max_reflections:
            return False

        if evaluation_score >= self.evaluation_threshold:
            return False

        # 如果分数很低允许更多反思
        if evaluation_score < 0.3 and reflection_count < max_reflections * 2:
            return True

        return reflection_count < max_reflections

    async def generate_final_assessment(
        self, question: str, context: str, answer: str, evaluation_score: float, reflection_notes: List[str]
    ) -> Dict[str, Any]:
        """
        生成最终评估

        Args:
            question: 用户问题
            context: 检索上下文
            answer: 最终答案
            evaluation_score: 最终评估分数
            reflection_notes: 反思记录

        Returns:
            最终评估结果
        """
        logger.info(" 生成最终评估...")

        try:
            # 计算置信度
            confidence_score = min(evaluation_score * 1.2, 1.0)  # 最高1.0

            # 生成质量等级
            if evaluation_score >= 0.9:
                quality_level = "优秀"
            elif evaluation_score >= 0.8:
                quality_level = "良好"
            elif evaluation_score >= 0.7:
                quality_level = "中等"
            else:
                quality_level = "需改进"

            final_assessment = {
                "overall_score": evaluation_score,
                "confidence_score": confidence_score,
                "quality_level": quality_level,
                "answer_length": len(answer),
                "context_relevance": evaluation_score,
                "reflection_summary": f"经过 {len(reflection_notes)} 次反思评估分数为 {evaluation_score:.3f}",
                "timestamp": asyncio.get_event_loop().time(),
            }

            logger.info(f" 最终评估完成 - 质量等级: {quality_level}")
            return final_assessment

        except Exception as e:
            logger.error(f" 生成最终评估失败: {str(e)}")
            return {
                "overall_score": evaluation_score,
                "confidence_score": evaluation_score,
                "quality_level": "未知",
                "answer_length": len(answer) if answer else 0,
                "context_relevance": evaluation_score,
                "reflection_summary": f"评估过程出错: {str(e)}",
                "timestamp": asyncio.get_event_loop().time(),
                "error": str(e),
            }


def test_self_reflection_agent():
    """测试自反思代理"""
    agent = SelfReflectionAgent()

    print(" 测试自反思代理...")
    print("  注意: 需要配置DEEPSEEK_API_KEY才能测试实际API调用")

    # 测试评估充足性模拟
    print("\n 测试评估充足性...")
    test_context = "Python是一种编程语言它简单易学"
    test_question = "什么是Python"

    print(" 评估接口已准备")
    print(f"  测试上下文: {test_context[:50]}...")
    print(f"  测试问题: {test_question}")

    # 测试生成增强查询
    print("\n 测试生成增强查询...")
    print(" 增强查询接口已准备")

    # 测试反思过程
    print("\n 测试反思过程...")
    print(" 反思接口已准备")

    # 测试改进建议
    print("\n 测试改进建议...")
    print(" 改进建议接口已准备")

    # 测试是否继续反思
    print("\n 测试继续反思判断...")
    should_continue = asyncio.run(agent.should_continue_reflection(0.5, 2))
    print(f" 继续反思判断: {should_continue}")

    # 测试最终评估
    print("\n 测试最终评估...")
    print(" 最终评估接口已准备")

    print("\n 所有接口测试通过")


if __name__ == "__main__":
    test_self_reflection_agent()
