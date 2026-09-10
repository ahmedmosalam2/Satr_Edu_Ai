"""
src/agent/tools/concept_map.py
──────────────────────────────
Concept Map Tool — بيولد خريطة مفاهيم (Concept Map) تفاعلية من محتوى الكورس.

المخرجات تشمل:
  - مخطط Mermaid.js (رسم بياني)
  - شرح هرمي مبسط (Nested Lists)
  - JSON مبسط لو الـ frontend عايز يرسمه بطريقة خاصة
"""

import json
import logging
import re
from typing import List, Optional
from src.agent.base_agent import BaseTool

logger = logging.getLogger("uvicorn.error")

MAP_PROMPT_AR = """أنت معلم خبير متخصص في التفكير البصري وتنظيم المعلومات.
قم بإنشاء خريطة مفاهيم (Concept Map) شاملة ومترابطة للمفهوم التالي: "{query}"

بناءً على هذا المحتوى التعليمي المسترجع:
{context}

قواعد التوليد:
1. صمم خريطة المفاهيم لتوضيح العلاقات بين المفاهيم الرئيسية والفرعية.
2. يجب أن تتكون الإجابة من ثلاثة أجزاء رئيسية:
   أولاً: شرح عام للمفهوم الرئيسي (فقرة بسيطة).
   ثانياً: خريطة مفاهيم بصرية باستخدام كود Mermaid.js (استخدم `graph TD` أو `mindmap`). تأكد من خلو كود Mermaid من الأخطاء النحوية والرموز غير الصالحة. استخدم نصوص عربية واضحة للـ nodes والـ links.
   ثالثاً: تفصيل هرمي نصي (Nested Bullet Points) يشرح العلاقات.
3. أجب باللغة العربية.

صيغة الإجابة المطلوبة:
---
[شرح المفهوم باختصار]

```mermaid
graph TD
    A[المفهوم الرئيسي] -->|علاقة| B[مفهوم فرعي 1]
    A -->|علاقة| C[مفهوم فرعي 2]
    B -->|تفصيل| D[مثال/تفصيل]
```

### التفصيل الهرمي للمفاهيم:
- **المفهوم الرئيسي**:
  - **مفهوم فرعي 1**: شرح العلاقة وكيف يرتبط بالرئيسي.
  - **مفهوم فرعي 2**: شرح العلاقة وكيف يرتبط بالرئيسي.
---
"""

MAP_PROMPT_EN = """You are an expert tutor specialized in visual thinking and concept mapping.
Generate a comprehensive concept map for: "{query}"

Based on the retrieved educational context:
{context}

Rules:
1. Design a concept map showcasing relationships between main concepts and sub-concepts.
2. The output must have three parts:
   First: Brief textual introduction of the main concept.
   Second: Visual Mermaid.js diagram (`graph TD` or `mindmap`). Ensure syntax is completely valid.
   Third: Hierarchical bullet points detailing the relationships.
3. Answer in English.
"""


class ConceptMapTool(BaseTool):
    """
    Concept Map Tool — بيعمل RAG وسيرش على المفهوم،
    وبعدين بيطلب من الـ LLM يرسم خريطة مفاهيم تفصيلية.
    """

    def __init__(self, nlp_controller, project, generation_client):
        self.nlp_controller = nlp_controller
        self.project = project
        self.generation_client = generation_client
        self._last_citations = []

    @property
    def name(self) -> str:
        return "concept_map"

    @property
    def description(self) -> str:
        return "Generates a conceptual map/mind-map for a given concept using retrieved documents. Input: concept/topic name."

    @property
    def last_citations(self) -> list:
        return self._last_citations

    async def execute(self, query: str = "", limit: int = 5, language: str = "ar", **kwargs) -> str:
        if not query:
            return "Error: No concept query provided."

        try:
            # 1. Search knowledge base for the concept
            results = await self.nlp_controller.search_vector_db_collection(
                project=self.project,
                text=query,
                limit=limit,
            )

            context_parts = []
            citations = []
            if results:
                for i, doc in enumerate(results):
                    payload = doc.payload if hasattr(doc, "payload") else {}
                    full_text = payload.get("text", "")
                    source_file = payload.get("source", payload.get("source_file", "unknown"))
                    page = payload.get("page", payload.get("page_number", None))
                    
                    context_parts.append(f"[Source: {source_file} (Page {page})]\n{full_text}")

            context = "\n\n".join(context_parts) if context_parts else "لا توجد وثائق مسترجعة في قاعدة البيانات التعليمية."

            # 2. Call LLM to generate the concept map
            template = MAP_PROMPT_AR if language == "ar" else MAP_PROMPT_EN
            prompt = template.format(query=query, context=context)

            import inspect
            result = self.generation_client.generate_text(prompt=prompt, max_tokens=1500)
            if inspect.isawaitable(result):
                answer = await result
            else:
                answer = result

            return answer or "Failed to generate concept map."

        except Exception as e:
            logger.error(f"[ConceptMapTool] Error: {e}", exc_info=True)
            return f"Error creating concept map: {str(e)}"
