from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from src.models.enums.ExamStatus import ExamStatus


class Exam(BaseModel):
    exam_id: str = Field(..., min_length=1)
    exam_title: str = Field(..., min_length=1)
    project_id: str                          # مرتبط بمشروع المحتوى
    teacher_id: str                          # المعلم المنشئ
    status: str = ExamStatus.DRAFT.value     # draft | approved
    question_ids: List[str] = []             # قائمة question_ids
    difficulty: str = "mixed"               # easy | medium | hard | mixed
    num_questions: int = 10
    created_at: datetime = Field(default_factory=datetime.now)
    approved_at: Optional[datetime] = None

    class Config:
        arbitrary_types_allowed = True

    @classmethod
    def get_indexes(cls):
        return [
            {
                "key": [("exam_id", 1)],
                "name": "exam_id_unique",
                "unique": True,
            },
            {
                "key": [("project_id", 1)],
                "name": "exam_project_id_index",
                "unique": False,
            },
            {
                "key": [("teacher_id", 1)],
                "name": "exam_teacher_id_index",
                "unique": False,
            },
        ]
