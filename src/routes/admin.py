"""
src/routes/admin.py
────────────────────
Admin routes — متاحة لـ OPERATIONS role فقط.

Endpoints:
  GET    /api/v1/admin/users               → كل المستخدمين (مع filter)
  GET    /api/v1/admin/users/{user_id}     → مستخدم بالتفصيل
  PUT    /api/v1/admin/users/{user_id}/activate   → تفعيل/إيقاف حساب
  DELETE /api/v1/admin/users/{user_id}     → حذف مستخدم
  GET    /api/v1/admin/stats               → إحصائيات النظام
  GET    /api/v1/admin/projects            → كل المشاريع
"""

import logging
from fastapi import APIRouter, Request, HTTPException, status, Depends, Query
from fastapi.responses import JSONResponse
from typing import Optional

from src.models.UserModel import UserModel
from src.models.ProjectModel import ProjectModel
from src.models.ChunkModel import ChunkModel
from src.models.enums.UserRole import UserRole
from src.helpers.auth import get_current_user, require_roles

logger = logging.getLogger("uvicorn.error")

admin_router = APIRouter(
    prefix="/api/v1/admin",
    tags=["Admin"],
    dependencies=[Depends(require_roles(UserRole.OPERATIONS.value))],
)


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/v1/admin/users
# ─────────────────────────────────────────────────────────────────────────────
@admin_router.get("/users")
async def list_users(
    request: Request,
    role: Optional[str] = Query(None, description="Filter by role: teacher/student/operations/parent"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """عرض كل المستخدمين مع إمكانية الفلترة بالـ role والـ pagination."""
    user_model = UserModel(client=request.app.client)

    users = await user_model.get_all_users(role_filter=role, page=page, page_size=page_size)
    total = await user_model.count_users(role_filter=role)

    return JSONResponse(content={
        "status": "success",
        "total": total,
        "page": page,
        "page_size": page_size,
        "users": [
            {
                "user_id": u.user_id,
                "user_name": u.user_name,
                "user_email": u.user_email,
                "user_role": u.user_role,
                "is_approved": u.is_approved,
                "is_active": u.is_active,
            }
            for u in users
        ],
    })


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/v1/admin/users/{user_id}
# ─────────────────────────────────────────────────────────────────────────────
@admin_router.get("/users/{user_id}")
async def get_user(user_id: str, request: Request):
    """عرض مستخدم بالتفصيل."""
    user_model = UserModel(client=request.app.client)
    user = await user_model.get_user_by_id(user_id)

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return JSONResponse(content={
        "status": "success",
        "user": {
            "user_id": user.user_id,
            "user_name": user.user_name,
            "user_email": user.user_email,
            "user_role": user.user_role,
            "is_approved": user.is_approved,
            "is_active": user.is_active,
        },
    })


# ─────────────────────────────────────────────────────────────────────────────
# PUT /api/v1/admin/users/{user_id}/activate
# ─────────────────────────────────────────────────────────────────────────────
@admin_router.put("/users/{user_id}/activate")
async def toggle_user_activation(
    user_id: str,
    request: Request,
    active: bool = Query(..., description="True لتفعيل / False لإيقاف"),
):
    """تفعيل أو إيقاف حساب مستخدم."""
    user_model = UserModel(client=request.app.client)

    if active:
        success = await user_model.activate_user(user_id)
        action = "activated"
    else:
        success = await user_model.deactivate_user(user_id)
        action = "deactivated"

    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    logger.info(f"[Admin] User {user_id} {action}")
    return JSONResponse(content={"status": "success", "message": f"User {user_id} {action}"})


# ─────────────────────────────────────────────────────────────────────────────
# DELETE /api/v1/admin/users/{user_id}
# ─────────────────────────────────────────────────────────────────────────────
@admin_router.delete("/users/{user_id}")
async def delete_user(user_id: str, request: Request):
    """حذف مستخدم نهائياً من النظام."""
    user_model = UserModel(client=request.app.client)
    success = await user_model.delete_user(user_id)

    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    logger.info(f"[Admin] User {user_id} deleted")
    return JSONResponse(content={"status": "success", "message": f"User {user_id} deleted"})


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/v1/admin/stats
# ─────────────────────────────────────────────────────────────────────────────
@admin_router.get("/stats")
async def get_system_stats(request: Request):
    """إحصائيات عامة عن النظام: عدد المستخدمين، المشاريع، الـ chunks."""
    user_model = UserModel(client=request.app.client)
    project_model = ProjectModel(client=request.app.client)

    # User counts by role
    total_users     = await user_model.count_users()
    total_teachers  = await user_model.count_users(role_filter=UserRole.TEACHER.value)
    total_students  = await user_model.count_users(role_filter=UserRole.STUDENT.value)
    total_ops       = await user_model.count_users(role_filter=UserRole.OPERATIONS.value)

    # Projects
    projects_data = await project_model.get_all_projects(page=1, page_size=1)
    total_projects = projects_data.get("total_document", 0)

    # Chunks — count from the single 'chunk' collection
    total_chunks = 0
    try:
        db = request.app.client["Satr-Edu"]
        if db is not None:
            total_chunks = await db["chunk"].count_documents({})
    except Exception as e:
        logger.warning(f"[Admin] Error counting chunks: {e}")


    return JSONResponse(content={
        "status": "success",
        "stats": {
            "users": {
                "total": total_users,
                "teachers": total_teachers,
                "students": total_students,
                "operations": total_ops,
            },
            "projects": {
                "total": total_projects,
            },
            "chunks": {
                "total": total_chunks,
            },
        },
    })


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/v1/admin/projects
# ─────────────────────────────────────────────────────────────────────────────
@admin_router.get("/projects")
async def list_all_projects(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=50),
):
    """عرض كل المشاريع في النظام."""
    project_model = ProjectModel(client=request.app.client)
    data = await project_model.get_all_projects(page=page, page_size=page_size)

    return JSONResponse(content={
        "status": "success",
        "total": data.get("total_document", 0),
        "total_pages": data.get("total_page", 0),
        "page": page,
        "projects": [p.dict() for p in data.get("projects", [])],
    })


@admin_router.get('/storage/status')
async def get_storage_status():
    """عرض حالة الـ Storage Backend — MinIO أو Filesystem."""
    from src.controllers.StorageController import get_storage
    storage = get_storage()
    return JSONResponse(content={'status': 'success', 'storage': storage.status()})
