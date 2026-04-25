import uuid
from fastapi import APIRouter, Request, HTTPException, status, Depends
from fastapi.responses import JSONResponse
from datetime import datetime

from src.models.UserModel import UserModel
from src.models.scheme_db.user import User
from src.models.enums.UserRole import UserRole
from src.helpers.auth import (
    hash_password, verify_password,
    create_access_token, get_current_user, require_roles
)
from src.routes.schemes.auth import RegisterRequest, LoginRequest, UserResponse, TokenResponse
import logging

logger = logging.getLogger("uvicorn.error")

auth_router = APIRouter(
    prefix="/api/v1/auth",
    tags=["auth"],
)


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/v1/auth/register
# ─────────────────────────────────────────────────────────────────────────────
@auth_router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(request: Request, body: RegisterRequest):
    user_model = UserModel(client=request.app.client)

    # منع التسجيل بإيميل موجود
    if await user_model.email_exists(body.user_email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered"
        )

    user_id = str(uuid.uuid4())
    # Teachers تحتاج موافقة من Ops — باقي الأدوار موافقة تلقائية
    is_approved = body.user_role != UserRole.TEACHER

    new_user = User(
        user_id=user_id,
        user_name=body.user_name,
        user_email=body.user_email,
        user_password=hash_password(body.user_password),
        user_role=body.user_role.value,
        is_approved=is_approved,
        is_active=True,
        created_at=datetime.now(),
    )

    await user_model.create_user(new_user)
    logger.info(f"New user registered: {body.user_email} [{body.user_role}]")

    return UserResponse(
        user_id=user_id,
        user_name=new_user.user_name,
        user_email=new_user.user_email,
        user_role=new_user.user_role,
        is_approved=new_user.is_approved,
        is_active=new_user.is_active,
    )


# ─────────────────────────────────────────────────────────────────────────────
# POST /api/v1/auth/login
# ─────────────────────────────────────────────────────────────────────────────
@auth_router.post("/login", response_model=TokenResponse)
async def login(request: Request, body: LoginRequest):
    user_model = UserModel(client=request.app.client)

    user = await user_model.get_user_by_email(body.user_email)
    if not user or not verify_password(body.user_password, user.user_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated"
        )

    # المعلم لازم يكون متموافق عليه من Ops
    if user.user_role == UserRole.TEACHER.value and not user.is_approved:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Teacher account is pending approval by Operations"
        )

    token_data = {
        "user_id": user.user_id,
        "user_email": user.user_email,
        "user_role": user.user_role,
        "user_name": user.user_name,
    }
    access_token = create_access_token(data=token_data)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse(
            user_id=user.user_id,
            user_name=user.user_name,
            user_email=user.user_email,
            user_role=user.user_role,
            is_approved=user.is_approved,
            is_active=user.is_active,
        )
    )


# ─────────────────────────────────────────────────────────────────────────────
# GET /api/v1/auth/me
# ─────────────────────────────────────────────────────────────────────────────
@auth_router.get("/me", response_model=UserResponse)
async def get_me(request: Request, current_user: dict = Depends(get_current_user)):
    user_model = UserModel(client=request.app.client)
    user = await user_model.get_user_by_id(current_user["user_id"])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return UserResponse(
        user_id=user.user_id,
        user_name=user.user_name,
        user_email=user.user_email,
        user_role=user.user_role,
        is_approved=user.is_approved,
        is_active=user.is_active,
    )


# ─────────────────────────────────────────────────────────────────────────────
# PUT /api/v1/auth/approve/{user_id}  — Operations only
# ─────────────────────────────────────────────────────────────────────────────
@auth_router.put("/approve/{user_id}")
async def approve_teacher(
    user_id: str,
    request: Request,
    current_user: dict = Depends(require_roles(UserRole.OPERATIONS.value))
):
    user_model = UserModel(client=request.app.client)
    success = await user_model.approve_teacher(user_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Teacher not found or already approved"
        )

    return JSONResponse(content={
        "message": f"Teacher {user_id} approved successfully"
    })
