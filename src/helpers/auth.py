from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import OAuth2PasswordBearer
from src.helpers.config import get_settings


pwd_context = CryptContext(schemes=["sha256_crypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ────────────────────────────────────────────────────────
# JWT token helpers
# ────────────────────────────────────────────────────────
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None, expires_minutes: Optional[int] = None) -> str:
    settings = get_settings()
    to_encode = data.copy()
    if expires_minutes is not None:
        delta = timedelta(minutes=expires_minutes)
    else:
        delta = expires_delta or timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    expire = datetime.utcnow() + delta
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

def decode_token(token: str) -> dict:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

def verify_token(token: str) -> Optional[dict]:
    try:
        settings = get_settings()
        return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None


# ────────────────────────────────────────────────────────
# FastAPI Dependencies
# ────────────────────────────────────────────────────────
async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    x_internal_api_key: Optional[str] = Header(None, alias="X-Internal-API-Key"),
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
    x_user_role: Optional[str] = Header(None, alias="X-User-Role"),
) -> dict:
    """Returns the decoded token payload (user_id, user_role, etc.) or mock payload via Internal API key."""
    settings = get_settings()
    if x_internal_api_key and x_internal_api_key == settings.INTERNAL_API_KEY:
        return {
            "user_id": x_user_id or "internal_service",
            "user_role": x_user_role or "operations",
        }

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return decode_token(token)


def require_roles(*allowed_roles: str):
    """
    Factory that returns a FastAPI dependency enforcing role-based access.
    Usage: Depends(require_roles("teacher", "operations"))
    """
    async def role_checker(current_user: dict = Depends(get_current_user)) -> dict:
        if current_user.get("user_role") not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {list(allowed_roles)}"
            )
        return current_user
    return role_checker
