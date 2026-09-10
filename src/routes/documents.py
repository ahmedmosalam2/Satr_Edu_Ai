from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Request, Query
from typing import List, Optional
from datetime import datetime
import os
import uuid
import logging

logger = logging.getLogger("uvicorn.error")

documents_router = APIRouter(
    prefix="/api/v1/documents",
    tags=["Documents — File Management"],
)


async def _get_document_model(request: Request):
    from src.models.DocumentModel import DocumentModel
    return await DocumentModel.create_index(db_client=request.app.client)


@documents_router.post("/{project_id}/upload")
async def upload_and_process(
    request: Request,
    project_id: str,
    file: UploadFile = File(...),
    chunk_strategy: str = Form("naive"),
    chunk_size: int = Form(500),
    chunk_overlap: int = Form(50),
    auto_process: bool = Form(True),
):
    from src.pipeline.pipeline_manager import DocumentPipeline
    from src.models.scheme_db.document import Document
    from src.models.ChunkModel import ChunkModel
    from src.models.scheme_db.data_chunk import DataChunk
    from src.controllers.ProjectController import ProjectController

    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    pipeline = DocumentPipeline()
    ext = os.path.splitext(file.filename)[-1].lower()
    if ext not in pipeline.supported_extensions():
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Supported: {pipeline.supported_extensions()}"
        )

    doc_id = f"{project_id}_{uuid.uuid4().hex[:8]}_{file.filename}"

    project_path = ProjectController().get_project_path(project_id=project_id)
    os.makedirs(project_path, exist_ok=True)
    file_path = os.path.join(project_path, file.filename)

    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    doc_model = await _get_document_model(request)
    now = datetime.now()

    document = Document(
        document_id=doc_id,
        project_id=project_id,
        file_name=file.filename,
        file_type=ext,
        file_size=len(content),
        file_path=file_path,
        status="uploaded",
        chunk_strategy=chunk_strategy,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        created_at=now,
        updated_at=now,
    )
    await doc_model.create_document(document)

    if not auto_process:
        return {
            "status": "success",
            "message": "File uploaded — waiting for processing",
            "document_id": doc_id,
            "file_name": file.filename,
            "file_type": ext,
            "file_size": len(content),
        }

    await doc_model.update_status(doc_id, "processing")

    try:
        result = pipeline.process(
            file_path=file_path,
            chunk_strategy=chunk_strategy,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

        if not result.success:
            await doc_model.update_status(doc_id, "failed", error=result.error)
            raise HTTPException(status_code=422, detail=result.error)

        chunk_model = await ChunkModel.create_index(db_client=request.app.client)
        chunks_to_save = [
            DataChunk(
                chunk_id=f"{project_id}_{doc_id}_{i}",
                chunk_text=chunk.chunk_text,
                chunk_metadata={
                    **(chunk.chunk_metadata or {}),
                    "document_id": doc_id,
                    "source_file": file.filename,
                },
                chunk_order=i,
                chunk_created_at=now.isoformat(),
                chunk_updated_at=now.isoformat(),
                chunk_project_id=project_id,
            )
            for i, chunk in enumerate(result.chunks)
        ]

        if chunks_to_save:
            await chunk_model.insert_many_chunks(
                project_id=project_id,
                chunks=chunks_to_save,
            )

        await doc_model.update_document(doc_id, {
            "status": "processed",
            "pages_count": result.pages_count,
            "chunks_count": result.chunks_count,
            "parse_time_ms": result.parse_time_ms,
            "chunk_time_ms": result.chunk_time_ms,
            "processed_at": datetime.now(),
        })

        return {
            "status": "success",
            "message": "File uploaded and processed",
            "document_id": doc_id,
            "file_name": file.filename,
            "file_type": ext,
            "file_size": len(content),
            "chunk_strategy": chunk_strategy,
            "pages_count": result.pages_count,
            "chunks_count": result.chunks_count,
            "parse_time_ms": round(result.parse_time_ms, 2),
            "chunk_time_ms": round(result.chunk_time_ms, 2),
            "total_time_ms": round(result.total_time_ms, 2),
        }

    except HTTPException:
        raise
    except Exception as e:
        await doc_model.update_status(doc_id, "failed", error=str(e))
        logger.error(f"[Documents] Processing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@documents_router.post("/{project_id}/batch-upload")
async def batch_upload(
    request: Request,
    project_id: str,
    files: List[UploadFile] = File(...),
    chunk_strategy: str = Form("naive"),
    chunk_size: int = Form(500),
    chunk_overlap: int = Form(50),
):
    from src.pipeline.pipeline_manager import DocumentPipeline
    from src.models.scheme_db.document import Document
    from src.models.ChunkModel import ChunkModel
    from src.models.scheme_db.data_chunk import DataChunk
    from src.controllers.ProjectController import ProjectController

    pipeline = DocumentPipeline()
    doc_model = await _get_document_model(request)
    chunk_model = await ChunkModel.create_index(db_client=request.app.client)
    project_path = ProjectController().get_project_path(project_id=project_id)
    os.makedirs(project_path, exist_ok=True)

    results = []

    for file in files:
        ext = os.path.splitext(file.filename)[-1].lower()
        doc_id = f"{project_id}_{uuid.uuid4().hex[:8]}_{file.filename}"

        try:
            file_path = os.path.join(project_path, file.filename)
            content = await file.read()
            with open(file_path, "wb") as f:
                f.write(content)

            now = datetime.now()

            document = Document(
                document_id=doc_id,
                project_id=project_id,
                file_name=file.filename,
                file_type=ext,
                file_size=len(content),
                file_path=file_path,
                status="processing",
                chunk_strategy=chunk_strategy,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                created_at=now,
                updated_at=now,
            )
            await doc_model.create_document(document)

            result = pipeline.process(
                file_path=file_path,
                chunk_strategy=chunk_strategy,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )

            if result.success:
                chunks_to_save = [
                    DataChunk(
                        chunk_id=f"{project_id}_{doc_id}_{i}",
                        chunk_text=chunk.chunk_text,
                        chunk_metadata={
                            **(chunk.chunk_metadata or {}),
                            "document_id": doc_id,
                            "source_file": file.filename,
                        },
                        chunk_order=i,
                        chunk_created_at=now.isoformat(),
                        chunk_updated_at=now.isoformat(),
                        chunk_project_id=project_id,
                    )
                    for i, chunk in enumerate(result.chunks)
                ]
                if chunks_to_save:
                    await chunk_model.insert_many_chunks(
                        project_id=project_id,
                        chunks=chunks_to_save,
                    )

                await doc_model.update_document(doc_id, {
                    "status": "processed",
                    "pages_count": result.pages_count,
                    "chunks_count": result.chunks_count,
                    "parse_time_ms": result.parse_time_ms,
                    "chunk_time_ms": result.chunk_time_ms,
                    "processed_at": datetime.now(),
                })

                results.append({
                    "file_name": file.filename,
                    "status": "success",
                    "document_id": doc_id,
                    "chunks_count": result.chunks_count,
                })
            else:
                await doc_model.update_status(doc_id, "failed", error=result.error)
                results.append({
                    "file_name": file.filename,
                    "status": "failed",
                    "error": result.error,
                })

        except Exception as e:
            results.append({
                "file_name": file.filename,
                "status": "failed",
                "error": str(e),
            })

    successful = sum(1 for r in results if r["status"] == "success")
    return {
        "status": "success",
        "total_files": len(files),
        "successful": successful,
        "failed": len(files) - successful,
        "results": results,
    }


@documents_router.get("/{project_id}/stats")
async def project_stats(request: Request, project_id: str):
    doc_model = await _get_document_model(request)
    stats = await doc_model.get_project_stats(project_id)
    return {
        "status": "success",
        "project_id": project_id,
        "stats": stats,
    }


@documents_router.get("/{project_id}")
async def list_documents(
    request: Request,
    project_id: str,
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    doc_model = await _get_document_model(request)
    result = await doc_model.get_project_documents(
        project_id=project_id,
        status=status,
        page=page,
        page_size=page_size,
    )
    return {
        "status": "success",
        "project_id": project_id,
        "total": result["total"],
        "total_pages": result["total_pages"],
        "page": result["page"],
        "documents": [
            {
                "document_id": d.document_id,
                "file_name": d.file_name,
                "file_type": d.file_type,
                "file_size": d.file_size,
                "status": d.status,
                "is_enabled": d.is_enabled,
                "chunk_strategy": d.chunk_strategy,
                "pages_count": d.pages_count,
                "chunks_count": d.chunks_count,
                "error_message": d.error_message if d.status == "failed" else None,
                "created_at": d.created_at.isoformat() if d.created_at else None,
                "processed_at": d.processed_at.isoformat() if d.processed_at else None,
            }
            for d in result["documents"]
        ],
    }


@documents_router.get("/{project_id}/{document_id}")
async def get_document(request: Request, project_id: str, document_id: str):
    doc_model = await _get_document_model(request)
    doc = await doc_model.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return {
        "status": "success",
        "document": doc.dict(exclude={"_id"}),
    }


@documents_router.delete("/{project_id}/{document_id}")
async def delete_document(request: Request, project_id: str, document_id: str):
    doc_model = await _get_document_model(request)
    doc = await doc_model.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if doc.file_path and os.path.exists(doc.file_path):
        try:
            os.remove(doc.file_path)
        except Exception:
            pass

    from src.models.ChunkModel import ChunkModel
    chunk_model = ChunkModel(client=request.app.client)
    try:
        if chunk_model.collection is not None:
            await chunk_model.collection.delete_many(
                {"chunk_metadata.document_id": document_id}
            )
    except Exception as e:
        logger.warning(f"Could not delete document chunks: {e}")

    await doc_model.delete_document(document_id)

    return {
        "status": "success",
        "message": f"Document '{doc.file_name}' deleted",
        "document_id": document_id,
    }


@documents_router.patch("/{project_id}/{document_id}/toggle")
async def toggle_document(
    request: Request,
    project_id: str,
    document_id: str,
    enabled: bool = Query(...),
):
    doc_model = await _get_document_model(request)
    success = await doc_model.toggle_document(document_id, enabled)
    if not success:
        raise HTTPException(status_code=404, detail="Document not found")
    return {
        "status": "success",
        "document_id": document_id,
        "is_enabled": enabled,
    }


@documents_router.post("/{project_id}/{document_id}/reprocess")
async def reprocess_document(
    request: Request,
    project_id: str,
    document_id: str,
    chunk_strategy: str = Form("naive"),
    chunk_size: int = Form(500),
    chunk_overlap: int = Form(50),
):
    from src.pipeline.pipeline_manager import DocumentPipeline
    from src.models.ChunkModel import ChunkModel
    from src.models.scheme_db.data_chunk import DataChunk

    doc_model = await _get_document_model(request)
    doc = await doc_model.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if not doc.file_path or not os.path.exists(doc.file_path):
        raise HTTPException(status_code=404, detail="File not found on disk")

    chunk_model = ChunkModel(client=request.app.client)
    if chunk_model.collection is not None:
        await chunk_model.collection.delete_many(
            {"chunk_metadata.document_id": document_id}
        )

    await doc_model.update_status(document_id, "processing")
    pipeline = DocumentPipeline()

    try:
        result = pipeline.process(
            file_path=doc.file_path,
            chunk_strategy=chunk_strategy,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

        if not result.success:
            await doc_model.update_status(document_id, "failed", error=result.error)
            raise HTTPException(status_code=422, detail=result.error)

        now = datetime.now()
        chunk_model_indexed = await ChunkModel.create_index(db_client=request.app.client)
        chunks_to_save = [
            DataChunk(
                chunk_id=f"{project_id}_{document_id}_r_{i}",
                chunk_text=chunk.chunk_text,
                chunk_metadata={
                    **(chunk.chunk_metadata or {}),
                    "document_id": document_id,
                    "source_file": doc.file_name,
                },
                chunk_order=i,
                chunk_created_at=now.isoformat(),
                chunk_updated_at=now.isoformat(),
                chunk_project_id=project_id,
            )
            for i, chunk in enumerate(result.chunks)
        ]
        if chunks_to_save:
            await chunk_model_indexed.insert_many_chunks(
                project_id=project_id,
                chunks=chunks_to_save,
            )

        await doc_model.update_document(document_id, {
            "status": "processed",
            "chunk_strategy": chunk_strategy,
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
            "pages_count": result.pages_count,
            "chunks_count": result.chunks_count,
            "parse_time_ms": result.parse_time_ms,
            "chunk_time_ms": result.chunk_time_ms,
            "processed_at": datetime.now(),
        })

        return {
            "status": "success",
            "message": "Document reprocessed",
            "document_id": document_id,
            "chunk_strategy": chunk_strategy,
            "chunks_count": result.chunks_count,
            "total_time_ms": round(result.total_time_ms, 2),
        }

    except HTTPException:
        raise
    except Exception as e:
        await doc_model.update_status(document_id, "failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
