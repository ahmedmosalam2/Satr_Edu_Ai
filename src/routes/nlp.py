from fastapi import APIRouter, status, Request, BackgroundTasks
from fastapi.responses import JSONResponse
from src.routes.schemes.nlp import PushRequest, SearchRequest, MultiSearchRequest
from src.models.ProjectModel import ProjectModel
from src.models.ChunkModel import ChunkModel
from src.controllers.NLPController import NLPController
from src.models.enums.Response import ResponseSignal as Response
from src.helpers.nlp_clients import get_vectordb_client, get_embedding_client, get_generation_client, template_parser
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


def _serialize_search_result(result):
    payload = getattr(result, "payload", {}) or {}
    return {
        "id": str(getattr(result, "id", "")),
        "score": getattr(result, "score", None),
        "payload": payload,
    }

@nlp_router.post("/index/push/{project_id}")
async def index_project(request: Request, project_id: str, push_request: PushRequest, background_tasks: BackgroundTasks):
    project_id = project_id.strip()

    try:
        db_client = request.app.client
        if db_client is None:
            raise AttributeError
    except AttributeError:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "signal": Response.RAG_ANSWER_ERROR.value,
                "message": "Database connection is not available."
            }
        )

    project_model = await ProjectModel.create_index(db_client=db_client)
    project = await project_model.get_project(project_id=project_id)
    chunk_model = await ChunkModel.create_index(db_client=db_client)

    nlp_controller = NLPController(
        vectordb_client=get_or_init_vectordb(),
        generation_client=get_or_init_generation(),
        embedding_client=get_or_init_embedding(),
        template_parser=template_parser,
        chunk_model=chunk_model,
    )

    async def _process_chunks_in_background():
        page = 1
        page_size = 50
        indexed_count = 0
        try:
            while True:
                chunks = await chunk_model.get_project_chunks(
                    project_id=project.project_id,
                    page=page,
                    page_size=page_size,
                )
                if not chunks:
                    break
                chunks_ids = list(range(indexed_count, indexed_count + len(chunks)))
                for chunk in chunks:
                    if not chunk.chunk_metadata:
                        chunk.chunk_metadata = {}
                    chunk.chunk_metadata["chunk_id"] = chunk.chunk_id
                    chunk.chunk_metadata["chunk_order"] = chunk.chunk_order
                    if "source" not in chunk.chunk_metadata and "source_file" not in chunk.chunk_metadata:
                        chunk.chunk_metadata["source_file"] = (
                            chunk.chunk_id.split("_")[2]
                            if chunk.chunk_id.count("_") >= 2 else chunk.chunk_id
                        )
                await nlp_controller.index_into_vector_db(
                    project=project,
                    chunks=chunks,
                    chunks_ids=chunks_ids,
                    do_reset=(push_request.do_reset and page == 1),
                )
                indexed_count += len(chunks)
                page += 1
            logger.info(f"Background indexing for {project_id} completed: {indexed_count} chunks.")
        except Exception:
            logger.exception(f"Background indexing for {project_id} failed.")

    background_tasks.add_task(_process_chunks_in_background)
    return JSONResponse(
        content={
            "signal": Response.INSERT_INTO_VECTORDB_SUCCESS.value,
            "message": "Indexing started in the background"
        }
    )

@nlp_router.get("/index/info/{project_id}")
async def get_project_index_info(request: Request, project_id: str):
    try:
        db_client = request.app.client
        if db_client is None: raise AttributeError
    except AttributeError:
        return JSONResponse(status_code=503, content={"message": "DB not ready"})

    project_model = await ProjectModel.create_index(db_client=db_client)
    project = await project_model.get_project(project_id=project_id)
    chunk_model = ChunkModel(client=db_client, project_id=project_id)
    nlp_controller = NLPController(
        vectordb_client=get_or_init_vectordb(),
        generation_client=get_or_init_generation(),
        embedding_client=get_or_init_embedding(),
        template_parser=template_parser,
        chunk_model=chunk_model,
    )
    collection_info = await nlp_controller.get_vector_db_collection_info(project=project)
    return JSONResponse(
        content={
            "signal": Response.VECTORDB_COLLECTION_RETRIEVED.value,
            "collection_info": collection_info
        }
    )

@nlp_router.post("/search/{project_id}")
async def nlp_search(request: Request, project_id: str, search_request: SearchRequest):
    logger.info(f"NLP Search hit for project: {project_id}")
    try:
        db_client = request.app.client
        project_model = await ProjectModel.create_index(db_client=db_client)
        project = await project_model.get_project(project_id=project_id)

        if not project:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"signal": Response.PROJECT_NOT_FOUND.value, "message": "Project not found"}
            )

        nlp_controller = NLPController(
            vectordb_client=get_or_init_vectordb(),
            generation_client=get_or_init_generation(),
            embedding_client=get_or_init_embedding(),
            template_parser=template_parser,
            chunk_model=ChunkModel(client=db_client, project_id=project_id),
        )

        results = await nlp_controller.search_vector_db_collection(
            project=project,
            text=search_request.text,
            limit=search_request.limit
        )

        if not results:
            return {
                "status": Response.SUCCESS.value,
                "message": "No results found",
                "data": []
            }

        return {
            "status": Response.SUCCESS.value,
            "message": f"Found {len(results)} results",
            "data": [_serialize_search_result(r) for r in results]
        }

    except Exception as e:
        logger.error(f"Error in nlp_search: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"signal": Response.RAG_ANSWER_ERROR.value, "message": str(e)}
        )

