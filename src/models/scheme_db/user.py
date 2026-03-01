from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime
from src.models.enums.UserRole import UserRole


class User(BaseModel):
    user_id: str
    user_name: str
    user_email: str
    user_password: str          # bcrypt hashed — لا يُرجَع للـ client أبداً
    user_role: str              # UserRole enum value
    is_approved: bool = False   # للـ Teachers: يوافق عليهم Ops
    is_active: bool = True
    created_at: datetime = None
    updated_at: Optional[datetime] = None
