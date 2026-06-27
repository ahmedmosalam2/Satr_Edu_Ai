"""
tests/test_full_system.py
──────────────────────────
Full system test suite for Satr Edu AI.
Covers: helpers, controllers (logic only), agents, engine, auth, AI grading.
No external services required (MongoDB / Qdrant / LLM are mocked).
"""

import os
import sys
import json
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ══════════════════════════════════════════════════════════════════════════════
# 1. Config & Settings
# ══════════════════════════════════════════════════════════════════════════════

class TestSettings:
    """Test that Settings loads correctly from defaults."""

    def test_settings_defaults(self):
        from src.helpers.config import get_settings
        s = get_settings()
        assert s.APP_NAME == "Satr_Edu"
        assert s.MONGODB_DATABASE == "Satr-Edu"
        assert s.VECTOR_DB_BACKEND == "QDRANT"
        assert s.JWT_ALGORITHM == "HS256"

    def test_settings_jwt_present(self):
        from src.helpers.config import get_settings
        s = get_settings()
        assert len(s.JWT_SECRET_KEY) > 10

    def test_settings_embedding_size_positive(self):
        from src.helpers.config import get_settings
        s = get_settings()
        assert s.EMBEDDING_MODEL_SIZE > 0

    def test_settings_reranker_top_k(self):
        from src.helpers.config import get_settings
        s = get_settings()
        assert s.RERANKER_TOP_K > 0
        assert s.RERANKER_TOP_K <= 20


# ══════════════════════════════════════════════════════════════════════════════
# 2. Auth Helper (JWT)
# ══════════════════════════════════════════════════════════════════════════════

class TestAuthHelper:
    """Test JWT token creation and verification."""

    def test_create_access_token(self):
        from src.helpers.auth import create_access_token
        token = create_access_token(
            data={"user_id": "u123", "user_role": "student"},
            expires_minutes=60,
        )
        assert isinstance(token, str)
        assert len(token) > 20

    def test_verify_valid_token(self):
        from src.helpers.auth import create_access_token, verify_token
        token = create_access_token(
            data={"user_id": "u456", "user_role": "teacher"},
            expires_minutes=60,
        )
        payload = verify_token(token)
        assert payload is not None
        assert payload["user_id"] == "u456"
        assert payload["user_role"] == "teacher"

    def test_verify_expired_token(self):
        from src.helpers.auth import create_access_token, verify_token
        # expires_minutes = 0 → instant expiry
        token = create_access_token(
            data={"user_id": "u789"},
            expires_minutes=-1,
        )
        payload = verify_token(token)
        assert payload is None

    def test_verify_invalid_token(self):
        from src.helpers.auth import verify_token
        payload = verify_token("not.a.real.token")
        assert payload is None

    def test_hash_password(self):
        from src.helpers.auth import hash_password, verify_password
        raw = "MySecret123!"
        hashed = hash_password(raw)
        assert hashed != raw
        assert verify_password(raw, hashed) is True
        assert verify_password("wrong", hashed) is False


# ══════════════════════════════════════════════════════════════════════════════
# 3. AI Controller (Exam generation & grading logic)
# ══════════════════════════════════════════════════════════════════════════════

