from fastapi import APIRouter, Request, HTTPException, UploadFile, File, status
from fastapi.responses import JSONResponse

from src.controllers.AIController import AIController
from src.controllers.OCRController import OCRController
from src.helpers.project_content import fetch_project_content
from src.routes.schemes.ai import (
    ExamGenerateRequest,
    ExamGenerateFromChunksRequest,
    SummarizeRequest,
    GradeEssayRequest,
)
import logging

logger = logging.getLogger("uvicorn.error")

ai_router = APIRouter(
    prefix="/api/v1/ai",
    tags=["AI"],
)

_ai_controller = None
_ocr_controller = None

def get_ai_controller() -> AIController:
    global _ai_controller
    if _ai_controller is None:
        _ai_controller = AIController()
    return _ai_controller

def get_ocr_controller() -> OCRController:
    global _ocr_controller
    if _ocr_controller is None:
        _ocr_controller = OCRController()
    return _ocr_controller


@ai_router.post("/exam/generate")
async def generate_exam_from_text(request: Request, body: ExamGenerateRequest):
    ai = get_ai_controller()
    content = body.content

    if not content and body.project_id:
        content = await fetch_project_content(request.app.client, body.project_id)

    if not content or len(content.strip()) < 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No content provided. Send 'content' text or a valid 'project_id' with uploaded chunks."
        )

    result = await ai.generate_exam_questions(
        content=content,
        num_questions=body.num_questions,
        difficulty=body.difficulty,
        question_types=body.question_types,
    )

    if "error" in result and not result.get("questions") and not result.get("raw_text"):
        raise HTTPException(status_code=500, detail=result["error"])

    return JSONResponse(content={
        "status": "success",
        "questions_count": len(result.get("questions", [])),
        "exam": result,
    })


@ai_router.post("/exam/generate/file")
async def generate_exam_from_file(
    request: Request,
    num_questions: int = 10,
    difficulty: str = "mixed",
    file: UploadFile = File(...),
):
    ocr = get_ocr_controller()
    ai = get_ai_controller()

    file_bytes = await file.read()
    content_type = file.content_type or ""

    if content_type == "application/pdf" or file.filename.endswith(".pdf"):
        content = ocr.extract_from_pdf_bytes(file_bytes)
    elif content_type.startswith("image/"):
        content = ocr.extract_from_image_bytes(file_bytes)
    else:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Send a PDF or image file."
        )

    if not content or len(content.strip()) < 50:
        raise HTTPException(status_code=400, detail="Could not extract meaningful text from file.")

    result = await ai.generate_exam_questions(
        content=content,
        num_questions=num_questions,
        difficulty=difficulty,
    )

    return JSONResponse(content={
        "status": "success",
        "filename": file.filename,
        "extracted_text_length": len(content),
        "questions_count": len(result.get("questions", [])),
        "exam": result,
    })


@ai_router.post("/summarize")
async def summarize_content(request: Request, body: SummarizeRequest):
    ai = get_ai_controller()
    content = body.content

    if not content and body.project_id:
        content = await fetch_project_content(request.app.client, body.project_id)

    if not content or len(content.strip()) < 50:
        raise HTTPException(
            status_code=400,
            detail="No content provided. Send 'content' text or a valid 'project_id'."
        )

    summary = await ai.summarize_content(content)

    return JSONResponse(content={
        "status": "success",
        "content_length": len(content),
        "summary": summary,
    })


@ai_router.post("/summarize/file")
async def summarize_file(
    request: Request,
    file: UploadFile = File(...),
):
    ocr = get_ocr_controller()
    ai = get_ai_controller()

    file_bytes = await file.read()
    content_type = file.content_type or ""

    if content_type == "application/pdf" or file.filename.endswith(".pdf"):
        content = ocr.extract_from_pdf_bytes(file_bytes)
    elif content_type.startswith("image/"):
        content = ocr.extract_from_image_bytes(file_bytes)
    else:
        raise HTTPException(status_code=400, detail="Unsupported file type.")

    if not content or len(content.strip()) < 50:
        raise HTTPException(status_code=400, detail="Could not extract meaningful text from file.")

    summary = await ai.summarize_content(content)

    return JSONResponse(content={
        "status": "success",
        "filename": file.filename,
        "extracted_text_length": len(content),
        "summary": summary,
    })


@ai_router.post("/grade/essay")
async def grade_essay(body: GradeEssayRequest):
    ai = get_ai_controller()

    result = await ai.grade_essay(
        question=body.question,
        model_answer=body.model_answer,
        student_answer=body.student_answer,
        max_score=body.max_score,
    )

    return JSONResponse(content={
        "status": "success",
        "max_score": body.max_score,
        "grading_result": result,
    })


