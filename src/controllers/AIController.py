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

STRICT RULES you MUST follow:
1. DISTRIBUTE correct answers across A, B, C, D — do NOT put all correct answers as "A".
   Example for 4 questions: first→"B", second→"D", third→"A", fourth→"C".
2. The explanation MUST start with the correct_answer letter and justify WHY it is right, then briefly why the others are wrong.
   Example: "B is correct because ... A is wrong because ... C is wrong because ..."
   The letter at the start of the explanation MUST match correct_answer exactly.
3. Make options plausible — wrong options should seem reasonable, not obviously fake.
4. Vary question depth: include recall, comprehension, AND application questions.
5. correct_answer must be ONLY the letter: "A", "B", "C", or "D" (no extra text).
6. NEVER ask about ISBN numbers, page numbers, copyright dates, or any publication metadata.
   Focus ONLY on the educational content — concepts, ideas, events, people's roles.
7. If question_type is "MCQ" or "TRUE_FALSE", you MUST include options. If question_type is "Essay", do NOT include options (set options to null).

Respond with ONLY this JSON structure (no other text):
{{"questions": [{{
  "question_text": "question here",
  "question_type": "MCQ",
  "options": ["A) option1", "B) option2", "C) option3", "D) option4"],
  "correct_answer": "B",
  "explanation": "B is correct because ... A is wrong because ... C is wrong because ...",
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

 
    async def generate_exam_questions(
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
        max_chars = 3000
        if len(content) > max_chars:
            content = content[:max_chars] + "\n\n[Content truncated...]"

        prompt = EXAM_GENERATION_PROMPT.format(
            num_questions=num_questions,
            difficulty=difficulty,
            question_types=", ".join(question_types),
            content=content,
        )

        try:
            # كل سؤال يحتاج ~400 token (question + options + explanation)
            # نضيف 500 token buffer للـ JSON structure والـ prompt overhead
            tokens_needed = max(2000, num_questions * 400 + 500)
            raw_response = await self.generation_client.generate_text(
                prompt=prompt,
                max_tokens=tokens_needed,
                temperature=0.7,   # عشوائية عالية = أسئلة مختلفة كل مرة
            )
            logger.info(f"LLM exam generation response length: {len(raw_response) if raw_response else 0}")

            if not raw_response:
                return {"questions": [], "error": "LLM returned empty response"}

            # Extract JSON from response (handle markdown code blocks)
            json_str = self._extract_json(raw_response)
            result = json.loads(json_str)

            # Validate structure
            if "questions" not in result:
                result = {"questions": result} if isinstance(result, list) else {"questions": []}

            # Post-generation validation: remove bad questions, warn on bias
            result["questions"] = self._validate_questions(result["questions"])

            logger.info(f"Generated {len(result['questions'])} questions (after validation)")
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
    async def summarize_content(self, content: str) -> str:
        """
        Summarize lecture content using LLM.
        Returns markdown-formatted summary.
        """
        max_chars = 8000
        if len(content) > max_chars:
            content = content[:max_chars] + "\n\n[Content truncated...]"

        prompt = SUMMARIZATION_PROMPT.format(content=content)

        try:
            summary = await self.generation_client.generate_text(
                prompt=prompt,
                max_tokens=1500,
            )
            if not summary:
                return "لم يتمكن الـ AI من إنشاء ملخص لهذا المحتوى."
            return summary
        except Exception as e:
            logger.error(f"Summarization error: {e}")
            return f"خطأ في إنشاء الملخص: {str(e)}"

    # ──────────────────────────────────────────────────────
    # ESSAY GRADING
    # ──────────────────────────────────────────────────────
    async def grade_essay(
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
            raw_response = await self.generation_client.generate_text(
                prompt=prompt,
                max_tokens=800,
            )

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
    def _validate_questions(self, questions: list) -> list:
        """
        Post-generation validation:
        1. Remove questions where correct_answer letter is not present in options.
        2. Warn if all correct answers are the same letter (A-bias).
        """
        valid = []
        answer_letters = []

        for q in questions:
            raw_answer = q.get("correct_answer")
            answer = str(raw_answer).strip() if raw_answer is not None else ""
            
            options = q.get("options") or []
            question_text = q.get("question_text", "")
            q_type = q.get("question_type", "").upper()

            if not answer or not question_text:
                logger.warning("Skipping question with missing answer or text")
                continue

            # Skip option validation for ESSAY questions since they don't have options
            if q_type == "ESSAY":
                valid.append(q)
                continue

            # Check correct_answer letter appears in one of the options
            answer_upper = answer.upper()
            answer_in_options = any(
                opt.strip().upper().startswith(answer_upper) for opt in options
            )

            if options and not answer_in_options:
                logger.warning(
                    f"Dropping question — correct_answer '{answer}' not found in options: {options}"
                )
                continue

            answer_letters.append(answer_upper)
            valid.append(q)

        # Detect A-bias: warn if all answers are the same letter
        if answer_letters and len(set(answer_letters)) == 1:
            logger.warning(
                f"Answer bias detected: all {len(answer_letters)} questions have correct_answer='{answer_letters[0]}'"
            )

        logger.info(
            f"Validation: {len(valid)}/{len(questions)} questions passed. "
            f"Answer distribution: {dict((l, answer_letters.count(l)) for l in set(answer_letters))}"
        )
        return valid

    def _extract_json(self, text: str) -> str:
        """Extract JSON from LLM response (handle markdown code blocks and truncation)."""
        text = text.strip()

        # 1. Try markdown code fences first
        patterns = [
            r"```json\s*([\s\S]*?)\s*```",
            r"```\s*([\s\S]*?)\s*```",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                candidate = match.group(1).strip()
                try:
                    json.loads(candidate)
                    return candidate
                except json.JSONDecodeError:
                    candidate = self._repair_truncated_json(candidate)
                    if candidate:
                        return candidate

        # 2. Find the JSON object boundaries
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            candidate = text[start:end + 1]
            try:
                json.loads(candidate)
                return candidate
            except json.JSONDecodeError:
                # JSON is truncated — try to repair it
                repaired = self._repair_truncated_json(text[start:])
                if repaired:
                    return repaired

        # 3. Fallback: LLM returned non-JSON text
        logger.warning("LLM returned non-JSON response, using raw text fallback")
        safe = text.replace('"', "'").replace('\n', ' ')
        return f'{{"questions": [], "raw_text": "{safe[:1000]}", "error": "LLM returned text not JSON"}}'

    def _repair_truncated_json(self, text: str) -> Optional[str]:
        """
        Try to salvage complete question objects from a truncated JSON array.
        Extracts all fully-formed question objects even if the outer structure is cut off.
        """
        try:
            # Find all complete question objects using regex
            # A question object starts with { and ends with } on a balanced basis
            question_pattern = re.compile(
                r'\{\s*"question_text"[^{}]*(?:\{[^{}]*\}[^{}]*)*\}',
                re.DOTALL
            )
            matches = question_pattern.findall(text)
            valid_questions = []
            for m in matches:
                try:
                    obj = json.loads(m)
                    # Must have at minimum question_text and correct_answer
                    if "question_text" in obj and "correct_answer" in obj:
                        valid_questions.append(obj)
                except json.JSONDecodeError:
                    continue

            if valid_questions:
                logger.warning(
                    f"Repaired truncated JSON: recovered {len(valid_questions)} complete questions"
                )
                return json.dumps({"questions": valid_questions})
        except Exception as e:
            logger.warning(f"JSON repair failed: {e}")
        return None
