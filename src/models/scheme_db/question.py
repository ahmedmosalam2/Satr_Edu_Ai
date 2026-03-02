from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from src.models.enums.QuestionType import QuestionType


class Question(BaseModel):
    question_id: str = Field(..., min_length=1)
    exam_id: str                             # مرتبط بالامتحان
    question_text: str
    question_type: str                       # MCQ | TRUE_FALSE | ESSAY
    options: Optional[List[str]] = None      # خيارات الـ MCQ فقط
    correct_answer: str                      # الإجابة الصحيحة
    points: float = 1.0                      # درجة السؤال
    chunk_ref: Optional[str] = None          # مرجع الجزء من المحتوى (للـ weak points)
    created_at: datetime = Field(default_factory=datetime.now)

    class Config:
        arbitrary_types_allowed = True

    @classmethod
    def get_indexes(cls):
        return [
            {
                "key": [("question_id", 1)],
                "name": "question_id_unique",
                "unique": True,
            },
            {
                "key": [("exam_id", 1)],
                "name": "question_exam_id_index",
                "unique": False,
            },
        ]
