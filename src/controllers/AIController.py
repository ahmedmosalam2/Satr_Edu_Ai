import json
import re
import logging
from typing import List, Optional
from src.helpers.nlp_clients import get_generation_client, get_embedding_client, get_vectordb_client

logger = logging.getLogger("uvicorn.error")


EXAM_GENERATION_PROMPT = """<SYSTEM>You are a JSON API. You MUST respond with ONLY a valid JSON object. No explanations, no markdown, no extra text before or after the JSON.</SYSTEM>

Generate {num_questions} exam questions from the lecture content below.
Difficulty: {difficulty}
Question types to include: {question_types}

Respond with ONLY this JSON structure (no other text):
{{"questions": [{{
  "question_text": "question here",
  "question_type": "MCQ",
  "options": ["A) option1", "B) option2", "C) option3", "D) option4"],
  "correct_answer": "A",
  "explanation": "why correct",
  "difficulty": "medium"
}}]}}

LECTURE CONTENT:
{content}

JSON OUTPUT:"""


ESSAY_GRADING_PROMPT = """You are an expert educational grader.

QUESTION: {question}
MODEL ANSWER: {model_answer}
STUDENT ANSWER: {student_answer}

Grade the student's answer on a scale of 0 to {max_score}.

Evaluate based on:
1. Accuracy of key concepts (40%)
2. Completeness of the answer (30%)
3. Clarity of explanation (20%)
4. Extra relevant details (10%)

Return ONLY valid JSON:
{{
  "score": <number between 0 and {max_score}>,
  "feedback": "Detailed feedback explaining the grade...",
  "missing_points": ["Key point 1 that was missing", "Key point 2..."],
  "correct_points": ["What the student got right..."]
}}
"""


SUMMARIZATION_PROMPT = """You are an expert educational content summarizer.

Summarize the following lecture content in a clear, structured way that helps students understand and remember the key concepts.

LECTURE CONTENT:
{content}

Create a comprehensive summary that includes:
1. **Main Topic**: What this lecture is about
2. **Key Concepts**: The most important ideas (bullet points)
3. **Important Details**: Supporting information
4. **Key Takeaways**: What students must remember

Format your response in clear markdown.
Language: Match the language of the content (Arabic → Arabic summary, English → English summary).
"""


class AIController:
    """
    Central AI controller for:
    - Exam generation from lecture content
    - Lecture summarization
    - Essay grading with LLM
    """

    def __init__(self):
        self.generation_client = get_generation_client()

 
    def generate_exam_questions(
        self,
        content: str,
        num_questions: int = 10,
        difficulty: str = "mixed",       # easy / medium / hard / mixed
        question_types: Optional[List[str]] = None,
    ) -> dict:
        """
        Generate exam questions from lecture text using LLM.
        Returns structured dict with questions list.
        """
        if question_types is None:
            question_types = ["MCQ", "TRUE_FALSE", "ESSAY"]

        # Truncate content if too long (local LLMs are slow with large inputs)
        max_chars = 2000
        if len(content) > max_chars:
            content = content[:max_chars] + "\n\n[Content truncated...]"

        prompt = EXAM_GENERATION_PROMPT.format(
            num_questions=num_questions,
            difficulty=difficulty,
            question_types=", ".join(question_types),
            content=content,
        )

        try:
            raw_response = self.generation_client.generate_text(prompt=prompt)
            logger.info(f"LLM exam generation response length: {len(raw_response) if raw_response else 0}")

            if not raw_response:
                return {"questions": [], "error": "LLM returned empty response"}

            # Extract JSON from response (handle markdown code blocks)
            json_str = self._extract_json(raw_response)
            result = json.loads(json_str)

            # Validate structure
            if "questions" not in result:
                result = {"questions": result} if isinstance(result, list) else {"questions": []}

            logger.info(f"Generated {len(result['questions'])} questions")
            return result

        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error in exam generation: {e}")
            logger.error(f"Raw response: {raw_response[:500] if raw_response else 'None'}")
            return {"questions": [], "error": f"Failed to parse LLM response: {str(e)}", "raw": raw_response}

        except Exception as e:
            logger.error(f"Exam generation error: {e}")
            return {"questions": [], "error": str(e)}

    # ──────────────────────────────────────────────────────
    # SUMMARIZATION
    # ──────────────────────────────────────────────────────
    def summarize_content(self, content: str) -> str:
        """
        Summarize lecture content using LLM.
        Returns markdown-formatted summary.
        """
        max_chars = 8000
        if len(content) > max_chars:
            content = content[:max_chars] + "\n\n[Content truncated...]"

        prompt = SUMMARIZATION_PROMPT.format(content=content)

        try:
            summary = self.generation_client.generate_text(prompt=prompt)
            if not summary:
                return "لم يتمكن الـ AI من إنشاء ملخص لهذا المحتوى."
            return summary
        except Exception as e:
            logger.error(f"Summarization error: {e}")
            return f"خطأ في إنشاء الملخص: {str(e)}"

    # ──────────────────────────────────────────────────────
    # ESSAY GRADING
    # ──────────────────────────────────────────────────────
    def grade_essay(
        self,
        question: str,
        model_answer: str,
        student_answer: str,
        max_score: float = 10.0,
    ) -> dict:
        """
        Grade an essay answer using LLM comparison with model answer.
        Returns score, feedback, missing_points, correct_points.
        """
        prompt = ESSAY_GRADING_PROMPT.format(
            question=question,
            model_answer=model_answer,
            student_answer=student_answer,
            max_score=max_score,
        )

        try:
            raw_response = self.generation_client.generate_text(prompt=prompt)

            if not raw_response:
                return {
                    "score": 0,
                    "feedback": "Could not grade: LLM returned empty response",
                    "missing_points": [],
                    "correct_points": [],
                }

            json_str = self._extract_json(raw_response)
            result = json.loads(json_str)

            # Clamp score between 0 and max
            result["score"] = max(0, min(float(result.get("score", 0)), max_score))
            return result

        except json.JSONDecodeError as e:
            logger.error(f"Essay grading JSON parse error: {e}")
            return {
                "score": 0,
                "feedback": f"Grading failed: could not parse LLM response",
                "missing_points": [],
                "correct_points": [],
                "raw": raw_response if raw_response else "",
            }
        except Exception as e:
            logger.error(f"Essay grading error: {e}")
            return {
                "score": 0,
                "feedback": f"Grading error: {str(e)}",
                "missing_points": [],
                "correct_points": [],
            }

    # ──────────────────────────────────────────────────────
    # HELPERS
    # ──────────────────────────────────────────────────────
    def _extract_json(self, text: str) -> str:
        """Extract JSON from LLM response (handle markdown code blocks)."""
        text = text.strip()
        # Try markdown code fences first
        patterns = [
            r"```json\s*([\s\S]*?)\s*```",
            r"```\s*([\s\S]*?)\s*```",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()

        # Try to find JSON object/array directly
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return text[start:end + 1]

        # Fallback: LLM returned markdown text (not JSON)
        # Build a JSON from the raw markdown as a single text question
        logger.warning("LLM returned non-JSON response, using raw text fallback")
        safe = text.replace('"', "'").replace('\n', ' ')
        return f'{{"questions": [], "raw_text": "{safe[:1000]}", "error": "LLM returned text not JSON"}}'
