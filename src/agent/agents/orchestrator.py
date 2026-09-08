"""
src/agent/agents/orchestrator.py
────────────────────────────────
Orchestrator — المنسق بين الـ agents.

الترقية عن النسخة القديمة:
  ❌ قبل: Keyword matching بسيط → "فهمني" ← tutor
  ✅ بعد: LLM-based intent classification مع confidence scoring

Flow الجديد:
  User Query
      ↓
  [IntentClassifier (LLM)] → {intent, confidence, entities}
      ↓
      ├── confidence ≥ 0.7 → Route مباشرة
      ├── confidence 0.5-0.7 → Route مع ملاحظة "غير متأكد"
      └── confidence < 0.5 → Default to research
      ↓
  [Agent.run() with ReAct loop]
      ↓
  [ResponseFormatter] → Unified response with thinking_trace + confidence
"""

import logging
from typing import List, Optional
from dataclasses import dataclass, field

from src.agent.base_agent import BaseAgent, AgentResult, BaseTool
from src.agent.core.message_bus import MessageBus, MessageType
from src.agent.core.memory import AgentMemory
from src.agent.core.intent_classifier import IntentClassifier

logger = logging.getLogger("uvicorn.error")


@dataclass
class OrchestratorResult:
    """نتيجة الـ Orchestrator مع metadata كاملة عن القرار."""
    answer: str
    agent_used: str
    intent: str
    confidence: float = 0.8
    confidence_label: str = "high"
    steps_count: int = 0
    actions: list = field(default_factory=list)
    sources: list = field(default_factory=list)
    conversation_log: list = field(default_factory=list)
    thinking_trace: list = field(default_factory=list)
    follow_up_questions: list = field(default_factory=list)
    intent_reasoning: str = ""
    intent_method: str = "llm"

    def to_dict(self) -> dict:
        return {
            "answer": self.answer,
            "agent_used": self.agent_used,
            "intent": self.intent,
            "confidence": round(self.confidence, 2),
            "confidence_label": self.confidence_label,
            "steps_count": self.steps_count,
            "actions": self.actions,
            "sources": self.sources,
            "conversation_log": self.conversation_log,
            "thinking_trace": self.thinking_trace,
            "follow_up_questions": self.follow_up_questions,
            "intent_reasoning": self.intent_reasoning,
            "intent_method": self.intent_method,
        }


