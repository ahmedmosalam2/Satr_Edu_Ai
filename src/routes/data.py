from fastapi import FastAPI,APIRouter,UploadFile,Depends,status
from src.helpers.config import get_settings, Settings
from src.helpers.ocr_helper import get_ocr_helper
import os
from src.controllers import DataController
from src.controllers import ProjectController
from src.models.enums.Response import Response
import aiofiles
import logging

logger=logging.getLogger("unicorn error")

router=APIRouter(
    prefix="/api/v1",
    tags=["api_v1"],
)


@router.post("/upload/{project_id}")
async def upload(project_id: str,file:UploadFile,app_settings: Settings = Depends(get_settings)):
    data_controller=DataController()
    is_valied=data_controller.valied_upload(project_id,file=file)
    if is_valied:
        return {
            "status":Response.SUCCESS.value,
            "message":"File is valid",
            "data":{
                "project_id":project_id,
                "file_name":file.filename,
                "file_size":file.size,
                "file_content_type":file.content_type
            }
            }
    else:
        return {
            "status":Response.BAD_REQUEST.value,
            "message":"File is not valid",
            "data":{
                "project_id":project_id,
                "file_name":file.filename,
                "file_size":file.size,
                "file_content_type":file.content_type
            }
            }
    project_controller=ProjectController()
    project_dir_path=project_controller.get_project_path(project_id=project_id)
    file_path=data_controller.generate_file_name(file.filename,project_id)

    try:
        async with aiofiles.open(file_path, "wb") as f:
            while chunk := await file.read(app_settings.FILE_DEFALUTE_CHUNK):
                await f.write(chunk)
    except Exception as e:
        logger.error(f"Error during file upload: {str(e)}")


    ocr_text = None
    if file.content_type.startswith("image/"):
        try:
            # We need to read the file again or use the saved file path if local access is allowed.
            # Since we just saved it to 'file_path', we can read it from there.
            async with aiofiles.open(file_path, "rb") as f:
                 content = await f.read()
            
            ocr_helper = get_ocr_helper()
            ocr_text = ocr_helper.process_image(content)
        except Exception as e:
            logger.error(f"Error during OCR processing: {str(e)}")
            ocr_text = f"OCR Failed: {str(e)}"

    return {
        "status":Response.SUCCESS.value,
        "message":"File is uploaded successfully",
        "data":{
            "project_id":project_id,
            "file_name":file.filename,
            "file_size":file.size,
            "file_content_type":file.content_type,
            "ocr_text": ocr_text
        }
    }

    





