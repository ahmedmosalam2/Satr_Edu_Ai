
from fastapi import FastAPI,APIRouter,UploadFile,Depends,status,Request
from src.helpers.config import get_settings, Settings
from src.helpers.ocr_helper import get_ocr_helper
import os
from src.controllers import DataController
from src.controllers import ProjectController
from src.models.enums.Response import ResponseSignal as Response
import aiofiles
import logging
from src.routes.schemes.data import ProcessRequest
from src.controllers import ProcessController
from src.models.ProjectModel import ProjectModel
from src.models.ChunkModel import ChunkModel
from src.models.AssetModel import AssetModel
from src.models.scheme_db.asset import Asset
from src.models.scheme_db.data_chunk import DataChunk
from src.models.scheme_db.project import Project
from src.models.enums.AssetType import AssetType
from datetime import datetime
from bson import ObjectId




logger=logging.getLogger("unicorn error")


router=APIRouter(
    prefix="/api/v1",
    tags=["api_v1"],
)


@router.post("/upload/{project_id}")
async def upload(request: Request, project_id: str,file:UploadFile,app_settings: Settings = Depends(get_settings)):
    data_controller=DataController()
    is_valied=data_controller.valied_upload(project_id,file=file)
    project_model=await ProjectModel.create_index(db_client=request.app.client)
    chunk_model=await ChunkModel.create_index(db_client=request.app.client)



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
    project_controller=ProjectController(db_client=request.app.client)
    project_dir_path=project_controller.get_project_path(project_id=project_id)
    file_path,file_id=data_controller.generate_file_name(file.filename,project_id)

    try:
        print(f"📂 Saving file to: {file_path}")

        await file.seek(0)
        content = await file.read()
        print(f"[DEBUG] Content length received: {len(content)} bytes")
        with open(file_path, "wb") as f:
            f.write(content)
        print(" File saved successfully")
        await project_controller.add_file_to_project(project_id=project_id, file_name=file.filename)
        print(" Project saved to MongoDB")
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

    now = datetime.now()
    asset_model=AssetModel(client=request.app.client, project_id=project_id)
    resource_asset=Asset(
        asset_id=file_id,
        asset_name=file.filename,
        asset_size=os.path.getsize(file_path),
        asset_type=AssetType.FILE.value,
        asset_project_id=project_id,
        asset_created_at=now
    )
    await asset_model.create_asset(resource_asset)

     

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
async def process(
    request: Request,
    project_id: str,
    body: ProcessRequest,
    app_settings: Settings = Depends(get_settings),
):
    """
    رفع مهمة معالجة الملف لـ Celery في الخلفية.
    يرجع task_id فوراً بدل ما يستنى.

    قبل:  POST /process → يستني دقايق → يرجع النتيجة
    بعد:  POST /process → يرجع task_id فوراً ✅
    """
    from src.tasks.process_tasks import process_file_task

    task = process_file_task.delay(
        project_id=project_id,
        file_id=body.file_id,
        chunk_size=body.chunk_size,
        chunk_overlap=body.chunk_overlap,
        mongodb_url=app_settings.MONGODB_URL,
        mongodb_database=app_settings.MONGODB_DATABASE,
    )

    logger.info(f"Dispatched process_file_task: {task.id} for file {body.file_id}")

    return {
        "status": Response.SUCCESS.value,
        "message": "✅ الملف اتبعت للمعالجة في الخلفية",
        "data": {
            "task_id": task.id,
            "project_id": project_id,
            "file_id": body.file_id,
            "hint": f"GET /api/v1/process/status/{task.id}",
        },
    }


@router.get("/process/status/{task_id}")
async def get_process_status(task_id: str):
    """
    تابع حالة مهمة المعالجة.

    الحالات الممكنة:
    - PENDING    → في الطابور لسه
    - PROCESSING → جاري المعالجة
    - SUCCESS    → خلصت بنجاح
    - FAILURE    → فشلت
    """
    from src.tasks.process_tasks import celery_app

    task_result = celery_app.AsyncResult(task_id)

    response = {
        "task_id": task_id,
        "state": task_result.state,
    }

    if task_result.state == "SUCCESS":
        response["result"] = task_result.result
        response["message"] = "Process is SUCCESS"
    elif task_result.state == "FAILURE":
        response["error"] = str(task_result.result)
        response["message"] = "Process is FAILURE"
    elif task_result.state == "PROCESSING":
        response["progress"] = task_result.info
        response["message"] = " PROCESSING ....."
    else:
        response["message"] = "Process is PENDING"

    return response