@nlp_router.post("/answer/{project_id}")
async def nlp_answer(request: Request, project_id: str, search_request: SearchRequest):
    logger.info(f"NLP Answer hit for project: {project_id}")
    try:
        db_client = request.app.client
        project_model = await ProjectModel.create_index(db_client=db_client)
        project = await project_model.get_project(project_id=project_id)

        if not project:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={"signal": Response.PROJECT_NOT_FOUND.value, "message": "Project not found"}
            )

        nlp_controller = NLPController(
            vectordb_client=get_or_init_vectordb(),
            generation_client=get_or_init_generation(),
            embedding_client=get_or_init_embedding(),
            template_parser=template_parser,
            chunk_model=ChunkModel(client=db_client, project_id=project_id),
        )

        answer, _, _, sources = await nlp_controller.answer_rag_question(
            project=project,
            query=search_request.text,
            limit=search_request.limit
        )

        if not answer:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={"signal": Response.RAG_ANSWER_ERROR.value, "message": "Failed to generate answer"}
            )

        return {
            "status": Response.SUCCESS.value,
            "message": "Answer generated successfully",
            "data": {
                "answer": answer,
                "sources": sources
            }
        }

    except Exception as e:
        logger.error(f"Error in nlp_answer: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"signal": Response.RAG_ANSWER_ERROR.value, "message": str(e)}
        )


# ──────────────────────────────────────────────────────────────────────────────
# Multi-Project RAG
# ──────────────────────────────────────────────────────────────────────────────

@nlp_router.post("/search-multi")
async def nlp_search_multi(request: Request, body: MultiSearchRequest):
    """
    Search across multiple projects at once.
    Merges results from all projects sorted by relevance score.
    """
    logger.info(f"Multi-project search: {len(body.project_ids)} projects, query='{body.text[:50]}'")
    try:
        db_client = request.app.client
        if db_client is None:
            return JSONResponse(
                status_code=503,
                content={"signal": Response.RAG_ANSWER_ERROR.value, "message": "DB not ready"}
            )

        project_model = await ProjectModel.create_index(db_client=db_client)

        # Load all requested projects
        projects = []
        not_found = []
        for pid in body.project_ids:
            project = await project_model.get_project(project_id=pid.strip())
            if project:
                projects.append(project)
            else:
                not_found.append(pid)

        if not projects:
            return JSONResponse(
                status_code=404,
                content={"signal": Response.PROJECT_NOT_FOUND.value,
                         "message": "None of the requested projects were found"}
            )

        nlp_controller = NLPController(
            vectordb_client=get_or_init_vectordb(),
            generation_client=get_or_init_generation(),
            embedding_client=get_or_init_embedding(),
            template_parser=template_parser,
        )

        results = await nlp_controller.search_multiple_projects(
            projects=projects,
            text=body.text,
            limit_per_project=body.limit_per_project,
        )

        return {
            "status": Response.SUCCESS.value,
            "message": f"Found {len(results)} results across {len(projects)} projects",
            "projects_searched": [p.project_id for p in projects],
            "projects_not_found": not_found,
            "data": [_serialize_multi_result(r) for r in results]
        }

    except Exception as e:
        logger.error(f"Error in multi-project search: {e}")
        return JSONResponse(
            status_code=500,
            content={"signal": Response.RAG_ANSWER_ERROR.value, "message": str(e)}
        )


@nlp_router.post("/answer-multi")
async def nlp_answer_multi(request: Request, body: MultiSearchRequest):
    """
    Generate a RAG answer using context from multiple projects.
    The AI pulls relevant info from all projects and combines them.
    """
    logger.info(f"Multi-project answer: {len(body.project_ids)} projects, query='{body.text[:50]}'")
    try:
        db_client = request.app.client
        if db_client is None:
            return JSONResponse(
                status_code=503,
                content={"signal": Response.RAG_ANSWER_ERROR.value, "message": "DB not ready"}
            )

        project_model = await ProjectModel.create_index(db_client=db_client)

        projects = []
        not_found = []
        for pid in body.project_ids:
            project = await project_model.get_project(project_id=pid.strip())
            if project:
                projects.append(project)
            else:
                not_found.append(pid)

        if not projects:
            return JSONResponse(
                status_code=404,
                content={"signal": Response.PROJECT_NOT_FOUND.value,
                         "message": "None of the requested projects were found"}
            )

        nlp_controller = NLPController(
            vectordb_client=get_or_init_vectordb(),
            generation_client=get_or_init_generation(),
            embedding_client=get_or_init_embedding(),
            template_parser=template_parser,
        )

        answer, sources = await nlp_controller.answer_rag_multi_project(
            projects=projects,
            query=body.text,
            limit_per_project=body.limit_per_project,
        )

        if not answer:
            return JSONResponse(
                status_code=400,
                content={"signal": Response.RAG_ANSWER_ERROR.value,
                         "message": "Could not generate answer. No relevant content found in the given projects."}
            )

        return {
            "status": Response.SUCCESS.value,
            "message": "Multi-project answer generated successfully",
            "projects_searched": [p.project_id for p in projects],
            "projects_not_found": not_found,
            "data": {
                "answer": answer,
                "sources": sources
            }
        }

    except Exception as e:
        logger.error(f"Error in multi-project answer: {e}")
        return JSONResponse(
            status_code=500,
            content={"signal": Response.RAG_ANSWER_ERROR.value, "message": str(e)}
        )


def _serialize_multi_result(result):
    """Serialize a search result with project info."""
    payload = getattr(result, "payload", {}) or {}
    return {
        "id": str(getattr(result, "id", "")),
        "score": getattr(result, "score", None),
        "project_id": payload.get("_project_id", ""),
        "project_name": payload.get("_project_name", ""),
        "payload": {
            k: v for k, v in payload.items()
            if not k.startswith("_")  # exclude internal fields
        },
    }

