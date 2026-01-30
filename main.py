from fastapi import FastAPI
from src.routes import base
from src.routes import data
from dotenv import load_dotenv
from src.routes import ocr
from motor.motor_asyncio import AsyncIOMotorClient 
from src.helpers.config import get_settings

load_dotenv(".env")

app = FastAPI()
@app.on_event("startup")
async def startup():
    settings=get_settings()
    app.client=AsyncIOMotorClient(settings.MONGODB_URL)
    app.db=app.client[settings.MONGODB_DATABASE]
@app.on_event("shutdown")
async def shutdown():
    app.client.close()

app.include_router(base.router)
app.include_router(data.router)
app.include_router(ocr.router)