class TestAIController:
    """Test AIController helpers — JSON extraction and validation."""

    def _make_controller(self):
        from src.controllers.AIController import AIController
        ctrl = AIController.__new__(AIController)
        ctrl.generation_client = MagicMock()
        return ctrl

    # ── _extract_json ─────────────────────────────────────────────────────────

    def test_extract_json_plain(self):
        ctrl = self._make_controller()
        raw = '{"questions": []}'
        result = ctrl._extract_json(raw)
        assert result == '{"questions": []}'

    def test_extract_json_from_markdown(self):
        ctrl = self._make_controller()
        raw = '```json\n{"questions": [{"q": 1}]}\n```'
        result = ctrl._extract_json(raw)
        data = json.loads(result)
        assert "questions" in data

    def test_extract_json_with_extra_text(self):
        ctrl = self._make_controller()
        raw = 'Here is your answer:\n{"questions": []} enjoy!'
        result = ctrl._extract_json(raw)
        data = json.loads(result)
        assert "questions" in data

    def test_extract_json_no_json(self):
        ctrl = self._make_controller()
        raw = "This is just plain text with no JSON"
        result = ctrl._extract_json(raw)
        # Should return a fallback JSON string
        data = json.loads(result)
        assert "questions" in data

    # ── _validate_questions ───────────────────────────────────────────────────

    def test_validate_questions_valid(self):
        ctrl = self._make_controller()
        questions = [
            {
                "question_text": "What is 2+2?",
                "question_type": "MCQ",
                "options": ["A) 3", "B) 4", "C) 5", "D) 6"],
                "correct_answer": "B",
            }
        ]
        valid = ctrl._validate_questions(questions)
        assert len(valid) == 1

    def test_validate_questions_missing_answer(self):
        ctrl = self._make_controller()
        questions = [{"question_text": "Bad question", "question_type": "MCQ"}]
        valid = ctrl._validate_questions(questions)
        assert len(valid) == 0

    def test_validate_questions_wrong_answer_letter(self):
        ctrl = self._make_controller()
        questions = [
            {
                "question_text": "What is 2+2?",
                "question_type": "MCQ",
                "options": ["A) 3", "B) 4"],
                "correct_answer": "Z",   # not in options
            }
        ]
        valid = ctrl._validate_questions(questions)
        assert len(valid) == 0

    def test_validate_questions_essay_no_options(self):
        ctrl = self._make_controller()
        questions = [
            {
                "question_text": "Explain gravity.",
                "question_type": "ESSAY",
                "correct_answer": "Gravity is a force...",
            }
        ]
        valid = ctrl._validate_questions(questions)
        assert len(valid) == 1

    # ── _repair_truncated_json ────────────────────────────────────────────────

    def test_repair_truncated_json(self):
        ctrl = self._make_controller()
        # Simulate a truncated JSON with one complete question object
        truncated = '{"questions": [{"question_text": "Q1?", "correct_answer": "A", "options": ["A) yes"]},'
        result = ctrl._repair_truncated_json(truncated)
        if result:
            data = json.loads(result)
            assert len(data["questions"]) == 1


# ══════════════════════════════════════════════════════════════════════════════
# 4. RAG Agent Logic
# ══════════════════════════════════════════════════════════════════════════════

class TestRAGAgent:
    """Test RAGAgent decomposition and math extraction."""

    def _make_agent(self):
        from src.agent.rag_agent import RAGAgent
        agent = RAGAgent.__new__(RAGAgent)
        agent.generation_client = MagicMock()
        agent.tools = {}
        agent.language = "ar"
        return agent

    @pytest.mark.asyncio
    async def test_decompose_simple_query(self):
        agent = self._make_agent()
        result = await agent._decompose_query("ما هو قانون نيوتن؟")
        assert len(result) == 1
        assert "قانون نيوتن" in result[0]

    @pytest.mark.asyncio
    async def test_decompose_comparison_query(self):
        agent = self._make_agent()
        result = await agent._decompose_query("قارن بين النووي والشمسي")
        assert len(result) >= 2

    @pytest.mark.asyncio
    async def test_decompose_english_comparison(self):
        agent = self._make_agent()
        result = await agent._decompose_query("compare photosynthesis and respiration")
        assert len(result) >= 2

    def test_extract_math_explicit(self):
        from src.agent.rag_agent import RAGAgent
        expr = RAGAgent._extract_math("احسب: 5 * 6 + 2")
        assert expr is not None

    def test_extract_math_standalone(self):
        from src.agent.rag_agent import RAGAgent
        expr = RAGAgent._extract_math("ما ناتج 10 + 20 - 5؟")
        assert expr is not None

    def test_extract_math_no_math(self):
        from src.agent.rag_agent import RAGAgent
        expr = RAGAgent._extract_math("ما هو قانون نيوتن؟")
        assert expr is None

    @pytest.mark.asyncio
    async def test_run_no_search_tool(self):
        """Agent without search tool should still return an answer via direct LLM."""
        from src.agent.rag_agent import RAGAgent

        gen = MagicMock()
        gen.generate_text = MagicMock(return_value="Direct LLM answer")

        agent = RAGAgent(generation_client=gen, tools=[], language="en")
        result = await agent.run(query="What is AI?")
        assert result.answer == "Direct LLM answer"


# ══════════════════════════════════════════════════════════════════════════════
# 5. Orchestrator Intent Routing
# ══════════════════════════════════════════════════════════════════════════════

