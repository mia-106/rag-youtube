import asyncio
import os
import sys
import json
import logging

# Add project root to path
sys.path.append(os.getcwd())

from src.retrieval.search_service import SearchService

logging.basicConfig(level=logging.INFO)


async def test_search_service():
    service = SearchService()

    test_queries = [
        "OpenClaw 是什么？",
        "2026年 Dan Koe 的生活方式趋势如何？",
        "如何通过 super individual 策略获得 leverage？",
    ]

    print("\n" + "=" * 50)
    print("🚀 Testing SearchService Refactor")
    print("=" * 50 + "\n")

    for query in test_queries:
        print(f"User Query: {query}")

        # 1. Test Intent Analysis
        intent = await service.analyze_intent(query)
        print(f"Intent JSON: {json.dumps(intent, indent=2, ensure_ascii=False)}")

        # 2. Test Hybrid Query Generation
        queries = service.generate_hybrid_queries(intent, query)
        print(f"Hybrid Queries: {queries}")

        # 3. Test Search & Protection (Skip actual Tavily call if no API key)
        if not service.tavily_api_key:
            print("⚠️ Skipping actual search (No API Key)")
        else:
            print("📡 Executing Search & Reranking...")
            # We use a dummy search domain
            results = await service.search(query, ["youtube.com", "dan-koe.com"])
            print(f"Results Count: {len(results)}")
            if results:
                print(f"Top 1 Title: {results[0].get('title')}")
            else:
                print("🛑 Circuit Breaker triggered or no results.")

        print("-" * 50)


if __name__ == "__main__":
    asyncio.run(test_search_service())
