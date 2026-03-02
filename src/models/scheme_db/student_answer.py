from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class StudentAnswer(BaseModel):
    answer_id: str = Field(..., min_length=1)
    exam_id: str
    student_id: str
    question_id: str
    student_answer: str                      # إجابة الطالب
    is_correct: Optional[bool] = None        # صح/غلط (None لو ESSAY)
    score: Optional[float] = None            # الدرجة على السؤال ده
    feedback: Optional[str] = None           # تعليق من الـ AI (للـ ESSAY)
    submitted_at: datetime = Field(default_factory=datetime.now)

    class Config:
        arbitrary_types_allowed = True

    @classmethod
    def get_indexes(cls):
        return [
            {
                "key": [("answer_id", 1)],
                "name": "answer_id_unique",
                "unique": True,
            },
            {
                "key": [("exam_id", 1), ("student_id", 1)],
                "name": "exam_student_index",
                "unique": False,
            },
        ]
