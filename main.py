from fastapi import FastAPI
from src.routes import base
from src.routes import data
from dotenv import load_dotenv
from src.routes import ocr

load_dotenv(".env")

app=FastAPI()

app.include_router(base.router)
app.include_router(data.router)
app.include_router(ocr.router)