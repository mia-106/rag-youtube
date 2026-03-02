import os
import json
import asyncio
import logging
import aiohttp
from typing import List, Dict, Any
from src.core.config import settings
from src.agent.llm import generate_response
from src.retrieval.reranker import BGEReranker

logger = logging.getLogger(__name__)


class SearchService:
    """
    重构后的搜索服务意图提取 -> 混合查询 -> 异步执行 -> 语义熔断精排
    """

    def __init__(self):
        self.tavily_api_key = os.getenv("TAVILY_API_KEY") or settings.TAVILY_API_KEY
        self.reranker = None  # Lazy init
        self.tavily_url = "https://api.tavily.com/search"

    async def initialize(self):
        if not self.reranker:
            self.reranker = await asyncio.to_thread(BGEReranker)

    async def analyze_intent(self, query: str) -> Dict[str, Any]:
        """
        第一步Intent Analysis (意图与实体提取)
        """
        prompt = f"""You are an Intent Analyzer for the Dan Koe Digital Twin. 
Analyze the user's query and extract key information in JSON format.

RULES:
1. Extract 'core_entity' (proper nouns, names, specific tools).
2. DO NOT translate or generalize proper nouns. If user says "OpenClaw", extract "OpenClaw", NOT "automation tool".
3. Extract 'time_horizon' (years, specific dates) if mentioned.
4. Categorize 'intent_type' as "fact_check" (specific info needed) or "concept_exploration" (general philosophy).
5. List 'keywords' for auxiliary search.

User Query: "{query}"

Output ONLY a valid JSON object:
{{
  "core_entity": "string or null",
  "time_horizon": "string or null",
  "intent_type": "fact_check | concept_exploration",
  "keywords": ["word1", "word2"]
}}
"""
        try:
            messages = [{"role": "user", "content": prompt}]
            response = await generate_response(messages, stream=False)
            # Cleanup potential markdown wrapper
            cleaned = response.replace("```json", "").replace("```", "").strip()
            return json.loads(cleaned)
        except Exception as e:
            logger.error(f"Intent analysis failed: {e}. Falling back to default.")
            return {
                "core_entity": None,
                "time_horizon": None,
                "intent_type": "concept_exploration",
                "keywords": [query],
            }

    def generate_hybrid_queries(self, intent: Dict[str, Any], original_query: str) -> List[str]:
        """
        第二步Hybrid Query Generation (混合查询策略)
        基于意图提取结果生成互补的搜索词
        """
        core_entity = intent.get("core_entity")
        keywords = " ".join(intent.get("keywords", []))
        time_horizon = intent.get("time_horizon")

        queries = []

        # 1. Broad Concept Query (广义概念查询 - 不强制 Dan Koe)
        # 用于捕捉像 "AQAL model" 这样的通用权威概念
        if core_entity:
            queries.append(f"{core_entity} {keywords} definition explained")
        else:
            queries.append(f"{original_query} explained")

        # 2. Dan Koe Knowledge Gap Filling (知识缺口填补)
        # 不仅仅是搜“看法”，而是搜“原始内容”，假设它是数据库的延伸
        # 使用 site: 语法强制在官方渠道挖掘
        if core_entity:
            # 优先搜博客长文
            queries.append(f"site:thedankoe.com {core_entity}")
            # 补充搜推特线索 (通常包含简短但核心的定义)
            queries.append(f"site:x.com/thedankoe {core_entity}")
        else:
            queries.append(f"site:thedankoe.com {original_query}")

        # 3. Dan Koe Context Query (Dan Koe 视角查询)
        # 尝试寻找 Dan Koe 对此话题的特定观点
        if core_entity:
            queries.append(f"Dan Koe philosophy on {core_entity}")
        else:
            queries.append(f"Dan Koe philosophy on {original_query}")

        # 3. Specific/Temporal Query (细节/时效查询)
        if time_horizon:
            entity_part = core_entity if core_entity else keywords
            queries.append(f"{entity_part} {time_horizon} trends")
        else:
             # 如果没有时间限制，尝试组合查询
             if core_entity:
                 queries.append(f"{core_entity} application in personal branding")
             else:
                 queries.append(f"{original_query} system thinking")

        return list(set(queries))  # 去重

    async def _tavily_call(
        self, session: aiohttp.ClientSession, query: str, search_domains: List[str]
    ) -> List[Dict[str, Any]]:
        """执行单个 Tavily 搜索"""
        
        # 智能动态域名控制 (Dynamic Domain Control)
        # 1. 如果是 site:thedankoe.com 查询，必须清除 include_domains 限制
        #    因为 Tavily 的 include_domains 可能会与 site: 语法冲突，或者我们需要确保不被其他域名干扰
        if "site:" in query:
             payload_domains = [] # 允许 site: 语法完全接管
        
        # 2. 如果是广义概念查询 (Query 1: explained/definition)，我们希望搜索全网权威源 (Wiki, Investopedia等)
        #    因此暂时移除白名单限制，让 Tavily 自由发挥，找到最好的定义
        elif "explained" in query or "definition" in query:
             payload_domains = []
             
        # 3. 其他情况 (Query 3 & 4)，保持白名单 (x.com, youtube, etc.) 以确保信噪比
        else:
             payload_domains = search_domains

        payload = {
            "api_key": self.tavily_api_key,
            "query": query,
            "search_depth": "advanced",
            "max_results": 5,
        }
        
        # 仅当 payload_domains 不为空时才添加参数
        if payload_domains:
            payload["include_domains"] = payload_domains

        try:
            async with session.post(self.tavily_url, json=payload, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("results", [])
                else:
                    logger.warning(f"Tavily API error for query '{query}': {resp.status}")
                    return []
        except Exception as e:
            logger.error(f"Tavily request failed for '{query}': {e}")
            return []

    async def execute_and_rerank(
        self, original_query: str, queries: List[str], intent: Dict[str, Any], search_domains: List[str]
    ) -> List[Dict[str, Any]]:
        """
        第三步Execution & Reranking (执行与熔断)
        """
        if not self.tavily_api_key:
            logger.error("Tavily API key missing.")
            return []

        # 1. 并行搜索
        # Use ClientSession as a context manager
        async with aiohttp.ClientSession() as session:
            tasks = [self._tavily_call(session, q, search_domains) for q in queries]
            search_results_lists = await asyncio.gather(*tasks)

        # 2. 去重 (按 URL)
        unique_results = {}
        for results in search_results_lists:
            for item in results:
                url = item.get("url")
                if url and url not in unique_results:
                    unique_results[url] = item

        results_list = list(unique_results.values())
        if not results_list:
            return []

        # 3. 简化精排 (Skip local BGE Rerank to avoid timeouts)
        # Tavily already ranks by relevance. We just take the top results from the unique set.
        # If we really need reranking, we should use a lightweight method or external API.
        # For now, we trust Tavily's ranking and just slice the top K.
        final_results = results_list[:5]

        # 4. 实体安全检查 (Entity Safety Check & Circuit Breaking)
        core_entity = intent.get("core_entity")
        if core_entity:
            entity_found = False
            # 检查前 3 名结果
            for res in final_results[:3]:
                text = (res.get("content", "") + res.get("title", "")).lower()
                if core_entity.lower() in text:
                    entity_found = True
                    break

            if not entity_found:
                logger.warning(f"Circuit breaker triggered: Entity '{core_entity}' not found in top search results.")
                # Fallback: return at least 1 result if it looks promising, instead of empty list
                if final_results:
                     logger.info("Circuit breaker soft override: Returning top result despite entity mismatch.")
                     return [final_results[0]]
                return []  # 熔断

        return final_results

    async def search(self, original_query: str, search_domains: List[str]) -> List[Dict[str, Any]]:
        """主入口"""
        # 1. 意图提取
        intent = await self.analyze_intent(original_query)
        logger.info("Initializing SearchService...")

        # 2. 生成查询
        queries = self.generate_hybrid_queries(intent, original_query)
        logger.info(f"Generated queries: {queries}")

        # 3. 执行精排与熔断
        results = await self.execute_and_rerank(original_query, queries, intent, search_domains)

        # 记录元数据供 Prompt 使用
        for r in results:
            r["intent_metadata"] = intent

        return results
