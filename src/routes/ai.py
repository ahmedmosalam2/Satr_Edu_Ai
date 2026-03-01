import logging
from fastapi import APIRouter, Request, HTTPException, UploadFile, File, status
from fastapi.responses import JSONResponse

from src.controllers.AIController import AIController
from src.controllers.OCRController import OCRController
from src.routes.schemes.ai import (
    ExamGenerateRequest,
    ExamGenerateFromChunksRequest,
    SummarizeRequest,
    GradeEssayRequest,
)

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
        content = await _fetch_project_content(request, body.project_id)

    if not content or len(content.strip()) < 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No content provided. Send 'content' text or a valid 'project_id' with uploaded chunks."
        )

    result = ai.generate_exam_questions(
        content=content,
        num_questions=body.num_questions,
        difficulty=body.difficulty,
        question_types=body.question_types,
    )

    if "error" in result and not result.get("questions"):
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

    # Extract text based on file type
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

    result = ai.generate_exam_questions(
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
        content = await _fetch_project_content(request, body.project_id)

    if not content or len(content.strip()) < 50:
        raise HTTPException(
            status_code=400,
            detail="No content provided. Send 'content' text or a valid 'project_id'."
        )

    summary = ai.summarize_content(content)

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

    summary = ai.summarize_content(content)

    return JSONResponse(content={
        "status": "success",
        "filename": file.filename,
        "extracted_text_length": len(content),
        "summary": summary,
    })


@ai_router.post("/grade/essay")
async def grade_essay(body: GradeEssayRequest):
    """
    Grade a student essay answer using LLM comparison with the model answer.
    Returns score, feedback, missing_points, correct_points.
    """
    ai = get_ai_controller()

    result = ai.grade_essay(
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




@ai_router.post("/ocr/extract")
async def ocr_extract(file: UploadFile = File(...)):
    """
    Extract text from an uploaded PDF or image file.
    Returns the raw extracted text.
    """
    ocr = get_ocr_controller()
    file_bytes = await file.read()
    content_type = file.content_type or ""

    if content_type == "application/pdf" or file.filename.endswith(".pdf"):
        text = ocr.extract_from_pdf_bytes(file_bytes)
    elif content_type.startswith("image/"):
        text = ocr.extract_from_image_bytes(file_bytes)
    else:
        raise HTTPException(status_code=400, detail="Unsupported file type. Send a PDF or image.")

    return JSONResponse(content={
        "status": "success",
        "filename": file.filename,
        "text_length": len(text),
        "text": text,
    })



async def _fetch_project_content(request: Request, project_id: str) -> str:
    """Fetch all chunks from MongoDB for a project and concatenate them."""
    try:
        from src.models.ChunkModel import ChunkModel
        chunk_model = ChunkModel(client=request.app.client, project_id=project_id)

        all_text = []
        page = 1
        while True:
            chunks = await chunk_model.get_project_chunks(
                project_id=project_id, page=page, page_size=100
            )
            if not chunks:
                break
            all_text.extend([c.chunk_text for c in chunks if c.chunk_text])
            page += 1

        return "\n\n".join(all_text)
    except Exception as e:
        logger.error(f"Error fetching project chunks: {e}")
        return ""