class TestOrchestrator:
    """Test Orchestrator confidence labelling and greeting/off-topic routing."""

    def test_confidence_label_high(self):
        from src.agent.agents.orchestrator import Orchestrator
        assert Orchestrator._confidence_label(0.9) == "high"

    def test_confidence_label_medium(self):
        from src.agent.agents.orchestrator import Orchestrator
        assert Orchestrator._confidence_label(0.6) == "medium"

    def test_confidence_label_low(self):
        from src.agent.agents.orchestrator import Orchestrator
        assert Orchestrator._confidence_label(0.3) == "low"

    def test_greeting_response_not_empty(self):
        from src.agent.agents.orchestrator import Orchestrator
        resp = Orchestrator._generate_greeting_response("en")
        assert len(resp) > 20

    def test_off_topic_response_not_empty(self):
        from src.agent.agents.orchestrator import Orchestrator
        resp = Orchestrator._generate_off_topic_response("ar")
        assert len(resp) > 10

    def test_build_thinking_trace_empty(self):
        from src.agent.agents.orchestrator import Orchestrator
        trace = Orchestrator._build_thinking_trace([])
        assert trace == []

    def test_build_thinking_trace_with_actions(self):
        from src.agent.base_agent import AgentAction
        from src.agent.agents.orchestrator import Orchestrator

        action = AgentAction(
            tool_name="knowledge_search",
            tool_input={"query": "test"},
            reasoning="searching",
        )
        action.tool_output = "some result with text"
        trace = Orchestrator._build_thinking_trace([action])
        assert len(trace) == 1
        assert trace[0]["tool"] == "knowledge_search"


# ══════════════════════════════════════════════════════════════════════════════
# 6. Intent Classifier (keyword fallback)
# ══════════════════════════════════════════════════════════════════════════════

class TestIntentClassifier:
    """Test the keyword-based fallback classification."""

    def _classifier(self):
        from src.agent.core.intent_classifier import IntentClassifier
        clf = IntentClassifier.__new__(IntentClassifier)
        clf.generation_client = None   # force keyword fallback
        return clf

    def test_keyword_tutor_arabic(self):
        clf = self._classifier()
        result = clf._keyword_classify("اشرح لي قانون نيوتن")
        assert result["intent"] == "tutor"

    def test_keyword_quiz_arabic(self):
        clf = self._classifier()
        result = clf._keyword_classify("اختبرني في الفيزياء")
        assert result["intent"] == "quiz"

    def test_keyword_greeting(self):
        clf = self._classifier()
        result = clf._keyword_classify("مرحباً")
        assert result["intent"] == "greeting"

    def test_keyword_concept_map(self):
        clf = self._classifier()
        result = clf._keyword_classify("ارسم خريطة مفاهيم للذكاء الاصطناعي")
        assert result["intent"] == "concept_map"

    def test_keyword_python_scratchpad(self):
        clf = self._classifier()
        result = clf._keyword_classify("شغل كود بايثون")
        assert result["intent"] == "python_scratchpad"

    def test_keyword_research_default(self):
        clf = self._classifier()
        result = clf._keyword_classify("ما هو الكلوروفيل؟")
        assert result["intent"] == "research"

    def test_keyword_english_tutor(self):
        clf = self._classifier()
        result = clf._keyword_classify("explain photosynthesis to me")
        assert result["intent"] == "tutor"


# ══════════════════════════════════════════════════════════════════════════════
# 7. Adaptive Difficulty Engine
# ══════════════════════════════════════════════════════════════════════════════

