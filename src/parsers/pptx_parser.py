"""
src/parsers/pptx_parser.py
──────────────────────────
PowerPoint Parser (.pptx) — مهم جداً للتعليم!

بيستخرج:
  - نص كل slide (عنوان + محتوى)
  - الجداول داخل الشرائح
  - speaker notes
  - metadata: رقم الشريحة، العنوان، نوع المحتوى
"""

import logging
from typing import List
from .base_parser import BaseParser, ParsedPage

logger = logging.getLogger("uvicorn.error")


class PPTXParser(BaseParser):
    """PowerPoint (.pptx) parser using python-pptx."""

    @property
    def supported_extensions(self) -> List[str]:
        return [".pptx", ".ppt"]

    def parse(self, file_path: str, **kwargs) -> List[ParsedPage]:
        try:
            from pptx import Presentation
            from pptx.util import Inches
        except ImportError:
            logger.error("[PPTXParser] python-pptx not installed")
            return []

        try:
            prs = Presentation(file_path)
            pages = []

            for slide_idx, slide in enumerate(prs.slides):
                slide_texts = []
                slide_title = ""
                tables_text = []

                for shape in slide.shapes:
                    # ── Title ──────────────────────────────────────────
                    if shape.has_text_frame:
                        for paragraph in shape.text_frame.paragraphs:
                            text = paragraph.text.strip()
                            if text:
                                slide_texts.append(text)

                        # Try to detect title
                        if getattr(shape, "is_placeholder", False):
                            try:
                                ph_type = shape.placeholder_format.type
                                # type 1 = CENTER_TITLE, type 15 = TITLE
                                if ph_type in (1, 15) and hasattr(shape, "text") and shape.text.strip():
                                    slide_title = shape.text.strip()
                            except Exception as pe:
                                pass

                    # ── Tables ─────────────────────────────────────────
                    if shape.has_table:
                        table = shape.table
                        rows = []
                        for row in table.rows:
                            cells = [cell.text.strip() for cell in row.cells]
                            rows.append(" | ".join(cells))
                        table_text = "\n".join(rows)
                        if table_text.strip():
                            tables_text.append(table_text)

                # ── Speaker Notes ──────────────────────────────────────
                notes_text = ""
                if slide.has_notes_slide and slide.notes_slide.notes_text_frame:
                    notes_text = slide.notes_slide.notes_text_frame.text.strip()

                # ── Build slide content ────────────────────────────────
                content_parts = []
                if slide_texts:
                    content_parts.append("\n".join(slide_texts))
                if tables_text:
                    content_parts.append("\n---\n".join(tables_text))
                if notes_text:
                    content_parts.append(f"\n[Speaker Notes]\n{notes_text}")

                full_content = "\n\n".join(content_parts).strip()

                if full_content:
                    pages.append(ParsedPage(
                        page_content=full_content,
                        metadata={
                            "source": file_path,
                            "page": slide_idx,
                            "slide_number": slide_idx + 1,
                            "title": slide_title,
                            "has_tables": len(tables_text) > 0,
                            "has_notes": bool(notes_text),
                            "content_type": "slide",
                            "parser": "pptx",
                        }
                    ))

            logger.info(f"[PPTXParser] Extracted {len(pages)} slides from {file_path}")
            return pages

        except Exception as e:
            logger.error(f"[PPTXParser] Failed to parse {file_path}: {e}")
            return []
