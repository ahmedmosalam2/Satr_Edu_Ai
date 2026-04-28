"""
src/chunking/semantic_chunker.py
────────────────────────────────
Semantic Chunker — يقسم بناءً على تغيّر المعنى.

الفكرة:
  1. يقسم النص لجمل
  2. يحسب embedding لكل جملة
  3. يقارن similarity بين الجمل المتجاورة
  4. لما الـ similarity ينزل كتير → يبدأ chunk جديد

كده الـ chunks بتكون coherent semantically مش بس بالحجم.
"""

import re
import logging
import numpy as np
from typing import List, Optional
from .base_chunker import BaseChunker, Chunk

logger = logging.getLogger("uvicorn.error")


class SemanticChunker(BaseChunker):
    """
    Embedding-based semantic chunker.

    يحتاج embedding_client (أي provider عنده embed_text method).
    لو مفيش embedding_client → بيعمل fallback على NaiveChunker.
    """

    def __init__(self, embedding_client=None, similarity_threshold: float = 0.5):
        """
        Parameters:
        - embedding_client: أي object عنده embed_text(text, document_type) method
        - similarity_threshold: لما cosine similarity ينزل تحت القيمة دي → chunk جديد
        """
        self.embedding_client = embedding_client
        self.similarity_threshold = similarity_threshold

    @property
    def name(self) -> str:
        return "semantic"

    def chunk(
        self,
        pages: list,
        chunk_size: int = 800,
        chunk_overlap: int = 0,
        **kwargs
    ) -> List[Chunk]:
        # If no embedding client, fall back to naive
        if self.embedding_client is None:
            logger.warning("[SemanticChunker] No embedding client — falling back to NaiveChunker")
            from .naive_chunker import NaiveChunker
            return NaiveChunker().chunk(pages, chunk_size, chunk_overlap)

        all_chunks = []

        for page in pages:
            text = page.page_content if hasattr(page, "page_content") else str(page)
            meta = page.metadata if hasattr(page, "metadata") else {}

            if not text or not text.strip():
                continue

            # Split into sentences
            sentences = self._split_sentences(text)
            if len(sentences) <= 1:
                all_chunks.append(Chunk(
                    chunk_text=text.strip(),
                    chunk_metadata={**meta, "chunk_type": "semantic"}
                ))
                continue

            # Get embeddings for all sentences
            try:
                import asyncio
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If already in async context, use nest_asyncio or thread
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        embeddings = executor.submit(
                            asyncio.run,
                            self.embedding_client.embed_text(text=sentences, document_type="document")
                        ).result()
                else:
                    embeddings = asyncio.run(
                        self.embedding_client.embed_text(text=sentences, document_type="document")
                    )
            except Exception as e:
                logger.warning(f"[SemanticChunker] Embedding failed: {e} — falling back to naive")
                from .naive_chunker import NaiveChunker
                return NaiveChunker().chunk(pages, chunk_size, chunk_overlap)

            if not embeddings or len(embeddings) != len(sentences):
                from .naive_chunker import NaiveChunker
                return NaiveChunker().chunk(pages, chunk_size, chunk_overlap)

            # Find breakpoints based on similarity drops
            breakpoints = self._find_breakpoints(embeddings)

            # Group sentences into chunks
            page_chunks = self._group_sentences(sentences, breakpoints, chunk_size, meta)
            all_chunks.extend(page_chunks)

        logger.info(f"[SemanticChunker] Generated {len(all_chunks)} semantic chunks")
        return all_chunks

    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences (Arabic + English aware)."""
        # Split on sentence boundaries
        sentences = re.split(
            r'(?<=[.!?؟。])\s+|(?<=\n)\s*',
            text.strip()
        )
        return [s.strip() for s in sentences if s.strip() and len(s.strip()) > 5]

    def _find_breakpoints(self, embeddings: list) -> List[int]:
        """Find indices where semantic similarity drops significantly."""
        if len(embeddings) < 2:
            return []

        similarities = []
        for i in range(len(embeddings) - 1):
            sim = self._cosine_similarity(embeddings[i], embeddings[i + 1])
            similarities.append(sim)

        if not similarities:
            return []

        # Breakpoint = where similarity is below threshold
        # Use percentile-based threshold for adaptivity
        avg_sim = np.mean(similarities)
        std_sim = np.std(similarities)
        adaptive_threshold = max(self.similarity_threshold, avg_sim - std_sim)

        breakpoints = []
        for i, sim in enumerate(similarities):
            if sim < adaptive_threshold:
                breakpoints.append(i + 1)  # break AFTER sentence i

        return breakpoints

    def _group_sentences(
        self, sentences: List[str], breakpoints: List[int],
        chunk_size: int, base_meta: dict
    ) -> List[Chunk]:
        """Group sentences into chunks using breakpoints."""
        chunks = []
        current_sentences = []
        chunk_idx = 0

        for i, sentence in enumerate(sentences):
            current_sentences.append(sentence)
            current_text = " ".join(current_sentences)

            # Break if: breakpoint here OR text exceeds chunk_size
            is_breakpoint = i + 1 in breakpoints
            is_too_long = len(current_text) >= chunk_size

            if (is_breakpoint or is_too_long) and current_sentences:
                chunk_text = " ".join(current_sentences)
                if chunk_text.strip():
                    chunks.append(Chunk(
                        chunk_text=chunk_text.strip(),
                        chunk_metadata={
                            **base_meta,
                            "chunk_type": "semantic",
                            "chunk_index": chunk_idx,
                        }
                    ))
                    chunk_idx += 1
                current_sentences = []

        # Flush remaining
        if current_sentences:
            chunk_text = " ".join(current_sentences)
            if chunk_text.strip():
                chunks.append(Chunk(
                    chunk_text=chunk_text.strip(),
                    chunk_metadata={**base_meta, "chunk_type": "semantic", "chunk_index": chunk_idx}
                ))

        return chunks

    @staticmethod
    def _cosine_similarity(vec_a: list, vec_b: list) -> float:
        """Compute cosine similarity between two vectors."""
        a = np.array(vec_a)
        b = np.array(vec_b)
        dot = np.dot(a, b)
        norm = np.linalg.norm(a) * np.linalg.norm(b)
        if norm == 0:
            return 0.0
        return float(dot / norm)