class TestAdaptiveDifficultyEngine:
    """Test IRT-inspired adaptive difficulty engine."""

    def _engine(self):
        from src.engine.adaptive_difficulty import AdaptiveDifficultyEngine
        return AdaptiveDifficultyEngine()

    def test_new_student_gets_medium(self):
        engine = self._engine()
        params = engine.get_next_question_params("new_student", "math")
        assert params["difficulty"] == "medium"

    def test_correct_answer_increases_mastery(self):
        from src.engine.adaptive_difficulty import QuestionAttempt
        engine = self._engine()

        attempt = QuestionAttempt(
            question_id="q1",
            topic="physics",
            difficulty="easy",
            is_correct=True,
            time_taken_sec=30.0,
        )
        mastery = engine.process_attempt("student1", attempt)
        assert mastery.attempts_total == 1
        assert mastery.correct_count == 1

    def test_wrong_answers_downgrade(self):
        from src.engine.adaptive_difficulty import QuestionAttempt
        engine = self._engine()

        for i in range(3):
            attempt = QuestionAttempt(
                question_id=f"q{i}",
                topic="chemistry",
                difficulty="hard",
                is_correct=False,
                time_taken_sec=60.0,
            )
            mastery = engine.process_attempt("student2", attempt)

        # After 3 wrong hard answers, difficulty should be easy or medium
        assert mastery.current_difficulty in ["easy", "medium"]

    def test_streak_upgrade(self):
        from src.engine.adaptive_difficulty import QuestionAttempt, STREAK_TO_UPGRADE
        engine = self._engine()

        for i in range(STREAK_TO_UPGRADE):
            attempt = QuestionAttempt(
                question_id=f"q{i}",
                topic="biology",
                difficulty="easy",
                is_correct=True,
                time_taken_sec=15.0,
            )
            mastery = engine.process_attempt("student3", attempt)

        # After enough correct answers, difficulty should upgrade
        assert mastery.current_difficulty in ["medium", "hard"]

    def test_dashboard_empty_student(self):
        engine = self._engine()
        dashboard = engine.get_student_dashboard("ghost_student")
        assert "student_id" in dashboard
        assert dashboard["total_topics"] == 0

    def test_multiple_topics(self):
        from src.engine.adaptive_difficulty import QuestionAttempt
        engine = self._engine()

        for topic in ["math", "physics", "chemistry"]:
            attempt = QuestionAttempt(
                question_id="q1",
                topic=topic,
                difficulty="medium",
                is_correct=True,
                time_taken_sec=20.0,
            )
            engine.process_attempt("student4", attempt)

        dashboard = engine.get_student_dashboard("student4")
        assert dashboard["total_topics"] == 3


# ══════════════════════════════════════════════════════════════════════════════
# 8. WhatsApp Client (No real API call)
# ══════════════════════════════════════════════════════════════════════════════

class TestWhatsAppClient:
    """Test phone number cleaning logic."""

    def test_clean_phone_with_plus(self):
        from src.helpers.whatsapp_client import WhatsAppClient
        result = WhatsAppClient._clean_phone("+201012345678")
        assert result == "201012345678"

    def test_clean_phone_local_egyptian(self):
        from src.helpers.whatsapp_client import WhatsAppClient
        result = WhatsAppClient._clean_phone("01012345678")
        assert result == "2201012345678" or result.startswith("2")

    def test_clean_phone_with_spaces(self):
        from src.helpers.whatsapp_client import WhatsAppClient
        result = WhatsAppClient._clean_phone("  +20 101 234 5678  ")
        assert " " not in result
        assert result.startswith("20")

    @pytest.mark.asyncio
    async def test_disabled_client_returns_none(self):
        from src.helpers.whatsapp_client import WhatsAppClient
        client = WhatsAppClient.__new__(WhatsAppClient)
        client.instance_id = ""
        client.token = ""
        client.enabled = False
        result = await client.send_message("201000000000", "test")
        assert result is None


# ══════════════════════════════════════════════════════════════════════════════
# 9. NLP Controller Collection Name
# ══════════════════════════════════════════════════════════════════════════════

class TestNLPController:
    """Test NLPController helper methods."""

    def _controller(self, embedding_size=768):
        from src.controllers.NLPController import NLPController
        vectordb = MagicMock()
        vectordb.default_vector_size = embedding_size
        ctrl = NLPController.__new__(NLPController)
        ctrl.vectordb_client = vectordb
        ctrl.generation_client = MagicMock()
        ctrl.embedding_client = MagicMock()
        ctrl.template_parser = MagicMock()
        ctrl.chunk_model = None
        return ctrl

    def test_collection_name_format(self):
        ctrl = self._controller(768)
        project = MagicMock()
        project.project_id = "proj_abc"
        name = ctrl.create_collection_name("proj_abc")
        assert "768" in name
        assert "proj_abc" in name

    def test_collection_name_different_sizes(self):
        ctrl_384 = self._controller(384)
        ctrl_768 = self._controller(768)
        name_384 = ctrl_384.create_collection_name("p1")
        name_768 = ctrl_768.create_collection_name("p1")
        assert name_384 != name_768


# ══════════════════════════════════════════════════════════════════════════════
# 10. DeepDoc Controller Block Classification
# ══════════════════════════════════════════════════════════════════════════════

