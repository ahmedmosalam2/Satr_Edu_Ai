from fastapi import FastAPI, APIRouter, status, Request
from fastapi.responses import JSONResponse
from src.routes.schemes.nlp import PushRequest, SearchRequest
from src.models.ProjectModel import ProjectModel
from src.models.ChunkModel import ChunkModel
from src.controllers.NLPController import NLPController
from src.models.enums.Response import ResponseSignal as Response
from src.helpers.nlp_clients import LLMWrapper, get_vectordb_client, get_embedding_client, get_generation_client, template_parser
from tqdm.auto import tqdm

import logging

logger = logging.getLogger('uvicorn.error')

nlp_router = APIRouter(
    prefix="/api/v1/nlp",
    tags=["api_v1", "nlp"],
)

_vectordb_client = None
_embedding_client = None
_generation_client = None

def get_or_init_vectordb():
    global _vectordb_client
    if _vectordb_client is None:
        _vectordb_client = get_vectordb_client()
    return _vectordb_client

def get_or_init_embedding():
    global _embedding_client
    if _embedding_client is None:
        _embedding_client = get_embedding_client()
    return _embedding_client

def get_or_init_generation():
    global _generation_client
    if _generation_client is None:
        _generation_client = get_generation_client()
    return _generation_client


@nlp_router.post("/index/push/{project_id}")
async def index_project(request: Request, project_id: str, push_request: PushRequest):

    project_model = await ProjectModel.create_index(
        db_client=request.app.client
    )

    project = await project_model.get_project(
        project_id=project_id
    )

    chunk_model = await ChunkModel.create_index(
        db_client=request.app.client
    )

    nlp_controller = NLPController(
        vectordb_client=get_or_init_vectordb(),
        generation_client=get_or_init_generation(),
        embedding_client=get_or_init_embedding(),
        template_parser=template_parser,
    )

    page = 1
    page_size = 50
    indexed_count = 0

    while True:
        chunks = await chunk_model.get_project_chunks(
            project_id=project.project_id,
            page=page,
            page_size=page_size,
        )

        if not chunks or len(chunks) == 0:
            break

        chunks_ids = list(range(indexed_count, indexed_count + len(chunks)))

        # ── Enrich each chunk's metadata with source info for RAG citations ──
        for chunk in chunks:
            if not chunk.chunk_metadata:
                chunk.chunk_metadata = {}
            chunk.chunk_metadata["chunk_id"]    = chunk.chunk_id
            chunk.chunk_metadata["chunk_order"] = chunk.chunk_order
            # source_file: pick from existing metadata keys or chunk_id prefix
            if "source" not in chunk.chunk_metadata and "source_file" not in chunk.chunk_metadata:
                chunk.chunk_metadata["source_file"] = chunk.chunk_id.split("_")[2] if chunk.chunk_id.count("_") >= 2 else chunk.chunk_id

        _ = await nlp_controller.index_into_vector_db(
            project=project,
            chunks=chunks,
            chunks_ids=chunks_ids,
            do_reset=(push_request.do_reset and page == 1),
        )

        indexed_count += len(chunks)
        page += 1

    return JSONResponse(
        content={
            "signal": Response.INSERT_INTO_VECTORDB_SUCCESS.value,
            "indexed_count": indexed_count
        }
    )


@nlp_router.get("/index/info/{project_id}")
async def get_project_index_info(request: Request, project_id: str):

    project_model = await ProjectModel.create_index(
        db_client=request.app.client
    )

    project = await project_model.get_project(
        project_id=project_id
    )

    nlp_controller = NLPController(
        vectordb_client=get_or_init_vectordb(),
        generation_client=get_or_init_generation(),
        embedding_client=get_or_init_embedding(),
        template_parser=template_parser,
    )

    collection_info = await nlp_controller.get_vector_db_collection_info(project=project)

    return JSONResponse(
        content={
            "signal": Response.VECTORDB_COLLECTION_RETRIEVED.value,
            "collection_info": collection_info
        }
    )


@nlp_router.post("/index/search/{project_id}")
async def search_index(request: Request, project_id: str, search_request: SearchRequest):

    project_model = await ProjectModel.create_index(
        db_client=request.app.client
    )

    project = await project_model.get_project(
        project_id=project_id
    )

    nlp_controller = NLPController(
        vectordb_client=get_or_init_vectordb(),
        generation_client=get_or_init_generation(),
        embedding_client=get_or_init_embedding(),
        template_parser=template_parser,
    )

    results = await nlp_controller.search_vector_db_collection(
        project=project, text=search_request.text, limit=search_request.limit
    )

    if not results:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "signal": Response.VECTORDB_SEARCH_ERROR.value
            }
        )

    return JSONResponse(
        content={
            "signal": Response.VECTORDB_SEARCH_SUCCESS.value,
            "results": [result.dict() for result in results]
        }
    )


@nlp_router.post("/index/answer/{project_id}")
async def answer_rag(request: Request, project_id: str, search_request: SearchRequest):

    project_model = await ProjectModel.create_index(
        db_client=request.app.client
    )

    project = await project_model.get_project(
        project_id=project_id
    )

    nlp_controller = NLPController(
        vectordb_client=get_or_init_vectordb(),
        generation_client=get_or_init_generation(),
        embedding_client=get_or_init_embedding(),
        template_parser=template_parser,
    )

    answer, full_prompt, chat_history, sources = await nlp_controller.answer_rag_question(
        project=project,
        query=search_request.text,
        limit=search_request.limit,
    )

    if not answer:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "signal": Response.RAG_ANSWER_ERROR.value
            }
        )

    return JSONResponse(
        content={
            "signal": Response.RAG_ANSWER_SUCCESS.value,
            "answer": answer,
            "sources": sources,           # ← citations: chunk_id, source_file, chunk_order, score, snippet
            "full_prompt": full_prompt,
            "chat_history": chat_history
        }
    )
