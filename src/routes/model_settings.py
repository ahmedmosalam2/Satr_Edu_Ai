from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from typing import Optional
import logging

from src.helpers.auth import require_roles
from src.helpers.config import get_settings
from src.models.enums.UserRole import UserRole
from pydantic import BaseModel

logger = logging.getLogger("uvicorn.error")

model_router = APIRouter(
    prefix="/api/v1/models",
    tags=["Model Settings"],
)


class ModelSetRequest(BaseModel):
    generation_model: Optional[str] = None
    embedding_model: Optional[str] = None
    embedding_size: Optional[int] = None


class ModelTestRequest(BaseModel):
    prompt: str = "مرحباً، هل أنت شغال؟"


@model_router.get("/current")
async def get_current_model(request: Request):
    settings = get_settings()
    return JSONResponse(content={
        "status": "success",
        "current_models": {
            "generation_backend": settings.GENERATION_BACKEND,
            "generation_model": settings.GENERATION_MODEL_ID,
            "embedding_backend": settings.EMBEDDING_BACKEND,
            "embedding_model": settings.EMBEDDING_MODEL_ID,
            "embedding_size": settings.EMBEDDING_MODEL_SIZE,
            "ollama_url": settings.OLLAMA_BASE_URL,
        }
    })


@model_router.get("/available")
async def list_available_models():
    import requests as req
    settings = get_settings()

    for url in [settings.OLLAMA_BASE_URL, "http://host.docker.internal:11434", "http://localhost:11434"]:
        try:
            resp = req.get(f"{url}/api/tags", timeout=3.0)
            if resp.status_code == 200:
                data = resp.json()
                models = data.get("models", [])
                return JSONResponse(content={
                    "status": "success",
                    "ollama_url": url,
                    "total": len(models),
                    "models": [
                        {
                            "name": m.get("name"),
                            "size_gb": round(m.get("size", 0) / 1e9, 2),
                            "modified_at": m.get("modified_at", ""),
                        }
                        for m in models
                    ],
                })
        except Exception:
            continue

    raise HTTPException(
        status_code=503,
        detail="Ollama not reachable. Make sure Ollama is running with OLLAMA_HOST=0.0.0.0"
    )


@model_router.put("/set")
async def set_model(
    body: ModelSetRequest,
    request: Request,
    current_user: dict = Depends(require_roles(UserRole.OPERATIONS.value)),
):
    from src.helpers.nlp_clients import get_generation_client, get_embedding_client
    from src.story.llm.LLMproviderfactory import LLMProviderFactory
    from src.story.llm.LLMEnums import LLMEnums

    settings = get_settings()
    changes = []
    warnings = []

    if not body.generation_model and not body.embedding_model:
        raise HTTPException(status_code=400, detail="Provide at least one of: generation_model, embedding_model")

    if body.generation_model:
        old_model = settings.GENERATION_MODEL_ID
        try:
            factory = LLMProviderFactory(settings)
            provider = factory.create_provider(LLMEnums.ProviderType.OLLAMA)
            provider.set_generate_model(body.generation_model)

            from src.helpers.nlp_clients import LLMWrapper
            wrapper = LLMWrapper(provider)
            test_resp = await wrapper.generate_text("Say OK in one word", max_tokens=10)

            if test_resp:
                settings.GENERATION_MODEL_ID = body.generation_model
                changes.append(f"generation_model: {old_model} → {body.generation_model}")
                logger.info(f"[ModelSettings] Generation model changed to: {body.generation_model}")
            else:
                raise ValueError("Model returned empty response")

        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to switch generation model to '{body.generation_model}': {str(e)}"
            )

    if body.embedding_model:
        old_embed = settings.EMBEDDING_MODEL_ID
        new_size = body.embedding_size or settings.EMBEDDING_MODEL_SIZE
        try:
            factory = LLMProviderFactory(settings)
            provider = factory.create_provider(LLMEnums.ProviderType.OLLAMA)
            provider.set_embedding_model(body.embedding_model, new_size)

            from src.helpers.nlp_clients import LLMWrapper
            wrapper = LLMWrapper(provider)
            test_vec = await wrapper.embed_text("test")
            if not test_vec:
                raise ValueError("Embedding returned empty result")

            settings.EMBEDDING_MODEL_ID = body.embedding_model
            settings.EMBEDDING_MODEL_SIZE = new_size
            changes.append(f"embedding_model: {old_embed} → {body.embedding_model} (size={new_size})")
            logger.info(f"[ModelSettings] Embedding model changed to: {body.embedding_model}")
            warnings.append("⚠️ Embedding model changed — you MUST re-index all projects for RAG to work correctly!")

        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to switch embedding model to '{body.embedding_model}': {str(e)}"
            )

    return JSONResponse(content={
        "status": "success",
        "message": "Model(s) updated successfully",
        "changes": changes,
        "warnings": warnings,
        "current": {
            "generation_model": settings.GENERATION_MODEL_ID,
            "embedding_model": settings.EMBEDDING_MODEL_ID,
            "embedding_size": settings.EMBEDDING_MODEL_SIZE,
        }
    })


@model_router.post("/test")
async def test_model(
    body: ModelTestRequest,
    current_user: dict = Depends(require_roles(UserRole.OPERATIONS.value, UserRole.TEACHER.value)),
):
    from src.helpers.nlp_clients import get_generation_client
    import time

    gen = get_generation_client()
    start = time.time()

    try:
        response = await gen.generate_text(prompt=body.prompt, max_tokens=200)
        elapsed = round(time.time() - start, 2)

        return JSONResponse(content={
            "status": "success",
            "prompt": body.prompt,
            "response": response,
            "response_time_seconds": elapsed,
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Model test failed: {str(e)}")
