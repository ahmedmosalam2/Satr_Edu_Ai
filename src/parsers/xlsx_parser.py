"""
src/parsers/xlsx_parser.py
──────────────────────────
Excel Parser (.xlsx, .xls) — بيستخدم openpyxl.

بيستخرج:
  - كل sheet كـ page منفصلة
  - الجداول بتتحول لنص مقروء
  - بيتجاهل الخلايا الفاضية
"""

import logging
from typing import List
from .base_parser import BaseParser, ParsedPage

logger = logging.getLogger("uvicorn.error")


class XLSXParser(BaseParser):
    """Excel (.xlsx/.xls) parser using openpyxl."""

    @property
    def supported_extensions(self) -> List[str]:
        return [".xlsx", ".xls"]

    def parse(self, file_path: str, **kwargs) -> List[ParsedPage]:
        try:
            import openpyxl
        except ImportError:
            logger.error("[XLSXParser] openpyxl not installed")
            return []

        try:
            wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
            pages = []

            for sheet_name in wb.sheetnames:
                ws = wb[sheet_name]
                rows = []

                for row in ws.iter_rows(values_only=True):
                    cells = [str(c).strip() if c is not None else "" for c in row]
                    # Skip completely empty rows
                    if any(c for c in cells):
                        rows.append(" | ".join(cells))

                if rows:
                    # Use first row as potential header
                    content = "\n".join(rows)
                    pages.append(ParsedPage(
                        page_content=content,
                        metadata={
                            "source": file_path,
                            "sheet_name": sheet_name,
                            "row_count": len(rows),
                            "content_type": "spreadsheet",
                            "parser": "xlsx",
                        }
                    ))

            wb.close()
            logger.info(f"[XLSXParser] Extracted {len(pages)} sheets from {file_path}")
            return pages

        except Exception as e:
            logger.error(f"[XLSXParser] Failed to parse {file_path}: {e}")
            return []