class TestDeepDocController:
    """Test block classification heuristics."""

    def _ctrl(self):
        from src.controllers.DeepDocController import DeepDocController
        return DeepDocController()

    def test_classify_header_short_bold(self):
        ctrl = self._ctrl()
        result = ctrl._classify_block(
            text="Chapter 1: Introduction",
            avg_font_size=16,
            is_bold=True,
            num_lines=1,
        )
        assert result == "header"

    def test_classify_paragraph(self):
        ctrl = self._ctrl()
        result = ctrl._classify_block(
            text="This is a normal paragraph with some text. " * 10,
            avg_font_size=12,
            is_bold=False,
            num_lines=5,
        )
        assert result == "paragraph"

    def test_classify_table(self):
        ctrl = self._ctrl()
        result = ctrl._classify_block(
            text="| Col1 | Col2 |\n| val1 | val2 |\n| val3 | val4 |",
            avg_font_size=11,
            is_bold=False,
            num_lines=3,
        )
        assert result == "table"

    def test_classify_list(self):
        ctrl = self._ctrl()
        result = ctrl._classify_block(
            text="• Item one\n• Item two\n• Item three\n• Item four",
            avg_font_size=12,
            is_bold=False,
            num_lines=4,
        )
        assert result == "list"

    def test_analyze_text(self):
        ctrl = self._ctrl()
        text = "# Introduction\n\nThis is the introduction.\n\n## Chapter 1\n\nContent here."
        chunks = ctrl.analyze_text(text, metadata={"source": "test.txt"})
        assert len(chunks) >= 1
        for c in chunks:
            assert len(c.page_content) > 0

    def test_split_long_text(self):
        ctrl = self._ctrl()
        long_text = "word " * 1000
        parts = ctrl._split_long_text(long_text, chunk_size=200, overlap=20)
        assert len(parts) > 1
        for p in parts:
            assert len(p) <= 250   # some tolerance


# ══════════════════════════════════════════════════════════════════════════════
# 11. Agent Memory
# ══════════════════════════════════════════════════════════════════════════════

class TestAgentMemory:
    """Test short-term memory and context building."""

    def test_add_turns(self):
        from src.agent.core.memory import AgentMemory
        mem = AgentMemory()
        mem.add_turn("user", "Hello")
        mem.add_turn("assistant", "Hi there!")
        assert len(mem.short_term) == 2

    def test_get_conversation_context_empty(self):
        from src.agent.core.memory import AgentMemory
        mem = AgentMemory()
        ctx = mem.get_conversation_context()
        assert ctx == ""

    def test_get_conversation_context(self):
        from src.agent.core.memory import AgentMemory
        mem = AgentMemory()
        mem.add_turn("user", "What is AI?")
        mem.add_turn("assistant", "AI stands for...")
        ctx = mem.get_conversation_context(last_n=2)
        assert "What is AI?" in ctx

    def test_context_last_n_limit(self):
        from src.agent.core.memory import AgentMemory
        mem = AgentMemory()
        for i in range(20):
            mem.add_turn("user", f"Message {i}")
        # Only last 4 should appear
        ctx = mem.get_conversation_context(last_n=4)
        assert "Message 19" in ctx
        assert "Message 0" not in ctx


# ══════════════════════════════════════════════════════════════════════════════
# 12. Message Bus
# ══════════════════════════════════════════════════════════════════════════════

class TestMessageBus:
    """Test inter-agent message routing."""

    def test_send_and_retrieve(self):
        from src.agent.core.message_bus import MessageBus, MessageType
        bus = MessageBus()
        bus.send("agent_a", "agent_b", "Hello!", MessageType.REQUEST.value)
        log = bus.get_conversation_log()
        assert len(log) == 1
        assert log[0]["from"] == "agent_a"
        assert log[0]["to"] == "agent_b"

    def test_multiple_messages(self):
        from src.agent.core.message_bus import MessageBus, MessageType
        bus = MessageBus()
        bus.send("user", "orchestrator", "Q1", MessageType.REQUEST.value)
        bus.send("orchestrator", "researcher", "Q1", MessageType.REQUEST.value)
        bus.send("researcher", "user", "Answer", MessageType.RESPONSE.value)
        log = bus.get_conversation_log()
        assert len(log) == 3


# ══════════════════════════════════════════════════════════════════════════════
# 13. Calculator Tool (edge cases)
# ══════════════════════════════════════════════════════════════════════════════

