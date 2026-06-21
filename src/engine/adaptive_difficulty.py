"""
src/engine/adaptive_difficulty.py
──────────────────────────────────
Adaptive Difficulty Engine — يحدد صعوبة السؤال التالي بناءً على أداء الطالب.

المفهوم: Item Response Theory (IRT) مبسّطة
  - لو الطالب جاوب صح متتالية → صعّب
  - لو جاوب غلط → سهّل
  - بيحتسب "Mastery Score" لكل موضوع
  - بيقترح فترة المراجعة بناءً على Spaced Repetition

الفرق عن الـ adaptive الموجود:
  - الموجود: LLM يكتب توصيات نصية
  - الجديد: engine يقرر الصعوبة التالية رياضياً + يُرجع difficulty_level واضح
"""

import logging
import math
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger("uvicorn.error")


# ── Constants ─────────────────────────────────────────────────────────────────

DIFFICULTY_LEVELS = ["easy", "medium", "hard"]

# الوقت المثالي للمراجعة بناءً على مستوى الإتقان (Spaced Repetition)
REVIEW_INTERVALS = {
    "mastered":     timedelta(days=14),
    "learning":     timedelta(days=3),
    "struggling":   timedelta(hours=24),
    "new":          timedelta(hours=1),
}

# عدد الإجابات الصحيحة المتتالية للانتقال لمستوى أعلى
STREAK_TO_UPGRADE = 3
STREAK_TO_DOWNGRADE = -2  # سالب = إجابات غلط


# ── Data Classes ──────────────────────────────────────────────────────────────

@dataclass
class QuestionAttempt:
    """محاولة إجابة سؤال واحد."""
    question_id: str
    topic: str
    difficulty: str       # easy / medium / hard
    is_correct: bool
    time_taken_sec: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class TopicMastery:
    """مستوى إتقان موضوع معين."""
    topic: str
    mastery_score: float = 0.5    # 0.0 → 1.0
    current_difficulty: str = "medium"
    total_attempts: int = 0
    correct_attempts: int = 0
    streak: int = 0               # موجب = صح متتالية، سالب = غلط متتالية
    last_practiced: Optional[datetime] = None

    @property
    def accuracy(self) -> float:
        if self.total_attempts == 0:
            return 0.0
        return self.correct_attempts / self.total_attempts

    @property
    def mastery_level(self) -> str:
        if self.mastery_score >= 0.85:
            return "mastered"
        elif self.mastery_score >= 0.60:
            return "learning"
        elif self.mastery_score >= 0.30:
            return "struggling"
        return "new"

    @property
    def next_review_date(self) -> datetime:
        base = self.last_practiced or datetime.utcnow()
        interval = REVIEW_INTERVALS.get(self.mastery_level, timedelta(days=1))
        return base + interval

    def to_dict(self) -> dict:
        return {
            "topic": self.topic,
            "mastery_score": round(self.mastery_score, 3),
            "mastery_level": self.mastery_level,
            "current_difficulty": self.current_difficulty,
            "accuracy": round(self.accuracy, 3),
            "total_attempts": self.total_attempts,
            "correct_attempts": self.correct_attempts,
            "streak": self.streak,
            "next_review": self.next_review_date.isoformat(),
        }


# ── Adaptive Difficulty Engine ────────────────────────────────────────────────

