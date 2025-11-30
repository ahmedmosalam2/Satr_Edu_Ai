from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from src.ai_engine.ocr_model import OCREngine
from api.deps import get_ocr_model
from PIL import Image
import io

router = APIRouter()

@router.post("/upload-material")
async def upload_material(
    file: UploadFile = File(...),
    engine: OCREngine = Depends(get_ocr_model)  
    """
    Endpoint to upload an image/lecture and extract text using the configured AI model.
    """
    # 1. التأكد من نوع الملف (صور فقط حالياً)
    if file.content_type not in ["image/jpeg", "image/png", "image/webp"]:
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload an image.")

    try:
       
        contents = await file.read()
        image = Image.open(io.BytesIO(contents))

   
        print(f"Received file: {file.filename}, processing...")
        

        extracted_text = engine.run_inference(image)

     
        return {
            "filename": file.filename,
            "status": "success",
            "extracted_text": extracted_text
        }

    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail=f"AI Processing failed: {str(e)}")