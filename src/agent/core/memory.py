"""
src/agent/core/memory.py
────────────────────────
Agent Memory — ذاكرة قصيرة وطويلة المدى.

Short-term: المحادثة الحالية
Long-term: ملف الطالب (نقاط القوة والضعف)
"""

import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

logger = logging.getLogger("uvicorn.error")


@dataclass
class StudentProfile:
    """ملف الطالب — الـ agent بيتعلم منه."""
    student_id: str = ""
    strong_topics: List[str] = field(default_factory=list)
    weak_topics: List[str] = field(default_factory=list)
    learning_style: str = "mixed"    # visual | textual | interactive | mixed
    level: str = "intermediate"      # beginner | intermediate | advanced
    language: str = "ar"
    total_interactions: int = 0
    avg_score: float = 0.0

    def to_context(self) -> str:
        """حوّل الملف لنص يفهمه الـ LLM."""
        parts = [f"Student Level: {self.level}"]
        if self.strong_topics:
            parts.append(f"Strong in: {', '.join(self.strong_topics[:5])}")
        if self.weak_topics:
            parts.append(f"Needs help with: {', '.join(self.weak_topics[:5])}")
        parts.append(f"Learning style: {self.learning_style}")
        if self.avg_score > 0:
            parts.append(f"Average score: {self.avg_score:.1f}%")
        return "\n".join(parts)


class AgentMemory:
    """
    ذاكرة الـ agent system.

    - short_term: رسائل المحادثة الحالية
    - working: معلومات مؤقتة بين الخطوات
    - student: ملف الطالب
    """

    def __init__(self, max_short_term: int = 20):
        self.short_term: List[Dict[str, str]] = []
        self.working: Dict[str, Any] = {}
        self.student: StudentProfile = StudentProfile()
        self._max_short_term = max_short_term

    def add_turn(self, role: str, content: str):
        """أضف دور في المحادثة."""
        self.short_term.append({"role": role, "content": content})
        if len(self.short_term) > self._max_short_term:
            self.short_term = self.short_term[-self._max_short_term:]

    def get_conversation_context(self, last_n: int = 6) -> str:
        """ارجع آخر N رسائل كنص."""
        recent = self.short_term[-last_n:]
        if not recent:
            return ""
        lines = []
        for msg in recent:
            prefix = "User" if msg["role"] == "user" else "Assistant"
            lines.append(f"{prefix}: {msg['content']}")
        return "\n".join(lines)

    def set_working(self, key: str, value: Any):
        """خزّن معلومة مؤقتة."""
        self.working[key] = value

    def get_working(self, key: str, default=None) -> Any:
        """ارجع معلومة مؤقتة."""
        return self.working.get(key, default)

    def update_student_from_results(self, exam_results: list):
        """حدّث ملف الطالب بناءً على نتائج الامتحانات."""
        if not exam_results:
            return

        self.student.total_interactions = len(exam_results)

        # Calculate average score
        scores = [r.get("percentage", 0) for r in exam_results]
        self.student.avg_score = sum(scores) / len(scores) if scores else 0

        # Determine level from average
        if self.student.avg_score >= 80:
            self.student.level = "advanced"
        elif self.student.avg_score >= 50:
            self.student.level = "intermediate"
        else:
            self.student.level = "beginner"

        # Collect weak chunks
        weak = set()
        for r in exam_results:
            for chunk in r.get("weak_chunks", []):
                weak.add(chunk)
        self.student.weak_topics = list(weak)[:10]

    def clear_working(self):
        """مسح الذاكرة المؤقتة."""
        self.working.clear()

    def clear_all(self):
        """مسح كل حاجة."""
        self.short_term.clear()
        self.working.clear()
        self.student = StudentProfile()
