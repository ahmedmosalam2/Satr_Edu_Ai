# app/api/v1/endpoints/chatbot.py
from fastapi import APIRouter, Depends, HTTPException
from app import schema
from app.api import deps

router = APIRouter()


@router.post("/ask", response_model=schema.ChatResponse)
def chat_with_ai(
    request: schema.ChatRequest, 
    db = Depends(deps.get_db)
):



    

    print(f"User {request.student_id} is asking: {request.question}")
    fake_ai_answer = f"أهلاً، أنا الـ AI. إجابة سؤالك '{request.question}' موجودة في المحاضرة الثانية."
    
    return {
        "answer": fake_ai_answer,
        "source_page": 5
    }
