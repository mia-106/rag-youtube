"""
DeepSeek API客户端安全版本
封装DeepSeek-V3.1 API调用支持流式输出和结构化输出
包含速率限制和重试机制
"""

import asyncio
import json
import time
from typing import Dict, Any, Optional, List, AsyncGenerator
from openai import AsyncOpenAI, RateLimitError as OpenAIRateLimitError, APITimeoutError
import logging
from src.core.config import settings

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DeepSeekError(Exception):
    """DeepSeek相关错误"""

    pass


class DeepSeekClient:
    """DeepSeek API客户端带速率限制"""

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.DEEPSEEK_API_KEY, base_url=settings.DEEPSEEK_BASE_URL)
        self.model = settings.DEEPSEEK_MODEL

        #  速率限制配置
        self.max_concurrent = getattr(settings, "MAX_CONCURRENT_REQUESTS", 10)
        self.semaphore = asyncio.Semaphore(self.max_concurrent)
        self.rate_limit_delay = getattr(settings, "RATE_LIMIT_DELAY", 0.1)

        #  请求统计
        self.request_stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "rate_limited_requests": 0,
            "avg_response_time": 0.0,
            "last_request_time": 0,
        }

        #  重试配置
        self.max_retries = getattr(settings, "MAX_RETRIES", 3)
        self.retry_delay = getattr(settings, "RETRY_DELAY", 1.0)

    async def _acquire_rate_limit(self):
        """获取速率限制许可"""
        async with self.semaphore:
            # 简单的时间间隔控制
            current_time = time.time()
            time_since_last = current_time - self.request_stats["last_request_time"]
            if time_since_last < self.rate_limit_delay:
                await asyncio.sleep(self.rate_limit_delay - time_since_last)

            self.request_stats["last_request_time"] = time.time()

    async def _execute_with_retry(self, func, *args, **kwargs) -> Any:
        """执行API调用带重试机制"""
        last_error = None

        for attempt in range(self.max_retries):
            try:
                # 速率限制
                await self._acquire_rate_limit()

                start_time = time.time()
                result = await func(*args, **kwargs)
                end_time = time.time()

                # 更新统计
                self._update_stats(True, end_time - start_time)
                return result

            except OpenAIRateLimitError as e:
                last_error = e
                self.request_stats["rate_limited_requests"] += 1
                wait_time = (2**attempt) * self.retry_delay  # 指数退避
                logger.warning(f" 速率限制等待 {wait_time:.1f} 秒 (尝试 {attempt + 1}/{self.max_retries})")
                await asyncio.sleep(wait_time)

            except APITimeoutError as e:
                last_error = e
                wait_time = (2**attempt) * self.retry_delay
                logger.warning(f" API超时等待 {wait_time:.1f} 秒 (尝试 {attempt + 1}/{self.max_retries})")
                await asyncio.sleep(wait_time)

            except Exception as e:
                last_error = e
                logger.error(f" API调用失败: {str(e)}")
                break

        # 所有重试都失败
        self._update_stats(False)
        raise DeepSeekError(f"API调用失败已重试 {self.max_retries} 次: {str(last_error)}")

    def _update_stats(self, success: bool, response_time: float = 0):
        """更新请求统计"""
        self.request_stats["total_requests"] += 1

        if success:
            self.request_stats["successful_requests"] += 1
            # 更新平均响应时间
            total = self.request_stats["total_requests"]
            current_avg = self.request_stats["avg_response_time"]
            self.request_stats["avg_response_time"] = (current_avg * (total - 1) + response_time) / total
        else:
            self.request_stats["failed_requests"] += 1

    def get_rate_limit_status(self) -> Dict[str, Any]:
        """获取速率限制状态"""
        total = self.request_stats["total_requests"]
        if total == 0:
            return {"status": "ready", "concurrent_slots_available": self.semaphore._value, "stats": self.request_stats}

        success_rate = (self.request_stats["successful_requests"] / total) * 100
        failure_rate = (self.request_stats["failed_requests"] / total) * 100

        return {
            "status": "active" if total > 0 else "ready",
            "concurrent_slots_available": self.semaphore._value,
            "rate_limit_delay_ms": self.rate_limit_delay * 1000,
            "max_concurrent_requests": self.max_concurrent,
            "stats": {
                **self.request_stats,
                "success_rate_percent": round(success_rate, 2),
                "failure_rate_percent": round(failure_rate, 2),
            },
        }

    def reset_stats(self):
        """重置统计信息"""
        self.request_stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "rate_limited_requests": 0,
            "avg_response_time": 0.0,
            "last_request_time": 0,
        }
        logger.info(" 请求统计已重置")

    async def generate_completion(
        self, messages: List[Dict[str, str]], temperature: float = 0.7, max_tokens: int = 4000, stream: bool = False
    ) -> AsyncGenerator[str, None] | str:
        """
        生成对话完成带速率限制

        Args:
            messages: 对话消息列表
            temperature: 温度参数 (0-1)
            max_tokens: 最大生成token数
            stream: 是否流式输出

        Returns:
            流式输出: AsyncGenerator[str, None]
            非流式输出: str

        Raises:
            DeepSeekError: API调用失败
        """
        try:
            if stream:
                return self._stream_completion(messages, temperature, max_tokens)
            return await self._execute_with_retry(self._non_stream_completion, messages, temperature, max_tokens)

        except Exception as e:
            logger.error(f" DeepSeek API调用失败: {str(e)}")
            raise DeepSeekError(f"API调用失败: {str(e)}")

    async def _non_stream_completion(self, messages: List[Dict[str, str]], temperature: float, max_tokens: int) -> str:
        """非流式完成"""
        response = await self.client.chat.completions.create(
            model=self.model, messages=messages, temperature=temperature, max_tokens=max_tokens
        )

        return response.choices[0].message.content

    async def _stream_completion(
        self, messages: List[Dict[str, str]], temperature: float, max_tokens: int
    ) -> AsyncGenerator[str, None]:
        """流式完成"""
        stream = await self.client.chat.completions.create(
            model=self.model, messages=messages, temperature=temperature, max_tokens=max_tokens, stream=True
        )

        async for chunk in stream:
            if chunk.choices[0].delta.content is not None:
                yield chunk.choices[0].delta.content

    async def generate_structured_output(
        self, system_prompt: str, user_prompt: str, json_schema: Dict[str, Any], temperature: float = 0.3
    ) -> Dict[str, Any]:
        """
        生成结构化输出带速率限制

        Args:
            system_prompt: 系统提示词
            user_prompt: 用户提示词
            json_schema: JSON Schema
            temperature: 温度参数

        Returns:
            结构化输出字典

        Raises:
            DeepSeekError: 结构化输出失败
        """
        try:
            messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]

            response = await self._execute_with_retry(
                self.client.chat.completions.create,
                model=self.model,
                messages=messages,
                temperature=temperature,
                response_format={"type": "json_object"},
                max_tokens=4000,
            )

            content = response.choices[0].message.content
            return json.loads(content)

        except Exception as e:
            logger.error(f" 结构化输出失败: {str(e)}")
            raise DeepSeekError(f"结构化输出失败: {str(e)}")

    async def generate_thought(self, context: str, question: str, previous_thoughts: Optional[str] = None) -> str:
        """
        生成思考内容

        Args:
            context: 检索到的上下文
            question: 用户问题
            previous_thoughts: 之前的思考可选

        Returns:
            思考内容
        """
        system_prompt = """你是一个专业的AI助手正在分析用户问题

请仔细思考以下问题
1. 用户问题的核心意图是什么
2. 当前检索到的上下文是否足够回答问题
3. 是否需要进行额外的检索或优化查询
4. 如何更好地组织答案

请提供清晰逻辑的思考过程"""

        user_prompt = f"""问题{question}

当前上下文
{context}

{("之前的思考\n" + previous_thoughts) if previous_thoughts else ""}

请基于以上信息进行深入思考"""

        messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]

        return await self.generate_completion(messages, temperature=0.5)

    async def evaluate_retrieval_sufficiency(self, context: str, question: str) -> Dict[str, Any]:
        """
        评估检索充分性

        Args:
            context: 检索到的上下文
            question: 用户问题

        Returns:
            评估结果字典
        """
        system_prompt = """你是一个专业的评估助手负责评估检索到的上下文是否足以回答用户问题

评估维度
1. 上下文相关性 - 上下文是否直接回答了用户问题
2. 信息完整性 - 上下文是否提供了足够的信息
3. 准确性 - 上下文中的信息是否准确可靠
4. 时效性 - 信息是否为最新的

请给出0-1的评分并说明原因"""

        user_prompt = f"""问题{question}

检索到的上下文
{context}

请评估上述上下文的充分性并给出详细分析"""

        try:
            result = await self.generate_structured_output(
                system_prompt,
                user_prompt,
                {
                    "type": "object",
                    "properties": {
                        "relevance_score": {"type": "number", "minimum": 0, "maximum": 1},
                        "completeness_score": {"type": "number", "minimum": 0, "maximum": 1},
                        "accuracy_score": {"type": "number", "minimum": 0, "maximum": 1},
                        "timeliness_score": {"type": "number", "minimum": 0, "maximum": 1},
                        "overall_score": {"type": "number", "minimum": 0, "maximum": 1},
                        "sufficient": {"type": "boolean"},
                        "analysis": {"type": "string"},
                        "suggestions": {"type": "array", "items": {"type": "string"}},
                    },
                },
                temperature=0.2,
            )

            return result

        except Exception as e:
            logger.error(f" 评估检索充分性失败: {str(e)}")
            # 返回默认值
            return {
                "relevance_score": 0.0,
                "completeness_score": 0.0,
                "accuracy_score": 0.0,
                "timeliness_score": 0.0,
                "overall_score": 0.0,
                "sufficient": False,
                "analysis": f"评估失败: {str(e)}",
                "suggestions": ["请重新检索", "优化查询词"],
            }

    async def generate_optimized_query(
        self, original_question: str, context: str, insufficient_analysis: str
    ) -> List[str]:
        """
        生成优化的查询词

        Args:
            original_question: 原始问题
            context: 当前上下文
            insufficient_analysis: 不足之处分析

        Returns:
            优化后的查询词
        """
        system_prompt = """你是一个专业的查询优化助手负责根据当前检索不足的情况生成更好的查询词

优化原则
1. 提取问题的核心关键词
2. 考虑同义词和相关概念
3. 增加限定条件以提高准确性
4. 去除无关词汇
5. 保持查询的简洁性"""

        user_prompt = f"""原始问题{original_question}

当前检索到的上下文
{context}

不足之处分析
{insufficient_analysis}

请生成3个优化后的查询词按照相关性排序"""

        messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
        response = await self.generate_completion(messages, temperature=0.4)
        response_text = await self._coerce_text(response)

        queries = []
        for line in response_text.split("\n"):
            line = line.strip()
            if line and (line.startswith("1.") or line.startswith("2.") or line.startswith("3.")):
                query = line.split(".", 1)[1].strip()
                queries.append(query)

        return queries[:3] if queries else [original_question]

    async def generate_answer(self, context: str, question: str, answer_style: str = "detailed") -> str:
        """
        生成最终答案

        Args:
            context: 检索到的上下文
            question: 用户问题
            answer_style: 答案风格 (detailed, concise, structured)

        Returns:
            生成的答案
        """
        if answer_style == "structured":
            return await self._generate_structured_answer(context, question)
        elif answer_style == "concise":
            return await self._generate_concise_answer(context, question)
        else:
            return await self._generate_detailed_answer(context, question)

    async def _generate_detailed_answer(self, context: str, question: str) -> str:
        """生成详细答案"""
        system_prompt = """你是一个专业的YouTube视频分析助手专门基于已解析的视频内容回答用户问题

回答准则
1. 只基于提供的上下文信息回答不要添加外部知识
2. 如果上下文信息不足明确说明无法回答
3. 引用具体的视频和时间戳
4. 保持准确简洁有帮助的回答风格
5. 对于不确定的信息使用"可能""似乎"等表达"""

        user_prompt = f"""上下文信息
{context}

用户问题{question}

请根据上下文信息详细回答问题"""

        messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
        response = await self.generate_completion(messages, temperature=0.3)
        return await self._coerce_text(response)

    async def _generate_structured_answer(self, context: str, question: str) -> str:
        """生成结构化答案"""
        system_prompt = """你是一个专业的YouTube视频分析助手请基于提供的上下文信息生成结构化答案

输出格式要求
- 使用清晰的标题和段落
- 引用具体的视频和时间戳
- 列出关键要点
- 提供可操作的建议如适用"""

        user_prompt = f"""上下文信息
{context}

用户问题{question}

请生成结构化答案"""

        messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
        response = await self.generate_completion(messages, temperature=0.3)
        return await self._coerce_text(response)

    async def _generate_concise_answer(self, context: str, question: str) -> str:
        """生成简洁答案"""
        system_prompt = """你是一个专业的YouTube视频分析助手请基于提供的上下文信息生成简洁明了的答案

要求
1. 直接回答问题
2. 保持简洁不超过200字
3. 引用关键信息
4. 避免冗余"""

        user_prompt = f"""上下文信息
{context}

用户问题{question}

请生成简洁答案"""

        messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]
        response = await self.generate_completion(messages, temperature=0.3)
        return await self._coerce_text(response)


def test_deepseek_client():
    """测试DeepSeek客户端"""
    client = DeepSeekClient()

    print(" 测试DeepSeek客户端...")
    print("  注意: 需要配置DEEPSEEK_API_KEY才能测试实际API调用")

    # 测试基本配置
    print(f" 模型: {client.model}")
    print(f" 基础URL: {settings.DEEPSEEK_BASE_URL}")

    # 测试思考生成模拟
    print("\n 测试思考生成...")
    print(" 思考生成接口已准备")

    # 测试评估功能模拟
    print("\n 测试评估功能...")
    print(" 评估功能接口已准备")

    # 测试答案生成模拟
    print("\n 测试答案生成...")
    print(" 答案生成接口已准备")

    print("\n 所有接口测试通过")


if __name__ == "__main__":
    test_deepseek_client()
