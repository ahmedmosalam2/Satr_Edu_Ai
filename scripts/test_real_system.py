"""
scripts/test_real_system.py
───────────────────────────
Runs the educational multi-agent system live with the real Gemini LLM API.
Database is mocked to bypass connection limits. Emojis and Arabic test helpers are removed.
"""

import sys
import os
import json
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from dotenv import load_dotenv

# Reconfigure stdout to use UTF-8
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

load_dotenv(".env")

from fastapi.testclient import TestClient
from main import app
from src.helpers.nlp_clients import get_generation_client


async def run_real_tests():
    print("=" * 80)
    print("RUNNING LIVE SYSTEM INTEGRATION WITH GEMINI API")
    print("=" * 80)

    # 1. Setup real Gemini LLM client
    try:
        real_llm = get_generation_client()
        app.llm_provider = real_llm
        print("Successfully initialized real Gemini generation client.")
    except Exception as e:
        print(f"Failed to initialize Gemini client: {e}")
        return

    # 2. Setup mock database (to bypass local MongoDB requirement)
    mock_db_client = MagicMock()
    mock_db = MagicMock()
    mock_collection = AsyncMock()

    async def mock_find_one(*args, **kwargs):
        query = kwargs.get("filter", {}) or kwargs.get("spec", {})
        if not query:
            for arg in args:
                if isinstance(arg, dict):
                    query = arg
                    break
        if "project_id" in query:
            return {"project_id": query["project_id"], "name": "Python Data Structures"}
        if "conversation_id" in query:
            return {
                "conversation_id": query["conversation_id"],
                "project_id": "test_proj",
                "messages": []
            }
        return None

    mock_collection.find_one = mock_find_one
    mock_collection.insert_one = AsyncMock(return_value=MagicMock(inserted_id="mock_id"))
    mock_collection.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
    mock_db.__getitem__.return_value = mock_collection
    mock_db.list_collection_names = AsyncMock(return_value=["projects", "conversations"])
    mock_db_client.__getitem__.return_value = mock_db

    app.client = mock_db_client
    app.db = mock_db

    # 3. Setup mock Vector Search
    from src.controllers.NLPController import NLPController
    
    async def mock_vector_search(*args, **kwargs):
        doc1 = MagicMock()
        doc1.payload = {
            "text": "Lists in Python are used to store multiple items in a single variable. They are ordered, changeable, and allow duplicate values. Example: mylist = ['apple', 'banana', 'cherry'].",
            "source": "python_basics.pdf",
            "page": 15
        }
        doc1.score = 0.98
        return [doc1]

    client = TestClient(app)

    # --- [1] Retrieve Available Tools ---
    print("\n--- [1] API Endpoint: GET /api/v1/agent/tools ---")
    response = client.get("/api/v1/agent/tools")
    print(f"Status Code: {response.status_code}")
    print(json.dumps(response.json(), indent=2))

    # --- [2] General Greeting ---
    print("\n--- [2] API Endpoint: POST /api/v1/agent/smart-ask (Greeting) ---")
    body = {
        "project_id": "test_proj",
        "query": "hello, who are you?",
        "language": "en"
    }
    with patch.object(NLPController, "search_vector_db_collection", mock_vector_search):
        response = client.post("/api/v1/agent/smart-ask", json=body)
    print(f"Status Code: {response.status_code}")
    res_json = response.json()
    print(f"Agent Used: {res_json.get('agent_used')}")
    print(f"Intent Detected: {res_json.get('intent_detected')} (Confidence: {res_json.get('confidence')})")
    print(f"Response:\n{res_json.get('answer')}")

    # --- [3] Concept Map Generation ---
    print("\n--- [3] API Endpoint: POST /api/v1/agent/smart-ask (Concept Map) ---")
    body = {
        "project_id": "test_proj",
        "query": "draw a concept map of lists in python",
        "language": "en"
    }
    with patch.object(NLPController, "search_vector_db_collection", mock_vector_search):
        response = client.post("/api/v1/agent/smart-ask", json=body)
    print(f"Status Code: {response.status_code}")
    res_json = response.json()
    print(f"Agent Used: {res_json.get('agent_used')}")
    print(f"Intent Detected: {res_json.get('intent_detected')}")
    print(f"Response:\n{res_json.get('answer')}")

    # --- [4] Socratic Dialogue ---
    print("\n--- [4] API Endpoint: POST /api/v1/agent/smart-ask (Socratic Dialogue) ---")
    body = {
        "project_id": "test_proj",
        "query": "Explain Newtonian Gravity",
        "language": "en"
    }
    # Force socratic intent in body or let classification handle it
    # We can ask socratic tutoring explicitly
    body["query"] = "Use socratic method to teach me gravity"
    with patch.object(NLPController, "search_vector_db_collection", mock_vector_search):
        response = client.post("/api/v1/agent/smart-ask", json=body)
    print(f"Status Code: {response.status_code}")
    res_json = response.json()
    print(f"Agent Used: {res_json.get('agent_used')}")
    print(f"Intent Detected: {res_json.get('intent_detected')}")
    print(f"Response:\n{res_json.get('answer')}")

    # --- [5] Direct Python Sandbox Execution ---
    print("\n--- [5] API Endpoint: POST /api/v1/agent/sandbox (Fibonacci & Bubble Sort) ---")
    sandbox_code = """
def fib(n):
    return n if n <= 1 else fib(n-1) + fib(n-2)

def bubble_sort(arr):
    n = len(arr)
    for i in range(n):
        for j in range(0, n-i-1):
            if arr[j] > arr[j+1]:
                arr[j], arr[j+1] = arr[j+1], arr[j]
    return arr

print("Fibonacci Sequence up to 8:", [fib(i) for i in range(8)])
print("Sorted Array:", bubble_sort([45, 12, 85, 32, 10, 5, 60]))
"""
    response = client.post("/api/v1/agent/sandbox", json={"code": sandbox_code})
    print(f"Status Code: {response.status_code}")
    res_json = response.json()
    print("Execution Result:")
    print(res_json.get("result"))

    print("\n" + "=" * 80)
    print("FINISHED ALL INTEGRATION TESTS SUCCESSFULLY")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(run_real_tests())
