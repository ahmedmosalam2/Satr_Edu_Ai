"""
src/agent/agents/tutor_agent.py
───────────────────────────────
Tutor Agent — بيشرح المفاهيم بأسلوب مبسط حسب مستوى الطالب.

مختلف عن الـ RAG العادي:
  - بياخد في الاعتبار مستوى الطالب (beginner/intermediate/advanced)
  - بيدي أمثلة وتشبيهات
  - بيشرح خطوة بخطوة
"""

import logging
from src.agent.base_agent import BaseAgent, AgentResult, AgentAction, BaseTool
from typing import List

logger = logging.getLogger("uvicorn.error")


TUTOR_PROMPT_AR = """أنت معلم خبير ودود. اسمك "المعلم الذكي".

مستوى الطالب: {level}
{student_context}

استخدم المعلومات التالية من المحتوى التعليمي:
{context}

قواعد مهمة:
1. اشرح بأسلوب بسيط يناسب مستوى الطالب.
2. استخدم أمثلة وتشبيهات من الحياة اليومية.
3. قسّم الشرح لخطوات واضحة.
4. إذا كان الطالب مبتدئ: ابدأ من الأساسيات.
5. إذا كان الطالب متقدم: ركز على التفاصيل العميقة.
6. إذا كانت المعلومات المتاحة فارغة أو غير متوفرة (مثل "لا توجد معلومات متاحة" أو "No relevant documents found")، أخبر الطالب بوضوح ولطف أنه لا توجد مستندات أو ملفات تعليمية مرفوعة في قاعدة معرفة هذا الكورس حالياً، واطلب منه رفع مستندات تعليمية (مثل كتب أو محاضرات PDF) عبر زر المرفقات لتتمكن من شرحها بدقة، وتجنب اختراع أو شرح مواضيع عامة خارج سياق المنهج.
7. أجب بالعربي.

السؤال: {query}

اشرح بوضوح:"""

TUTOR_PROMPT_EN = """You are an expert, friendly tutor. Your name is "Smart Tutor".

Student level: {level}
{student_context}

Use the following educational content:
{context}

Rules:
1. Explain in a simple way appropriate to the student's level.
2. Use real-life examples and analogies.
3. Break the explanation into clear steps.
4. If beginner: start from basics.
5. If advanced: focus on deep details.
6. If the educational content is empty or states that no documents are found (e.g. "No relevant documents found" or "لا توجد معلومات متاحة"), state clearly and politely that no educational documents have been uploaded to this course's knowledge base yet, and ask the user to upload PDF files or slides using the attachment button so that you can explain them accurately. Do not make up general explanations.

Question: {query}

Clear explanation:"""


class TutorAgent(BaseAgent):
    """Agent متخصص في شرح المفاهيم."""

    def __init__(self, generation_client, tools: List[BaseTool],
                 language: str = "ar", student_level: str = "intermediate",
                 student_context: str = ""):
        self.generation_client = generation_client
        self.tools = {tool.name: tool for tool in tools}
        self.language = language
        self.student_level = student_level
        self.student_context = student_context

    async def run(self, query: str, chat_history: list = None, **kwargs) -> AgentResult:
        actions = []
        context_parts = []

        # Step 1: Search knowledge base
        search_tool = self.tools.get("knowledge_search")
        if search_tool:
            action = AgentAction(
                tool_name="knowledge_search",
                tool_input={"query": query},
                reasoning=f"Searching for: {query}",
            )
            try:
                result = await search_tool.execute(query=query, limit=5)
                action.tool_output = result
                context_parts.append(result)
            except Exception as e:
                action.tool_output = f"Error: {e}"
            actions.append(action)

        context = "\n".join(context_parts) if context_parts else "لا توجد معلومات متاحة."

        template = TUTOR_PROMPT_AR if self.language == "ar" else TUTOR_PROMPT_EN
        prompt = template.format(
            level=self.student_level,
            student_context=self.student_context,
            context=context,
            query=query,
        )

        import inspect
        result = self.generation_client.generate_text(
            prompt=prompt,
            chat_history=chat_history,
            max_tokens=1500
        )
        if inspect.isawaitable(result):
            answer = await result
        else:
            answer = result

        return AgentResult(
            answer=answer or "",
            actions=actions,
            steps_count=len(actions),
        )
