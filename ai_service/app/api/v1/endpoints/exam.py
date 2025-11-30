from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List

router = APIRouter()


class ExamRequest(BaseModel):
    text_content: str
    num_questions: int = 5
    difficulty: str = "medium"

@router.post("/generate-exam")
async def generate_exam(request: ExamRequest):
    """
    Takes text content and generates MCQ questions using LLM.
    """
    # TODO: هنا هننادي على Llama 3 قدام
    
    return {
        "status": "success",
        "questions": [
            {
                "q": "What is the main topic of the text?",
                "options": ["AI", "History", "Math", "Science"],
                "answer": "AI"
            }
        ] * request.num_questions
    }