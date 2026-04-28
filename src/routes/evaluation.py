from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import logging

logger = logging.getLogger("uvicorn.error")

eval_router = APIRouter(
    prefix="/api/v1/eval",
    tags=["Evaluation — RAG Quality"],
)


class EvalQuery(BaseModel):
    project_id: str
    query: str
    limit: int = 5


@eval_router.post("/retrieval")
async def evaluate_retrieval(request: Request, body: EvalQuery):
    from src.evaluation.retrieval_metrics import RetrievalEvaluator
    from src.controllers.NLPController import NLPController
    from src.helpers.nlp_clients import get_embedding_client, get_vectordb_client, template_parser
    from src.models.ProjectModel import ProjectModel

    project_model = await ProjectModel.create_index(db_client=request.app.client)
    project = await project_model.get_project(body.project_id)

    embedding_client = get_embedding_client()
    nlp_controller = NLPController(
        vectordb_client=get_vectordb_client(),
        generation_client=None,
        embedding_client=embedding_client,
        template_parser=template_parser,
    )

    results = await nlp_controller.search_vector_db_collection(
        project=project,
        text=body.query,
        limit=body.limit,
    )

    evaluator = RetrievalEvaluator(embedding_client=embedding_client)
    metrics = await evaluator.evaluate(
        query=body.query,
        retrieved_docs=results,
    )

    return {
        "status": "success",
        "query": body.query,
        "metrics": metrics,
        "retrieved_count": len(results),
    }


@eval_router.post("/rag")
async def evaluate_rag(request: Request, body: EvalQuery):
    from src.evaluation.retrieval_metrics import RetrievalEvaluator, GenerationEvaluator
    from src.controllers.NLPController import NLPController
    from src.helpers.nlp_clients import get_embedding_client, get_vectordb_client, template_parser
    from src.models.ProjectModel import ProjectModel
    from src.models.ChunkModel import ChunkModel

    project_model = await ProjectModel.create_index(db_client=request.app.client)
    project = await project_model.get_project(body.project_id)

    embedding_client = get_embedding_client()

    if request.app.llm_provider is None:
        raise HTTPException(status_code=503, detail="LLM provider not available")

    nlp_controller = NLPController(
        vectordb_client=get_vectordb_client(),
        generation_client=request.app.llm_provider,
        embedding_client=embedding_client,
        template_parser=template_parser,
        chunk_model=ChunkModel(client=request.app.client),
    )

    answer, full_prompt, chat_history, sources = await nlp_controller.answer_rag_question(
        project=project,
        query=body.query,
        limit=body.limit,
    )

    results = await nlp_controller.search_vector_db_collection(
        project=project,
        text=body.query,
        limit=body.limit,
    )

    retrieval_eval = RetrievalEvaluator(embedding_client=embedding_client)
    retrieval_metrics = await retrieval_eval.evaluate(
        query=body.query,
        retrieved_docs=results,
        answer=answer or "",
    )

    gen_metrics = GenerationEvaluator.evaluate(
        query=body.query,
        answer=answer or "",
        retrieved_docs=results,
    )

    return {
        "status": "success",
        "query": body.query,
        "answer": answer,
        "sources": sources,
        "retrieval_metrics": retrieval_metrics,
        "generation_metrics": gen_metrics,
    }
