"""
src/agent/core/intent_classifier.py
────────────────────────────────────
LLM-Based Intent Classifier — بديل احترافي للـ keyword matching.

بدل ما نفحص كلمات مفتاحية زي "فهمني" أو "اختبرني"،
بنسأل الـ LLM نفسه يفهم نية المستخدم من السياق الكامل للمحادثة.

الفايدة:
  - بيفهم السياق: "مش فاهم الجزء ده" → tutor (مش بس الكلمات المحددة)
  - بيدعم العربي والإنجليزي والعامية بشكل طبيعي
  - بيرجع confidence score عشان نقدر نتعامل مع الحالات الغامضة
  - بيشيل الـ entities المهمة من السؤال

Output format:
  {
    "intent": "research" | "tutor" | "quiz" | "greeting" | "off_topic" | "concept_map" | "python_scratchpad" | "socratic",
    "confidence": 0.0 - 1.0,
    "reasoning": "لماذا اخترت هذا الـ intent",
    "entities": ["موضوع 1", "موضوع 2"],
    "suggested_follow_up": "سؤال مقترح للمتابعة (اختياري)"
  }
"""

import json
import logging
import re
from typing import Dict, Any, Optional

logger = logging.getLogger("uvicorn.error")


# ── System Prompt ─────────────────────────────────────────────────────────────

INTENT_SYSTEM_PROMPT = """أنت محلل نوايا ذكي لنظام تعليمي.
مهمتك: تحليل رسالة المستخدم وتحديد نيته الحقيقية.

الأنواع الممكنة للنية:
- research          : يريد معلومة أو إجابة على سؤال تعليمي عام
- tutor             : يريد شرحاً مبسطاً أو لا يفهم موضوعاً
- quiz              : يريد أسئلة لاختبار فهمه أو مراجعة
- greeting          : تحية عامة أو حديث اجتماعي
- off_topic         : موضوع خارج عن النطاق التعليمي
- concept_map       : يريد خريطة مفاهيم أو خريطة ذهنية أو تمثيل مرئي للمعلومات (مثل: "ارسم خريطة مفاهيم")
- python_scratchpad : يريد تشغيل أو تجربة كود برمجي (بايثون) (مثل: "شغل الكود"، "run python")
- socratic          : يريد التعلم بطريقة الحوار السقراطي أو التوجيه التفاعلي بالأسئلة بدلاً من الإجابات المباشرة (مثل: "علمني بسقراط"، "طريقة سقراط"، "ناقشني")

قواعد مهمة:
1. حلّل النية الحقيقية وراء الكلمات، ليس الكلمات نفسها فقط.
2. "شغل كود بايثون" أو "جرب الكود" أو "sandbox" -> python_scratchpad
3. "خريطة ذهنية" أو "مخطط مفاهيم" أو "concept map" -> concept_map
4. "علمني بطريقة سقراط" أو "ناقشني وسلني" -> socratic
5. confidence عالي (0.8+) = واضح جداً، متوسط (0.5-0.8) = محتمل، منخفض (<0.5) = غامض

أجب بـ JSON فقط، بدون أي نص إضافي:
{
  "intent": "research|tutor|quiz|greeting|off_topic|concept_map|python_scratchpad|socratic",
  "confidence": 0.0-1.0,
  "reasoning": "سبب مختصر للاختيار بجملة واحدة",
  "entities": ["موضوع 1", "موضوع 2"]
}"""


