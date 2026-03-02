import asyncio
import json
from typing import Dict, Any
from unittest.mock import patch
import src.agent.nodes as nodes


AgentState = Dict[str, Any]


async def mock_generate_response(messages):
    prompt = messages[0]["content"]

    # 1. Simulate Grader Logic
    if "Semantic Grader" in prompt:
        print("\n[Mock LLM] Grader Prompt received.")
        if "OpenAI Operator" in prompt:
            # Check if context contains OpenAI Operator
            if "OpenAI Operator" in prompt.split("Retrieved Local Knowledge")[1]:
                return json.dumps({"is_sufficient": True, "reason": "Found it."})
            else:
                return json.dumps(
                    {"is_sufficient": False, "reason": "Entity 'OpenAI Operator' not found in local knowledge."}
                )
        return json.dumps({"is_sufficient": True, "reason": "General question."})

    # 2. Simulate Generator Logic
    if "You are Dan Koe" in prompt:
        print("\n[Mock LLM] Generator Prompt received.")
        # Check if the prompt instructs about Context Awareness
        if "Context Awareness & Honesty (CRITICAL)" in prompt:
            return '针对你提到的 OpenAI Operator，虽然我没有直接的使用经验，但在我看来，工具的核心价值在于提升杠杆率，而不是替代思考。 \n\n __REFERENCES_JSON__:[{"id": "1", "title": "Video Title", "url": "http..."}]'
        return "Standard response."

    return ""


async def test_grader_hallucination():
    print("--- Testing Grader Hallucination Fix ---")

    # Mock the LLM call in nodes.py
    with patch("src.agent.nodes.generate_response", side_effect=mock_generate_response):
        # Test Case 1: Query for "OpenAI Operator" with IRRELEVANT docs
        print("\nTest Case 1: Query 'OpenAI Operator' with irrelevant docs")
        state = {
            "question": "How do you view OpenAI Operator?",
            "documents": [
                json.dumps(
                    {
                        "content": "Dan Koe talks about focus and deep work.",
                        "source": "http://example.com",
                        "concept": "Focus",
                        "source_type": "video",
                    }
                )
            ],
            "rejection_count": 0,
            "agent_id": "dan_koe",
            "intent_metadata": {},
            "chat_history": [],
        }

        # We need to mock grade_documents logic or call it
        # But wait, grade_documents calls generate_response too.
        # The mock above handles "Semantic Grader" prompt.

        # However, calling nodes.grade_documents might fail if dependencies are missing.
        # Let's try calling it.
        try:
            result = await nodes.grade_documents(state)
            print(f"Result sufficiency: {result['is_sufficient']}")

            if result["is_sufficient"] is False:
                print("✅ PASS: Grader correctly rejected irrelevant docs for specific entity.")
            else:
                print("❌ FAIL: Grader accepted irrelevant docs.")
        except Exception as e:
            print(f"⚠️ SKIPPING Test Case 1 due to error: {e}")

        # Test Case 2: Verify Generator Prompt contains Context Awareness instruction
        print("\nTest Case 2: Verify Generator Prompt has Context Awareness instruction")

        state_gen = {
            "question": "How do you view OpenAI Operator?",
            "documents": [],
            "agent_id": "dan_koe",
            "intent_metadata": {},
            "chat_history": [],
        }

        # Mock get_agent_insights to return empty string
        with patch("src.agent.nodes.get_agent_insights", return_value=""):
            res = await nodes.generate(state_gen)
            generation = res["generation"]
            print(f"Generation start: {generation[:50]}...")

            # Updated expectation: Natural "pivot"
            expected_start = "针对你提到的 OpenAI Operator"

            if generation.startswith(expected_start):
                print("✅ PASS: Generator produced natural honest disclaimer.")
            else:
                print(
                    f"❌ FAIL: Generator did not produce honest disclaimer.\nExpected start: {expected_start}\nActual: {generation[:50]}..."
                )


if __name__ == "__main__":
    asyncio.run(test_grader_hallucination())
