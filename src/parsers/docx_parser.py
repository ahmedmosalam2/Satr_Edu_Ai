"""
src/parsers/docx_parser.py
──────────────────────────
Word Document Parser (.docx) — بيستخدم python-docx.

بيستخرج:
  - فقرات (paragraphs)
  - جداول (tables)
  - عناوين (headings) مع مستواها
  - metadata: نوع المحتوى (heading/paragraph/table)
"""

import logging
from typing import List
from .base_parser import BaseParser, ParsedPage

logger = logging.getLogger("uvicorn.error")


class DOCXParser(BaseParser):
    """Word Document (.docx) parser using python-docx."""

    @property
    def supported_extensions(self) -> List[str]:
        return [".docx", ".doc"]

    def parse(self, file_path: str, **kwargs) -> List[ParsedPage]:
        try:
            from docx import Document
        except ImportError:
            logger.error("[DOCXParser] python-docx not installed")
            return []

        try:
            doc = Document(file_path)
            pages = []

            # ── Paragraphs ────────────────────────────────────────────────
            current_section = []
            current_heading = ""
            section_idx = 0

            for para in doc.paragraphs:
                text = para.text.strip()
                if not text:
                    continue

                # Detect heading
                if para.style and para.style.name.startswith("Heading"):
                    # Flush previous section
                    if current_section:
                        pages.append(ParsedPage(
                            page_content="\n".join(current_section),
                            metadata={
                                "source": file_path,
                                "section": section_idx,
                                "heading": current_heading,
                                "content_type": "paragraph",
                                "parser": "docx",
                            }
                        ))
                        section_idx += 1
                        current_section = []

                    current_heading = text
                    current_section.append(text)
                else:
                    current_section.append(text)

            # Flush last section
            if current_section:
                pages.append(ParsedPage(
                    page_content="\n".join(current_section),
                    metadata={
                        "source": file_path,
                        "section": section_idx,
                        "heading": current_heading,
                        "content_type": "paragraph",
                        "parser": "docx",
                    }
                ))

            # ── Tables ────────────────────────────────────────────────────
            for t_idx, table in enumerate(doc.tables):
                table_text = self._table_to_text(table)
                if table_text.strip():
                    pages.append(ParsedPage(
                        page_content=table_text,
                        metadata={
                            "source": file_path,
                            "content_type": "table",
                            "table_index": t_idx,
                            "parser": "docx",
                        }
                    ))

            logger.info(f"[DOCXParser] Extracted {len(pages)} sections/tables from {file_path}")
            return pages

        except Exception as e:
            logger.error(f"[DOCXParser] Failed to parse {file_path}: {e}")
            return []

    @staticmethod
    def _table_to_text(table) -> str:
        """Convert docx table to readable text."""
        rows = []
        for row in table.rows:
            cells = [cell.text.strip() for cell in row.cells]
            rows.append(" | ".join(cells))
        return "\n".join(rows)
