"""
src/routes/chat.py
──────────────────
Multi-turn RAG Chat — محادثة تراكمية مع قاعدة المعرفة.

Endpoints:
  POST   /api/v1/chat/{project_id}              → سؤال جديد أو متابعة محادثة
  GET    /api/v1/chat/conversations              → قائمة محادثات المستخدم
  GET    /api/v1/chat/conversations/{conv_id}   → تفاصيل محادثة كاملة
  DELETE /api/v1/chat/conversations/{conv_id}   → حذف محادثة
  POST   /api/v1/chat/conversations/{conv_id}/clear → مسح رسائل المحادثة
"""

import logging
from typing import Optional

from fastapi import APIRouter, Request, HTTPException, Depends, Query
from fastapi.responses import JSONResponse

from src.helpers.auth import get_current_user
from src.models.ConversationModel import ConversationModel
from src.models.ProjectModel import ProjectModel
from src.controllers.NLPController import NLPController
from src.models.ChunkModel import ChunkModel
from src.helpers.nlp_clients import (
    get_vectordb_client, get_embedding_client,
    get_generation_client, template_parser,
)
from src.routes.schemes.chat import ChatRequest, ChatResponse, MessageResponse, ConversationSummary

logger = logging.getLogger("uvicorn.error")

chat_router = APIRouter(
    prefix="/api/v1/chat",
    tags=["Chat"],
)

# ── Lazy singletons (نفس نمط باقي الـ routes) ────────────────────────────────
_vectordb = None
_embedding = None
_generation = None

def _get_vectordb():
    global _vectordb
    if _vectordb is None:
        _vectordb = get_vectordb_client()
    return _vectordb

def _get_embedding():
    global _embedding
    if _embedding is None:
        _embedding = get_embedding_client()
    return _embedding

def _get_generation():
    global _generation
    if _generation is None:
        _generation = get_generation_client()
    return _generation


# ─── POST /api/v1/chat/{project_id} ──────────────────────────────────────────

