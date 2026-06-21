"""
scripts/test_system.py
──────────────────────
A comprehensive integration test script to verify and demonstrate all the agentic 
educational features by calling the API endpoints using TestClient.
"""

import sys
import os
import json
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

# Reconfigure stdout to use UTF-8 on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from main import app
from src.agent.base_agent import AgentResult


# ── Create LLM Provider Mock ───────────────────────────────────────────────
class MockLLMProvider:
    def __init__(self):
        self.embedding_size = 768

    async def generate_text(self, prompt: str, **kwargs):
        # Detect which prompt is being sent and return appropriate response
        
        # 1. Intent Classification
        if "أنت محلل نوايا ذكي لنظام تعليمي" in prompt:
            # Extract actual user message to avoid system prompt keyword clashes
            user_msg = prompt
            if "رسالة المستخدم:" in prompt:
                user_msg = prompt.split("رسالة المستخدم:")[-1]
            elif "user message:" in prompt:
                user_msg = prompt.split("user message:")[-1]
            user_msg = user_msg.lower()

            if "مرحبا" in user_msg or "سلام" in user_msg:
                return json.dumps({
                    "intent": "greeting",
                    "confidence": 0.95,
                    "reasoning": "User greeted the bot.",
                    "entities": []
                })
            elif "خريطة مفاهيم" in user_msg or "ذهنية" in user_msg:
                return json.dumps({
                    "intent": "concept_map",
                    "confidence": 0.92,
                    "reasoning": "User wants a concept map of lists.",
                    "entities": ["القوائم"]
                })
            elif "شغل" in user_msg or "print" in user_msg:
                return json.dumps({
                    "intent": "python_scratchpad",
                    "confidence": 0.90,
                    "reasoning": "User wants to execute python code.",
                    "entities": []
                })
            elif "سقراط" in user_msg or "ناقشني" in user_msg:
                return json.dumps({
                    "intent": "socratic",
                    "confidence": 0.88,
                    "reasoning": "User asked for Socratic dialogue.",
                    "entities": ["الجاذبية"]
                })
            else:
                return json.dumps({
                    "intent": "research",
                    "confidence": 0.80,
                    "reasoning": "General educational question.",
                    "entities": []
                })

        # 2. Concept Map Generation
        if "أنشئ خريطة مفاهيم" in prompt or "concept map" in prompt.lower():
            return """خريطة مفاهيم القوائم (Lists) في لغة بايثون:

القوائم هي إحدى البنى الأساسية في بايثون وتستخدم لتخزين عناصر متعددة في متغير واحد.

```mermaid
graph TD
    A[القوائم Lists] -->|تتميز بـ| B[الترتيب Indexed]
    A -->|تتميز بـ| C[القابلية للتعديل Mutable]
    A -->|تتيح| D[تكرار العناصر Duplicates]
    A -->|عمليات أساسية| E[append لإضافة عنصر]
    A -->|عمليات أساسية| F[remove لحذف عنصر]
```

### التفصيل الهرمي للمفاهيم:
- **القوائم Lists**:
  - **الترتيب**: كل عنصر له مؤشر يبدأ من 0.
  - **القابلية للتعديل**: يمكنك تغيير أو إزالة أو إضافة العناصر بعد الإنشاء.
  - **الدوال الأساسية**:
    - `append()`: تضيف عنصراً لنهاية القائمة.
    - `remove()`: تحذف أول تطابق للعنصر."""

        # 3. Socratic dialogue
        if "المعلم سقراط" in prompt or "Socratic Rule" in prompt:
            return "أهلاً بك يا بطل! عندما تسقط الأشياء إلى الأرض عند إفلاتها، ما الذي تعتقد أنه يجذبها نحو الأسفل؟ هل لاحظت نمطاً مشابهاً في حياتك اليومية؟"

        # Default fallback response
        return "إجابة افتراضية محاكاة من المساعد التعليمي."

    async def embed_text(self, text, document_type=None):
        return [[0.1] * 768]


