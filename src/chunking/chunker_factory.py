"""
src/chunking/chunker_factory.py
───────────────────────────────
Factory for chunking strategies.

Usage:
    from src.chunking.chunker_factory import get_chunker

    chunker = get_chunker("structure")
    chunks = chunker.chunk(pages, chunk_size=500, chunk_overlap=50)
"""

import logging
from typing import Optional
from .base_chunker import BaseChunker

logger = logging.getLogger("uvicorn.error")


def get_chunker(
    strategy: str = "naive",
    embedding_client=None,
    **kwargs
) -> BaseChunker:
    """
    ارجع الـ chunker المناسب.

    Strategies:
    - "naive": تقسيم عادي بالحجم (الافتراضي)
    - "structure": يحترم هيكل المستند (headers, tables, lists)
    - "semantic": يقسم بناءً على تغيّر المعنى (يحتاج embedding_client)

    Parameters:
    - strategy: اسم الاستراتيجية
    - embedding_client: مطلوب للـ semantic chunker فقط
    """
    strategy = strategy.lower().strip()

    if strategy == "naive":
        from .naive_chunker import NaiveChunker
        return NaiveChunker()

    elif strategy == "structure":
        from .structure_chunker import StructureChunker
        return StructureChunker()

    elif strategy == "semantic":
        from .semantic_chunker import SemanticChunker
        return SemanticChunker(
            embedding_client=embedding_client,
            similarity_threshold=kwargs.get("similarity_threshold", 0.5),
        )

    elif strategy == "qa":
        from .qa_chunker import QAChunker
        return QAChunker(
            generation_client=kwargs.get("generation_client"),
            language=kwargs.get("language", "ar"),
        )

    else:
        logger.warning(f"[ChunkerFactory] Unknown strategy '{strategy}', falling back to 'naive'")
        from .naive_chunker import NaiveChunker
        return NaiveChunker()


def list_strategies() -> list:
    """ارجع كل الاستراتيجيات المتاحة."""
    return ["naive", "structure", "semantic", "qa"]
