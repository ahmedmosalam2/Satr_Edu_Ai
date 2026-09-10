from fastapi import APIRouter, Request, Depends
from src.helpers.config import get_settings, Settings

router = APIRouter(
    prefix="/api/v1",
    tags=["api_v1"],
)

@router.get("/")
async def welcome(request: Request, app_settings: Settings = Depends(get_settings)):
    return {
        "app_name": app_settings.APP_NAME,
        "app_version": app_settings.APP_VERSION,
        "status": "running",
        "db_connected": request.app.client is not None,
        "llm_ready": getattr(request.app, "llm_provider", None) is not None,
    }


@router.get("/health")
async def health_check(request: Request):
    db_ok = False
    try:
        if request.app.client is not None:
            await request.app.client.admin.command("ping")
            db_ok = True
    except Exception:
        db_ok = False

    llm_ok = getattr(request.app, "llm_provider", None) is not None

    return {
        "status": "healthy" if db_ok else "degraded",
        "services": {
            "mongodb": "connected" if db_ok else "disconnected",
            "llm_provider": "ready" if llm_ok else "unavailable",
        }
    }