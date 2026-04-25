from fastapi import FastAPI, APIRouter, UploadFile, Depends, status, Request, BackgroundTasks, HTTPException, Query
from src.helpers.config import get_settings, Settings
from src.helpers.ocr_helper import get_ocr_helper
import os
from src.controllers import DataController
from src.controllers import ProjectController
from src.controllers.ProcessController import ProcessController
from src.models.enums.Response import ResponseSignal as Response
from src.models.enums.AssetType import AssetType
import aiofiles
import logging
from src.routes.schemes.data import ProcessRequest
from src.models.ProjectModel import ProjectModel
from src.models.ChunkModel import ChunkModel
from src.models.AssetModel import AssetModel
from src.models.scheme_db.asset import Asset
from src.models.scheme_db.data_chunk import DataChunk
from src.models.scheme_db.project import Project
from datetime import datetime
from typing import Optional


logger = logging.getLogger("uvicorn.error")


router = APIRouter(
    prefix="/api/v1",
    tags=["api_v1"],
)


# ─── Upload ────────────────────────────────────────────────────────────────────

@router.post("/upload/{project_id}")
async def upload(
    request: Request,
    project_id: str,
    file: UploadFile,
    app_settings: Settings = Depends(get_settings)
):
    """رفع ملف جديد لمشروع. يدعم PDF, TXT, DOCX, images."""
    data_controller = DataController()
    is_valid = data_controller.valied_upload(project_id, file=file)

    if not is_valid:
        return {
            "status": Response.BAD_REQUEST.value,
            "message": "File is not valid — check type or size",
            "data": {
                "project_id": project_id,
                "file_name": file.filename,
                "file_size": file.size,
                "file_content_type": file.content_type
            }
        }

    asset_model = AssetModel(client=request.app.client, project_id=project_id)

    file_path, file_id = data_controller.generate_file_name(
        file_name=file.filename,
        project_id=project_id
    )

    content = await file.read()
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(content)

    ocr_text = ""
    if file.content_type and file.content_type.startswith("image/"):
        try:
            ocr_helper = get_ocr_helper()
            ocr_text = ocr_helper.process_image(content)
        except Exception as e:
            logger.error(f"OCR error: {e}")
            ocr_text = ""

    now = datetime.now()
    resource_asset = Asset(
        asset_id=file_id,
        asset_name=file.filename,
        asset_size=os.path.getsize(file_path),
        asset_type=AssetType.FILE.value,
        asset_project_id=project_id,
        asset_created_at=now
    )
    await asset_model.create_asset(resource_asset)

    return {
        "status": Response.SUCCESS.value,
        "message": "File is uploaded successfully",
        "data": {
            "project_id": project_id,
            "file_id": file_id,
            "file_name": file.filename,
            "file_size": file.size,
            "file_content_type": file.content_type,
            "ocr_text": ocr_text
        }
    }


# ─── List Files in a Project ───────────────────────────────────────────────────

