

import logging
from typing import List, Any

logger = logging.getLogger("uvicorn.error")


class MultiRetriever:


    def __init__(
        self,
        vectordb_client,         # Qdrant provider instance
        chunk_model,             # ChunkModel instance (لـ keyword search)
        reranker=None,           # RerankerHelper (optional)
        vector_limit: int = 10,
        keyword_limit: int = 10,
        final_top_k: int = 3,
    ):
        self.vectordb_client = vectordb_client
        self.chunk_model = chunk_model
        self.reranker = reranker
        self.vector_limit = vector_limit
        self.keyword_limit = keyword_limit
        self.final_top_k = final_top_k

    async def retrieve(
        self,
        query: str,
        query_vector: List[float],
        collection_name: str,
        project_id: str,
    ) -> List[Any]:
        """
        الـ method الرئيسية: ترجع النتائج المدمجة والـ reranked.

        Parameters:
        - query: نص السؤال (للـ keyword search والـ reranker)
        - query_vector: الـ embedding (للـ Qdrant)
        - collection_name: اسم الـ Qdrant collection
        - project_id: لفلترة نتائج MongoDB

        Returns:
        - list of scored results (Qdrant ScoredPoint-compatible)
        """
        # ── 1. Vector Search (Qdrant) ────────────────────────────────────────
        vector_results = []
        try:
            vector_results = await self.vectordb_client.search_by_vector(
                collection_name=collection_name,
                vector=query_vector,
                limit=self.vector_limit,
            )
            logger.info(f"[MultiRetriever] Vector search: {len(vector_results)} results")
        except Exception as e:
            logger.warning(f"[MultiRetriever] Vector search failed: {e}")

        # ── 2. Keyword Search (MongoDB) ──────────────────────────────────────
        keyword_results = []
        try:
            if self.chunk_model and self.chunk_model.collection is not None:
                keyword_results = await self.chunk_model.search_by_keyword(
                    project_id=project_id,
                    query=query,
                    limit=self.keyword_limit,
                )
                logger.info(f"[MultiRetriever] Keyword search: {len(keyword_results)} results")
        except Exception as e:
            logger.warning(f"[MultiRetriever] Keyword search failed: {e}")

        # ── 3. Merge + Deduplicate ───────────────────────────────────────────
        merged = _merge_and_deduplicate(vector_results, keyword_results)
        logger.info(f"[MultiRetriever] Merged: {len(merged)} unique results")

        if not merged:
            return []

        # ── 4. Rerank ────────────────────────────────────────────────────────
        if self.reranker is not None:
            final = self.reranker.rerank(
                query=query,
                documents=merged,
                top_k=self.final_top_k,
            )
            logger.info(f"[MultiRetriever] After rerank: {len(final)} results")
        else:
            final = merged[:self.final_top_k]

        return final


def _merge_and_deduplicate(vector_results: list, keyword_results: list) -> list:

    seen_ids = set()
    merged = []

    for doc in vector_results:
        chunk_id = _get_chunk_id(doc)
        if chunk_id and chunk_id not in seen_ids:
            seen_ids.add(chunk_id)
            merged.append(doc)
        elif not chunk_id:
            merged.append(doc)  # مفيش chunk_id → ضيفه على طول

    for doc in keyword_results:
        chunk_id = _get_chunk_id(doc)
        if chunk_id and chunk_id not in seen_ids:
            seen_ids.add(chunk_id)
            merged.append(doc)
        elif not chunk_id:
            merged.append(doc)

    return merged


def _get_chunk_id(doc) -> str:
    """استخرج chunk_id من أي نوع نتيجة (Qdrant أو MongoDB)."""
    try:
        payload = doc.payload if hasattr(doc, "payload") else {}
        return str(payload.get("chunk_id", ""))
    except Exception:
        return ""
