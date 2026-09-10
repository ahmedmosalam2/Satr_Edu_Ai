import uuid
from fastapi import APIRouter, Request, HTTPException, status, Depends
from fastapi.responses import JSONResponse
from datetime import datetime
from pydantic import BaseModel, EmailStr
from typing import Optional

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


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class UpdateProfileRequest(BaseModel):
    user_name: Optional[str] = None
    user_email: Optional[EmailStr] = None


@auth_router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(request: Request, body: RegisterRequest):
    user_model = UserModel(client=request.app.client)

    if await user_model.email_exists(body.user_email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered"
        )

    user_id = str(uuid.uuid4())
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


@auth_router.put("/me/profile")
async def update_profile(
    request: Request,
    body: UpdateProfileRequest,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]
    user_model = UserModel(client=request.app.client)
    user = await user_model.get_user_by_id(user_id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    update_fields = {}
    if body.user_name and body.user_name.strip():
        update_fields["user_name"] = body.user_name.strip()

    if body.user_email and body.user_email != user.user_email:
        if await user_model.email_exists(body.user_email):
            raise HTTPException(status_code=409, detail="Email already in use by another account")
        update_fields["user_email"] = body.user_email

    if not update_fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    db = request.app.client["Satr-Edu"]
    await db["user"].update_one({"user_id": user_id}, {"$set": update_fields})

    logger.info(f"[Auth] Profile updated for user {user_id}")

    return JSONResponse(content={
        "status": "success",
        "message": "Profile updated successfully",
        "updated_fields": list(update_fields.keys())
    })


@auth_router.put("/me/change-password")
async def change_password(
    request: Request,
    body: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]
    user_model = UserModel(client=request.app.client)
    user = await user_model.get_user_by_id(user_id)

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not verify_password(body.current_password, user.user_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    if len(body.new_password) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters")

    new_hashed = hash_password(body.new_password)
    db = request.app.client["Satr-Edu"]
    await db["user"].update_one({"user_id": user_id}, {"$set": {"user_password": new_hashed}})

    logger.info(f"[Auth] Password changed for user {user_id}")

    return JSONResponse(content={
        "status": "success",
        "message": "Password changed successfully"
    })


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
