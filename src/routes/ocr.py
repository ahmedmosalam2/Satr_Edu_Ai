import io
import logging
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import JSONResponse

from src.controllers.OCRController import OCRController
from src.helpers.auth import get_current_user
from src.models.enums.Response import ResponseSignal as Response

logger = logging.getLogger("uvicorn.error")

router = APIRouter(
    prefix="/api/v1/ocr",
    tags=["OCR"],
)

_ocr_controller: OCRController = None


def get_ocr_controller() -> OCRController:
    global _ocr_controller
    if _ocr_controller is None:
        _ocr_controller = OCRController()
    return _ocr_controller


@router.get("/status")
async def ocr_status(current_user: dict = Depends(get_current_user)):
    ctrl = get_ocr_controller()
    return JSONResponse(content={
        "status": "success",
        "ocr_status": ctrl.get_status(),
    })


@router.post("/extract")
async def extract_from_image(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    allowed_types = {"image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif", "image/tiff"}
    content_type = file.content_type or "image/png"
    if content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {content_type}. Allowed: {allowed_types}"
        )

    try:
        image_bytes = await file.read()
        ctrl = get_ocr_controller()
        text = await ctrl.extract_from_image_bytes_async(image_bytes, content_type)

        return JSONResponse(content={
            "status": Response.SUCCESS.value,
            "message": "Text extracted successfully",
            "data": {
                "filename": file.filename,
                "content_type": content_type,
                "text": text,
                "char_count": len(text),
            },
        })

    except Exception as e:
        logger.error(f"[OCR] Extract error: {e}")
        return JSONResponse(status_code=500, content={
            "status": "error",
            "message": f"OCR failed: {str(e)}",
            "data": None,
        })


@router.post("/extract/pdf")
async def extract_from_pdf(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")

    try:
        pdf_bytes = await file.read()
        ctrl = get_ocr_controller()

        import asyncio
        text = await asyncio.to_thread(ctrl.extract_from_pdf_bytes, pdf_bytes)

        if not text or len(text.strip()) < 10:
            return JSONResponse(content={
                "status": "warning",
                "message": "PDF processed but little text extracted. File may be encrypted or fully image-only.",
                "data": {"text": text or "", "char_count": 0},
            })

        return JSONResponse(content={
            "status": Response.SUCCESS.value,
            "message": "PDF text extracted successfully",
            "data": {
                "filename": file.filename,
                "text": text,
                "char_count": len(text),
                "pages_detected": text.count("[Page "),
            },
        })

    except Exception as e:
        logger.error(f"[OCR] PDF extract error: {e}")
        raise HTTPException(status_code=500, detail=f"PDF OCR failed: {str(e)}")


@router.get("/surya/status")
async def surya_status():
    try:
        from src.helpers.surya_ocr_helper import get_surya_ocr
        helper = get_surya_ocr()
        if helper:
            return JSONResponse(content={"status": "success", "surya": helper.get_status()})
        return JSONResponse(content={"status": "unavailable", "surya": {}})
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


