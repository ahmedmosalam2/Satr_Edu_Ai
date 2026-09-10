"""
src/pipeline/pipeline_manager.py
────────────────────────────────
Document Processing Pipeline — The Orchestrator.

بيعمل الـ flow كامل:
  Upload → Detect Type → Parse → Chunk → Return

Usage:
    from src.pipeline.pipeline_manager import DocumentPipeline

    pipeline = DocumentPipeline()

    # Process any file
    result = pipeline.process(
        file_path="/path/to/document.pptx",
        chunk_strategy="structure",
        chunk_size=500,
    )

    print(result.chunks)        # list of Chunk objects
    print(result.file_type)     # ".pptx"
    print(result.pages_count)   # 15
    print(result.chunks_count)  # 42

NOTE: ده كود جديد تماماً — مش بيأثر على أي كود موجود.
      الـ ProcessController القديم شغال زي ما هو.
"""

import os
import time
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

from src.parsers.parser_factory import parse_file, get_parser, is_supported, get_supported_extensions
from src.parsers.base_parser import ParsedPage
from src.chunking.chunker_factory import get_chunker, list_strategies
from src.chunking.base_chunker import Chunk

logger = logging.getLogger("uvicorn.error")


@dataclass
class PipelineResult:
    """نتيجة معالجة ملف كامل."""
    success: bool
    file_path: str
    file_type: str
    file_name: str

    # Parsing results
    pages: List[ParsedPage] = field(default_factory=list)
    pages_count: int = 0

    # Chunking results
    chunks: List[Chunk] = field(default_factory=list)
    chunks_count: int = 0

    # Config used
    chunk_strategy: str = "naive"
    chunk_size: int = 500
    chunk_overlap: int = 50

    # Performance
    parse_time_ms: float = 0
    chunk_time_ms: float = 0
    total_time_ms: float = 0

    # Errors
    error: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to JSON-serializable dict."""
        return {
            "success": self.success,
            "file_path": self.file_path,
            "file_type": self.file_type,
            "file_name": self.file_name,
            "pages_count": self.pages_count,
            "chunks_count": self.chunks_count,
            "chunk_strategy": self.chunk_strategy,
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
            "parse_time_ms": round(self.parse_time_ms, 2),
            "chunk_time_ms": round(self.chunk_time_ms, 2),
            "total_time_ms": round(self.total_time_ms, 2),
            "error": self.error,
        }


class DocumentPipeline:
    """
    The main pipeline orchestrator.

    Usage:
        pipeline = DocumentPipeline()
        result = pipeline.process("document.pdf", chunk_strategy="structure")
    """

    def __init__(self, embedding_client=None):
        """
        Parameters:
        - embedding_client: optional، مطلوب بس للـ semantic chunker
        """
        self.embedding_client = embedding_client

    def process(
        self,
        file_path: str,
        chunk_strategy: str = "naive",
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        **kwargs
    ) -> PipelineResult:
        """
        معالجة ملف كامل: Parse → Chunk.

        Parameters:
        - file_path: المسار الكامل للملف
        - chunk_strategy: "naive" | "structure" | "semantic"
        - chunk_size: الحد الأقصى لحجم الـ chunk
        - chunk_overlap: overlap بين الـ chunks

        Returns:
        - PipelineResult مع كل التفاصيل
        """
        total_start = time.time()
        file_name = os.path.basename(file_path)
        file_type = os.path.splitext(file_path)[-1].lower()

        result = PipelineResult(
            success=False,
            file_path=file_path,
            file_type=file_type,
            file_name=file_name,
            chunk_strategy=chunk_strategy,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

        # ── 1. Validate ──────────────────────────────────────────────────────
        if not os.path.exists(file_path):
            result.error = f"File not found: {file_path}"
            logger.error(f"[Pipeline] {result.error}")
            return result

        if not is_supported(file_path):
            result.error = f"Unsupported file type: {file_type}. Supported: {get_supported_extensions()}"
            logger.error(f"[Pipeline] {result.error}")
            return result

        # ── 2. Parse ─────────────────────────────────────────────────────────
        logger.info(f"[Pipeline] Parsing: {file_name} ({file_type})")
        parse_start = time.time()

        # Smart OCR: لو الملف PDF، نربط OCR controller عشان يكتشف الصفحات المسحوبة
        parse_kwargs = {}
        if file_type == ".pdf":
            try:
                from src.controllers.OCRController import OCRController
                parse_kwargs["ocr_controller"] = OCRController()
                logger.info("[Pipeline] OCR controller attached — scanned pages will be auto-detected")
            except Exception as e:
                logger.warning(f"[Pipeline] OCR controller not available: {e}")

        try:
            pages = parse_file(file_path, **parse_kwargs)
            result.pages = pages
            result.pages_count = len(pages)
            result.parse_time_ms = (time.time() - parse_start) * 1000
        except Exception as e:
            result.error = f"Parsing failed: {str(e)}"
            result.parse_time_ms = (time.time() - parse_start) * 1000
            logger.error(f"[Pipeline] {result.error}")
            return result

        if not pages:
            result.error = "No content extracted from file"
            logger.warning(f"[Pipeline] {result.error}")
            return result

        logger.info(f"[Pipeline] Parsed {len(pages)} pages in {result.parse_time_ms:.0f}ms")

        # ── 3. Chunk ─────────────────────────────────────────────────────────
        logger.info(f"[Pipeline] Chunking with strategy: {chunk_strategy}")
        chunk_start = time.time()

        try:
            chunker = get_chunker(
                strategy=chunk_strategy,
                embedding_client=self.embedding_client,
                **kwargs
            )
            chunks = chunker.chunk(
                pages=pages,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
            result.chunks = chunks
            result.chunks_count = len(chunks)
            result.chunk_time_ms = (time.time() - chunk_start) * 1000
        except Exception as e:
            result.error = f"Chunking failed: {str(e)}"
            result.chunk_time_ms = (time.time() - chunk_start) * 1000
            logger.error(f"[Pipeline] {result.error}")
            return result

        # ── 4. Done! ──────────────────────────────────────────────────────────
        result.success = True
        result.total_time_ms = (time.time() - total_start) * 1000

        logger.info(
            f"[Pipeline] ✅ {file_name}: {result.pages_count} pages → "
            f"{result.chunks_count} chunks ({chunk_strategy}) in {result.total_time_ms:.0f}ms"
        )
        return result

    def process_text(
        self,
        text: str,
        chunk_strategy: str = "naive",
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        metadata: Optional[dict] = None,
        **kwargs
    ) -> PipelineResult:
        """
        معالجة نص خام (مش ملف).

        مفيد للـ:
        - نص مكتوب مباشرة
        - نص منسوخ
        - نتيجة OCR
        """
        total_start = time.time()
        metadata = metadata or {}

        result = PipelineResult(
            success=False,
            file_path="<raw_text>",
            file_type="text",
            file_name=metadata.get("source", "raw_text"),
            chunk_strategy=chunk_strategy,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

        if not text or not text.strip():
            result.error = "Empty text provided"
            return result

        # Wrap as ParsedPage
        pages = [ParsedPage(page_content=text, metadata=metadata)]
        result.pages = pages
        result.pages_count = 1

        # Chunk
        try:
            chunker = get_chunker(
                strategy=chunk_strategy,
                embedding_client=self.embedding_client,
                **kwargs
            )
            chunks = chunker.chunk(pages, chunk_size, chunk_overlap)
            result.chunks = chunks
            result.chunks_count = len(chunks)
            result.success = True
        except Exception as e:
            result.error = f"Chunking failed: {str(e)}"

        result.total_time_ms = (time.time() - total_start) * 1000
        return result

    @staticmethod
    def supported_extensions() -> List[str]:
        """ارجع كل الامتدادات المدعومة."""
        return get_supported_extensions()

    @staticmethod
    def available_strategies() -> List[str]:
        """ارجع كل استراتيجيات التقسيم المتاحة."""
        return list_strategies()