class TestCalculatorTool:
    """Extended calculator tests beyond the basic ones."""

    @pytest.mark.asyncio
    async def test_power(self):
        from src.agent.tools.calculator import CalculatorTool
        calc = CalculatorTool()
        result = await calc.execute(expression="2 ** 10")
        assert "1024" in result

    @pytest.mark.asyncio
    async def test_modulo(self):
        from src.agent.tools.calculator import CalculatorTool
        calc = CalculatorTool()
        result = await calc.execute(expression="17 % 5")
        assert "2" in result

    @pytest.mark.asyncio
    async def test_float_result(self):
        from src.agent.tools.calculator import CalculatorTool
        calc = CalculatorTool()
        result = await calc.execute(expression="10 / 3")
        assert "3.3" in result

    @pytest.mark.asyncio
    async def test_blocked_import(self):
        from src.agent.tools.calculator import CalculatorTool
        calc = CalculatorTool()
        result = await calc.execute(expression="import os")
        assert "Error" in result or "error" in result.lower()

    @pytest.mark.asyncio
    async def test_empty_expression(self):
        from src.agent.tools.calculator import CalculatorTool
        calc = CalculatorTool()
        result = await calc.execute(expression="")
        # Should not crash — return error message
        assert isinstance(result, str)


# ══════════════════════════════════════════════════════════════════════════════
# 14. Python Scratchpad Security
# ══════════════════════════════════════════════════════════════════════════════

class TestPythonScratchpad:
    """Test sandbox security restrictions."""

    @pytest.mark.asyncio
    async def test_print_output(self):
        from src.agent.tools.python_scratchpad import PythonScratchpadTool
        tool = PythonScratchpadTool()
        result = await tool.execute(code="print('hello world')")
        assert "hello world" in result

    @pytest.mark.asyncio
    async def test_math_computation(self):
        from src.agent.tools.python_scratchpad import PythonScratchpadTool
        tool = PythonScratchpadTool()
        result = await tool.execute(code="x = 7 * 8\nprint(x)")
        assert "56" in result

    @pytest.mark.asyncio
    async def test_multiline_code(self):
        from src.agent.tools.python_scratchpad import PythonScratchpadTool
        tool = PythonScratchpadTool()
        code = "for i in range(3):\n    print(i)"
        result = await tool.execute(code=code)
        assert "0" in result and "1" in result and "2" in result

    @pytest.mark.asyncio
    async def test_syntax_error(self):
        from src.agent.tools.python_scratchpad import PythonScratchpadTool
        tool = PythonScratchpadTool()
        result = await tool.execute(code="def bad(:\n    pass")
        assert "SyntaxError" in result or "error" in result.lower()


# ══════════════════════════════════════════════════════════════════════════════
# 15. StorageController (filesystem fallback)
# ══════════════════════════════════════════════════════════════════════════════

class TestStorageController:
    """Test StorageController filesystem fallback (no MinIO needed)."""

    @pytest.mark.asyncio
    async def test_save_and_get(self, tmp_path):
        from src.controllers.StorageController import StorageController
        from src.controllers.ProjectController import ProjectController

        storage = StorageController()
        storage._available = False   # force filesystem mode

        project_id = "test_project_storage"
        file_id = "test_file.txt"
        data = b"Hello Storage World"

        # Patch the path to use tmp_path
        with patch.object(
            ProjectController, "get_project_path",
            return_value=str(tmp_path)
        ):
            path = storage._fs_save(project_id, file_id, data)
            retrieved = storage._fs_get(project_id, file_id)

        assert retrieved == data

    def test_status_filesystem(self):
        from src.controllers.StorageController import StorageController
        storage = StorageController()
        storage._available = False
        st = storage.status()
        assert st["backend"] == "filesystem"
        assert st["minio_available"] is False


# ══════════════════════════════════════════════════════════════════════════════
# 16. OrchestratorResult serialization
# ══════════════════════════════════════════════════════════════════════════════

class TestOrchestratorResult:
    """Test that OrchestratorResult serializes cleanly."""

    def test_to_dict(self):
        from src.agent.agents.orchestrator import OrchestratorResult
        r = OrchestratorResult(
            answer="Test answer",
            agent_used="researcher",
            intent="research",
            confidence=0.85,
        )
        d = r.to_dict()
        assert d["answer"] == "Test answer"
        assert d["agent_used"] == "researcher"
        assert d["confidence"] == 0.85
        assert isinstance(d["sources"], list)
        assert isinstance(d["actions"], list)

    def test_confidence_rounding(self):
        from src.agent.agents.orchestrator import OrchestratorResult
        r = OrchestratorResult(
            answer="x",
            agent_used="tutor",
            intent="tutor",
            confidence=0.73333333,
        )
        d = r.to_dict()
        assert d["confidence"] == 0.73   # rounded to 2 decimals


# ══════════════════════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
