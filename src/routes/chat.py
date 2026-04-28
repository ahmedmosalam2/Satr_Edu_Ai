from fastapi import APIRouter, Request, HTTPException, Depends, Query
from fastapi.responses import JSONResponse
from typing import Optional
import logging

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


@chat_router.post("/{project_id}", response_model=ChatResponse)
async def chat(
    project_id: str,
    body: ChatRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]
    db_client = request.app.client

    if db_client is None:
        raise HTTPException(status_code=503, detail="Database not available")

    project_model = await ProjectModel.create_index(db_client=db_client)
    project = await project_model.get_project(project_id=project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    conv_model = ConversationModel(client=db_client)
    is_new = False

    if body.conversation_id:
        conversation = await conv_model.get_conversation(body.conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        if conversation.user_id != user_id:
            raise HTTPException(status_code=403, detail="Access denied")
    else:
        conversation = await conv_model.create_conversation(
            project_id=project_id,
            user_id=user_id,
            first_message=body.text,
        )
        is_new = True

    recent_messages = conversation.messages[-6:] if conversation.messages else []
    nlp = NLPController(
        vectordb_client=_get_vectordb(),
        generation_client=_get_generation(),
        embedding_client=_get_embedding(),
        template_parser=template_parser,
        chunk_model=ChunkModel(client=db_client, project_id=project_id),
    )

    previous_messages = [
        {"role": msg.role, "content": msg.content}
        for msg in recent_messages
    ]

    try:
        answer, _, _, sources = await nlp.answer_rag_question(
            project=project,
            query=body.text,
            limit=body.limit,
            previous_messages=previous_messages,
        )
    except Exception as e:
        logger.error(f"[Chat] RAG error: {e}")
        raise HTTPException(status_code=500, detail=f"RAG error: {str(e)}")

    if not answer:
        answer = "لم أجد إجابة كافية في قاعدة المعرفة. يرجى التأكد من رفع ومعالجة ملفات المشروع أولاً."

    await conv_model.append_turn(
        conversation_id=conversation.conversation_id,
        user_text=body.text,
        assistant_text=answer,
        sources=sources,
    )

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


@chat_router.get("/conversations")
async def list_my_conversations(
    request: Request,
    project_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    current_user: dict = Depends(get_current_user),
):
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


@chat_router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
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


@chat_router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    conv_model = ConversationModel(client=request.app.client)
    conv = await conv_model.get_conversation(conversation_id)

    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if conv.user_id != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Access denied")

    await conv_model.delete_conversation(conversation_id)
    return JSONResponse(content={"status": "success", "message": "Conversation deleted"})


@chat_router.post("/conversations/{conversation_id}/clear")
async def clear_conversation(
    conversation_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    conv_model = ConversationModel(client=request.app.client)
    conv = await conv_model.get_conversation(conversation_id)

    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if conv.user_id != current_user["user_id"]:
        raise HTTPException(status_code=403, detail="Access denied")

    await conv_model.clear_conversation(conversation_id)
    return JSONResponse(content={"status": "success", "message": "Conversation cleared"})
