import sys
import time
import uuid
import requests


def test_full_stack():
    print("🚀 Starting Full Stack Connection Test...")

    base_url = "http://127.0.0.1:8000"
    session_id = str(uuid.uuid4())
    agent_id = "dan_koe"

    # 1. Health Check
    print("\n1️⃣  Testing Backend Health...")
    try:
        resp = requests.get(f"{base_url}/health")
        if resp.status_code == 200:
            print("   ✅ Backend is UP")
        else:
            print(f"   ❌ Backend returned {resp.status_code}")
            sys.exit(1)
    except Exception as e:
        print(f"   ❌ Could not connect to backend: {e}")
        sys.exit(1)

    # 2. Check History (Empty)
    print(f"\n2️⃣  Testing History Retrieval (Session: {session_id})...")
    try:
        resp = requests.get(f"{base_url}/api/history/{session_id}")
        if resp.status_code == 200:
            history = resp.json()
            print(f"   ✅ History retrieved (Items: {len(history)})")
            if len(history) != 0:
                print("   ⚠️  Expected empty history for new session")
        else:
            print(f"   ❌ Failed to get history: {resp.status_code} - {resp.text}")
            sys.exit(1)
    except Exception as e:
        print(f"   ❌ Error fetching history: {e}")
        sys.exit(1)

    # 3. Send Chat Message
    print("\n3️⃣  Testing Chat Interaction...")
    payload = {
        "messages": [{"role": "user", "content": "Hello, are you online?"}],
        "agent_id": agent_id,
        "session_id": session_id,
    }

    try:
        # We need to handle streaming response
        print("   Sending POST /api/chat...")
        with requests.post(f"{base_url}/api/chat", json=payload, stream=True) as r:
            if r.status_code == 200:
                print("   ✅ Request accepted. Receiving stream...")
                full_response = ""
                for chunk in r.iter_content(chunk_size=1024):
                    if chunk:
                        text = chunk.decode("utf-8")
                        full_response += text
                        # print(text, end="", flush=True)
                print(f"\n   ✅ Stream finished. Response length: {len(full_response)}")
            else:
                print(f"   ❌ Chat request failed: {r.status_code} - {r.text}")
                sys.exit(1)
    except Exception as e:
        print(f"   ❌ Error sending chat: {e}")
        sys.exit(1)

    # 4. Verify Persistence
    print("\n4️⃣  Verifying Data Persistence...")
    # Allow a moment for async DB write
    time.sleep(1)
    try:
        resp = requests.get(f"{base_url}/api/history/{session_id}")
        if resp.status_code == 200:
            history = resp.json()
            print(f"   ✅ History retrieved. Items: {len(history)}")

            # Expect at least 2 messages: User + Assistant
            if len(history) >= 2:
                print("   ✅ Persistence Confirmed: User and Assistant messages found.")
                print("   🎉 FULL STACK TEST PASSED!")
            else:
                print(f"   ❌ Expected at least 2 messages, found {len(history)}")
                print(f"   Content: {history}")
                sys.exit(1)
        else:
            print(f"   ❌ Failed to get history verification: {resp.status_code}")
            sys.exit(1)
    except Exception as e:
        print(f"   ❌ Error verifying history: {e}")
        sys.exit(1)


if __name__ == "__main__":
    test_full_stack()
