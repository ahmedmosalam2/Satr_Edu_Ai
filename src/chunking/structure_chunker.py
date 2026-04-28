"""
src/chunking/structure_chunker.py
─────────────────────────────────
Structure-Aware Chunker — بيحترم هيكل المستند.

نفس فكرة DeepDocController بس بـ interface موحد:
  - العناوين بتبدأ chunk جديد
  - الجداول والقوائم تيجي كـ chunk كامل
  - الفقرات بتتجمع حتى chunk_size
"""

import re
import logging
from typing import List
from .base_chunker import BaseChunker, Chunk

logger = logging.getLogger("uvicorn.error")


class StructureChunker(BaseChunker):
    """Structure-aware chunker — يحترم headers, tables, lists."""

    # Header patterns
    HEADER_RE = re.compile(
        r"^(?:"
        r"\d+[\.\-\)]\s+\S"                    # "1. " or "1- "
        r"|#{1,6}\s"                            # Markdown headings
        r"|(?:Chapter|Section|Unit|Part)\b"     # English
        r"|(?:الفصل|الباب|المبحث|المطلب)\b"    # Arabic
        r")",
        re.MULTILINE
    )

    @property
    def name(self) -> str:
        return "structure"

    def chunk(
        self,
        pages: list,
        chunk_size: int = 800,
        chunk_overlap: int = 80,
        **kwargs
    ) -> List[Chunk]:
        all_chunks = []

        for page in pages:
            text = page.page_content if hasattr(page, "page_content") else str(page)
            meta = page.metadata if hasattr(page, "metadata") else {}

            if not text or not text.strip():
                continue

            content_type = meta.get("content_type", "")

            # Tables and spreadsheets: keep as single chunk
            if content_type in ("table", "spreadsheet"):
                all_chunks.append(Chunk(
                    chunk_text=text.strip(),
                    chunk_metadata={**meta, "chunk_type": "table"}
                ))
                continue

            # Parse blocks from text
            blocks = self._parse_blocks(text)
            page_chunks = self._blocks_to_chunks(blocks, chunk_size, chunk_overlap, meta)
            all_chunks.extend(page_chunks)

        logger.info(f"[StructureChunker] Generated {len(all_chunks)} chunks from {len(pages)} pages")
        return all_chunks

    def _parse_blocks(self, text: str) -> List[dict]:
        """Parse text into typed blocks: header, list, paragraph."""
        blocks = []
        raw_blocks = re.split(r"\n{2,}", text.strip())

        for block_text in raw_blocks:
            block_text = block_text.strip()
            if not block_text:
                continue

            # Classify
            lines = [l.strip() for l in block_text.split("\n") if l.strip()]

            if self.HEADER_RE.match(block_text) and len(block_text) < 150:
                btype = "header"
            elif len(lines) >= 2:
                list_lines = sum(1 for l in lines if re.match(r"^[•\-\*\d]\s", l))
                if list_lines / len(lines) >= 0.5:
                    btype = "list"
                else:
                    btype = "paragraph"
            else:
                btype = "paragraph"

            blocks.append({"text": block_text, "type": btype})

        return blocks

    def _blocks_to_chunks(
        self, blocks: list, chunk_size: int, chunk_overlap: int, base_meta: dict
    ) -> List[Chunk]:
        """Convert blocks to chunks respecting structure."""
        chunks = []
        current_header = ""
        current_text = ""

        def flush(chunk_type="paragraph"):
            nonlocal current_text
            if current_text.strip():
                sub_chunks = self._split_long_text(current_text.strip(), chunk_size, chunk_overlap)
                for i, sub in enumerate(sub_chunks):
                    chunks.append(Chunk(
                        chunk_text=sub,
                        chunk_metadata={
                            **base_meta,
                            "chunk_type": chunk_type,
                            "header": current_header,
                            "sub_chunk": i if len(sub_chunks) > 1 else 0,
                        }
                    ))
                current_text = ""

        for block in blocks:
            btype = block["type"]
            btext = block["text"]

            if btype == "header":
                flush()
                current_header = btext
                current_text = btext + "\n"

            elif btype == "list":
                flush()
                header_prefix = f"{current_header}\n\n" if current_header else ""
                chunks.append(Chunk(
                    chunk_text=(header_prefix + btext).strip(),
                    chunk_metadata={**base_meta, "chunk_type": "list", "header": current_header}
                ))

            else:  # paragraph
                candidate = current_text + "\n\n" + btext if current_text else btext
                if len(candidate) > chunk_size:
                    flush()
                    current_text = btext
                else:
                    current_text = candidate

        flush()
        return chunks

    @staticmethod
    def _split_long_text(text: str, chunk_size: int, overlap: int) -> List[str]:
        """Split text that exceeds chunk_size."""
        if len(text) <= chunk_size:
            return [text]

        parts = []
        start = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            if end < len(text):
                for sep in [". ", ".\n", "\n", " "]:
                    idx = text.rfind(sep, start, end)
                    if idx > start + chunk_size // 2:
                        end = idx + len(sep)
                        break
            parts.append(text[start:end].strip())
            start = max(start + 1, end - overlap)
        return [p for p in parts if p]
