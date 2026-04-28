"""
src/agent/tools/knowledge_search.py
────────────────────────────────────
Knowledge Search Tool — بحث في الـ Knowledge Base.

بيستخدم الـ NLPController الموجود للبحث.
"""

import logging
from src.agent.base_agent import BaseTool

logger = logging.getLogger("uvicorn.error")


class KnowledgeSearchTool(BaseTool):
    """بحث في الـ knowledge base باستخدام vector + keyword search."""

    def __init__(self, nlp_controller, project):
        self.nlp_controller = nlp_controller
        self.project = project

    @property
    def name(self) -> str:
        return "knowledge_search"

    @property
    def description(self) -> str:
        return "Search the knowledge base for information related to a query. Input: search query string."

    async def execute(self, query: str = "", limit: int = 5, **kwargs) -> str:
        if not query:
            return "Error: No query provided"

        try:
            results = await self.nlp_controller.search_vector_db_collection(
                project=self.project,
                text=query,
                limit=limit,
            )

            if not results:
                return "No relevant documents found."

            output_parts = []
            for i, doc in enumerate(results):
                payload = doc.payload if hasattr(doc, "payload") else {}
                text = payload.get("text", "")
                score = doc.score if hasattr(doc, "score") else 0
                source = payload.get("source", payload.get("source_file", "unknown"))
                output_parts.append(
                    f"[{i+1}] (score: {score:.3f}, source: {source})\n{text[:300]}"
                )

            return "\n\n".join(output_parts)

        except Exception as e:
            logger.error(f"[KnowledgeSearchTool] Error: {e}")
            return f"Search error: {str(e)}"
