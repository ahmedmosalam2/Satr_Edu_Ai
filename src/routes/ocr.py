"""
src/routes/ocr.py
──────────────────
OCR Endpoints — استخراج النص من الصور والملفات الممسوحة.

Endpoints:
  GET  /api/v1/ocr/status          → حالة الـ OCR backends
  POST /api/v1/ocr/extract         → استخراج نص من صورة
  POST /api/v1/ocr/extract/pdf     → استخراج نص من PDF (مسحوب أو مدمج)
  POST /api/v1/ocr/test/gemini     → اختبار اتصال Gemini API
"""

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

# Singleton
_ocr_controller: OCRController = None


def get_ocr_controller() -> OCRController:
    global _ocr_controller
    if _ocr_controller is None:
        _ocr_controller = OCRController()
    return _ocr_controller


# ── Status ────────────────────────────────────────────────────────────────────

@router.get("/status")
async def ocr_status(current_user: dict = Depends(get_current_user)):
    """عرض حالة كل الـ OCR backends المتاحة."""
    ctrl = get_ocr_controller()
    status = ctrl.get_status()
    return JSONResponse(content={
        "status": "success",
        "ocr_status": status,
    })


# ── Extract from Image ────────────────────────────────────────────────────────

@router.post("/extract")
async def extract_from_image(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    """
    استخرج النص من صورة (PNG, JPEG, etc.).
    يستخدم Gemini Vision تلقائياً لو الـ API key موجود.
    """
    # Validate file type
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

        # Use async method for better performance
        text = await ctrl.extract_from_image_bytes_async(image_bytes, content_type)

        return JSONResponse(content={
            "status": Response.SUCCESS.value,
            "message": "Text extracted successfully",
            "data": {
                "filename": file.filename,
                "content_type": content_type,
                "text": text,
                "char_count": len(text),
                "backend_used": ctrl._backend,
            },
        })

    except Exception as e:
        logger.error(f"[OCR] Extract error: {e}")
        return JSONResponse(status_code=500, content={
            "status": Response.FILE_UPLOAD_FAILED.value,
            "message": f"OCR failed: {str(e)}",
            "data": None,
        })


# ── Extract from PDF ──────────────────────────────────────────────────────────

@router.post("/extract/pdf")
async def extract_from_pdf(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    """
    استخرج النص من PDF.
    - الصفحات المدمجة → PyMuPDF مباشرة (سريع)
    - الصفحات المسحوبة → OCR chain (Gemini → Florence → Tesseract)
    """
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
                "message": "PDF processed but little text extracted. File may be encrypted or image-only.",
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


# ── Test Gemini Connection ─────────────────────────────────────────────────────

@router.post("/test/gemini")
async def test_gemini(current_user: dict = Depends(get_current_user)):
    """
    اختبار اتصال Gemini API.
    بيتحقق إن الـ API key صح والموديل شغال.
    """
    try:
        from src.helpers.gemini_ocr import get_gemini_ocr
        gemini = get_gemini_ocr()

        if not gemini:
            return JSONResponse(status_code=503, content={
                "status": "unavailable",
                "message": "GEMINI_API_KEY not configured in .env",
            })

        import asyncio
        result = await asyncio.to_thread(gemini.test_connection)

        return JSONResponse(content={
            "status": result.get("status"),
            "model": result.get("model"),
            "test_response": result.get("test_response", ""),
            "error": result.get("error"),
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Quick Test (NO AUTH) ──────────────────────────────────────────────────────

@router.post("/test/pdf")
async def test_extract_pdf_no_auth(
    file: UploadFile = File(...),
):
    """
    🔓 اختبار OCR بدون تسجيل دخول — للتجربة السريعة من Postman.
    ارفع PDF وشوف النتيجة.
    """
    logger.info(f"[OCR Test] Received file: {file.filename} ({file.content_type})")

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")

    try:
        pdf_bytes = await file.read()
        logger.info(f"[OCR Test] PDF size: {len(pdf_bytes)} bytes")

        ctrl = get_ocr_controller()

        import asyncio
        text = await asyncio.to_thread(ctrl.extract_from_pdf_bytes, pdf_bytes)

        logger.info(f"[OCR Test] Extraction done. Text length: {len(text) if text else 0}")

        if not text or len(text.strip()) < 10:
            return JSONResponse(content={
                "status": "warning",
                "message": "PDF processed but little text extracted. May be image-only or encrypted.",
                "data": {"text": text or "", "char_count": 0},
            })

        return JSONResponse(content={
            "status": "success",
            "message": "PDF text extracted successfully",
            "data": {
                "filename": file.filename,
                "text": text,
                "char_count": len(text),
                "pages_detected": text.count("[Page "),
            },
        })

    except Exception as e:
        logger.error(f"[OCR Test] Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"PDF OCR failed: {str(e)}")


@router.post("/test/image")
async def test_extract_image_no_auth(
    file: UploadFile = File(...),
):
    """
    🔓 اختبار OCR من صورة بدون تسجيل دخول.
    """
    logger.info(f"[OCR Test] Image: {file.filename} ({file.content_type})")

    allowed_types = {"image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif", "image/tiff"}
    content_type = file.content_type or "image/png"
    if content_type not in allowed_types:
        raise HTTPException(status_code=400, detail=f"Unsupported: {content_type}")

    try:
        image_bytes = await file.read()
        logger.info(f"[OCR Test] Image size: {len(image_bytes)} bytes")

        ctrl = get_ocr_controller()
        text = await ctrl.extract_from_image_bytes_async(image_bytes, content_type)

        return JSONResponse(content={
            "status": "success",
            "message": "Text extracted",
            "data": {
                "filename": file.filename,
                "text": text,
                "char_count": len(text),
            },
        })

    except Exception as e:
        logger.error(f"[OCR Test] Image error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"OCR failed: {str(e)}")
