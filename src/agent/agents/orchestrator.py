"""
src/agent/agents/orchestrator.py
────────────────────────────────
Orchestrator — المنسق بين الـ agents.

بيقرر مين يجاوب بناءً على نوع السؤال:
  - سؤال معلومة → Research Agent (RAGAgent الموجود)
  - "فهمني" / "اشرح" → Tutor Agent
  - "اختبرني" / "quiz" → Quiz Agent
  - حساب → Calculator (داخل RAGAgent)

Flow:
  User Query → Orchestrator → يحلل → يختار Agent → ينفذ → يرجع
"""

import re
import logging
from typing import List, Optional
from dataclasses import dataclass, field

from src.agent.base_agent import BaseAgent, AgentResult, BaseTool
from src.agent.core.message_bus import MessageBus, MessageType
from src.agent.core.memory import AgentMemory

logger = logging.getLogger("uvicorn.error")


# ── Intent Detection Patterns ─────────────────────────────────────────────────

TUTOR_PATTERNS_AR = [
    "فهمني", "اشرح", "وضحلي", "بسّط", "يعني ايه", "يعني إيه",
    "ازاي", "إزاي", "كيف", "لماذا", "ليه", "ليش",
    "مش فاهم", "مفهمتش", "اعد اشرح", "أعد شرح",
]
TUTOR_PATTERNS_EN = [
    "explain", "what is", "what are", "how does", "how do",
    "why", "clarify", "simplify", "break down", "teach me",
    "i don't understand", "can you explain",
]

QUIZ_PATTERNS_AR = [
    "اختبرني", "امتحني", "اسألني", "سؤال", "كويز",
    "عايز أتأكد", "هل فهمت", "اختبار سريع",
]
QUIZ_PATTERNS_EN = [
    "quiz me", "test me", "ask me", "quick test",
    "check my understanding", "practice questions",
]


@dataclass
class OrchestratorResult:
    """نتيجة الـ Orchestrator مع metadata عن القرار."""
    answer: str
    agent_used: str
    intent: str
    steps_count: int = 0
    actions: list = field(default_factory=list)
    sources: list = field(default_factory=list)
    conversation_log: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "answer": self.answer,
            "agent_used": self.agent_used,
            "intent": self.intent,
            "steps_count": self.steps_count,
            "actions": self.actions,
            "sources": self.sources,
            "conversation_log": self.conversation_log,
        }


class Orchestrator:
    """
    المنسق — بيقرر أي agent يشتغل.

    Agents:
      - researcher: RAGAgent — بحث وإجابة (الموجود)
      - tutor: TutorAgent — شرح مبسط
      - quiz: QuizAgent — أسئلة سريعة
    """

    def __init__(
        self,
        generation_client,
        tools: List[BaseTool],
        language: str = "ar",
        student_level: str = "intermediate",
        student_context: str = "",
    ):
        self.generation_client = generation_client
        self.tools = tools
        self.language = language
        self.student_level = student_level
        self.student_context = student_context

        # Infrastructure
        self.bus = MessageBus()
        self.memory = AgentMemory()

    def _detect_intent(self, query: str) -> str:
        """كشف نية المستخدم من السؤال."""
        query_lower = query.lower().strip()

        # Check tutor patterns
        for pattern in TUTOR_PATTERNS_AR + TUTOR_PATTERNS_EN:
            if pattern in query_lower:
                return "tutor"

        # Check quiz patterns
        for pattern in QUIZ_PATTERNS_AR + QUIZ_PATTERNS_EN:
            if pattern in query_lower:
                return "quiz"

        # Default: research
        return "research"

    async def run(self, query: str, **kwargs) -> OrchestratorResult:
        """تنفيذ الـ pipeline: detect intent → route → execute → return."""

        intent = self._detect_intent(query)
        logger.info(f"[Orchestrator] Intent: {intent} | Query: {query[:60]}")

        # Log to message bus
        self.bus.send(
            from_agent="user",
            to_agent="orchestrator",
            content=query,
            msg_type=MessageType.REQUEST.value,
        )

        # Save to memory
        self.memory.add_turn("user", query)

        # Route to the right agent
        if intent == "tutor":
            result = await self._run_tutor(query)
        elif intent == "quiz":
            result = await self._run_quiz(query)
        else:
            result = await self._run_researcher(query)

        # Log the response
        self.bus.send(
            from_agent=result.agent_used,
            to_agent="user",
            content=result.answer[:200] if result.answer else "",
            msg_type=MessageType.RESPONSE.value,
        )

        self.memory.add_turn("assistant", result.answer or "")

        # Attach conversation log
        result.conversation_log = self.bus.get_conversation_log()

        return result

    async def _run_researcher(self, query: str) -> OrchestratorResult:
        """تشغيل الـ RAG Agent (بحث + إجابة)."""
        from src.agent.rag_agent import RAGAgent

        agent = RAGAgent(
            generation_client=self.generation_client,
            tools=self.tools,
            language=self.language,
        )

        self.bus.send("orchestrator", "researcher", query, MessageType.REQUEST.value)

        result = await agent.run(query=query)

        return OrchestratorResult(
            answer=result.answer,
            agent_used="researcher",
            intent="research",
            steps_count=result.steps_count,
            actions=result.to_dict()["actions"],
            sources=result.sources,
        )

    async def _run_tutor(self, query: str) -> OrchestratorResult:
        """تشغيل الـ Tutor Agent (شرح مبسط)."""
        from src.agent.agents.tutor_agent import TutorAgent

        agent = TutorAgent(
            generation_client=self.generation_client,
            tools=self.tools,
            language=self.language,
            student_level=self.student_level,
            student_context=self.student_context,
        )

        self.bus.send("orchestrator", "tutor", query, MessageType.REQUEST.value)

        result = await agent.run(query=query)

        return OrchestratorResult(
            answer=result.answer,
            agent_used="tutor",
            intent="tutor",
            steps_count=result.steps_count,
            actions=result.to_dict()["actions"],
        )

    async def _run_quiz(self, query: str) -> OrchestratorResult:
        """تشغيل الـ Quiz Agent (أسئلة سريعة)."""
        from src.agent.agents.quiz_agent import QuizAgent

        agent = QuizAgent(
            generation_client=self.generation_client,
            tools=self.tools,
            language=self.language,
        )

        self.bus.send("orchestrator", "quiz", query, MessageType.REQUEST.value)

        result = await agent.run(query=query)

        return OrchestratorResult(
            answer=result.answer,
            agent_used="quiz",
            intent="quiz",
            steps_count=result.steps_count,
            actions=result.to_dict()["actions"],
            sources=result.sources,
        )
