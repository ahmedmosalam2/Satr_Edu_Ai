"""
src/agent/agents/socratic_agent.py
───────────────────────────────────
Socratic Agent — العميل السقراطي الذكي.

بدل من إعطاء الإجابات المباشرة، يتفاعل مع الطالب بطرح أسئلة موجهة 
لتوجيهه نحو الحل الصحيح، مما يعزز الفهم العميق والنشط.
"""

import logging
import inspect
from src.agent.base_agent import BaseAgent, AgentResult, AgentAction, BaseTool
from typing import List

logger = logging.getLogger("uvicorn.error")

SOCRATIC_PROMPT_AR = """أنت "المعلم سقراط" - عميل تعليمي ذكي تفاعلي.
مهمتك ليست إعطاء الإجابة مباشرة، بل توجيه الطالب ليكتشف الإجابة بنفسه باستخدام الطريقة السقراطية (الحوار والأسئلة الموجهة).

مستوى الطالب: {level}
{student_context}

استخدم المعلومات التالية كمصدر معرفي لك:
{context}

قواعد السلوك السقراطي:
1. لا تعطي الإجابة النهائية مباشرة أبداً.
2. اطرح سؤالاً واحداً قصيراً وموجهاً في كل مرة يدفع الطالب للتفكير في الخطوة التالية.
3. قسّم المفهوم الصعب إلى أجزاء صغيرة جداً.
4. إذا أجاب الطالب إجابة صحيحة أو جزئية، امتدحه واطرح سؤالاً يربطه بالخطوة التالية.
5. إذا كان الطالب مخطئاً تماماً أو تائهاً، لا تقل له "أنت مخطئ"، بل اطرح سؤالاً يبسط المشكلة أو يعطيه تلميحاً خفياً.
6. إذا كانت المعلومات المتاحة فارغة أو غير متوفرة (مثل "لا توجد معلومات قائمة" أو "No specific course content retrieved" أو "No relevant documents found")، فأخبر الطالب بلطف وبطريقة تفاعلية سقراطية أنه لا توجد مستندات مرفوعة في قاعدة معرفة الكورس حالياً، واطلب منه استخدام زر المرفقات لرفع ملفات (مثل كتب أو محاضرات PDF) لتتمكن من حواره ومساعدته فيها.
7. أجب باللغة العربية بأسلوب ودود وداعم.

السياق الحالي للمحادثة ورسالة الطالب الأخيرة: {query}

اكتب ردك السقراطي الآن (تذكر: اطرح سؤالاً تفاعلياً واحداً في النهاية):"""

SOCRATIC_PROMPT_EN = """You are "Socrates the Tutor" - an interactive, intelligent agent.
Your mission is NOT to give direct answers, but to guide the student to discover the answer themselves using Socratic dialogue.

Student Level: {level}
{student_context}

Use this source knowledge to guide you:
{context}

Socratic Rules:
1. NEVER give the final direct answer.
2. Ask exactly one short, guiding question at a time to lead the student to the next step.
3. Break complex concepts into tiny, digestible pieces.
4. Validate partial correct answers, then ask the next leading question.
5. If the student is lost or wrong, don't say "you are wrong"; ask a simpler question or provide a subtle hint.
6. If the source knowledge is empty or unavailable (e.g. "No specific course content retrieved" or "No relevant documents found"), politely guide the user to upload PDF slides or study materials using the attachment button so you can discuss it together.
7. Reply friendly in English.

Current conversation / user message: {query}

Your Socratic response (ending with one interactive question):"""


class SocraticAgent(BaseAgent):
    """
    Socratic Tutor Agent.
    """

    def __init__(self, generation_client, tools: List[BaseTool],
                 language: str = "ar", student_level: str = "intermediate",
                 student_context: str = ""):
        self.generation_client = generation_client
        self.tools = {tool.name: tool for tool in tools}
        self.language = language
        self.student_level = student_level
        self.student_context = student_context

    async def run(self, query: str, **kwargs) -> AgentResult:
        actions = []
        context_parts = []

        # Step 1: Query knowledge base to get content context for Socrates to draw from
        search_tool = self.tools.get("knowledge_search")
        if search_tool:
            action = AgentAction(
                tool_name="knowledge_search",
                tool_input={"query": query},
                reasoning=f"Searching background information for Socrates to guide the student: {query}",
            )
            try:
                result = await search_tool.execute(query=query, limit=4)
                action.tool_output = result
                context_parts.append(result)
            except Exception as e:
                action.tool_output = f"Error: {e}"
            actions.append(action)

        context = "\n".join(context_parts) if context_parts else "No specific course content retrieved."

        # Step 2: Format Socratic dialogue
        template = SOCRATIC_PROMPT_AR if self.language == "ar" else SOCRATIC_PROMPT_EN
        prompt = template.format(
            level=self.student_level,
            student_context=self.student_context,
            context=context,
            query=query,
        )

        result = self.generation_client.generate_text(prompt=prompt, max_tokens=1000)
        if inspect.isawaitable(result):
            answer = await result
        else:
            answer = result

        return AgentResult(
            answer=answer or "",
            actions=actions,
            steps_count=len(actions),
        )
