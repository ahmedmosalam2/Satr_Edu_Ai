# app/api/v1/router.py
from fastapi import APIRouter
from app.api.v1.endpoints import chatbot

api_router = APIRouter()

api_router.include_router(chatbot.router, prefix="/chat", tags=["Chatbot"])