@chat_router.post("/{project_id}", response_model=ChatResponse)
async def chat(
    project_id: str,
    body: ChatRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """
    سؤال RAG مع Chat History كامل.

    - لو `conversation_id` فاضي → ينشئ محادثة جديدة
    - لو `conversation_id` موجود → يكمل على نفس المحادثة
    - الـ context التراكمي بيتبعت للـ LLM عشان يفهم السياق
    """
    user_id = current_user["user_id"]
    db_client = request.app.client

    if db_client is None:
        raise HTTPException(status_code=503, detail="Database not available")

    # 1. الـ project لازم يكون موجود
    project_model = await ProjectModel.create_index(db_client=db_client)
    project = await project_model.get_project(project_id=project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    conv_model = ConversationModel(client=db_client)
    is_new = False

    # 2. جيب أو أنشئ المحادثة
    if body.conversation_id:
        conversation = await conv_model.get_conversation(body.conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        # أمان: تأكد إن المحادثة بتاعت نفس المستخدم
        if conversation.user_id != user_id:
            raise HTTPException(status_code=403, detail="Access denied")
    else:
        conversation = await conv_model.create_conversation(
            project_id=project_id,
            user_id=user_id,
            first_message=body.text,
        )
        is_new = True

    # 3. بنيّ الـ chat_history للـ LLM (آخر 6 رسائل = 3 أدوار)
    recent_messages = conversation.messages[-6:] if conversation.messages else []
    chat_history_for_llm = []
    nlp = NLPController(
        vectordb_client=_get_vectordb(),
        generation_client=_get_generation(),
        embedding_client=_get_embedding(),
        template_parser=template_parser,
        chunk_model=ChunkModel(client=db_client, project_id=project_id),
    )

    # أضف الـ history القديمة كـ context في الـ prompt system
    history_context = ""
    if recent_messages:
        lines = []
        for msg in recent_messages:
            prefix = "الطالب" if msg.role == "user" else "المساعد"
            lines.append(f"{prefix}: {msg.content}")
        history_context = "\n".join(lines)

    # 4. نفذ الـ RAG مع تعديل الـ query ليشمل الـ context
    enriched_query = body.text
    if history_context:
        enriched_query = (
            f"سياق المحادثة السابقة:\n{history_context}\n\n"
            f"السؤال الحالي: {body.text}"
        )

    try:
        answer, _, _, sources = await nlp.answer_rag_question(
            project=project,
            query=enriched_query,
            limit=body.limit,
        )
    except Exception as e:
        logger.error(f"[Chat] RAG error: {e}")
        raise HTTPException(status_code=500, detail=f"RAG error: {str(e)}")

    if not answer:
        answer = "لم أجد إجابة كافية في قاعدة المعرفة. يرجى التأكد من رفع ومعالجة ملفات المشروع أولاً."

    # 5. احفظ السؤال والإجابة في المحادثة
    await conv_model.append_turn(
        conversation_id=conversation.conversation_id,
        user_text=body.text,
        assistant_text=answer,
        sources=sources,
    )

    # 6. جيب المحادثة المحدّثة لإرجاعها كاملة
    updated_conv = await conv_model.get_conversation(conversation.conversation_id)
    history_response = []
    if updated_conv:
        for msg in updated_conv.messages:
            history_response.append(MessageResponse(
                role=msg.role,
                content=msg.content,
                timestamp=msg.timestamp,
            ))

    logger.info(
        f"[Chat] user={user_id} project={project_id} conv={conversation.conversation_id} "
        f"new={is_new} answer_len={len(answer)}"
    )

    return ChatResponse(
        conversation_id=conversation.conversation_id,
        answer=answer,
        sources=sources or [],
        history=history_response,
        is_new_conversation=is_new,
    )


# ─── GET /api/v1/chat/conversations ──────────────────────────────────────────

@chat_router.get("/conversations")
async def list_my_conversations(
    request: Request,
    project_id: Optional[str] = Query(None, description="فلترة بالمشروع (اختياري)"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    current_user: dict = Depends(get_current_user),
):
    """عرض كل محادثات المستخدم الحالي (مع فلترة اختيارية بالمشروع)."""
    user_id = current_user["user_id"]
    conv_model = ConversationModel(client=request.app.client)

    conversations = await conv_model.list_conversations(
        user_id=user_id,
        project_id=project_id,
        page=page,
        page_size=page_size,
    )

    return JSONResponse(content={
        "status": "success",
        "total": len(conversations),
        "conversations": [
            {
                "conversation_id": c.conversation_id,
                "project_id": c.project_id,
                "title": c.title,
                "message_count": len(c.messages),
                "created_at": c.created_at,
                "updated_at": c.updated_at,
            }
            for c in conversations
        ],
    })


# ─── GET /api/v1/chat/conversations/{conv_id} ────────────────────────────────

@chat_router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """جيب تفاصيل محادثة كاملة مع كل الرسائل."""
    conv_model = ConversationModel(client=request.app.client)
    conv = await conv_model.get_conversation(conversation_id)

    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if conv.user_id != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Access denied")

    return JSONResponse(content={
        "status": "success",
        "conversation_id": conv.conversation_id,
        "project_id": conv.project_id,
        "title": conv.title,
        "message_count": len(conv.messages),
        "messages": [m.dict() for m in conv.messages],
        "sources": conv.sources,
        "created_at": conv.created_at,
        "updated_at": conv.updated_at,
    })


# ─── DELETE /api/v1/chat/conversations/{conv_id} ─────────────────────────────

@chat_router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """حذف محادثة بالكامل."""
    conv_model = ConversationModel(client=request.app.client)
    conv = await conv_model.get_conversation(conversation_id)

    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if conv.user_id != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Access denied")

    await conv_model.delete_conversation(conversation_id)
    return JSONResponse(content={"status": "success", "message": "Conversation deleted"})


# ─── POST /api/v1/chat/conversations/{conv_id}/clear ─────────────────────────

@chat_router.post("/conversations/{conversation_id}/clear")
async def clear_conversation(
    conversation_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """مسح كل رسائل المحادثة مع الإبقاء على الـ ID."""
    conv_model = ConversationModel(client=request.app.client)
    conv = await conv_model.get_conversation(conversation_id)

    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if conv.user_id != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Access denied")

    await conv_model.clear_conversation(conversation_id)
    return JSONResponse(content={"status": "success", "message": "Conversation cleared"})
