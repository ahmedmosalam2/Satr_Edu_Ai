from fastapi import FastAPI
from src.routes import base
from src.routes import data
from src.routes import nlp
from src.routes import ocr
from src.routes import auth
from src.routes import ai
from src.routes import exam
from src.routes import analytics
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient 
from src.helpers.config import get_settings
from src.story.llm.LLMproviderfactory import LLMProviderFactory
from src.story.llm.LLMEnums import LLMEnums


load_dotenv(".env")

app = FastAPI()
@app.on_event("startup")
async def startup():
    import logging
    logger = logging.getLogger("uvicorn.error")
    settings = get_settings()

    # ── MongoDB ────────────────────────────────────────────────────────────
    try:
        app.client = AsyncIOMotorClient(settings.MONGODB_URL, serverSelectionTimeoutMS=5000)
        app.db = app.client[settings.MONGODB_DATABASE]
        # Quick ping to confirm connection
        await app.client.admin.command("ping")
        logger.info("MongoDB connected successfully")
    except Exception as e:
        logger.warning(f"⚠️  MongoDB connection failed: {e}. Some features may not work.")
        app.client = None
        app.db = None

    # ── LLM Provider ──────────────────────────────────────────────────────
    try:
        llm_provider = LLMProviderFactory(settings)
        app.llm_provider = llm_provider.create_provider(LLMEnums.ProviderType.OPENAI)
        app.llm_provider.set_generate_model(settings.GENERATION_MODEL_ID)
        app.llm_provider.set_embedding_model(settings.EMBEDDING_MODEL_ID, settings.EMBEDDING_MODEL_SIZE)
        logger.info(" LLM provider initialized")
    except Exception as e:
        logger.warning(f"⚠️  LLM provider init failed: {e}")
        app.llm_provider = None

    # ── MongoDB Indexes ────────────────────────────────────────────────────
    if app.client is not None:
        try:
            from src.models.ExamModel import ExamModel
            from src.models.ExamResultModel import ExamResultModel
            await ExamModel.create_indexes(app.client)
            await ExamResultModel.create_indexes(app.client)
            logger.info(" MongoDB indexes created")
        except Exception as e:
            logger.warning(f"⚠️  Index creation failed: {e}")
@app.on_event("shutdown")
async def shutdown():
    app.client.close()

app.include_router(base.router)
app.include_router(data.router)
app.include_router(nlp.nlp_router)
app.include_router(ocr.router)
app.include_router(auth.auth_router)
app.include_router(ai.ai_router)
app.include_router(exam.exam_router)
app.include_router(analytics.analytics_router)