class Orchestrator:
    """
    المنسق — بيقرر أي agent يشتغل باستخدام LLM Intent Classification.

    Agents:
      - researcher : RAGAgent — بحث وإجابة
      - tutor      : TutorAgent — شرح مبسط
      - quiz       : QuizAgent — أسئلة سريعة

    الجديد:
      - يستخدم LLM لفهم النية (مش keywords)
      - بيرجع confidence score لكل قرار
      - بيرجع thinking trace كامل
      - بيقترح أسئلة متابعة
    """

    def __init__(
        self,
        generation_client,
        tools: List[BaseTool],
        language: str = "ar",
        student_level: str = "intermediate",
        student_context: str = "",
    ):
        self.generation_client = generation_client
        self.tools = tools
        self.language = language
        self.student_level = student_level
        self.student_context = student_context

        # Infrastructure
        self.bus = MessageBus()
        self.memory = AgentMemory()

        # ✅ LLM-based intent classifier
        self.intent_classifier = IntentClassifier(
            generation_client=generation_client
        )

    async def run(self, query: str, **kwargs) -> OrchestratorResult:
        """تنفيذ الـ pipeline الكامل مع LLM intent classification."""

        # ── 1. Classify Intent with LLM ───────────────────────────────────
        conversation_context = self.memory.get_conversation_context(last_n=4)
        intent_data = await self.intent_classifier.classify(
            query=query,
            conversation_context=conversation_context,
        )

        intent = intent_data["intent"]
        confidence = intent_data["confidence"]
        reasoning = intent_data.get("reasoning", "")
        method = intent_data.get("method", "keyword")

        logger.info(
            f"[Orchestrator] Intent={intent} (conf={confidence:.2f}, method={method}) "
            f"| Query: {query[:60]}"
        )

        # ── 2. Log to message bus + memory ───────────────────────────────
        self.bus.send(
            from_agent="user",
            to_agent="orchestrator",
            content=query,
            msg_type=MessageType.REQUEST.value,
        )
        self.memory.add_turn("user", query)

        # ── 3. Handle special intents ────────────────────────────────────
        if intent == "greeting":
            try:
                # Let the LLM generate a dynamic greeting response
                prompt = (
                    "You are an intelligent educational AI assistant/tutor. "
                    "The student greeted you or asked who you are.\n"
                    f"Student message: '{query}'\n\n"
                    "Respond to the student dynamically, politely, and in a friendly and encouraging manner. "
                    f"Use the language: {self.language}. "
                    "Explain that you are their virtual learning assistant, ready to help them explain lessons, generate quizzes, "
                    "and answer any questions based on the course materials they upload. "
                    "Keep your response warm, interactive, and concise."
                )
                import inspect
                res = self.generation_client.generate_text(prompt=prompt, max_tokens=250)
                if inspect.isawaitable(res):
                    answer = await res
                else:
                    answer = res
                if not answer:
                    answer = self._generate_greeting_response(self.language)
            except Exception as e:
                logger.warning(f"[Orchestrator] Dynamic greeting failed: {e}")
                answer = self._generate_greeting_response(self.language)

            self.memory.add_turn("assistant", answer)
            return OrchestratorResult(
                answer=answer,
                agent_used="orchestrator",
                intent="greeting",
                confidence=confidence,
                confidence_label=self._confidence_label(confidence),
                intent_reasoning=reasoning,
                intent_method=method,
            )

        if intent == "off_topic":
            answer = self._generate_off_topic_response(self.language)
            self.memory.add_turn("assistant", answer)
            return OrchestratorResult(
                answer=answer,
                agent_used="orchestrator",
                intent="off_topic",
                confidence=confidence,
                confidence_label=self._confidence_label(confidence),
                intent_reasoning=reasoning,
                intent_method=method,
            )

        # ── 4. Route to Agent ─────────────────────────────────────────────
        if intent == "tutor":
            result = await self._run_tutor(query)
        elif intent == "quiz":
            result = await self._run_quiz(query)
        elif intent == "concept_map":
            result = await self._run_concept_map(query)
        elif intent == "python_scratchpad":
            result = await self._run_python_scratchpad(query)
        elif intent == "socratic":
            result = await self._run_socratic(query)
        else:
            result = await self._run_researcher(query)

        # ── 5. Enrich result with intent metadata ─────────────────────────
        result.confidence = confidence
        result.confidence_label = self._confidence_label(confidence)
        result.intent_reasoning = reasoning
        result.intent_method = method

        # ── 6. Generate follow-up questions ──────────────────────────────
        result.follow_up_questions = await self._generate_follow_ups(
            query=query, answer=result.answer
        )

        # ── 7. Log response ───────────────────────────────────────────────
        self.bus.send(
            from_agent=result.agent_used,
            to_agent="user",
            content=result.answer[:200] if result.answer else "",
            msg_type=MessageType.RESPONSE.value,
        )
        self.memory.add_turn("assistant", result.answer or "")
        result.conversation_log = self.bus.get_conversation_log()

        return result

    def _get_tool(self, name: str) -> Optional[BaseTool]:
        for tool in self.tools:
            if tool.name == name:
                return tool
        return None

    async def _run_researcher(self, query: str) -> OrchestratorResult:
        """تشغيل الـ RAG Agent."""
        from src.agent.rag_agent import RAGAgent

        agent = RAGAgent(
            generation_client=self.generation_client,
            tools=self.tools,
            language=self.language,
        )
        self.bus.send("orchestrator", "researcher", query, MessageType.REQUEST.value)

        result = await agent.run(
            query=query,
            chat_history=self.memory.short_term[-6:],
        )

        return OrchestratorResult(
            answer=result.answer,
            agent_used="researcher",
            intent="research",
            steps_count=result.steps_count,
            actions=result.to_dict()["actions"],
            sources=result.sources,
            thinking_trace=self._build_thinking_trace(result.actions),
        )

    async def _run_tutor(self, query: str) -> OrchestratorResult:
        """تشغيل الـ Tutor Agent."""
        from src.agent.agents.tutor_agent import TutorAgent

        agent = TutorAgent(
            generation_client=self.generation_client,
            tools=self.tools,
            language=self.language,
            student_level=self.student_level,
            student_context=self.student_context,
        )
        self.bus.send("orchestrator", "tutor", query, MessageType.REQUEST.value)
        result = await agent.run(query=query)

        return OrchestratorResult(
            answer=result.answer,
            agent_used="tutor",
            intent="tutor",
            steps_count=result.steps_count,
            actions=result.to_dict()["actions"],
            thinking_trace=self._build_thinking_trace(result.actions),
        )

    async def _run_quiz(self, query: str) -> OrchestratorResult:
        """تشغيل الـ Quiz Agent."""
        from src.agent.agents.quiz_agent import QuizAgent

        agent = QuizAgent(
            generation_client=self.generation_client,
            tools=self.tools,
            language=self.language,
        )
        self.bus.send("orchestrator", "quiz", query, MessageType.REQUEST.value)
        result = await agent.run(query=query)

        return OrchestratorResult(
            answer=result.answer,
            agent_used="quiz",
            intent="quiz",
            steps_count=result.steps_count,
            actions=result.to_dict()["actions"],
            sources=result.sources,
            thinking_trace=self._build_thinking_trace(result.actions),
        )

    async def _run_concept_map(self, query: str) -> OrchestratorResult:
        """تشغيل خريطة المفاهيم."""
        from src.agent.base_agent import AgentAction

        concept_tool = self._get_tool("concept_map")
        action = AgentAction(
            tool_name="concept_map",
            tool_input={"query": query},
            reasoning=f"Generating concept map for: {query}",
        )

        if concept_tool:
            try:
                answer = await concept_tool.execute(query=query, language=self.language)
                action.tool_output = answer[:200]
            except Exception as e:
                answer = f"Error generating concept map: {e}"
                action.tool_output = f"Error: {e}"
        else:
            answer = "Concept Map tool is not available."
            action.tool_output = "Tool not found"

        return OrchestratorResult(
            answer=answer,
            agent_used="concept_map_tool",
            intent="concept_map",
            steps_count=1,
            actions=[action],
            thinking_trace=self._build_thinking_trace([action]),
        )

    async def _run_python_scratchpad(self, query: str) -> OrchestratorResult:
        """تشغيل كود برمجي باستخدام بيئة بايثون للـ Scratchpad."""
        from src.agent.base_agent import AgentAction

        scratch_tool = self._get_tool("python_scratchpad")
        action = AgentAction(
            tool_name="python_scratchpad",
            tool_input={"code": query},
            reasoning=f"Running Python code snippet: {query[:60]}",
        )

        if scratch_tool:
            try:
                answer = await scratch_tool.execute(code=query)
                action.tool_output = answer[:200]
            except Exception as e:
                answer = f"Error executing code: {e}"
                action.tool_output = f"Error: {e}"
        else:
            answer = "Python scratchpad is not available."
            action.tool_output = "Tool not found"

        return OrchestratorResult(
            answer=answer,
            agent_used="python_scratchpad_tool",
            intent="python_scratchpad",
            steps_count=1,
            actions=[action],
            thinking_trace=self._build_thinking_trace([action]),
        )

    async def _run_socratic(self, query: str) -> OrchestratorResult:
        """تشغيل العميل السقراطي الذكي."""
        from src.agent.agents.socratic_agent import SocraticAgent

        agent = SocraticAgent(
            generation_client=self.generation_client,
            tools=self.tools,
            language=self.language,
            student_level=self.student_level,
            student_context=self.student_context,
        )
        self.bus.send("orchestrator", "socratic", query, MessageType.REQUEST.value)
        result = await agent.run(query=query)

        return OrchestratorResult(
            answer=result.answer,
            agent_used="socratic",
            intent="socratic",
            steps_count=result.steps_count,
            actions=result.to_dict()["actions"],
            thinking_trace=self._build_thinking_trace(result.actions),
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _confidence_label(score: float) -> str:
        if score >= 0.8:
            return "high"
        elif score >= 0.5:
            return "medium"
        return "low"

    @staticmethod
    def _build_thinking_trace(actions) -> list:
        trace = []
        for i, a in enumerate(actions or []):
            if hasattr(a, "tool_name"):
                trace.append({
                    "step": i + 1,
                    "type": "search",
                    "tool": a.tool_name,
                    "query": a.tool_input.get("query", ""),
                    "found": bool(a.tool_output and len(a.tool_output) > 20),
                })
        return trace

    @staticmethod
    def _generate_greeting_response(language: str) -> str:
        if language == "ar":
            return (
                "أهلاً بك! أنا مساعدك التعليمي والبرمجي الذكي.\n\n"
                "يمكنني مساعدتك في:\n"
                "- البحث والإجابة من محتوى المنهج والمستندات المرفوعة.\n"
                "- شرح وتبسيط المفاهيم والدروس البرمجية الصعبة.\n"
                "- توليد خرائط مفاهيمية وذهنية لمساعدتك على المذاكرة.\n"
                "- تشغيل وتجربة أكواد بايثون البرمجية مباشرة في البيئة البرمجية.\n"
                "- المناقشة بالطريقة السقراطية التفاعلية وتوليد اختبارات سريعة.\n\n"
                "تفضل بطرح أي سؤال تعليمي أو برمجي لنبدأ معاً!"
            )
        return (
            "Hello. I am the advanced educational assistant.\n\n"
            "Capabilities include:\n"
            "- Educational content retrieval\n"
            "- Concept explanation and simplification\n"
            "- Concept Map generation\n"
            "- Python code execution sandbox\n"
            "- Socratic dialogue for advanced topics\n"
            "- Interactive quizzes\n\n"
            "Please provide your query to begin."
        )

    @staticmethod
    def _generate_off_topic_response(language: str) -> str:
        if language == "ar":
            return (
                "عذراً، ينحصر نطاق عملي في الأسئلة والمواضيع التعليمية والبرمجية الخاصة بهذا الكورس فقط.\n"
                "يرجى طرح سؤال أكاديمي أو برمجي ذي صلة."
            )
        return (
            "My scope is restricted to educational queries within this domain.\n"
            "Please ask a relevant academic or technical question."
        )

    async def _generate_follow_ups(self, query: str, answer: str) -> list:
        """اقترح 3 أسئلة متابعة."""
        if not answer or not self.generation_client:
            return []
        try:
            if self.language == "ar":
                prompt = (
                    f"بناءً على هذا السؤال التعليمي: {query}\n"
                    f"والإجابة (مختصرة): {answer[:200]}\n\n"
                    "اقترح 3 أسئلة متابعة قصيرة ومفيدة.\n"
                    "أرجع الأسئلة فقط، سطر لكل سؤال."
                )
            else:
                prompt = (
                    f"Based on this question: {query}\n"
                    f"Answer (brief): {answer[:200]}\n\n"
                    "Suggest 3 short follow-up questions. One per line."
                )

            import inspect
            result = self.generation_client.generate_text(prompt=prompt, max_tokens=120)
            if inspect.isawaitable(result):
                raw = await result
            else:
                raw = result

            if not raw:
                return []

            lines = [l.strip().lstrip("0123456789.-) ") for l in raw.strip().splitlines()]
            return [q for q in lines if q and len(q) > 5][:3]
        except Exception:
            return []
