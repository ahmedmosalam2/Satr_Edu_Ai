import json
import logging
from typing import List, Dict, Any
from src.helpers.nlp_clients import get_generation_client

logger = logging.getLogger("uvicorn.error")


STUDENT_ANALYSIS_PROMPT = """You are an expert educational performance analyst.

Below are the results of a student across multiple exams:

STUDENT RESULTS:
{results_json}

Analyze the student's performance and provide:
1. **Overall Assessment**: Strong or weak? Overall percentage trend?
2. **Strong Topics**: What topics/areas did the student do well in? (based on correct answers)
3. **Weak Topics**: What topics/areas does the student struggle with? (based on wrong answers and weak_chunks)
4. **Recommendations**: Specific actionable advice for improvement
5. **Risk Level**: (low / medium / high) — is this student at risk of failing?

Return ONLY valid JSON:
{{
  "overall_percentage": <average across all exams>,
  "risk_level": "low" | "medium" | "high",
  "strong_topics": ["topic 1", "topic 2"],
  "weak_topics": ["topic 1", "topic 2"],
  "recommendations": ["advice 1", "advice 2", "advice 3"],
  "summary": "One paragraph describing the student's overall performance"
}}

Language: Arabic if topics are in Arabic, English if in English.
"""


EXAM_ANALYSIS_PROMPT = """You are an expert educational performance analyst.

Below are all student results for a single exam:

EXAM RESULTS:
{results_json}

Analyze the exam-level performance and provide:
1. **Class Performance**: How did the class do overall?
2. **Hard Questions**: Which questions were hardest? (lowest correct rate)
3. **Easy Questions**: Which were easiest?
4. **Common Mistakes**: What patterns of errors do you see?
5. **Recommendations for Teacher**: What to re-teach or emphasize?

Return ONLY valid JSON:
{{
  "class_average_percentage": <number>,
  "pass_rate": <percentage who passed (>=50%)>,
  "top_student_percentage": <highest score>,
  "lowest_student_percentage": <lowest score>,
  "common_weak_chunks": ["chunk1", "chunk2"],
  "recommendations_for_teacher": ["tip 1", "tip 2"],
  "summary": "One paragraph summary of class performance"
}}
"""


class AnalyticsController:
    """
    AI-powered performance analytics.
    Analyzes student results across exams and generates insights using LLM.
    """

    def __init__(self):
        self.generation_client = get_generation_client()

    def analyze_student_performance(self, results: List[Dict[str, Any]]) -> dict:
        """
        Analyze a student's performance across multiple exam results.
        results: list of ExamResult dicts
        """
        if not results:
            return {"error": "No exam results found for this student"}

        # Calculate basic stats ourselves first
        percentages = [r.get("percentage", 0) for r in results]
        avg = round(sum(percentages) / len(percentages), 2) if percentages else 0

        # Collect all weak chunks across exams
        all_weak_chunks = []
        for r in results:
            all_weak_chunks.extend(r.get("weak_chunks", []))

        results_summary = {
            "total_exams": len(results),
            "average_percentage": avg,
            "exam_results": results
        }

        prompt = STUDENT_ANALYSIS_PROMPT.format(
            results_json=json.dumps(results_summary, ensure_ascii=False, default=str)
        )

        try:
            raw = self.generation_client.generate_text(prompt=prompt)
            if not raw:
                return self._fallback_student_analysis(avg, all_weak_chunks)

            analysis = json.loads(self._extract_json(raw))
            analysis["total_exams_taken"] = len(results)
            analysis["all_weak_chunks"] = list(set(all_weak_chunks))
            return analysis

        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"Student analytics LLM error: {e}")
            return self._fallback_student_analysis(avg, all_weak_chunks)

    def analyze_exam_performance(self, results: List[Dict[str, Any]], exam_title: str = "") -> dict:
        """
        Analyze all student results for a single exam.
        results: list of ExamResult dicts for the same exam
        """
        if not results:
            return {"error": "No results yet for this exam"}

        percentages = [r.get("percentage", 0) for r in results]
        avg = round(sum(percentages) / len(percentages), 2) if percentages else 0
        pass_count = sum(1 for p in percentages if p >= 50)

        all_weak_chunks = []
        for r in results:
            all_weak_chunks.extend(r.get("weak_chunks", []))

        # Count chunk frequency → most common = hardest topics
        from collections import Counter
        weak_chunk_counts = Counter(all_weak_chunks)

        results_summary = {
            "exam_title": exam_title,
            "total_students": len(results),
            "average_percentage": avg,
            "pass_count": pass_count,
            "results": results
        }

        prompt = EXAM_ANALYSIS_PROMPT.format(
            results_json=json.dumps(results_summary, ensure_ascii=False, default=str)
        )

        try:
            raw = self.generation_client.generate_text(prompt=prompt)
            if not raw:
                return self._fallback_exam_analysis(avg, pass_count, len(results), all_weak_chunks)

            analysis = json.loads(self._extract_json(raw))
            analysis["total_students"] = len(results)
            analysis["most_common_weak_chunks"] = [c for c, _ in weak_chunk_counts.most_common(5)]
            return analysis

        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"Exam analytics LLM error: {e}")
            return self._fallback_exam_analysis(avg, pass_count, len(results), all_weak_chunks)

    # ── Fallback (no LLM / LLM error) ────────────────────────────────────────

    def _fallback_student_analysis(self, avg: float, weak_chunks: list) -> dict:
        risk = "low" if avg >= 70 else ("medium" if avg >= 50 else "high")
        return {
            "overall_percentage": avg,
            "risk_level": risk,
            "strong_topics": [],
            "weak_topics": list(set(weak_chunks))[:5],
            "recommendations": ["راجع المحتوى المرتبط بأسئلة الأخطاء"],
            "summary": f"متوسط الطالب {avg}% عبر الامتحانات.",
            "all_weak_chunks": list(set(weak_chunks)),
        }

    def _fallback_exam_analysis(self, avg: float, pass_count: int, total: int, weak_chunks: list) -> dict:
        pass_rate = round((pass_count / total * 100), 2) if total else 0
        return {
            "class_average_percentage": avg,
            "pass_rate": pass_rate,
            "total_students": total,
            "common_weak_chunks": list(set(weak_chunks))[:5],
            "recommendations_for_teacher": ["راجع المواضيع الأكثر أخطاءً مع الطلاب"],
            "summary": f"متوسط الفصل {avg}% ونسبة النجاح {pass_rate}%.",
        }

    def _extract_json(self, text: str) -> str:
        import re
        text = text.strip()
        for pattern in [r"```json\s*([\s\S]*?)\s*```", r"```\s*([\s\S]*?)\s*```"]:
            m = re.search(pattern, text)
            if m:
                return m.group(1).strip()
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return text[start:end + 1]
        return text
