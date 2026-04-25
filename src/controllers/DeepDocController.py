"""
src/controllers/DeepDocController.py
──────────────────────────────────────
Document Intelligence Pipeline — "DeepDoc" inspired by RAGFlow.

بدل ما تقطع النص عشوائياً بحجم ثابت,
بيحلل هيكل المستند وبيعمل chunks ذكية:

  PDF Page
    ├── ✅ عنوان  → chunk بنفسه كـ header
    ├── ✅ فقرة   → chunk طبيعي
    ├── ✅ جدول   → chunk واحد كامل مع العنوان
    └── ✅ قائمة → chunk واحد

يعمل كـ FALLBACK على ProcessController العادي لو PyMuPDF مش متاح.
أي كود موجود مش هيتأثر — فقط تستدعيه بشكل صريح.
"""

import logging
import re
from typing import List, Dict, Any, Optional

logger = logging.getLogger("uvicorn.error")


class SimpleDocument:
    """نفس interface الـ LangChain Document عشان نكون compatible."""
    def __init__(self, page_content: str, metadata: dict):
        self.page_content = page_content
        self.metadata = metadata

    def __repr__(self):
        preview = self.page_content[:60].replace("\n", " ")
        return f"Document(type={self.metadata.get('chunk_type','text')}, chars={len(self.page_content)}, preview='{preview}...')"


