import asyncio
import sys
import os
from uuid import uuid4

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.vector_storage.superabase_client import SuperabaseClient


async def test_history():
    client = SuperabaseClient()
    await client.connect()

    session_id = str(uuid4())
    print(f"Testing with session_id: {session_id}")

    # Test Save
    print("Saving user message...")
    await client.save_chat_message(session_id, "user", "Hello AI", "dan_koe")

    print("Saving assistant message...")
    await client.save_chat_message(session_id, "assistant", "Hello Human", "dan_koe")

    # Test Get
    print("Retrieving history...")
    history = await client.get_chat_history(session_id)
    print(f"Retrieved {len(history)} messages")

    for msg in history:
        print(f"- {msg['role']}: {msg['content']}")

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(test_history())
