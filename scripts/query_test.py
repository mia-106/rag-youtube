import asyncio
import sys
import os
import logging

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.retrieval.hybrid_search import HybridSearchEngine, SearchConfig
from src.core.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)


async def main():
    print("============================================================")
    print("YouTube Agentic RAG - Query Test")
    print("============================================================")

    if not settings.DATABASE_URL:
        print("❌ Error: DATABASE_URL is missing in .env")
        return

    # Initialize Search Engine
    print("🔧 Initializing Hybrid Search Engine...")
    engine = HybridSearchEngine(database_url=settings.DATABASE_URL)
    await engine.initialize()

    print("\n✅ System Ready! Enter your query (or 'exit' to quit).")
    print("-" * 60)

    while True:
        query = input("\n📝 Query: ").strip()
        if query.lower() in ("exit", "quit", "q"):
            break

        if not query:
            continue

        print(f"🔍 Searching for: '{query}'...")

        try:
            results = await engine.search(query=query, config=SearchConfig(top_k=5, vector_weight=0.7, bm25_weight=0.3))

            print(f"\n📊 Found {len(results)} results:\n")

            for i, res in enumerate(results):
                title = res.metadata.get("video_title", "Unknown")
                score = res.score
                content = res.content[:200].replace("\n", " ") + "..."

                print(f"[{i + 1}] {title} (Score: {score:.4f})")
                print(f"    Source: {res.source_type}")
                print(f"    Content: {content}\n")

        except Exception as e:
            print(f"❌ Search failed: {e}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