class DeepDocController:
    """
    Smart document analysis + structure-aware chunking.

    Features:
    - Header detection (Arabic + English)
    - Table detection and preservation
    - Bullet list grouping
    - Paragraph-aware splitting
    - Falls back to simple splitting if structure detection fails
    """

    # ── Regex patterns ────────────────────────────────────────────────────────

    # عناوين عربية (تبدأ بأرقام أو نقاط أو كلمات مثل "فصل/باب/مقدمة")
    ARABIC_HEADER_RE = re.compile(
        r"^(?:"
        r"\d+[\.\-\)]\s+\S"          # "1. " أو "1- " أو "1) "
        r"|[أ-ي]\.\s+\S"             # "أ. "
        r"|(?:الفصل|الباب|المبحث|المطلب|أولاً|ثانياً|ثالثاً|رابعاً|خلاصة|مقدمة|خاتمة)\b"
        r")",
        re.MULTILINE
    )

    # عناوين إنجليزية (أقصر من 80 حرف، مش بتنتهي بنقطة)
    ENGLISH_HEADER_RE = re.compile(
        r"^(?:"
        r"(?:Chapter|Section|Unit|Part|Module|Introduction|Conclusion|Summary|Overview)\b"
        r"|\d+\.\d*\s+[A-Z]"        # "1.2 Title"
        r"|[A-Z][A-Z\s]{3,40}$"      # UPPERCASE TITLE
        r")",
        re.MULTILINE
    )

    # ── Public API ────────────────────────────────────────────────────────────

    def analyze_pdf(
        self,
        file_path: str,
        chunk_size: int = 800,
        chunk_overlap: int = 80,
    ) -> List[SimpleDocument]:
        """
        الـ method الرئيسية: بتحلل PDF وترجع chunks ذكية.

        Parameters:
        - file_path: مسار الـ PDF
        - chunk_size: الحد الأقصى لحجم الـ chunk بالحروف
        - chunk_overlap: حروف الـ overlap بين chunks متجاورة

        Returns:
        - List[SimpleDocument] — نفس format الـ LangChain
        """
        logger.info(f"[DeepDoc] Analyzing: {file_path}")
        try:
            blocks = self._extract_blocks_from_pdf(file_path)
            if not blocks:
                logger.warning("[DeepDoc] No blocks extracted, using fallback")
                return self._fallback_load(file_path, chunk_size, chunk_overlap)

            chunks = self._blocks_to_chunks(blocks, chunk_size, chunk_overlap, file_path)
            logger.info(f"[DeepDoc] Generated {len(chunks)} smart chunks from {file_path}")
            return chunks

        except Exception as e:
            logger.error(f"[DeepDoc] Error analyzing {file_path}: {e}. Using fallback.")
            return self._fallback_load(file_path, chunk_size, chunk_overlap)

    def analyze_text(
        self,
        text: str,
        metadata: Optional[dict] = None,
        chunk_size: int = 800,
        chunk_overlap: int = 80,
    ) -> List[SimpleDocument]:
        """
        تحليل نص خام (مش PDF) وتقسيمه بشكل ذكي.
        """
        metadata = metadata or {}
        blocks = self._parse_text_blocks(text, page_num=metadata.get("page", 0))
        return self._blocks_to_chunks(blocks, chunk_size, chunk_overlap, source=metadata.get("source", ""))

    # ── Block extraction from PDF ─────────────────────────────────────────────

    def _extract_blocks_from_pdf(self, file_path: str) -> List[Dict]:
        """
        استخراج blocks مصنفة من PDF باستخدام PyMuPDF.
        كل block عنده: text, type (header/table/list/paragraph), page, bbox
        """
        import fitz  # PyMuPDF

        all_blocks = []
        doc = fitz.open(file_path)

        for page_num, page in enumerate(doc):
            # استخراج blocks مع metadata
            raw_blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]

            for block in raw_blocks:
                if block.get("type") != 0:  # type 0 = text, type 1 = image
                    continue

                # جمع النص من كل الـ lines
                lines = []
                font_sizes = []
                is_bold = False

                for line in block.get("lines", []):
                    line_text = ""
                    for span in line.get("spans", []):
                        line_text += span.get("text", "")
                        font_sizes.append(span.get("size", 12))
                        flags = span.get("flags", 0)
                        if flags & 16:  # Bold flag
                            is_bold = True
                    if line_text.strip():
                        lines.append(line_text.strip())

                if not lines:
                    continue

                block_text = "\n".join(lines)
                avg_font_size = sum(font_sizes) / len(font_sizes) if font_sizes else 12

                # تصنيف الـ block
                block_type = self._classify_block(
                    text=block_text,
                    avg_font_size=avg_font_size,
                    is_bold=is_bold,
                    num_lines=len(lines),
                )

                all_blocks.append({
                    "text": block_text,
                    "type": block_type,
                    "page": page_num,
                    "font_size": avg_font_size,
                    "is_bold": is_bold,
                })

        doc.close()
        return all_blocks

    # ── Block classification ──────────────────────────────────────────────────

    def _classify_block(
        self,
        text: str,
        avg_font_size: float,
        is_bold: bool,
        num_lines: int,
    ) -> str:
        """
        صنّف الـ block كـ: header, table, list, paragraph
        """
        stripped = text.strip()

        # جدول: فيه | أو أكتر من سطر وبيبدأوا بعلامات تشابه
        if "|" in stripped and stripped.count("\n") >= 2:
            return "table"

        # قائمة: أغلب السطور بتبدأ بـ • - * أو أرقام
        lines = [l.strip() for l in stripped.split("\n") if l.strip()]
        if len(lines) >= 2:
            list_lines = sum(
                1 for l in lines
                if re.match(r"^[•\-\*\d]\s", l)
            )
            if list_lines / len(lines) >= 0.6:
                return "list"

        # عنوان: خط كبير أو bold أو نص قصير يطابق patterns
        if (avg_font_size >= 14 or is_bold) and num_lines <= 3 and len(stripped) < 150:
            return "header"
        if self.ARABIC_HEADER_RE.match(stripped) or self.ENGLISH_HEADER_RE.match(stripped):
            if len(stripped) < 150:
                return "header"

        return "paragraph"

    # ── Text block parser (for plain text) ───────────────────────────────────

    def _parse_text_blocks(self, text: str, page_num: int = 0) -> List[Dict]:
        """تقسيم نص عادي لـ blocks بناءً على الأسطر الفاضية."""
        blocks = []
        raw_blocks = re.split(r"\n{2,}", text.strip())
        for block_text in raw_blocks:
            block_text = block_text.strip()
            if not block_text:
                continue
            block_type = self._classify_block(
                text=block_text,
                avg_font_size=12,
                is_bold=False,
                num_lines=block_text.count("\n") + 1,
            )
            blocks.append({"text": block_text, "type": block_type, "page": page_num})
        return blocks

    # ── Blocks → Chunks ───────────────────────────────────────────────────────

    def _blocks_to_chunks(
        self,
        blocks: List[Dict],
        chunk_size: int,
        chunk_overlap: int,
        source: str = "",
    ) -> List[SimpleDocument]:
        """
        حول الـ blocks لـ chunks محترمة:
        - الـ headers بتبدأ chunk جديد
        - الـ tables والـ lists تيجي كـ chunk واحد كامل
        - الـ paragraphs بتتجمع حتى chunk_size
        """
        chunks = []
        current_header = ""
        current_text = ""
        current_page = 0

        def flush(chunk_type="paragraph"):
            nonlocal current_text
            if current_text.strip():
                # لو الـ chunk كبير جداً، اقسمه
                sub_chunks = self._split_long_text(current_text.strip(), chunk_size, chunk_overlap)
                for i, sub in enumerate(sub_chunks):
                    chunks.append(SimpleDocument(
                        page_content=sub,
                        metadata={
                            "source": source,
                            "page": current_page,
                            "chunk_type": chunk_type,
                            "header": current_header,
                            "sub_chunk": i if len(sub_chunks) > 1 else 0,
                        }
                    ))
                current_text = ""

        for block in blocks:
            btype = block["type"]
            btext = block["text"]
            bpage = block.get("page", 0)

            if btype == "header":
                # ابدأ chunk جديد
                flush()
                current_header = btext
                current_page = bpage
                # الـ header نفسه بيبدأ الـ chunk الجديد
                current_text = btext + "\n"

            elif btype in ("table", "list"):
                # الـ tables والـ lists يجوا كـ chunk مستقل
                flush()
                header_prefix = f"{current_header}\n\n" if current_header else ""
                chunks.append(SimpleDocument(
                    page_content=(header_prefix + btext).strip(),
                    metadata={
                        "source": source,
                        "page": bpage,
                        "chunk_type": btype,
                        "header": current_header,
                    }
                ))
                current_page = bpage

            else:  # paragraph
                current_page = bpage
                # لو إضافة الـ paragraph هتعدي الـ chunk_size، flush الأول
                candidate = current_text + "\n\n" + btext if current_text else btext
                if len(candidate) > chunk_size:
                    flush()
                    current_text = btext
                else:
                    current_text = candidate

        flush()  # آخر chunk
        return chunks

    # ── Long text splitter ────────────────────────────────────────────────────

    def _split_long_text(self, text: str, chunk_size: int, overlap: int) -> List[str]:
        """قسّم نص طويل لأجزاء مع overlap."""
        if len(text) <= chunk_size:
            return [text]

        parts = []
        start = 0
        while start < len(text):
            end = min(start + chunk_size, len(text))
            # ابحث عن نهاية جملة قريبة
            if end < len(text):
                for sep in [". ", ".\n", "\n", " "]:
                    idx = text.rfind(sep, start, end)
                    if idx > start + chunk_size // 2:
                        end = idx + len(sep)
                        break
            parts.append(text[start:end].strip())
            start = max(start + 1, end - overlap)
        return [p for p in parts if p]

    # ── Fallback ──────────────────────────────────────────────────────────────

    def _fallback_load(
        self,
        file_path: str,
        chunk_size: int,
        chunk_overlap: int,
    ) -> List[SimpleDocument]:
        """
        Fallback: نفس الـ ProcessController القديم.
        يتنفذ لو PyMuPDF مش موجود أو فيه error.
        """
        from src.utils.content_processor import DirectPDFLoader, RecursiveTextSplitter

        try:
            loader = DirectPDFLoader(file_path)
            pages = loader.load()
            splitter = RecursiveTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
            texts = [p.page_content for p in pages]
            metas = [p.metadata for p in pages]
            return splitter.create_documents(texts, metadatas=metas)
        except Exception as e:
            logger.error(f"[DeepDoc] Fallback also failed: {e}")
            return []


# ── Singleton helper ──────────────────────────────────────────────────────────
_deepdoc_instance: Optional[DeepDocController] = None


def get_deepdoc() -> DeepDocController:
    global _deepdoc_instance
    if _deepdoc_instance is None:
        _deepdoc_instance = DeepDocController()
    return _deepdoc_instance
