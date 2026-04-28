"""
src/evaluation/retrieval_metrics.py
───────────────────────────────────
Retrieval Quality Metrics — قياس جودة البحث.

Metrics:
  - Context Relevance: هل الـ chunks المسترجعة ذات صلة بالسؤال؟
  - Chunk Utilization: كم من الـ chunks المسترجعة استُخدم فعلاً في الإجابة؟
  - MRR (Mean Reciprocal Rank): ترتيب أول نتيجة صحيحة
  - Diversity Score: تنوع المصادر
"""

import logging
from typing import List, Dict, Any, Optional
import numpy as np

logger = logging.getLogger("uvicorn.error")


class RetrievalEvaluator:
    """تقييم جودة الـ retrieval."""

    def __init__(self, embedding_client=None):
        self.embedding_client = embedding_client

    async def evaluate(
        self,
        query: str,
        retrieved_docs: list,
        answer: str = "",
    ) -> Dict[str, Any]:
        """
        تقييم شامل لنتائج البحث.

        Returns dict مع كل الـ metrics.
        """
        results = {
            "num_retrieved": len(retrieved_docs),
            "avg_score": 0.0,
            "score_distribution": {},
            "diversity_score": 0.0,
            "chunk_utilization": 0.0,
            "context_relevance": 0.0,
        }

        if not retrieved_docs:
            return results

        # ── Score Analysis ─────────────────────────────────────────────────
        scores = []
        for doc in retrieved_docs:
            score = doc.score if hasattr(doc, "score") else 0.0
            scores.append(score)

        results["avg_score"] = round(float(np.mean(scores)), 4) if scores else 0.0
        results["min_score"] = round(float(np.min(scores)), 4) if scores else 0.0
        results["max_score"] = round(float(np.max(scores)), 4) if scores else 0.0
        results["score_std"] = round(float(np.std(scores)), 4) if scores else 0.0

        # Score distribution buckets
        if scores:
            results["score_distribution"] = {
                "high (>0.8)": sum(1 for s in scores if s > 0.8),
                "medium (0.5-0.8)": sum(1 for s in scores if 0.5 <= s <= 0.8),
                "low (<0.5)": sum(1 for s in scores if s < 0.5),
            }

        # ── Source Diversity ───────────────────────────────────────────────
        sources = set()
        for doc in retrieved_docs:
            payload = doc.payload if hasattr(doc, "payload") else {}
            source = payload.get("source", payload.get("source_file", ""))
            if source:
                sources.add(source)

        results["unique_sources"] = len(sources)
        results["diversity_score"] = round(
            len(sources) / len(retrieved_docs) if retrieved_docs else 0, 4
        )

        # ── Chunk Utilization ──────────────────────────────────────────────
        if answer:
            used_chunks = 0
            for doc in retrieved_docs:
                payload = doc.payload if hasattr(doc, "payload") else {}
                chunk_text = payload.get("text", "")
                if chunk_text:
                    # Check if any significant words from chunk appear in answer
                    chunk_words = set(chunk_text.lower().split())
                    answer_words = set(answer.lower().split())
                    overlap = chunk_words & answer_words
                    if len(overlap) > 3:  # At least 3 common words
                        used_chunks += 1

            results["chunk_utilization"] = round(
                used_chunks / len(retrieved_docs) if retrieved_docs else 0, 4
            )

        # ── Context Relevance (embedding-based) ───────────────────────────
        if self.embedding_client and answer:
            try:
                query_emb = await self.embedding_client.embed_text(
                    text=query, document_type="query"
                )
                if query_emb:
                    query_vec = np.array(query_emb[0])
                    relevance_scores = []

                    for doc in retrieved_docs:
                        payload = doc.payload if hasattr(doc, "payload") else {}
                        chunk_text = payload.get("text", "")
                        if chunk_text:
                            chunk_emb = await self.embedding_client.embed_text(
                                text=chunk_text[:500], document_type="document"
                            )
                            if chunk_emb:
                                chunk_vec = np.array(chunk_emb[0])
                                sim = float(np.dot(query_vec, chunk_vec) / (
                                    np.linalg.norm(query_vec) * np.linalg.norm(chunk_vec) + 1e-8
                                ))
                                relevance_scores.append(sim)

                    if relevance_scores:
                        results["context_relevance"] = round(float(np.mean(relevance_scores)), 4)
            except Exception as e:
                logger.warning(f"[Eval] Context relevance failed: {e}")

        return results


class GenerationEvaluator:
    """تقييم جودة الإجابة المولّدة."""

    @staticmethod
    def evaluate(
        query: str,
        answer: str,
        retrieved_docs: list,
    ) -> Dict[str, Any]:
        """
        تقييم الإجابة بدون LLM (heuristic-based).
        """
        results = {
            "answer_length": len(answer),
            "answer_word_count": len(answer.split()),
            "has_answer": bool(answer and answer.strip()),
            "faithfulness_score": 0.0,
            "completeness_score": 0.0,
        }

        if not answer or not answer.strip():
            return results

        # ── Faithfulness: هل الإجابة مبنية على الـ context فعلاً؟ ──────
        answer_words = set(answer.lower().split())
        context_words = set()
        for doc in retrieved_docs:
            payload = doc.payload if hasattr(doc, "payload") else {}
            text = payload.get("text", "")
            context_words.update(text.lower().split())

        if context_words:
            overlap = answer_words & context_words
            # Remove common words
            common = {"في", "من", "على", "هو", "هي", "أن", "إن", "the", "is", "a", "an", "of", "to", "and", "in"}
            meaningful_overlap = overlap - common
            meaningful_answer = answer_words - common

            results["faithfulness_score"] = round(
                len(meaningful_overlap) / len(meaningful_answer) if meaningful_answer else 0, 4
            )

        # ── Completeness: هل الإجابة غطت نقاط كافية؟ ─────────────────
        # Simple heuristic: longer answers with paragraphs tend to be more complete
        if len(answer) > 200:
            results["completeness_score"] = min(1.0, len(answer) / 500)
        elif len(answer) > 50:
            results["completeness_score"] = 0.5
        else:
            results["completeness_score"] = 0.2

        return results
