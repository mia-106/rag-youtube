import httpx
import asyncio


async def test_chat_stream():
    url = "http://localhost:8000/api/chat"
    payload = {
        "agent_id": "dan_koe",
        "session_id": "test_session_999",
        "messages": [{"role": "user", "content": "26年怎么成为超级个体"}],
    }

    print(f"🚀 Sending request to {url}...")
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("POST", url, json=payload) as response:
                if response.status_code != 200:
                    print(f"❌ Error: {response.status_code}")
                    return

                print("📡 Receiving stream:")
                full_text = ""
                async for chunk in response.aiter_text():
                    if chunk:
                        print(f"Chunk: [{chunk}]")
                        full_text += chunk

                print("\n" + "=" * 50)
                print("✅ Full Response:")
                print(full_text)
                print("=" * 50)
    except Exception as e:
        print(f"❌ Failed: {e}")


if __name__ == "__main__":
    asyncio.run(test_chat_stream())
