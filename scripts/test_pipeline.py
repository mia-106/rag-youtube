import asyncio
import sys
import os
import time

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agent.graph import app


async def test_chat():
    print("🚀 Starting Pipeline Test...")

    # Test Question
    question = "How to become a super individual?"
    inputs = {"question": question, "chat_history": [], "retry_count": 0, "agent_id": "dan_koe"}

    start_time = time.time()
    print(f"❓ Question: {question}")

    try:
        # Run the graph
        print("⏳ Invoking graph...")
        # We use ainvoke for single result, or we can stream
        result = await app.ainvoke(inputs)

        duration = time.time() - start_time
        print(f"✅ Pipeline completed in {duration:.2f} seconds")
        print(f"📄 Answer length: {len(result.get('generation', ''))}")
        # print(f"📝 Answer: {result.get('generation', '')[:200]}...")

    except Exception as e:
        print(f"❌ Pipeline failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_chat())
