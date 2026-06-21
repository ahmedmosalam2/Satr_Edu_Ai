"""
src/routes/stream.py
─────────────────────
Streaming endpoint — الإجابة تيجي كلمة بكلمة زي ChatGPT.

يستخدم:
  - Server-Sent Events (SSE) — مدعوم في كل browser بدون WebSocket
  - نفس الـ RAGAgent الموجود بس مع generator
"""

import json
import logging
import asyncio
from typing import AsyncGenerator, Optional
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger("uvicorn.error")

stream_router = APIRouter(
    prefix="/api/v1/stream",
    tags=["Streaming — Real-time Responses"],
)


class StreamQuery(BaseModel):
    project_id: str
    query: str
    language: str = "ar"
    student_id: Optional[str] = None


# ── SSE Event Builder ─────────────────────────────────────────────────────────

def _sse_event(data: dict, event: str = "message") -> str:
    """بناء SSE event string."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


# ── Streaming Generator ───────────────────────────────────────────────────────

async def _stream_rag_response(
    request: Request,
    query: str,
    project_id: str,
    language: str,
) -> AsyncGenerator[str, None]:
    """
    Generator يبعت:
      1. citations أول ما يلاقيها (مش محتاج تستنى الإجابة)
      2. الإجابة token by token
      3. event نهائي بالـ metadata
    """
    from src.agent.tools.knowledge_search import KnowledgeSearchTool
    from src.agent.tools.calculator import CalculatorTool
    from src.controllers.NLPController import NLPController
    from src.helpers.nlp_clients import get_embedding_client, get_vectordb_client, template_parser
    from src.models.ProjectModel import ProjectModel

    db_client = request.app.client
    project_model = await ProjectModel.create_index(db_client=db_client)
    project = await project_model.get_project(project_id)

    if not project:
        yield _sse_event({"error": "Project not found"}, event="error")
        return

    if request.app.llm_provider is None:
        yield _sse_event({"error": "LLM provider not available"}, event="error")
        return

    nlp_controller = NLPController(
        vectordb_client=get_vectordb_client(),
        generation_client=None,
        embedding_client=get_embedding_client(),
        template_parser=template_parser,
    )

    search_tool = KnowledgeSearchTool(nlp_controller=nlp_controller, project=project)
    calc_tool   = CalculatorTool()

    # ── Step 1: بعت event إن الـ search بدأ ─────────────────────────────────
    yield _sse_event({"status": "searching", "message": "🔍 جاري البحث في قاعدة المعرفة..."}, event="status")
    await asyncio.sleep(0)  # yield control للـ event loop

    # ── Step 2: شغّل الـ search وبعت الـ citations فوراً ────────────────────
    try:
        search_result = await search_tool.execute(query=query, limit=5)
        citations = [c.to_dict() for c in search_tool.last_citations]

        # بعت الـ citations قبل الإجابة — الـ frontend يعرضها فوراً
        yield _sse_event({
            "status": "retrieved",
            "citations": citations,
            "citations_count": len(citations),
            "message": f"✅ وُجد {len(citations)} مصادر ذات صلة",
        }, event="citations")
        await asyncio.sleep(0)

    except Exception as e:
        logger.error(f"[Stream] Search failed: {e}")
        search_result = ""
        citations = []
        yield _sse_event({"status": "search_failed", "message": "⚠️ البحث فشل، سيتم الإجابة من المعرفة العامة"}, event="status")

    # ── Step 3: بناء الـ prompt ───────────────────────────────────────────────
    yield _sse_event({"status": "thinking", "message": "🤔 جاري توليد الإجابة..."}, event="status")
    await asyncio.sleep(0)

    if language == "ar":
        system_prompt = (
            "أنت مساعد تعليمي ذكي. استخدم المعلومات التالية للإجابة على السؤال. "
            "إذا كانت المعلومات غير كافية، اذكر ذلك. "
            "أجب بشكل واضح ومنظم."
        )
    else:
        system_prompt = (
            "You are an intelligent educational assistant. "
            "Use the following information to answer the question clearly and in an organized manner."
        )

    full_prompt = f"{system_prompt}\n\n{search_result}\n\nQuestion: {query}"

    # ── Step 4: Stream الإجابة ────────────────────────────────────────────────
    try:
        generation_client = request.app.llm_provider

        # لو الـ LLM يدعم streaming
        if hasattr(generation_client, "stream_text"):
            async for token in generation_client.stream_text(prompt=full_prompt):
                yield _sse_event({"token": token}, event="token")
                await asyncio.sleep(0)
        else:
            # Fallback: اجيب الإجابة كاملة وابعتها على chunks بحجم 20 كلمة
            import inspect
            result = generation_client.generate_text(prompt=full_prompt)
            if inspect.isawaitable(result):
                full_answer = await result
            else:
                full_answer = result

            full_answer = full_answer or ""

            # Simulate streaming: ابعت كل 20 كلمة كـ token
            words = full_answer.split()
            chunk_size = 5
            for i in range(0, len(words), chunk_size):
                chunk = " ".join(words[i:i + chunk_size])
                if i + chunk_size < len(words):
                    chunk += " "
                yield _sse_event({"token": chunk}, event="token")
                await asyncio.sleep(0.03)  # delay صغير عشان يبان كـ streaming حقيقي

    except Exception as e:
        logger.error(f"[Stream] Generation failed: {e}")
        yield _sse_event({"error": f"Generation failed: {str(e)}"}, event="error")
        return

    # ── Step 5: Event نهائي بالـ metadata ────────────────────────────────────
    yield _sse_event({
        "status": "done",
        "citations_count": len(citations),
        "message": "✅ اكتملت الإجابة",
    }, event="done")


# ── Route ─────────────────────────────────────────────────────────────────────

@stream_router.post("/ask")
async def stream_ask(request: Request, body: StreamQuery):
    """
    Streaming RAG endpoint — يبعت الإجابة كلمة بكلمة.

    Response format: Server-Sent Events (SSE)

    Events sequence:
      1. status: "searching"      → بدأ البحث
      2. citations: [...]         → المصادر (بمجرد إيجادها)
      3. status: "thinking"       → جاري التوليد
      4. token: "كلمة "          → كل جزء من الإجابة
      5. done: metadata           → انتهى

    Usage (JavaScript):
      const evtSource = new EventSource('/api/v1/stream/ask');
      evtSource.addEventListener('token', e => {
        const {token} = JSON.parse(e.data);
        document.getElementById('answer').textContent += token;
      });
      evtSource.addEventListener('citations', e => {
        const {citations} = JSON.parse(e.data);
        renderCitations(citations);  // ← هنا بتعمل الـ highlight
      });
    """
    return StreamingResponse(
        _stream_rag_response(
            request=request,
            query=body.query,
            project_id=body.project_id,
            language=body.language,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # مهم للـ Nginx
            "Connection": "keep-alive",
        },
    )
