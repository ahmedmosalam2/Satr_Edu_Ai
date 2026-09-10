from fastapi import FastAPI
from src.routes import base
from src.routes import nlp
from src.routes import ocr
from src.routes import auth
from src.routes import ai
from src.routes import exam
from src.routes import analytics
from src.routes import admin
from src.routes import chat
from src.routes import projects
from src.routes import model_settings
from src.routes import pipeline
from src.routes import documents
from src.routes import agent
from src.routes import evaluation
from src.routes import adaptive
from src.routes import stream
from src.routes import data
# from src.mcp.server import mcp_router
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient 
from src.helpers.config import get_settings
from src.story.llm.LLMproviderfactory import LLMProviderFactory
from src.story.llm.LLMEnums import LLMEnums
import logging
import requests

load_dotenv(".env")

app = FastAPI()

@app.on_event("startup")
async def startup():
    logger = logging.getLogger("uvicorn.error")
    settings = get_settings()

    # ── MongoDB ────────────────────────────────────────────────────────────
    app.client = None
    app.db = None
    
    max_retries = 5
    retry_delay = 2
    
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"Connecting to MongoDB (attempt {attempt}/{max_retries})...")
            app.client = AsyncIOMotorClient(settings.MONGODB_URL, serverSelectionTimeoutMS=5000)
            await app.client.admin.command("ping")
            app.db = app.client[settings.MONGODB_DATABASE]
            logger.info("✅ MongoDB connected successfully")
            break
        except Exception as e:
            if attempt < max_retries:
                logger.warning(f"⚠️ MongoDB connection attempt {attempt} failed: {e}. Retrying in {retry_delay}s...")
                import asyncio
                await asyncio.sleep(retry_delay)
            else:
                logger.error(f"❌ MongoDB connection failed after {max_retries} attempts: {e}")
                app.client = None
                app.db = None

    # ── Ollama / LLM Provider ────────────────────────────────────────────────
    try:
        # Quick health check for Ollama
        ollama_url = settings.OLLAMA_BASE_URL
        connected = False

        # Build candidate URLs — works in Docker, WSL, and bare uvicorn
        candidate_urls = [ollama_url]

        # Always try plain localhost (works in WSL2 mirrored-mode & bare uvicorn)
        if "localhost" not in ollama_url and "127.0.0.1" not in ollama_url:
            candidate_urls.append("http://localhost:11434")

        # Detect WSL2 Windows-host IP from default gateway (ip route)
        try:
            import subprocess, re as _re
            route = subprocess.run(
                ["ip", "route", "show", "default"],
                capture_output=True, text=True, timeout=2
            )
            m = _re.search(r"default via ([\d.]+)", route.stdout)
            if m:
                candidate_urls.append(f"http://{m.group(1)}:11434")
        except Exception:
            pass

        # Docker-internal hostname (works when running inside a container)
        candidate_urls.append("http://host.docker.internal:11434")

        for url in candidate_urls:
            try:
                logger.info(f"Checking Ollama at {url}...")
                resp = requests.get(f"{url}/api/tags", timeout=3.0)
                if resp.status_code == 200:
                    logger.info(f"✅ Ollama connected successfully at {url}")
                    settings.OLLAMA_BASE_URL = url
                    connected = True
                    break
            except Exception:
                continue

        if not connected:
            logger.warning("⚠️ Ollama NOT reachable. Check if Ollama is running on Windows with OLLAMA_HOST=0.0.0.0")

        from src.helpers.nlp_clients import get_generation_client
        app.llm_provider = get_generation_client().provider
        app.llm_provider.set_embedding_model(settings.EMBEDDING_MODEL_ID, settings.EMBEDDING_MODEL_SIZE)
        logger.info(f"✅ LLM provider initialized (Embed Model: {settings.EMBEDDING_MODEL_ID})")
    except Exception as e:
        logger.warning(f"⚠️ LLM provider init failed: {e}")
        app.llm_provider = None

    # ── MongoDB Indexes ────────────────────────────────────────────────────
    if app.client is not None:
        try:
            from src.models.ExamModel import ExamModel
            from src.models.ExamResultModel import ExamResultModel
            from src.models.ConversationModel import ConversationModel
            from src.models.AttendanceModel import AttendanceModel
            await ExamModel.create_indexes(app.client)
            await ExamResultModel.create_indexes(app.client)
            await ConversationModel.create_indexes(app.client)
            await AttendanceModel.create_indexes(app.client)
            logger.info("✅ MongoDB indexes created")
        except Exception as e:
            logger.warning(f"⚠️ Index creation failed: {e}")

    # ── MCP Auto-Discovery (Disabled) ──────────────────────────────────
    # try:
    #     from src.mcp.registry import mcp_registry
    #     from src.mcp.tools.knowledge_tool import CalculatorMCPTool
    #     mcp_registry.register(CalculatorMCPTool())
    #     count = mcp_registry.auto_discover("src.mcp.tools")
    #     logger.info(f"✅ MCP Server ready — {len(mcp_registry.list_all())} tools registered")
    # except Exception as e:
    #     logger.warning(f"⚠️ MCP auto-discovery failed: {e}")

@app.on_event("shutdown")
async def shutdown():
    if getattr(app, "client", None) is not None:
        app.client.close()

# ── Magic Fix: Redirect mangled status URLs ──────────────────────────────


app.include_router(base.router)
app.include_router(nlp.nlp_router)
app.include_router(ocr.router)
app.include_router(auth.auth_router)
app.include_router(ai.ai_router)
app.include_router(exam.exam_router)
app.include_router(analytics.analytics_router)
app.include_router(admin.admin_router)
app.include_router(chat.chat_router)
app.include_router(projects.projects_router)
app.include_router(model_settings.model_router)
app.include_router(pipeline.pipeline_router)
app.include_router(documents.documents_router)
app.include_router(agent.agent_router)
app.include_router(evaluation.eval_router)
app.include_router(adaptive.adaptive_router)
app.include_router(stream.stream_router)  # [NEW] Streaming SSE
app.include_router(data.router)
# app.include_router(mcp_router)            # [Disabled] MCP Server

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
