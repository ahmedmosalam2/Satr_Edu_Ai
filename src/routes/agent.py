from fastapi import APIRouter, Request, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
import logging

logger = logging.getLogger("uvicorn.error")

agent_router = APIRouter(
    prefix="/api/v1/agent",
    tags=["Agent — Agentic RAG"],
)


class AgentQuery(BaseModel):
    project_id: str
    query: str
    language: str = "ar"
    session_id: Optional[str] = None


class AgentSessionQuery(BaseModel):
    project_id: str
    query: str
    language: str = "ar"


@agent_router.post("/ask")
async def agent_ask(request: Request, body: AgentQuery):
    from src.agent.rag_agent import RAGAgent
    from src.agent.tools.knowledge_search import KnowledgeSearchTool
    from src.agent.tools.calculator import CalculatorTool
    from src.controllers.NLPController import NLPController
    from src.helpers.nlp_clients import get_embedding_client, get_vectordb_client, template_parser
    from src.models.ProjectModel import ProjectModel

    project_model = await ProjectModel.create_index(db_client=request.app.client)
    project = await project_model.get_project(body.project_id)

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    nlp_controller = NLPController(
        vectordb_client=get_vectordb_client(),
        generation_client=None,
        embedding_client=get_embedding_client(),
        template_parser=template_parser,
    )

    if request.app.llm_provider is None:
        raise HTTPException(status_code=503, detail="LLM provider not available")

    generation_client = request.app.llm_provider

    tools = [
        KnowledgeSearchTool(nlp_controller=nlp_controller, project=project),
        CalculatorTool(),
    ]

    agent = RAGAgent(
        generation_client=generation_client,
        tools=tools,
        language=body.language,
    )

    try:
        result = await agent.run(query=body.query)
        return {
            "status": "success",
            "answer": result.answer,
            "steps": result.to_dict()["actions"],
            "steps_count": result.steps_count,
        }
    except Exception as e:
        logger.error(f"[Agent] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@agent_router.get("/tools")
async def list_available_tools():
    return {
        "status": "success",
        "tools": [
            {
                "name": "knowledge_search",
                "description": "Search project knowledge base using vector similarity",
                "usage": "Automatically triggered when answering knowledge questions",
            },
            {
                "name": "calculator",
                "description": "Evaluate mathematical expressions safely",
                "usage": "Automatically triggered when a math expression is detected",
            },
        ]
    }


@agent_router.post("/batch")
async def agent_batch_ask(
    request: Request,
    project_id: str,
    queries: List[str],
    language: str = "ar",
):
    if len(queries) > 10:
        raise HTTPException(status_code=400, detail="Maximum 10 queries per batch")

    from src.agent.rag_agent import RAGAgent
    from src.agent.tools.knowledge_search import KnowledgeSearchTool
    from src.agent.tools.calculator import CalculatorTool
    from src.controllers.NLPController import NLPController
    from src.helpers.nlp_clients import get_embedding_client, get_vectordb_client, template_parser
    from src.models.ProjectModel import ProjectModel

    project_model = await ProjectModel.create_index(db_client=request.app.client)
    project = await project_model.get_project(project_id)

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if request.app.llm_provider is None:
        raise HTTPException(status_code=503, detail="LLM provider not available")

    nlp_controller = NLPController(
        vectordb_client=get_vectordb_client(),
        generation_client=None,
        embedding_client=get_embedding_client(),
        template_parser=template_parser,
    )

    tools = [
        KnowledgeSearchTool(nlp_controller=nlp_controller, project=project),
        CalculatorTool(),
    ]

    agent = RAGAgent(
        generation_client=request.app.llm_provider,
        tools=tools,
        language=language,
    )

    results = []
    for query in queries:
        try:
            result = await agent.run(query=query)
            results.append({
                "query": query,
                "status": "success",
                "answer": result.answer,
                "steps_count": result.steps_count,
            })
        except Exception as e:
            logger.error(f"[Agent Batch] Error for query '{query}': {e}")
            results.append({
                "query": query,
                "status": "error",
                "error": str(e),
            })

    return {
        "status": "success",
        "project_id": project_id,
        "total_queries": len(queries),
        "results": results,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Multi-Agent System
# ──────────────────────────────────────────────────────────────────────────────

class SmartAgentQuery(BaseModel):
    project_id: str
    query: str
    language: str = "ar"
    student_id: Optional[str] = None


@agent_router.post("/smart-ask")
async def multi_agent_ask(request: Request, body: SmartAgentQuery):
    """
    Multi-Agent endpoint — يختار الـ agent المناسب تلقائياً:
    
    - "فهمني" / "اشرح" → Tutor Agent (شرح مبسط)
    - "اختبرني" / "quiz" → Quiz Agent (أسئلة سريعة)
    - أي سؤال تاني → Research Agent (بحث + إجابة)
    
    لو بعتت student_id هيجيب بيانات الطالب من الامتحانات
    ويكيّف الإجابة حسب مستواه.
    """
    from src.agent.agents.orchestrator import Orchestrator
    from src.agent.tools.knowledge_search import KnowledgeSearchTool
    from src.agent.tools.calculator import CalculatorTool
    from src.controllers.NLPController import NLPController
    from src.helpers.nlp_clients import get_embedding_client, get_vectordb_client, template_parser
    from src.models.ProjectModel import ProjectModel
    from src.agent.core.memory import AgentMemory

    # 1. Load project
    project_model = await ProjectModel.create_index(db_client=request.app.client)
    project = await project_model.get_project(body.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if request.app.llm_provider is None:
        raise HTTPException(status_code=503, detail="LLM provider not available")

    # 2. Build student context if student_id provided
    student_level = "intermediate"
    student_context = ""
    if body.student_id:
        try:
            db = request.app.client["Satr-Edu"]
            cursor = db["exam_results"].find({"student_id": body.student_id})
            results = []
            async for doc in cursor:
                doc.pop("_id", None)
                results.append(doc)

            if results:
                memory = AgentMemory()
                memory.update_student_from_results(results)
                student_level = memory.student.level
                student_context = memory.student.to_context()
                logger.info(f"[MultiAgent] Student {body.student_id}: level={student_level}")
        except Exception as e:
            logger.warning(f"[MultiAgent] Could not load student profile: {e}")

    # 3. Setup tools
    nlp_controller = NLPController(
        vectordb_client=get_vectordb_client(),
        generation_client=None,
        embedding_client=get_embedding_client(),
        template_parser=template_parser,
    )

    tools = [
        KnowledgeSearchTool(nlp_controller=nlp_controller, project=project),
        CalculatorTool(),
    ]

    # 4. Run orchestrator
    orchestrator = Orchestrator(
        generation_client=request.app.llm_provider,
        tools=tools,
        language=body.language,
        student_level=student_level,
        student_context=student_context,
    )

    try:
        result = await orchestrator.run(query=body.query)
        return {
            "status": "success",
            "agent_used": result.agent_used,
            "intent_detected": result.intent,
            "student_level": student_level,
            "answer": result.answer,
            "steps_count": result.steps_count,
            "actions": result.actions,
            "sources": result.sources,
            "conversation_log": result.conversation_log,
        }
    except Exception as e:
        logger.error(f"[MultiAgent] Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

