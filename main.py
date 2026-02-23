from fastapi import FastAPI
from src.routes import base
from src.routes import data
from src.routes import nlp
from dotenv import load_dotenv
# from src.routes import ocr
from motor.motor_asyncio import AsyncIOMotorClient 
from src.helpers.config import get_settings
from src.story.llm.LLMproviderfactory import LLMProviderFactory
from src.story.llm.LLMEnums import LLMEnums


load_dotenv(".env")

app = FastAPI()
@app.on_event("startup")
async def startup():
    settings=get_settings()
    app.client=AsyncIOMotorClient(settings.MONGODB_URL)
    app.db=app.client[settings.MONGODB_DATABASE]
    #-------------------------
    llm_provider=LLMProviderFactory(settings)
    app.llm_provider=llm_provider.create_provider(LLMEnums.ProviderType.OPENAI)
    app.llm_provider.set_generate_model(settings.GENERATION_MODEL_ID)
    app.llm_provider.set_embedding_model(settings.EMBEDDING_MODEL_ID
    ,settings.EMBEDDING_MODEL_SIZE)
@app.on_event("shutdown")
async def shutdown():
    app.client.close()

app.include_router(base.router)
app.include_router(data.router)
app.include_router(nlp.nlp_router)
# app.include_router(ocr.router)