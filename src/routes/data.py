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
from src.models.ChunkModel import ChunkModel


logger=logging.getLogger("unicorn error")


router=APIRouter(
    prefix="/api/v1",
    tags=["api_v1"],
)


@router.post("/upload/{project_id}")
async def upload(project_id: str,file:UploadFile,app_settings: Settings = Depends(get_settings)):
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
    project_controller=ProjectController(db_client=request.app.client)
    project_dir_path=project_controller.get_project_path(project_id=project_id)
    file_path,file_id=data_controller.generate_file_name(file.filename,project_id)

    try:
        print(f"📂 Saving file to: {file_path}")

        content = await file.read()
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(content)
        print(" File saved successfully")
        
        # Save to MongoDB
        await project_controller.project_model.get_project(project_id=project_id)
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
async def process(request: Request, project_id: str, body: ProcessRequest, app_settings: Settings = Depends(get_settings)):
    from src.models.scheme_db.data_chunk import DataChunk
    from datetime import datetime
    
    file_id = body.file_id
    chunk_size = body.chunk_size
    chunk_overlap = body.chunk_overlap

    process_controller = ProcessController(project_id=project_id)
    file_content = process_controller.get_file_content(file_id=file_id)

    file_chunks = process_controller.process_file_content(
        file_content=file_content,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap
    )

    # Convert Document objects to DataChunk objects for MongoDB
    now = datetime.now().isoformat()
    chunks_to_save = [
        DataChunk(
            chunk_id=f"{project_id}_{file_id}_{i}",
            chunk_text=chunk.page_content,
            chunk_metadata=chunk.metadata,
            chunk_order=i,
            chunk_created_at=now,
            chunk_updated_at=now,
            chunk_project_id=project_id
        )
        for i, chunk in enumerate(file_chunks)
    ]

    # Save chunks to MongoDB
    chunk_model = ChunkModel(client=request.app.client, project_id=project_id)
    if chunk_model.collection is not None and len(chunks_to_save) > 0:
        await chunk_model.insert_many_chunks(project_id=project_id, chunks=chunks_to_save)
        print(f" Saved {len(chunks_to_save)} chunks to MongoDB")

    # Convert for JSON response
    chunks_data = [
        {
            "content": chunk.page_content,
            "metadata": chunk.metadata,
            "index": i
        }
        for i, chunk in enumerate(file_chunks)
    ]

    return {
        "status": Response.SUCCESS.value,
        "message": "File is processed successfully",
        "data": {
            "project_id": project_id,
            "file_id": file_id,
            "chunks_count": len(chunks_data),
            "chunks_saved_to_db": len(chunks_to_save),
            "chunks": chunks_data
        }
    }