@router.get("/files/{project_id}")
async def list_files(request: Request, project_id: str):
    """قائمة بكل الملفات المرفوعة لمشروع معين."""
    asset_model = AssetModel(client=request.app.client, project_id=project_id)
    try:
        assets = await asset_model.get_all_assets(
            project_id=project_id,
            asset_type=AssetType.FILE.value
        )
        return {
            "status": Response.SUCCESS.value,
            "project_id": project_id,
            "total_files": len(assets),
            "files": [
                {
                    "file_id": a.asset_id,
                    "file_name": a.asset_name,
                    "file_size": a.asset_size,
                    "uploaded_at": a.asset_created_at.isoformat() if a.asset_created_at else None
                }
                for a in assets
            ]
        }
    except Exception as e:
        logger.error(f"Error listing files: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ─── Delete a File ─────────────────────────────────────────────────────────────

@router.delete("/files/{project_id}/{file_id}")
async def delete_file(request: Request, project_id: str, file_id: str):
    """حذف ملف مع حذف الـ chunks الخاصة به من MongoDB."""
    asset_model = AssetModel(client=request.app.client, project_id=project_id)

    asset = await asset_model.get_asset(file_id)
    if not asset:
        raise HTTPException(status_code=404, detail="File not found")

    # Delete from filesystem
    data_controller = DataController()
    project_controller = ProjectController()
    project_path = project_controller.get_project_path(project_id=project_id)
    file_path = os.path.join(project_path, file_id)
    if os.path.exists(file_path):
        os.remove(file_path)

    # Delete from MongoDB (assets)
    await asset_model.delete_asset(file_id)

    # Delete related chunks from MongoDB
    chunk_model = ChunkModel(client=request.app.client, project_id=project_id)
    try:
        await chunk_model.collection.delete_many({"chunk_project_id": project_id})
        logger.info(f"Deleted chunks for project {project_id} after file deletion")
    except Exception as e:
        logger.warning(f"Could not delete chunks: {e}")

    return {
        "status": Response.SUCCESS.value,
        "message": f"File '{asset.asset_name}' deleted successfully",
        "file_id": file_id
    }


# ─── Process File ──────────────────────────────────────────────────────────────

@router.post("/process/{project_id}")
async def process(
    request: Request,
    project_id: str,
    body: ProcessRequest,
    background_tasks: BackgroundTasks,
    app_settings: Settings = Depends(get_settings),
):
    """
    معالجة الملف وتقسيمه لـ chunks وحفظها في MongoDB.
    يعمل بشكل سريع ويحفظ الـ chunks في الـ background.
    """
    chunk_model = await ChunkModel.create_index(db_client=request.app.client)
    process_controller = ProcessController(project_id=project_id)

    try:
        # ── DeepDoc path: PDF + use_deepdoc=True ─────────────────────────────
        file_ext = os.path.splitext(body.file_id)[-1].lower()
        use_deepdoc = body.use_deepdoc and file_ext == ".pdf"

        if use_deepdoc:
            from src.controllers.DeepDocController import get_deepdoc
            from src.controllers.ProjectController import ProjectController as PC
            project_path = PC().get_project_path(project_id=project_id)
            file_path = os.path.join(project_path, body.file_id)
            deepdoc = get_deepdoc()
            file_chunks = deepdoc.analyze_pdf(
                file_path=file_path,
                chunk_size=body.chunk_size,
                chunk_overlap=body.chunk_overlap,
            )
            chunking_method = "deepdoc"
            logger.info(f"[DeepDoc] {len(file_chunks)} smart chunks for {body.file_id}")
        else:
            # ── Legacy path (non-PDF or DeepDoc disabled) ─────────────────────
            file_content = process_controller.get_file_content(file_id=body.file_id)
            file_chunks = process_controller.process_file_content(
                file_content=file_content,
                chunk_size=body.chunk_size,
                chunk_overlap=body.chunk_overlap,
            )
            chunking_method = "recursive"

    except Exception as e:
        logger.error(f"File processing failed: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to process file: {str(e)}")

    logger.info(f"Generated {len(file_chunks)} chunks for file {body.file_id}")

    # Delete old chunks for this file prefix if do_reset
    if body.do_reset:
        try:
            await chunk_model.collection.delete_many({"chunk_project_id": project_id})
            logger.info(f"Reset: deleted existing chunks for project {project_id}")
        except Exception as e:
            logger.warning(f"Could not reset chunks: {e}")

    async def _save_chunks_to_db():
        try:
            now = datetime.now().isoformat()
            # Get current max order to avoid ID collisions on append
            existing_count = await chunk_model.collection.count_documents({"chunk_project_id": project_id})
            chunks_to_save = [
                DataChunk(
                    chunk_id=f"{project_id}_{body.file_id}_{existing_count + i}",
                    chunk_text=chunk.page_content,
                    chunk_metadata=chunk.metadata,
                    chunk_order=existing_count + i,
                    chunk_created_at=now,
                    chunk_updated_at=now,
                    chunk_project_id=project_id,
                )
                for i, chunk in enumerate(file_chunks)
            ]
            await chunk_model.insert_many_chunks(
                project_id=project_id,
                chunks=chunks_to_save
            )
            logger.info(f"✅ Saved {len(chunks_to_save)} chunks to MongoDB for project {project_id}")
        except Exception as e:
            logger.error(f"❌ Failed to save chunks to MongoDB: {e}")

    background_tasks.add_task(_save_chunks_to_db)

    return {
        "status": Response.SUCCESS.value,
        "message": "File is processed successfully",
        "data": {
            "project_id": project_id,
            "file_id": body.file_id,
            "chunking_method": chunking_method,
            "chunks_count": len(file_chunks),
            "chunks": [
                {
                    "text": chunk.page_content,
                    "page": chunk.metadata.get("page", 0),
                    "chunk_type": chunk.metadata.get("chunk_type", "text"),
                    "header": chunk.metadata.get("header", ""),
                    "order": i
                }
                for i, chunk in enumerate(file_chunks)
            ]
        }
    }


# ─── List Chunks ───────────────────────────────────────────────────────────────

@router.get("/chunks/{project_id}")
async def get_chunks(
    request: Request,
    project_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """استرجاع كل الـ chunks الخاصة بمشروع مع pagination."""
    chunk_model = ChunkModel(client=request.app.client, project_id=project_id)
    chunks = await chunk_model.get_project_chunks(
        project_id=project_id,
        page=page,
        page_size=page_size
    )

    return {
        "status": Response.SUCCESS.value,
        "message": "Chunks retrieved successfully",
        "data": {
            "project_id": project_id,
            "page": page,
            "page_size": page_size,
            "total_in_page": len(chunks),
            "chunks": [
                {
                    "chunk_id": c.chunk_id,
                    "chunk_text": c.chunk_text[:200] + "..." if len(c.chunk_text) > 200 else c.chunk_text,
                    "chunk_order": c.chunk_order,
                    "page": (c.chunk_metadata or {}).get("page", 0),
                }
                for c in chunks
            ]
        }
    }


# ─── Reset/Delete All Chunks ───────────────────────────────────────────────────

@router.delete("/chunks/{project_id}")
async def delete_chunks(request: Request, project_id: str):
    """حذف كل الـ chunks الخاصة بمشروع (قبل إعادة المعالجة)."""
    chunk_model = ChunkModel(client=request.app.client, project_id=project_id)
    try:
        result = await chunk_model.collection.delete_many({"chunk_project_id": project_id})
        return {
            "status": Response.SUCCESS.value,
            "message": f"Deleted {result.deleted_count} chunks for project {project_id}",
            "deleted_count": result.deleted_count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── Legacy task status (deprecated) ──────────────────────────────────────────

@router.get("/process/status/{task_id}")
async def get_process_status(task_id: str):
    """Legacy — Celery tasks no longer used."""
    return {
        "status": "deprecated",
        "message": "Processing is now synchronous. No task tracking needed.",
        "task_id": task_id
    }
