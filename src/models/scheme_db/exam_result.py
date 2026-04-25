from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class ExamResult(BaseModel):
    result_id: str = Field(..., min_length=1)
    exam_id: str
    student_id: str
    total_score: float                       # مجموع الدرجات
    max_score: float                         # أقصى درجة ممكنة
    percentage: float                        # النسبة المئوية
    weak_chunks: List[str] = []              # chunk_refs للأسئلة الغلط → للـ lecture highlighting
    submitted_at: datetime = Field(default_factory=datetime.now)

    class Config:
        arbitrary_types_allowed = True

    @classmethod
    def get_indexes(cls):
        return [
            {
                "key": [("result_id", 1)],
                "name": "result_id_unique",
                "unique": True,
            },
            {
                "key": [("exam_id", 1), ("student_id", 1)],
                "name": "result_exam_student_unique",
                "unique": True,   # طالب واحد → نتيجة واحدة لكل امتحان
            },
        ]
