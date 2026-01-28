from fastapi import FastAPI,APIRouter,Depends
from src.helpers.config import get_settings, Settings
import os
router=APIRouter(
    prefix="/api/v1",
    tags=["api_v1"],
)
@router.get("/")
async def welcome(app_settings: Settings = Depends(get_settings)):
    
    app_name=app_settings.APP_NAME.value
    app_version=app_settings.APP_VERSION.value
    return {
        "app_name":app_name,
        "app_version":app_version,
    }