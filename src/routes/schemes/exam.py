from pydantic import BaseModel
from typing import List, Optional


# ─── Question representation in responses ─────────────────────────────────────

class QuestionResponse(BaseModel):
    question_id: str
    question_text: str
    question_type: str
    options: Optional[List[str]] = None    # MCQ only
    points: float


# ─── Exam Creation ─────────────────────────────────────────────────────────────

class ExamCreateRequest(BaseModel):
    project_id: str
    exam_title: str = "امتحان جديد"
    num_questions: int = 10
    difficulty: str = "mixed"             # easy | medium | hard | mixed
    question_types: List[str] = ["MCQ", "TRUE_FALSE", "ESSAY"]


class ExamCreateResponse(BaseModel):
    exam_id: str
    exam_title: str
    status: str                           # draft
    questions: List[QuestionResponse]
    message: str


# ─── Exam Info ─────────────────────────────────────────────────────────────────

class ExamInfoResponse(BaseModel):
    exam_id: str
    exam_title: str
    project_id: str
    teacher_id: str
    status: str
    difficulty: str
    num_questions: int
    questions: List[QuestionResponse]


# ─── Exam Approval ─────────────────────────────────────────────────────────────

class ApproveExamResponse(BaseModel):
    exam_id: str
    status: str
    message: str


# ─── Student Submission ────────────────────────────────────────────────────────

class AnswerItem(BaseModel):
    question_id: str
    student_answer: str


class SubmitExamRequest(BaseModel):
    answers: List[AnswerItem]


class AnswerFeedback(BaseModel):
    question_id: str
    question_text: str
    student_answer: str
    correct_answer: str
    is_correct: Optional[bool]
    score: float
    feedback: Optional[str] = None        # AI feedback for essays


class SubmitExamResponse(BaseModel):
    exam_id: str
    student_id: str
    total_score: float
    max_score: float
    percentage: float
    per_question: List[AnswerFeedback]
    weak_chunks: List[str]               # chunk_refs of wrong answers
    message: str


# ─── Results ──────────────────────────────────────────────────────────────────

class StudentResultResponse(BaseModel):
    student_id: str
    total_score: float
    max_score: float
    percentage: float
    weak_chunks: List[str]
    submitted_at: str
