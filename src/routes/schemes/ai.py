from pydantic import BaseModel
from typing import List, Optional


# ─── Exam Generation ──────────────────────────────────────────

class ExamGenerateRequest(BaseModel):
    content: Optional[str] = None       # جlب النص مباشرة OR
    project_id: Optional[str] = None    # جلب من Vector DB/chunks
    num_questions: int = 10
    difficulty: str = "mixed"           # easy / medium / hard / mixed
    question_types: List[str] = ["MCQ", "TRUE_FALSE", "ESSAY"]

class ExamGenerateFromChunksRequest(BaseModel):
    project_id: str
    num_questions: int = 10
    difficulty: str = "mixed"
    question_types: List[str] = ["MCQ", "TRUE_FALSE", "ESSAY"]


# ─── Summarization ────────────────────────────────────────────

class SummarizeRequest(BaseModel):
    content: Optional[str] = None       # نص مباشر OR
    project_id: Optional[str] = None    # من الـ chunks في MongoDB


# ─── Essay Grading ────────────────────────────────────────────

class GradeEssayRequest(BaseModel):
    question: str
    model_answer: str
    student_answer: str
    max_score: float = 10.0


# ─── OCR ──────────────────────────────────────────────────────

class OCRTextRequest(BaseModel):
    text: str   # Raw text to process (if already extracted)
