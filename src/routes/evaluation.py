from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from typing import List
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


class QualityDashboardRequest(BaseModel):
    project_id: str
    test_questions: List[str]
    limit: int = 5


# ── Retrieval Metrics ─────────────────────────────────────────────────────────

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


# ── RAG Full Evaluation ───────────────────────────────────────────────────────

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


# ── [NEW] Quality Dashboard ───────────────────────────────────────────────────

@eval_router.post("/quality-dashboard")
async def quality_dashboard(request: Request, body: QualityDashboardRequest):
    """
    RAG Quality Dashboard الرئيسي — بيقيس المشروع بالكامل.

    Input: قائمة أسئلة اختبار (حتى 20 سؤال)

    Output:
      - overall_score: درجة إجمالية من 100
      - grade: A/B/C/D
      - faithfulness_avg: متوسط مدى الإجابة من المصادر (مش hallucination)
      - relevancy_avg: متوسط صلة المصادر بالأسئلة
      - hallucination_rate: نسبة تقديرية للـ hallucination
      - recommendation: توصية لتحسين الجودة
      - per_question: تفاصيل كل سؤال
    """
    from src.evaluation.retrieval_metrics import RetrievalEvaluator, GenerationEvaluator
    from src.controllers.NLPController import NLPController
    from src.helpers.nlp_clients import get_embedding_client, get_vectordb_client, template_parser
    from src.models.ProjectModel import ProjectModel
    from src.models.ChunkModel import ChunkModel

    if not body.test_questions:
        raise HTTPException(status_code=400, detail="test_questions is required")

    if len(body.test_questions) > 20:
        raise HTTPException(status_code=400, detail="Maximum 20 questions per dashboard run")

    if request.app.llm_provider is None:
        raise HTTPException(status_code=503, detail="LLM provider not available")

    project_model = await ProjectModel.create_index(db_client=request.app.client)
    project = await project_model.get_project(body.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    embedding_client = get_embedding_client()
    nlp_controller = NLPController(
        vectordb_client=get_vectordb_client(),
        generation_client=request.app.llm_provider,
        embedding_client=embedding_client,
        template_parser=template_parser,
        chunk_model=ChunkModel(client=request.app.client),
    )

    per_question_results = []
    faithfulness_scores  = []
    relevancy_scores     = []
    hallucination_flags  = []

    for q in body.test_questions:
        try:
            answer, _, _, sources = await nlp_controller.answer_rag_question(
                project=project,
                query=q,
                limit=body.limit,
            )

            docs = await nlp_controller.search_vector_db_collection(
                project=project,
                text=q,
                limit=body.limit,
            )

            r_eval    = RetrievalEvaluator(embedding_client=embedding_client)
            r_metrics = await r_eval.evaluate(query=q, retrieved_docs=docs, answer=answer or "")
            g_metrics = GenerationEvaluator.evaluate(query=q, answer=answer or "", retrieved_docs=docs)

            faithfulness     = g_metrics.get("faithfulness_score", 0.0)
            relevancy        = r_metrics.get("context_relevance", r_metrics.get("avg_score", 0.0))
            is_hallucination = faithfulness < 0.3 and bool(answer)

            faithfulness_scores.append(faithfulness)
            relevancy_scores.append(relevancy)
            hallucination_flags.append(is_hallucination)

            per_question_results.append({
                "question": q,
                "answer_preview": (answer or "")[:200],
                "sources_count": len(sources) if sources else 0,
                "faithfulness_score": round(faithfulness, 3),
                "relevancy_score": round(relevancy, 3),
                "hallucination_risk": "high" if is_hallucination else "low",
                "chunk_utilization": r_metrics.get("chunk_utilization", 0.0),
            })

        except Exception as e:
            logger.error(f"[QualityDashboard] Error on question '{q}': {e}")
            per_question_results.append({
                "question": q,
                "error": str(e),
                "faithfulness_score": 0.0,
                "relevancy_score": 0.0,
                "hallucination_risk": "unknown",
            })

    # ── حساب الـ overall score ────────────────────────────────────────────────
    n = len(faithfulness_scores) or 1
    faithfulness_avg   = sum(faithfulness_scores) / n
    relevancy_avg      = sum(relevancy_scores) / n
    hallucination_rate = sum(hallucination_flags) / len(hallucination_flags) if hallucination_flags else 0

    overall_score = round(
        (faithfulness_avg * 40) +
        (relevancy_avg    * 40) +
        ((1 - hallucination_rate) * 20),
        1,
    )

    if overall_score >= 75:
        recommendation = "✅ الجودة ممتازة. النظام يستجيب بدقة عالية من المصادر."
    elif overall_score >= 50:
        recommendation = "⚠️ الجودة متوسطة. يُنصح بتحسين chunking strategy أو زيادة limit."
    else:
        recommendation = "❌ الجودة منخفضة. تحقق من جودة الـ embeddings والـ chunking."

    return {
        "status": "success",
        "project_id": body.project_id,
        "questions_tested": len(body.test_questions),
        "overall_score": overall_score,
        "grade": "A" if overall_score >= 85 else "B" if overall_score >= 70 else "C" if overall_score >= 50 else "D",
        "metrics": {
            "faithfulness_avg": round(faithfulness_avg, 3),
            "relevancy_avg": round(relevancy_avg, 3),
            "hallucination_rate": round(hallucination_rate, 3),
            "hallucination_estimate_pct": f"{hallucination_rate * 100:.1f}%",
        },
        "recommendation": recommendation,
        "per_question": per_question_results,
    }


# ── [NEW] Arabic RAG Benchmark ────────────────────────────────────────────────

class BenchmarkQuestionInput(BaseModel):
    question_id: str
    question_text: str
    expected_answer: str
    topic: str = ""
    difficulty: str = "medium"


class BenchmarkRequest(BaseModel):
    project_id: str
    questions: List[BenchmarkQuestionInput]
    strategies: List[str] = ["no_rag", "vector_rag"]


@eval_router.post("/benchmark")
async def run_arabic_benchmark(request: Request, body: BenchmarkRequest):
    """
    Arabic RAG Benchmark — يقارن استراتيجيات الـ RAG على اسئلة حقيقية.

    Input: اسئلة مع الإجابات المرجعية (ground truth)

    Strategies:
      - no_rag:     LLM بدون استرجاع — baseline
      - vector_rag: الـ system الحالي

    Output:
      - results_per_strategy: مقارنة الـ faithfulness والـ latency لكل strategy
      - winner: الـ strategy الأفضل
      - per_question_results: تفاصيل كل سؤال
      - summary: ملخص جاهز للـ academic paper
    """
    from src.evaluation.arabic_rag_benchmark import ArabicRAGBenchmark, BenchmarkQuestion
    from src.controllers.NLPController import NLPController
    from src.helpers.nlp_clients import get_embedding_client, get_vectordb_client, template_parser
    from src.models.ProjectModel import ProjectModel

    if not body.questions:
        raise HTTPException(status_code=400, detail="questions list is required")

    if len(body.questions) > 30:
        raise HTTPException(status_code=400, detail="Maximum 30 questions per benchmark run")

    if request.app.llm_provider is None:
        raise HTTPException(status_code=503, detail="LLM provider not available")

    project_model = await ProjectModel.create_index(db_client=request.app.client)
    project = await project_model.get_project(body.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    nlp_controller = NLPController(
        vectordb_client=get_vectordb_client(),
        generation_client=request.app.llm_provider,
        embedding_client=get_embedding_client(),
        template_parser=template_parser,
    )

    benchmark = ArabicRAGBenchmark(
        nlp_controller=nlp_controller,
        llm_provider=request.app.llm_provider,
    )

    questions = [
        BenchmarkQuestion(
            question_id=q.question_id,
            question_text=q.question_text,
            expected_answer=q.expected_answer,
            topic=q.topic,
            difficulty=q.difficulty,
        )
        for q in body.questions
    ]

    try:
        report = await benchmark.run(
            project=project,
            questions=questions,
            strategies=body.strategies,
        )
        return {
            "status": "success",
            **report.to_dict(),
        }
    except Exception as e:
        logger.error(f"[Benchmark] Failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
