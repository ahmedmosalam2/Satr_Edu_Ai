from fastapi import APIRouter, Request, HTTPException, Depends, Query
from fastapi.responses import JSONResponse
from typing import Optional
import logging

from src.helpers.auth import get_current_user, require_roles
from src.models.ProjectModel import ProjectModel
from src.models.ChunkModel import ChunkModel
from src.models.AssetModel import AssetModel
from src.models.enums.AssetType import AssetType
from src.models.enums.UserRole import UserRole
from src.models.scheme_db.project import Project
from pydantic import BaseModel, Field
from typing import Optional
import uuid
from datetime import datetime

logger = logging.getLogger("uvicorn.error")

projects_router = APIRouter(
    prefix="/api/v1/projects",
    tags=["Projects"],
)


class ProjectCreateRequest(BaseModel):
    project_name: str = Field(..., min_length=1, max_length=100)
    project_description: str = Field("", max_length=500)


class ProjectSettingsRequest(BaseModel):
    chunk_size: Optional[int] = Field(None, ge=100, le=4000)
    chunk_overlap: Optional[int] = Field(None, ge=0, le=500)
    use_deepdoc: Optional[bool] = None
    generation_model: Optional[str] = None
    embedding_model: Optional[str] = None
    language: Optional[str] = None


@projects_router.post("", status_code=201)
async def create_project(
    body: ProjectCreateRequest,
    request: Request,
    current_user: dict = Depends(require_roles(UserRole.TEACHER.value, UserRole.OPERATIONS.value)),
):
    project_id = str(uuid.uuid4())
    now = datetime.now().isoformat()

    project = Project(
        project_id=project_id,
        project_name=body.project_name,
        project_description=body.project_description,
        project_files=[],
        project_created_at=now,
        project_updated_at=now,
    )

    project_model = await ProjectModel.create_index(db_client=request.app.client)
    await project_model.create_project(project)

    logger.info(f"[Projects] Created project {project_id} by {current_user['user_id']}")

    return JSONResponse(status_code=201, content={
        "status": "success",
        "message": "Project created successfully",
        "project": {
            "project_id": project_id,
            "project_name": body.project_name,
            "project_description": body.project_description,
            "created_at": now,
        }
    })


@projects_router.get("")
async def list_projects(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
    current_user: dict = Depends(get_current_user),
):
    project_model = await ProjectModel.create_index(db_client=request.app.client)
    data = await project_model.get_all_projects(page=page, page_size=page_size)

    projects_out = []
    for p in data.get("projects", []):
        projects_out.append({
            "project_id": p.project_id,
            "project_name": p.project_name,
            "project_description": p.project_description,
            "files_count": len(p.project_files),
            "created_at": p.project_created_at,
            "updated_at": p.project_updated_at,
        })

    return JSONResponse(content={
        "status": "success",
        "total": data.get("total_document", 0),
        "total_pages": data.get("total_page", 0),
        "page": page,
        "projects": projects_out,
    })


@projects_router.get("/{project_id}")
async def get_project(
    project_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    project_model = await ProjectModel.create_index(db_client=request.app.client)
    project = await project_model.get_project(project_id=project_id)

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    return JSONResponse(content={
        "status": "success",
        "project": {
            "project_id": project.project_id,
            "project_name": project.project_name,
            "project_description": project.project_description,
            "files_count": len(project.project_files),
            "created_at": project.project_created_at,
            "updated_at": project.project_updated_at,
        }
    })


@projects_router.put("/{project_id}/settings")
async def update_project_settings(
    project_id: str,
    body: ProjectSettingsRequest,
    request: Request,
    current_user: dict = Depends(require_roles(UserRole.TEACHER.value, UserRole.OPERATIONS.value)),
):
    db = request.app.client["Satr-Edu"]

    update_fields = {}
    settings_map = {
        "chunk_size": body.chunk_size,
        "chunk_overlap": body.chunk_overlap,
        "use_deepdoc": body.use_deepdoc,
        "generation_model": body.generation_model,
        "embedding_model": body.embedding_model,
        "language": body.language,
    }
    for key, val in settings_map.items():
        if val is not None:
            update_fields[f"settings.{key}"] = val

    if not update_fields:
        raise HTTPException(status_code=400, detail="No settings provided to update")

    update_fields["project_updated_at"] = datetime.now().isoformat()

    result = await db["project"].update_one(
        {"project_id": project_id},
        {"$set": update_fields}
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Project not found")

    logger.info(f"[Projects] Settings updated for {project_id}: {update_fields}")

    return JSONResponse(content={
        "status": "success",
        "message": "Project settings updated",
        "updated_fields": list(update_fields.keys()),
    })


@projects_router.get("/{project_id}/stats")
async def get_project_stats(
    project_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    db = request.app.client["Satr-Edu"]

    total_chunks = await db["chunk"].count_documents({"chunk_project_id": project_id})

    asset_model = AssetModel(client=request.app.client, project_id=project_id)
    try:
        assets = await asset_model.get_all_assets(
            project_id=project_id,
            asset_type=AssetType.FILE.value
        )
        total_files = len(assets)
        total_size_bytes = sum(a.asset_size or 0 for a in assets)
    except Exception:
        total_files = 0
        total_size_bytes = 0

    vector_count = 0
    try:
        from src.helpers.nlp_clients import get_vectordb_client
        vdb = get_vectordb_client()
        collection_name = f"collection_{vdb.default_vector_size}_{project_id}"
        info = await vdb.get_collection_info(collection_name)
        if info and hasattr(info, "vectors_count"):
            vector_count = info.vectors_count
        elif isinstance(info, dict):
            vector_count = info.get("vectors_count", 0)
    except Exception as e:
        logger.warning(f"[Stats] Could not get vector count: {e}")

    proj_doc = await db["project"].find_one({"project_id": project_id}, {"_id": 0})
    settings = proj_doc.get("settings", {}) if proj_doc else {}

    return JSONResponse(content={
        "status": "success",
        "project_id": project_id,
        "stats": {
            "files": {
                "total": total_files,
                "total_size_bytes": total_size_bytes,
                "total_size_mb": round(total_size_bytes / (1024 * 1024), 2),
            },
            "chunks": {"total": total_chunks},
            "vectors": {
                "total": vector_count,
                "indexed": vector_count > 0,
            },
            "settings": settings,
        }
    })


@projects_router.delete("/{project_id}")
async def delete_project(
    project_id: str,
    request: Request,
    current_user: dict = Depends(require_roles(UserRole.TEACHER.value, UserRole.OPERATIONS.value)),
):
    db = request.app.client["Satr-Edu"]

    if not await db["project"].find_one({"project_id": project_id}):
        raise HTTPException(status_code=404, detail="Project not found")

    chunks_result = await db["chunk"].delete_many({"chunk_project_id": project_id})
    assets_result = await db["asset"].delete_many({"asset_project_id": project_id})
    await db["project"].delete_one({"project_id": project_id})

    logger.info(
        f"[Projects] Deleted project {project_id}: "
        f"{chunks_result.deleted_count} chunks, {assets_result.deleted_count} assets"
    )

    return JSONResponse(content={
        "status": "success",
        "message": f"Project {project_id} deleted",
        "deleted": {
            "chunks": chunks_result.deleted_count,
            "assets": assets_result.deleted_count,
        }
    })