class AdaptiveDifficultyEngine:
    """
    Engine يحدد الصعوبة التالية لكل طالب بناءً على تاريخه.

    يشتغل بدون LLM — حسابات رياضية بحتة:
      1. يحتسب Mastery Score لكل موضوع
      2. يحدد الـ difficulty التالية (IRT مبسّطة)
      3. يرجع next_review_date (Spaced Repetition)
    """

    def __init__(self):
        # student_id → {topic → TopicMastery}
        self._student_profiles: Dict[str, Dict[str, TopicMastery]] = {}

    # ── Public API ────────────────────────────────────────────────────────────

    def process_attempt(
        self,
        student_id: str,
        attempt: QuestionAttempt,
    ) -> TopicMastery:
        """
        سجّل إجابة جديدة وحدّث الـ mastery.
        Returns: الـ TopicMastery المحدّثة للموضوع.
        """
        profile = self._get_or_create_profile(student_id, attempt.topic)
        self._update_mastery(profile, attempt)
        self._update_difficulty(profile)

        logger.info(
            f"[Adaptive] Student {student_id} | Topic '{attempt.topic}' | "
            f"{'✅' if attempt.is_correct else '❌'} | "
            f"Score: {profile.mastery_score:.2f} | "
            f"Next: {profile.current_difficulty}"
        )
        return profile

    def get_next_question_params(
        self,
        student_id: str,
        topic: str,
    ) -> Dict:
        """
        اجيب الـ parameters للسؤال التالي للطالب في موضوع معين.

        Returns:
          {
            "difficulty": "easy" | "medium" | "hard",
            "mastery_level": "new" | "struggling" | "learning" | "mastered",
            "mastery_score": 0.72,
            "should_review": True,    # وقت المراجعة جه؟
            "reasoning": "3 إجابات صحيحة متتالية → مستوى أعلى"
          }
        """
        profile = self._get_or_create_profile(student_id, topic)
        should_review = (
            profile.last_practiced is not None
            and datetime.utcnow() >= profile.next_review_date
        )

        reasoning = self._get_reasoning(profile)

        return {
            "difficulty": profile.current_difficulty,
            "mastery_level": profile.mastery_level,
            "mastery_score": round(profile.mastery_score, 3),
            "should_review": should_review,
            "next_review_date": profile.next_review_date.isoformat(),
            "reasoning": reasoning,
        }

    def get_student_dashboard(self, student_id: str) -> Dict:
        """
        ملخص كامل لمستوى الطالب في كل المواضيع.
        يُستخدم في الـ API response.
        """
        student_data = self._student_profiles.get(student_id, {})
        if not student_data:
            return {
                "student_id": student_id,
                "topics": [],
                "overall_mastery": 0.0,
                "weakest_topics": [],
                "strongest_topics": [],
                "due_for_review": [],
            }

        topics_list = [t.to_dict() for t in student_data.values()]
        now = datetime.utcnow()

        # ترتيب حسب الـ mastery_score
        sorted_topics = sorted(topics_list, key=lambda t: t["mastery_score"])
        weakest   = [t["topic"] for t in sorted_topics[:3]]
        strongest = [t["topic"] for t in sorted_topics[-3:] if t["mastery_score"] > 0]

        # المواضيع اللي حان وقت مراجعتها
        due_for_review = [
            t["topic"] for t in topics_list
            if datetime.fromisoformat(t["next_review"]) <= now
        ]

        overall_mastery = (
            sum(t["mastery_score"] for t in topics_list) / len(topics_list)
            if topics_list else 0.0
        )

        return {
            "student_id": student_id,
            "overall_mastery": round(overall_mastery, 3),
            "overall_level": self._score_to_level(overall_mastery),
            "topics": topics_list,
            "weakest_topics": weakest,
            "strongest_topics": strongest,
            "due_for_review": due_for_review,
            "total_topics_practiced": len(topics_list),
        }

    def load_from_exam_results(
        self,
        student_id: str,
        exam_results: List[Dict],
        questions_map: Dict[str, Dict] = None,
    ) -> None:
        """
        بناء الـ profile من نتائج الامتحانات الموجودة في MongoDB.
        يُستخدم عند أول استدعاء للـ engine للطالب.
        """
        for result in exam_results:
            # كل نتيجة امتحان عندها weak_chunks وscores
            score_pct = result.get("percentage", 0)
            exam_id   = result.get("exam_id", "unknown")

            # لو عندنا per-question data — الأفضل
            for answer_data in result.get("answers", []):
                topic = answer_data.get("topic", exam_id)
                diff  = answer_data.get("difficulty", "medium")
                is_correct = answer_data.get("is_correct", False)

                attempt = QuestionAttempt(
                    question_id=answer_data.get("question_id", ""),
                    topic=topic,
                    difficulty=diff,
                    is_correct=is_correct,
                )
                self.process_attempt(student_id, attempt)

            # Fallback: لو مفيش per-question data، نستخدم الـ overall score
            if not result.get("answers"):
                topic = result.get("topic", exam_id)
                attempt = QuestionAttempt(
                    question_id=exam_id,
                    topic=topic,
                    difficulty="medium",
                    is_correct=score_pct >= 60,
                )
                self.process_attempt(student_id, attempt)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _get_or_create_profile(
        self, student_id: str, topic: str
    ) -> TopicMastery:
        if student_id not in self._student_profiles:
            self._student_profiles[student_id] = {}
        if topic not in self._student_profiles[student_id]:
            self._student_profiles[student_id][topic] = TopicMastery(topic=topic)
        return self._student_profiles[student_id][topic]

    def _update_mastery(self, profile: TopicMastery, attempt: QuestionAttempt) -> None:
        """
        تحديث الـ mastery score بعد إجابة.

        Formula (ELO-inspired):
          - صح: mastery += learning_rate × (1 - mastery)
          - غلط: mastery -= learning_rate × mastery
        """
        learning_rate = self._get_learning_rate(attempt.difficulty)

        if attempt.is_correct:
            profile.mastery_score += learning_rate * (1.0 - profile.mastery_score)
            profile.streak = max(0, profile.streak) + 1
            profile.correct_attempts += 1
        else:
            profile.mastery_score -= learning_rate * profile.mastery_score
            profile.streak = min(0, profile.streak) - 1

        # Clamp
        profile.mastery_score = max(0.0, min(1.0, profile.mastery_score))
        profile.total_attempts += 1
        profile.last_practiced = datetime.utcnow()

    def _update_difficulty(self, profile: TopicMastery) -> None:
        """
        تحديث الـ difficulty التالية بناءً على الـ streak.
        """
        current_idx = DIFFICULTY_LEVELS.index(profile.current_difficulty)

        if profile.streak >= STREAK_TO_UPGRADE:
            # صعّب لو فيه إجابات صح متتالية كافية
            new_idx = min(current_idx + 1, len(DIFFICULTY_LEVELS) - 1)
            if new_idx != current_idx:
                profile.streak = 0  # إعادة العداد بعد الترقية
        elif profile.streak <= STREAK_TO_DOWNGRADE:
            # سهّل لو فيه إجابات غلط متتالية
            new_idx = max(current_idx - 1, 0)
            if new_idx != current_idx:
                profile.streak = 0  # إعادة العداد بعد التخفيض
        else:
            new_idx = current_idx

        profile.current_difficulty = DIFFICULTY_LEVELS[new_idx]

    @staticmethod
    def _get_learning_rate(difficulty: str) -> float:
        """
        معدل التعلم يختلف حسب الصعوبة:
        - سؤال صعب صح → يرفع الـ mastery أكتر
        - سؤال سهل غلط → يخفض الـ mastery أكتر
        """
        return {"easy": 0.08, "medium": 0.12, "hard": 0.18}.get(difficulty, 0.12)

    @staticmethod
    def _get_reasoning(profile: TopicMastery) -> str:
        """تفسير إنساني لقرار الـ engine."""
        if profile.total_attempts == 0:
            return "موضوع جديد → سنبدأ بمستوى متوسط"

        if profile.streak >= STREAK_TO_UPGRADE:
            return f"{profile.streak} إجابات صحيحة متتالية → مستوى أعلى"
        elif profile.streak <= STREAK_TO_DOWNGRADE:
            return f"{abs(profile.streak)} إجابات خاطئة متتالية → مستوى أسهل"
        elif profile.mastery_level == "mastered":
            return f"إتقان عالي ({profile.mastery_score:.0%}) → الحفاظ على المستوى الصعب"
        elif profile.mastery_level == "struggling":
            return f"مستوى إتقان منخفض ({profile.mastery_score:.0%}) → التركيز على الأساسيات"
        else:
            return f"مستوى إتقان {profile.mastery_score:.0%} → الاستمرار على نفس المستوى"

    @staticmethod
    def _score_to_level(score: float) -> str:
        if score >= 0.85:
            return "متقدم"
        elif score >= 0.60:
            return "متوسط"
        elif score >= 0.30:
            return "مبتدئ"
        return "جديد"


# ── Singleton ─────────────────────────────────────────────────────────────────
_engine_instance: Optional[AdaptiveDifficultyEngine] = None


def get_adaptive_engine() -> AdaptiveDifficultyEngine:
    """Shared engine instance."""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = AdaptiveDifficultyEngine()
    return _engine_instance
