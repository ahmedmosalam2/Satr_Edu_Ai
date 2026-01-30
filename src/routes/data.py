from fastapi import FastAPI,APIRouter,UploadFile,Depends,status,Request
from src.helpers.config import get_settings, Settings
from src.helpers.ocr_helper import get_ocr_helper
import os
from src.controllers import DataController
from src.controllers import ProjectController
from src.models.enums.Response import Response
import aiofiles
import logging
from src.routes.schemes.data import ProcessRequest
from src.controllers import ProcessController
from src.models.ProjectModel import ProjectModel


logger=logging.getLogger("unicorn error")


router=APIRouter(
    prefix="/api/v1",
    tags=["api_v1"],
)


@router.post("/upload/{project_id}")
async def upload(request:Request,project_id: str,file:UploadFile,app_settings: Settings = Depends(get_settings)):
    data_controller=DataController()
    is_valied=data_controller.valied_upload(project_id,file=file)

    if not is_valied:
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
    file_path,file_id=data_controller.generate_file_name(file.filename,project_id)

    try:
        print(f"📂 Saving file to: {file_path}")

        content = await file.read()
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(content)
        print(" File saved successfully")
    except Exception as e:
        logger.error(f"Error during file upload: {str(e)}")
        print(f" Error saving file: {e}")


    ocr_text = None
    if file.content_type.startswith("image/"):
        try:

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
            "file_id":file_id,
            "file_name":file.filename,
            "file_size":file.size,
            "file_content_type":file.content_type,
            "ocr_text": ocr_text
        }
    }

    

@router.post("/process/{project_id}")
def process(project_id: str,request: ProcessRequest,app_settings: Settings = Depends(get_settings)):
    file_id=request.file_id
    chunk_size=request.chunk_size
    chunk_overlap=request.chunk_overlap

    process_controller=ProcessController(project_id=project_id)
    file_content=process_controller.get_file_content(file_id=file_id)

    file_chunks=process_controller.process_file_content(file_content=file_content,
    chunk_size=chunk_size,
    chunk_overlap=chunk_overlap)
    return {
        "status":Response.SUCCESS.value,
        "message":"File is processed successfully",
        "data":{
            "project_id":project_id,
            "file_id":file_id,
            "chunks":file_chunks
       }
    }  

