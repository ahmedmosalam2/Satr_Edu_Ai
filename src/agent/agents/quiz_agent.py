"""
src/agent/agents/quiz_agent.py
──────────────────────────────
Quiz Agent — بيولد أسئلة سريعة بناءً على المحادثة.

الفرق عن exam generation العادي:
  - بيولد 2-3 أسئلة سريعة (مش امتحان كامل)
  - بناءً على اللي اتشرح في المحادثة
  - بيتأكد إن الطالب فهم
"""

import json
import logging
from src.agent.base_agent import BaseAgent, AgentResult, AgentAction, BaseTool
from typing import List

logger = logging.getLogger("uvicorn.error")


QUIZ_PROMPT = """أنت مساعد تعليمي. بناءً على المحتوى التالي، اعمل {num_questions} أسئلة سريعة لاختبار فهم الطالب.

المحتوى:
{context}

السؤال الأصلي اللي الطالب سأله: {query}

أنشئ الأسئلة بصيغة JSON فقط:
{{"quiz": [
  {{"question": "...", "options": ["A) ...", "B) ...", "C) ...", "D) ..."], "correct": "A", "hint": "تلميح بسيط"}},
]}}

JSON:"""


class QuizAgent(BaseAgent):
    """Agent متخصص في توليد أسئلة سريعة."""

    def __init__(self, generation_client, tools: List[BaseTool],
                 language: str = "ar", num_questions: int = 3):
        self.generation_client = generation_client
        self.tools = {tool.name: tool for tool in tools}
        self.language = language
        self.num_questions = num_questions

    async def run(self, query: str, **kwargs) -> AgentResult:
        actions = []
        context_parts = []

        # Search for relevant content
        search_tool = self.tools.get("knowledge_search")
        if search_tool:
            action = AgentAction(
                tool_name="knowledge_search",
                tool_input={"query": query},
                reasoning=f"Finding content to quiz on: {query}",
            )
            try:
                result = await search_tool.execute(query=query, limit=3)
                action.tool_output = result
                context_parts.append(result)
            except Exception as e:
                action.tool_output = f"Error: {e}"
            actions.append(action)

        context = "\n".join(context_parts) if context_parts else query

        prompt = QUIZ_PROMPT.format(
            num_questions=self.num_questions,
            context=context,
            query=query,
        )

        import inspect
        result = self.generation_client.generate_text(prompt=prompt, max_tokens=1200)
        if inspect.isawaitable(result):
            raw = await result
        else:
            raw = result

        # Try to parse JSON quiz
        quiz_data = None
        if raw:
            try:
                import re
                # Extract JSON from response
                json_match = re.search(r'\{[\s\S]*\}', raw)
                if json_match:
                    quiz_data = json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        answer = raw or ""
        if quiz_data:
            answer = json.dumps(quiz_data, ensure_ascii=False, indent=2)

        return AgentResult(
            answer=answer,
            actions=actions,
            steps_count=len(actions),
            sources=[{"type": "quiz", "parsed": quiz_data is not None}],
        )
