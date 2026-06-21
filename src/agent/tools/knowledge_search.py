"""
src/agent/tools/knowledge_search.py
────────────────────────────────────
Knowledge Search Tool — بحث في الـ Knowledge Base مع Citation Highlighting.

بيرجع:
  - text للـ LLM (عشان يولد الإجابة)
  - citations غنية للـ frontend (page, snippet, score, source)
"""

import logging
from dataclasses import dataclass, field
from typing import List, Optional
from src.agent.base_agent import BaseTool

logger = logging.getLogger("uvicorn.error")


@dataclass
class Citation:
    """Citation كاملة — كل المعلومات اللي الـ frontend محتاجها للـ highlight."""
    chunk_id: str = ""
    source_file: str = ""          # اسم الملف (PDF/DOCX)
    page_number: Optional[int] = None  # رقم الصفحة
    snippet: str = ""              # أول 300 حرف من الـ chunk
    full_text: str = ""            # النص كامل للـ LLM
    relevance_score: float = 0.0   # cosine similarity score
    chunk_order: int = 0           # ترتيب الـ chunk في الوثيقة
    section_title: Optional[str] = None  # عنوان الفصل/القسم لو موجود

    def to_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "source_file": self.source_file,
            "page_number": self.page_number,
            "snippet": self.snippet,
            "relevance_score": round(self.relevance_score, 4),
            "chunk_order": self.chunk_order,
            "section_title": self.section_title,
        }


class KnowledgeSearchTool(BaseTool):
    """
    بحث في الـ knowledge base مع citation tracking كامل.

    الفرق عن النسخة القديمة:
      - القديم: يرجع text فقط للـ LLM
      - الجديد: يرجع text للـ LLM + citations غنية للـ frontend
    """

    def __init__(self, nlp_controller, project):
        self.nlp_controller = nlp_controller
        self.project = project
        # Citations محفوظة لو الـ agent محتاجها بعدين
        self._last_citations: List[Citation] = []

    @property
    def name(self) -> str:
        return "knowledge_search"

    @property
    def description(self) -> str:
        return "Search the knowledge base for information related to a query. Input: search query string."

    @property
    def last_citations(self) -> List[Citation]:
        """الـ citations من آخر بحث — الـ RAGAgent يستخدمها."""
        return self._last_citations

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
                self._last_citations = []
                return "No relevant documents found."

            # ── بناء الـ citations ────────────────────────────────────
            citations = []
            output_parts = []

            for i, doc in enumerate(results):
                payload = doc.payload if hasattr(doc, "payload") else {}
                score   = doc.score if hasattr(doc, "score") else 0.0

                full_text   = payload.get("text", "")
                source_file = payload.get("source", payload.get("source_file", "unknown"))
                chunk_id    = payload.get("chunk_id", f"chunk_{i}")
                chunk_order = payload.get("chunk_order", i)

                # Page number — stored in metadata during ingestion
                page_number   = payload.get("page", payload.get("page_number", None))
                section_title = payload.get("section", payload.get("header", None))

                # Snippet = أول 300 حرف قابلة للـ highlight
                snippet = full_text[:300].strip()
                if len(full_text) > 300:
                    snippet += "..."

                citation = Citation(
                    chunk_id=str(chunk_id),
                    source_file=source_file,
                    page_number=page_number,
                    snippet=snippet,
                    full_text=full_text,
                    relevance_score=score,
                    chunk_order=chunk_order,
                    section_title=section_title,
                )
                citations.append(citation)

                # نص للـ LLM (مش للـ frontend)
                source_label = source_file
                if page_number:
                    source_label += f" (صفحة {page_number})"

                output_parts.append(
                    f"[مصدر {i+1}] {source_label} | relevance: {score:.3f}\n{full_text[:500]}"
                )

            # حفظ للـ agent
            self._last_citations = citations

            logger.info(
                f"[KnowledgeSearchTool] Found {len(citations)} results for: '{query[:60]}'"
            )
            return "\n\n".join(output_parts)

        except Exception as e:
            logger.error(f"[KnowledgeSearchTool] Error: {e}")
            self._last_citations = []
            return f"Search error: {str(e)}"
