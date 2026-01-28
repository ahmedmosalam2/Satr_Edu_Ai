from fastapi import FastAPI,APIRouter,UploadFile,Depends,status
from src.helpers.config import get_settings, Settings
import os
from src.controllers import DataController
from src.controllers import ProjectController
from src.models.enums.Response import Response
import aiofiles

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
    file_path=os.path.join(project_dir_path,file.filename)
    async with aiofiles.open(file_path, "wb") as f:
        while chunk := await file.read(app_settings.FILE_DEFALUTE_CHUNK):
            await f.write(chunk)
    return {
        "status":Response.SUCCESS.value,
        "message":"File is uploaded successfully",
        "data":{
            "project_id":project_id,
            "file_name":file.filename,
            "file_size":file.size,
            "file_content_type":file.content_type
        }
    }

    





