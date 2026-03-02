from pydantic import BaseModel, EmailStr
from src.models.enums.UserRole import UserRole


# ─── Request Schemas ───────────────────────────────────────────

class RegisterRequest(BaseModel):
    user_name: str
    user_email: EmailStr
    user_password: str
    user_role: UserRole  # يختار المستخدم دوره عند التسجيل

class LoginRequest(BaseModel):
    user_email: EmailStr
    user_password: str


# ─── Response Schemas ──────────────────────────────────────────

class UserResponse(BaseModel):
    user_id: str
    user_name: str
    user_email: str
    user_role: str
    is_approved: bool
    is_active: bool

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
