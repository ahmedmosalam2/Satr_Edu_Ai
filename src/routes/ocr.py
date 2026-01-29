from fastapi import APIRouter, UploadFile, File, HTTPException, status
from src.helpers.ocr_helper import OCRHelper
from src.models.enums.Response import Response
import torch
from PIL import Image
import io

router = APIRouter(
    prefix="/ocr",
    tags=["OCR"]
)

ocr_helper = None
def get_ocr_helper():
    global ocr_helper
    if ocr_helper is None:
        try:
            ocr_helper = OCRHelper()
        except Exception as e:
            raise HTTPException(status_code=500, detail=Response.FILE_UPLOAD_FAILED.value)
    return ocr_helper

@router.post("/extract")
async def extract_text(file: UploadFile = File(...)):
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail=Response.FILE_TYPE_NOT_SUPPORTED.value)
    
    try:
        content = await file.read()
        helper = get_ocr_helper()
        text = helper.process_image(content)
        
        return {
            "status": Response.SUCCESS.value,
            "message": "Text extracted successfully",
            "data": {
                "text": text,
                "filename": file.filename
            }
        }
    except Exception as e:
         return {
            "status": Response.FILE_UPLOAD_FAILED.value,
            "message": f"Error during extraction: {str(e)}",
            "data": None
        }
