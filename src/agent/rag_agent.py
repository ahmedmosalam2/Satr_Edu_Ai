"""
src/agent/rag_agent.py
──────────────────────
RAG Agent — Multi-step reasoning with knowledge search.

الفرق عن الـ RAG العادي:
  - RAG العادي: بحث مرة واحدة → إجابة
  - RAG Agent: يفكر → يبحث → يحلل → يبحث تاني لو محتاج → يجيب

مثال:
  Q: "قارن بين قانون نيوتن الأول والثاني"
  Agent:
    Step 1: بحث عن "قانون نيوتن الأول" → لقي نتائج
    Step 2: بحث عن "قانون نيوتن الثاني" → لقي نتائج
    Step 3: دمج المعلومات → إجابة مقارنة شاملة
"""

import logging
import json
import re
from typing import List, Optional

from .base_agent import BaseAgent, AgentAction, AgentResult, BaseTool

logger = logging.getLogger("uvicorn.error")


class RAGAgent(BaseAgent):
    """
    Multi-step RAG Agent.

    بيقرر لوحده:
    - هل محتاج يبحث؟
    - هل محتاج يبحث مرة تانية بكلمات مختلفة؟
    - هل الإجابة كافية؟
    """

    MAX_STEPS = 5

    def __init__(
        self,
        generation_client,
        tools: List[BaseTool],
        language: str = "ar",
    ):
        self.generation_client = generation_client
        self.tools = {tool.name: tool for tool in tools}
        self.language = language

    async def run(self, query: str, chat_history: list = None, **kwargs) -> AgentResult:
        """
        تنفيذ الـ agent مع multi-step reasoning.
        """
        actions = []
        all_context = []
        all_sources = []
        all_citations = []  # [NEW] نجمع citations من كل search step

        # ── Step 1: Decompose query if complex ────────────────────────────
        sub_queries = await self._decompose_query(query)
        logger.info(f"[RAGAgent] Query decomposed into {len(sub_queries)} sub-queries")

        # ── Step 2: Search for each sub-query ─────────────────────────────
        search_tool = self.tools.get("knowledge_search")
        if not search_tool:
            # No search tool — just generate directly
            import inspect
            result = self.generation_client.generate_text(prompt=query)
            if inspect.isawaitable(result):
                answer = await result
            else:
                answer = result
            return AgentResult(answer=answer or "", steps_count=1)

        for i, sub_q in enumerate(sub_queries):
            if i >= self.MAX_STEPS:
                break

            action = AgentAction(
                tool_name="knowledge_search",
                tool_input={"query": sub_q},
                reasoning=f"Searching for: {sub_q}",
            )

            try:
                result = await search_tool.execute(query=sub_q, limit=3)
                action.tool_output = result
                all_context.append(f"--- Search {i+1}: {sub_q} ---\n{result}")

                # [NEW] اجمع الـ citations من الـ tool بعد كل search
                if hasattr(search_tool, "last_citations"):
                    for cit in search_tool.last_citations:
                        # تجنب التكرار بناءً على chunk_id
                        if not any(s.get("chunk_id") == cit.chunk_id for s in all_sources):
                            all_citations.append(cit)
                            all_sources.append(cit.to_dict())

            except Exception as e:
                action.tool_output = f"Error: {e}"

            actions.append(action)

        # ── Step 3: Check if calculator is needed ─────────────────────────
        calc_tool = self.tools.get("calculator")
        if calc_tool:
            math_expr = self._extract_math(query)
            if math_expr:
                action = AgentAction(
                    tool_name="calculator",
                    tool_input={"expression": math_expr},
                    reasoning=f"Calculating: {math_expr}",
                )
                try:
                    result = await calc_tool.execute(expression=math_expr)
                    action.tool_output = result
                    all_context.append(f"--- Calculation ---\n{result}")
                except Exception as e:
                    action.tool_output = f"Error: {e}"
                actions.append(action)

        context = "\n\n".join(all_context) if all_context else "No information found."

        if self.language == "ar":
            system_prompt = (
                "أنت مساعد تعليمي ذكي. استخدم المعلومات التالية للإجابة على السؤال. "
                "إذا كانت المعلومات غير كافية، اذكر ذلك. "
                "أجب بشكل واضح ومنظم."
            )
        else:
            system_prompt = (
                "You are an intelligent educational assistant. Use the following information to answer the question. "
                "If the information is insufficient, state that. "
                "Answer clearly and in an organized manner."
            )

        full_prompt = f"{system_prompt}\n\n{context}\n\nQuestion: {query}"

        import inspect
        result = self.generation_client.generate_text(prompt=full_prompt)
        if inspect.isawaitable(result):
            answer = await result
        else:
            answer = result

        return AgentResult(
            answer=answer or "",
            actions=actions,
            sources=all_sources,
            steps_count=len(actions),
        )

    async def _decompose_query(self, query: str) -> List[str]:
        """
        Decompose complex query into sub-queries.
        Simple heuristic — no LLM needed for most cases.
        """
        # Check for comparison words
        comparison_patterns_ar = ["قارن", "الفرق بين", "ما الفرق", "مقارنة"]
        comparison_patterns_en = ["compare", "difference between", "versus", "vs"]

        for pattern in comparison_patterns_ar + comparison_patterns_en:
            if pattern in query.lower():
                # Extract the two topics
                parts = re.split(
                    r"(?:و|وبين|مع|and|vs\.?|versus)",
                    query.replace(pattern, ""),
                    maxsplit=1,
                )
                if len(parts) >= 2:
                    return [p.strip() for p in parts if p.strip()] + [query]

        # Check for "and" conjunctions suggesting multiple topics
        if " و " in query or " and " in query.lower():
            parts = re.split(r" و |,| and ", query)
            if len(parts) >= 2 and all(len(p.strip()) > 5 for p in parts):
                return [p.strip() for p in parts if p.strip()] + [query]

        # Single query — no decomposition needed
        return [query]

    @staticmethod
    def _extract_math(query: str) -> Optional[str]:
        """Extract math expression from query if present."""
        # Look for explicit math expressions
        math_pattern = re.search(
            r"(?:احسب|حساب|calculate|compute|eval)\s*[:\s]*(.+?)(?:\?|$)",
            query,
            re.IGNORECASE,
        )
        if math_pattern:
            return math_pattern.group(1).strip()

        # Look for standalone expressions
        expr_pattern = re.search(r"(\d+[\s]*[\+\-\*\/\^][\s]*\d+[\s\d\+\-\*\/\^]*)", query)
        if expr_pattern:
            return expr_pattern.group(1).strip()

        return None