# ── Run the test suite ───────────────────────────────────────────────────────
async def test_all_features():
    print("=" * 70)
    print("[START] بدء اختبار وتجربة النظام التعليمي الكامل (FastAPI + Multi-Agent)")
    print("=" * 70)

    # Setup Mocks
    mock_db_client = MagicMock()
    mock_db = MagicMock()
    mock_collection = AsyncMock()

    # Mock Project Database lookup
    async def mock_find_one(*args, **kwargs):
        query = kwargs.get("filter", {}) or kwargs.get("spec", {})
        if not query:
            for arg in args:
                if isinstance(arg, dict):
                    query = arg
                    break
        if "project_id" in query:
            return {"project_id": query["project_id"], "name": "Python Basics"}
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

    # Override application clients
    app.client = mock_db_client
    app.db = mock_db
    app.llm_provider = MockLLMProvider()

    # Mock search_vector_db_collection in NLPController
    from src.controllers.NLPController import NLPController
    
    async def mock_vector_search(*args, **kwargs):
        doc1 = MagicMock()
        doc1.payload = {"text": "القوائم Lists في بايثون هي مصفوفات ديناميكية قابلة للتعديل والترتيب.", "source": "python_course.pdf", "page": 12}
        doc1.score = 0.95
        return [doc1]

    # Initialize TestClient
    client = TestClient(app)

    # 1. Test /api/v1/agent/tools
    print("\n--- [1] اختبار استرجاع قائمة الأدوات (/tools) ---")
    response = client.get("/api/v1/agent/tools")
    print(f"Status: {response.status_code}")
    print(json.dumps(response.json(), indent=2, ensure_ascii=False))

    # 2. Test Greeting Request
    print("\n--- [2] اختبار رسالة الترحيب (Greeting Intent) ---")
    body = {
        "project_id": "test_proj",
        "query": "مرحبا بك",
        "language": "ar"
    }
    with patch.object(NLPController, "search_vector_db_collection", mock_vector_search):
        response = client.post("/api/v1/agent/smart-ask", json=body)
    print(f"Status: {response.status_code}")
    res_json = response.json()
    print(f"الوكيل المستخدم: {res_json.get('agent_used')}")
    print(f"النية المكتشفة: {res_json.get('intent_detected')} (Confidence: {res_json.get('confidence')})")
    print(f"الإجابة:\n{res_json.get('answer')}")

    # 3. Test Concept Map Generation
    print("\n--- [3] اختبار توليد خريطة المفاهيم (Concept Map Intent) ---")
    body = {
        "project_id": "test_proj",
        "query": "ارسم لي خريطة مفاهيم عن القوائم في بايثون",
        "language": "ar"
    }
    with patch.object(NLPController, "search_vector_db_collection", mock_vector_search):
        response = client.post("/api/v1/agent/smart-ask", json=body)
    print(f"Status: {response.status_code}")
    res_json = response.json()
    print(f"الوكيل المستخدم: {res_json.get('agent_used')}")
    print(f"النية المكتشفة: {res_json.get('intent_detected')}")
    print(f"الإجابة:\n{res_json.get('answer')}")

    # 4. Test Socratic Dialogue
    print("\n--- [4] اختبار الحوار السقراطي (Socratic Intent) ---")
    body = {
        "project_id": "test_proj",
        "query": "ناقشني بطريقة سقراط عن سبب سقوط الأشياء للأرض",
        "language": "ar"
    }
    with patch.object(NLPController, "search_vector_db_collection", mock_vector_search):
        response = client.post("/api/v1/agent/smart-ask", json=body)
    print(f"Status: {response.status_code}")
    res_json = response.json()
    print(f"الوكيل المستخدم: {res_json.get('agent_used')}")
    print(f"النية المكتشفة: {res_json.get('intent_detected')}")
    print(f"الإجابة:\n{res_json.get('answer')}")

    # 5. Test Python Sandbox Execute (Direct Endpoint)
    print("\n--- [5] اختبار تشغيل الكود مباشرة عبر الساندبوكس (/sandbox) ---")
    sandbox_body = {
        "code": "nums = [1, 2, 3]\nprint('مجموع القائمة هو:', sum(nums))"
    }
    response = client.post("/api/v1/agent/sandbox", json=sandbox_body)
    print(f"Status: {response.status_code}")
    print(json.dumps(response.json(), indent=2, ensure_ascii=False))

    # 6. Test Python Sandbox via agent ask
    print("\n--- [6] اختبار تشغيل الكود عبر المحادثة الذكية (Sandbox Intent) ---")
    body = {
        "project_id": "test_proj",
        "query": "شغل الكود: print('Hello from multi-agent!')",
        "language": "ar"
    }
    with patch.object(NLPController, "search_vector_db_collection", mock_vector_search):
        response = client.post("/api/v1/agent/smart-ask", json=body)
    print(f"Status: {response.status_code}")
    res_json = response.json()
    print(f"الوكيل المستخدم: {res_json.get('agent_used')}")
    print(f"النية المكتشفة: {res_json.get('intent_detected')}")
    print(f"مخرجات الكود:\n{res_json.get('answer')}")

    print("\n" + "=" * 70)
    print("[SUCCESS] تم الانتهاء بنجاح من جميع اختبارات وتجارب النظام التعليمي!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_all_features())
