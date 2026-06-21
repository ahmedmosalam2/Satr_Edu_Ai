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
    from src.agent.tools.concept_map import ConceptMapTool
    from src.agent.tools.python_scratchpad import PythonScratchpadTool
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
        ConceptMapTool(nlp_controller=nlp_controller, project=project, generation_client=generation_client),
        PythonScratchpadTool(),
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
            {
                "name": "concept_map",
                "description": "Generate concept maps and visual summaries from course contents",
                "usage": "Automatically triggered when visual maps, mind maps, or diagrams are requested",
            },
            {
                "name": "python_scratchpad",
                "description": "Run Python code safely in a playground sandbox",
                "usage": "Automatically triggered when code execution or sandboxing is requested",
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
    conversation_id: Optional[str] = None   # لو عايز يكمل محادثة قديمة
    auto_quiz: bool = False                 # لو True: بعد الشرح يولد أسئلة تلقائياً


@agent_router.post("/smart-ask")
async def multi_agent_ask(request: Request, body: SmartAgentQuery):
    """
    Multi-Agent endpoint — يختار الـ agent المناسب تلقائياً:
    
    - "فهمني" / "اشرح" / "explain" → Tutor Agent (شرح مبسط)
    - "اختبرني" / "quiz me" → Quiz Agent (أسئلة سريعة)
    - أي سؤال تاني → Research Agent (بحث + إجابة)
    
    Features:
    - conversation_id: يكمل محادثة قديمة (يحفظ التاريخ في MongoDB)
    - student_id: يجيب مستوى الطالب ويكيّف الإجابة
    - auto_quiz: بعد الشرح يولد أسئلة تلقائياً (Tutor → Quiz handoff)
    """
    from src.agent.agents.orchestrator import Orchestrator
    from src.agent.tools.knowledge_search import KnowledgeSearchTool
    from src.agent.tools.calculator import CalculatorTool
    from src.controllers.NLPController import NLPController
    from src.helpers.nlp_clients import get_embedding_client, get_vectordb_client, template_parser
    from src.models.ProjectModel import ProjectModel
    from src.models.ConversationModel import ConversationModel
    from src.agent.core.memory import AgentMemory

    db_client = request.app.client

    # 1. Load project
    project_model = await ProjectModel.create_index(db_client=db_client)
    project = await project_model.get_project(body.project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if request.app.llm_provider is None:
        raise HTTPException(status_code=503, detail="LLM provider not available")

    # 2. Handle conversation persistence
    conv_model = ConversationModel(client=db_client)
    conversation = None
    is_new = False
    user_id = body.student_id or "anonymous"

    if body.conversation_id:
        conversation = await conv_model.get_conversation(body.conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        conversation = await conv_model.create_conversation(
            project_id=body.project_id,
            user_id=user_id,
            first_message=body.query,
        )
        is_new = True

    # 3. Build student context if student_id provided
    student_level = "intermediate"
    student_context = ""
    if body.student_id:
        try:
            db = db_client["Satr-Edu"]
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

    # 4. Setup tools
    from src.agent.tools.concept_map import ConceptMapTool
    from src.agent.tools.python_scratchpad import PythonScratchpadTool

    nlp_controller = NLPController(
        vectordb_client=get_vectordb_client(),
        generation_client=None,
        embedding_client=get_embedding_client(),
        template_parser=template_parser,
    )

    tools = [
        KnowledgeSearchTool(nlp_controller=nlp_controller, project=project),
        CalculatorTool(),
        ConceptMapTool(nlp_controller=nlp_controller, project=project, generation_client=request.app.llm_provider),
        PythonScratchpadTool(),
    ]

    # 5. Run orchestrator
    orchestrator = Orchestrator(
        generation_client=request.app.llm_provider,
        tools=tools,
        language=body.language,
        student_level=student_level,
        student_context=student_context,
    )

    # Load previous conversation into orchestrator memory
    if conversation and conversation.messages:
        for msg in conversation.messages[-10:]:
            orchestrator.memory.add_turn(msg.role, msg.content)

    try:
        result = await orchestrator.run(query=body.query)

        # ── Auto-handoff: Tutor → Quiz ────────────────────────────────
        quiz_result = None
        if body.auto_quiz and result.agent_used == "tutor" and result.answer:
            logger.info("[MultiAgent] Auto-handoff: tutor → quiz")
            quiz_result_raw = await orchestrator._run_quiz(body.query)
            quiz_result = quiz_result_raw.answer

        # ── Save conversation to MongoDB ──────────────────────────────
        answer_text = result.answer or ""
        if quiz_result:
            answer_text += f"\n\n--- أسئلة سريعة ---\n{quiz_result}"

        await conv_model.append_turn(
            conversation_id=conversation.conversation_id,
            user_text=body.query,
            assistant_text=answer_text,
            sources=result.sources,
        )

        response = {
            "status": "success",
            "conversation_id": conversation.conversation_id,
            "is_new_conversation": is_new,
            "agent_used": result.agent_used,
            "intent_detected": result.intent,
            "intent_reasoning": result.intent_reasoning,
            "intent_method": result.intent_method,
            "confidence": round(result.confidence, 2),
            "confidence_label": result.confidence_label,
            "student_level": student_level,
            "answer": result.answer,
            "steps_count": result.steps_count,
            "actions": result.actions,
            "sources": result.sources,
            "thinking_trace": result.thinking_trace,
            "follow_up_questions": result.follow_up_questions,
            "conversation_log": result.conversation_log,
        }

        if quiz_result:
            response["auto_quiz"] = quiz_result

        return response

    except Exception as e:
        logger.error(f"[MultiAgent] Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


class SandboxQuery(BaseModel):
    code: str


@agent_router.post("/sandbox")
async def run_sandbox(body: SandboxQuery):
    """
    Direct code execution endpoint for the student code playground.
    """
    from src.agent.tools.python_scratchpad import PythonScratchpadTool

    tool = PythonScratchpadTool()
    try:
        output = await tool.execute(code=body.code)
        return {
            "status": "success",
            "result": output
        }
    except Exception as e:
        logger.error(f"[Sandbox] Error running code: {e}")
        raise HTTPException(status_code=500, detail=str(e))


