"""
src/chunking/naive_chunker.py
─────────────────────────────
Naive (Recursive) Text Splitter — نفس المنطق القديم بس بـ interface جديد.

بيقسم بناءً على:
  1. فقرات (\\n\\n)
  2. أسطر (\\n)
  3. جمل (. )
  4. كلمات ( )

مع overlap بين الـ chunks.
"""

import logging
from typing import List
from .base_chunker import BaseChunker, Chunk

logger = logging.getLogger("uvicorn.error")


class NaiveChunker(BaseChunker):
    """Recursive text splitter — simple but effective."""

    SEPARATORS = ["\n\n", "\n", ". ", " ", ""]

    @property
    def name(self) -> str:
        return "naive"

    def chunk(
        self,
        pages: list,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        **kwargs
    ) -> List[Chunk]:
        all_chunks = []

        for page in pages:
            text = page.page_content if hasattr(page, "page_content") else str(page)
            meta = page.metadata if hasattr(page, "metadata") else {}

            if not text or not text.strip():
                continue

            splits = self._split_text(text, chunk_size, self.SEPARATORS)

            for idx, split in enumerate(splits):
                chunk_meta = {**meta, "chunk_type": "naive", "chunk_index": idx}
                all_chunks.append(Chunk(chunk_text=split, chunk_metadata=chunk_meta))

        logger.info(f"[NaiveChunker] Generated {len(all_chunks)} chunks from {len(pages)} pages")
        return all_chunks

    def _split_text(self, text: str, chunk_size: int, separators: list) -> List[str]:
        """Recursive split."""
        if len(text) <= chunk_size and "\n" not in text:
            return [text.strip()] if text.strip() else []

        # Find best separator
        separator = separators[-1]
        for sep in separators:
            if sep in text:
                separator = sep
                break

        if separator:
            splits = text.split(separator)
        else:
            splits = list(text)

        # Merge splits into chunks
        good_splits = []
        current_chunk = []
        current_len = 0

        for s in splits:
            s_strip = s.strip()
            if not s_strip:
                continue

            s_len = len(s_strip)

            # If single split is too large, recurse with next separator
            if s_len > chunk_size:
                if current_chunk:
                    good_splits.append(separator.join(current_chunk))
                    current_chunk = []
                    current_len = 0

                next_seps = separators[separators.index(separator) + 1:] if separator in separators else []
                if not next_seps:
                    next_seps = [""]
                good_splits.extend(self._split_text(s_strip, chunk_size, next_seps))
                continue

            sep_len = len(separator) if current_chunk else 0
            if current_len + s_len + sep_len <= chunk_size:
                current_chunk.append(s_strip)
                current_len += s_len + sep_len
            else:
                if current_chunk:
                    good_splits.append(separator.join(current_chunk))
                current_chunk = [s_strip]
                current_len = s_len

        if current_chunk:
            good_splits.append(separator.join(current_chunk))

        return [s for s in good_splits if s.strip()]
