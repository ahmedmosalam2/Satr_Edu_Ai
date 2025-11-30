# app/schemas.py
from pydantic import BaseModel

class ChatRequest(BaseModel):
    student_id: int
    question: str
    course_id: str


class ChatResponse(BaseModel):
    answer: str
    source_page: int | None = None 
