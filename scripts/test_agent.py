import asyncio
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agent.graph import app


async def main():
    print("🤖 Initializing Agentic RAG System...")

    # Test query
    question = "Dan Koe 在过去两年里，对‘专注力’的看法发生了什么演变？"
    print(f"❓ User Question: {question}")

    inputs = {"question": question, "retry_count": 0}

    try:
        # Run the graph
        final_generation = None
        async for output in app.astream(inputs):
            for key, value in output.items():
                print(f"Node '{key}':")
                if key == "generate":
                    final_generation = value.get("generation")

        if final_generation:
            print("\n🏁 Agent Execution Completed.")
            # Since output was already streamed, we don't need to print it again.

    except Exception as e:
        print(f"❌ Error running agent: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
