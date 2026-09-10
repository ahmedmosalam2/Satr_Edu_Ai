"""
src/agent/core/response_formatter.py
─────────────────────────────────────
Unified Response Formatter — كل الـ agents بيرجعوا نفس الـ format.

الهدف:
  - توحيد الـ API response من كل agents
  - إضافة metadata مفيدة (confidence, thinking_trace, sources)
  - تسهيل display في الـ frontend

Response Structure:
  {
    "answer":         str,            # الإجابة النهائية
    "agent_used":     str,            # اسم الـ agent
    "intent":         str,            # النية المكتشفة
    "confidence":     float,          # ثقة الإجابة (0-1)
    "thinking_trace": list,           # خطوات التفكير (ReAct steps)
    "sources":        list,           # المصادر المستخدمة
    "steps_count":    int,            # عدد الخطوات
    "follow_up_questions": list,      # أسئلة مقترحة للمتابعة
    "metadata":       dict,           # بيانات إضافية
  }
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

logger = logging.getLogger("uvicorn.error")


@dataclass
class AgentResponse:
    """الرسبونس الموحد من كل الـ agents."""

    # ── Core ────────────────────────────────────────────────────────────────
    answer: str
    agent_used: str = "researcher"
    intent: str = "research"

    # ── Quality Signals ──────────────────────────────────────────────────────
    confidence: float = 0.8             # 0.0 - 1.0
    confidence_label: str = "high"      # "high" | "medium" | "low"

    # ── Traceability ────────────────────────────────────────────────────────
    thinking_trace: List[Dict] = field(default_factory=list)
    sources: List[Dict] = field(default_factory=list)
    steps_count: int = 0
    actions: List[Dict] = field(default_factory=list)

    # ── Engagement ──────────────────────────────────────────────────────────
    follow_up_questions: List[str] = field(default_factory=list)

    # ── Conversation ────────────────────────────────────────────────────────
    conversation_id: Optional[str] = None
    is_new_conversation: bool = False
    student_level: str = "intermediate"

    # ── Additional ──────────────────────────────────────────────────────────
    auto_quiz: Optional[str] = None     # لو auto_quiz مفعّل
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "status": "success",
            "answer": self.answer,
            "agent_used": self.agent_used,
            "intent_detected": self.intent,
            "confidence": round(self.confidence, 2),
            "confidence_label": self.confidence_label,
            "thinking_trace": self.thinking_trace,
            "sources": self.sources,
            "steps_count": self.steps_count,
            "actions": self.actions,
            "follow_up_questions": self.follow_up_questions,
            "conversation_id": self.conversation_id,
            "is_new_conversation": self.is_new_conversation,
            "student_level": self.student_level,
            **({"auto_quiz": self.auto_quiz} if self.auto_quiz else {}),
            "metadata": self.metadata,
        }


class ResponseFormatter:
    """
    Builds AgentResponse from raw agent results + metadata.
    """

    @staticmethod
    def _confidence_label(score: float) -> str:
        if score >= 0.8:
            return "high"
        elif score >= 0.5:
            return "medium"
        return "low"

    @staticmethod
    def _build_thinking_trace(actions: list) -> List[Dict]:
        """حوّل AgentActions لـ thinking trace يفهمه الـ frontend."""
        trace = []
        for i, action in enumerate(actions):
            if hasattr(action, "tool_name"):
                trace.append({
                    "step": i + 1,
                    "type": "search" if "search" in action.tool_name else "tool",
                    "tool": action.tool_name,
                    "query": action.tool_input.get("query", action.tool_input.get("expression", "")),
                    "found": bool(action.tool_output and "No results" not in action.tool_output),
                    "reasoning": action.reasoning,
                })
            elif isinstance(action, dict):
                trace.append({
                    "step": i + 1,
                    "type": action.get("type", "act"),
                    "tool": action.get("tool", ""),
                    "query": str(action.get("input", "")),
                    "found": True,
                    "reasoning": action.get("reasoning", ""),
                })
        return trace

    @staticmethod
    def _estimate_confidence(answer: str, sources: list, actions: list) -> float:
        """
        تقدير ثقة الإجابة بناءً على:
        - هل فيه مصادر؟
        - هل الإجابة طويلة كفاية؟
        - هل الـ agent بحث مرات متعددة؟
        """
        score = 0.5  # Base score

        # وجود مصادر يزيد الثقة
        if sources:
            score += 0.2
            if len(sources) >= 3:
                score += 0.1

        # طول الإجابة يشير للجودة
        if answer and len(answer) > 200:
            score += 0.1
        if answer and len(answer) > 500:
            score += 0.05

        # لو الـ agent بحث أكتر من مرة = موضوع معقد بس بحث كويس
        if len(actions) >= 2:
            score += 0.05

        # لو الإجابة تحتوي على عبارات عدم يقين
        uncertainty_phrases = [
            "لا أعلم", "لا توجد معلومات", "غير متأكد",
            "i don't know", "no information", "uncertain", "not found"
        ]
        if any(p in (answer or "").lower() for p in uncertainty_phrases):
            score -= 0.3

        return min(max(score, 0.0), 1.0)

    @staticmethod
    async def _generate_follow_up(
        query: str,
        answer: str,
        generation_client,
        language: str = "ar",
    ) -> List[str]:
        """اقترح 3 أسئلة متابعة بناءً على الإجابة."""
        if not generation_client or not answer:
            return []

        try:
            if language == "ar":
                prompt = (
                    f"بناءً على هذا السؤال: {query}\n"
                    f"وهذه الإجابة: {answer[:300]}...\n\n"
                    "اقترح 3 أسئلة متابعة مفيدة وقصيرة (سطر واحد لكل سؤال).\n"
                    "أرجع الأسئلة فقط، سطر لكل سؤال، بدون ترقيم أو شرح."
                )
            else:
                prompt = (
                    f"Based on this question: {query}\n"
                    f"And this answer: {answer[:300]}...\n\n"
                    "Suggest 3 useful follow-up questions (one line each).\n"
                    "Return questions only, one per line, no numbering or explanation."
                )

            import inspect
            result = generation_client.generate_text(prompt=prompt, max_tokens=150)
            if inspect.isawaitable(result):
                raw = await result
            else:
                raw = result

            if not raw:
                return []

            lines = [l.strip() for l in raw.strip().splitlines() if l.strip()]
            # نظّف الأسطر من الترقيم
            questions = []
            for line in lines[:3]:
                line = line.lstrip("0123456789.-) ")
                if line and len(line) > 5:
                    questions.append(line)
            return questions

        except Exception as e:
            logger.debug(f"[Formatter] Follow-up generation failed: {e}")
            return []

    @classmethod
    async def format(
        cls,
        answer: str,
        agent_used: str,
        intent: str,
        actions: list = None,
        sources: list = None,
        steps_count: int = 0,
        conversation_id: str = None,
        is_new_conversation: bool = False,
        student_level: str = "intermediate",
        auto_quiz: str = None,
        generation_client=None,
        language: str = "ar",
        generate_follow_up: bool = True,
    ) -> AgentResponse:
        """
        Build a complete AgentResponse.
        """
        actions = actions or []
        sources = sources or []

        # Build thinking trace
        thinking_trace = cls._build_thinking_trace(actions)

        # Estimate confidence
        confidence = cls._estimate_confidence(answer, sources, actions)
        confidence_label = cls._confidence_label(confidence)

        # Generate follow-up questions (async, non-blocking on failure)
        follow_ups = []
        if generate_follow_up and generation_client and answer:
            follow_ups = await cls._generate_follow_up(
                query="",  # نحتاج الـ query هنا
                answer=answer,
                generation_client=generation_client,
                language=language,
            )

        # Serialize actions for JSON
        serialized_actions = []
        for a in actions:
            if hasattr(a, "tool_name"):
                serialized_actions.append({
                    "tool": a.tool_name,
                    "input": a.tool_input,
                    "output": (a.tool_output or "")[:300],
                    "reasoning": a.reasoning,
                })
            elif isinstance(a, dict):
                serialized_actions.append(a)

        return AgentResponse(
            answer=answer,
            agent_used=agent_used,
            intent=intent,
            confidence=confidence,
            confidence_label=confidence_label,
            thinking_trace=thinking_trace,
            sources=sources,
            steps_count=steps_count or len(actions),
            actions=serialized_actions,
            follow_up_questions=follow_ups,
            conversation_id=conversation_id,
            is_new_conversation=is_new_conversation,
            student_level=student_level,
            auto_quiz=auto_quiz,
        )