class IntentClassifier:
    """
    LLM-based intent classifier.

    يستخدم الـ LLM نفسه لتحليل النية بدل الـ keyword matching.
    مع fallback للـ keyword matching لو الـ LLM فشل.
    """

    # Fallback keywords (لو الـ LLM مش متاح)
    _TUTOR_KW = [
        "فهمني", "اشرح", "وضحلي", "بسّط", "يعني ايه", "يعني إيه",
        "ازاي", "إزاي", "كيف", "لماذا", "ليه", "ليش",
        "مش فاهم", "مفهمتش", "اعد اشرح", "أعد شرح",
        "explain", "what is", "what are", "how does", "how do",
        "why", "clarify", "simplify", "teach me",
    ]
    _QUIZ_KW = [
        "اختبرني", "امتحني", "اسألني", "كويز", "مراجعة",
        "عايز أتأكد", "هل فهمت", "اختبار سريع",
        "quiz me", "test me", "ask me", "practice questions",
    ]
    _GREETING_KW = [
        "مرحبا", "أهلاً", "هاي", "سلام", "hello", "hi", "hey",
        "ازيك", "إزيك", "كيفك", "شلونك", "عامله ايه", "عامله إيه",
        "صباح الخير", "مساء الخير", "منور", "السلام عليكم", "ازيك يا بوت",
        "ازيك يا مساعد", "يا هلا", "هلا", "شخباركم", "شخبارك",
    ]
    _MAP_KW = [
        "خريطة مفاهيم", "خريطة ذهنية", "مخطط مفاهيم", "مخطط ذهني",
        "mindmap", "mind map", "concept map", "conceptmap",
        "ارسم خريطة", "ارسم مخطط", "شكل توضيحي",
    ]
    _SCRATCHPAD_KW = [
        "شغل الكود", "شغل كود", "تشغيل الكود", "نفذ الكود", "نفذ كود",
        "بايثون كود", "sandbox", "run python", "run code", "execute python",
        "compiler", "بيئة تجربة", "اسكراتش", "جرب الكود",
    ]
    _SOCRATIC_KW = [
        "سقراط", "سقراطي", "ناقشني", "طريقة سقراط", "socratic", "socrates",
        "اسألني وساعدني", "علمني بسقراط",
    ]

    def __init__(self, generation_client=None):
        self.generation_client = generation_client

    async def classify(
        self,
        query: str,
        conversation_context: str = "",
    ) -> Dict[str, Any]:
        """
        حدد نية المستخدم.

        Args:
            query: رسالة المستخدم
            conversation_context: آخر N رسائل من المحادثة (للسياق)

        Returns:
            dict: {intent, confidence, reasoning, entities}
        """
        # جرب LLM أولاً
        if self.generation_client:
            result = await self._classify_with_llm(query, conversation_context)
            if result:
                return result

        # Fallback: keyword matching
        return self._classify_with_keywords(query)

    async def _classify_with_llm(
        self, query: str, context: str = ""
    ) -> Optional[Dict[str, Any]]:
        """تصنيف باستخدام الـ LLM."""
        try:
            user_message = f"رسالة المستخدم: {query}"
            if context:
                user_message = f"سياق المحادثة:\n{context}\n\nرسالة المستخدم: {query}"

            full_prompt = f"{INTENT_SYSTEM_PROMPT}\n\n{user_message}"

            import inspect
            result = self.generation_client.generate_text(
                prompt=full_prompt, max_tokens=200
            )
            if inspect.isawaitable(result):
                raw = await result
            else:
                raw = result

            if not raw:
                return None

            # استخرج الـ JSON من الإجابة
            json_match = re.search(r"\{[\s\S]*\}", raw)
            if not json_match:
                return None

            data = json.loads(json_match.group())

            # تحقق من الحقول الأساسية
            intent = data.get("intent", "research")
            allowed_intents = {
                "research", "tutor", "quiz", "greeting", "off_topic",
                "concept_map", "python_scratchpad", "socratic"
            }
            if intent not in allowed_intents:
                intent = "research"

            return {
                "intent": intent,
                "confidence": float(data.get("confidence", 0.7)),
                "reasoning": data.get("reasoning", ""),
                "entities": data.get("entities", []),
                "method": "llm",
            }

        except Exception as e:
            logger.warning(f"[IntentClassifier] LLM classification failed: {e}")
            return None

    def _classify_with_keywords(self, query: str) -> Dict[str, Any]:
        """Fallback: keyword matching البسيط."""
        query_lower = query.lower().strip()

        for kw in self._GREETING_KW:
            if kw in query_lower and len(query.split()) < 5:
                return {"intent": "greeting", "confidence": 0.9, "reasoning": "greeting keyword", "entities": [], "method": "keyword"}

        for kw in self._MAP_KW:
            if kw in query_lower:
                return {"intent": "concept_map", "confidence": 0.85, "reasoning": f"keyword: {kw}", "entities": [], "method": "keyword"}

        for kw in self._SCRATCHPAD_KW:
            if kw in query_lower:
                return {"intent": "python_scratchpad", "confidence": 0.85, "reasoning": f"keyword: {kw}", "entities": [], "method": "keyword"}

        for kw in self._SOCRATIC_KW:
            if kw in query_lower:
                return {"intent": "socratic", "confidence": 0.85, "reasoning": f"keyword: {kw}", "entities": [], "method": "keyword"}

        for kw in self._TUTOR_KW:
            if kw in query_lower:
                return {"intent": "tutor", "confidence": 0.75, "reasoning": f"keyword: {kw}", "entities": [], "method": "keyword"}

        for kw in self._QUIZ_KW:
            if kw in query_lower:
                return {"intent": "quiz", "confidence": 0.75, "reasoning": f"keyword: {kw}", "entities": [], "method": "keyword"}

        return {"intent": "research", "confidence": 0.6, "reasoning": "default", "entities": [], "method": "keyword"}

    def _keyword_classify(self, query: str) -> Dict[str, Any]:
        """Alias for _classify_with_keywords to support tests."""
        return self._classify_with_keywords(query)
