"""
src/parsers/parser_factory.py
─────────────────────────────
Auto-detect file type and return the right parser.

Usage:
    from src.parsers.parser_factory import get_parser, parse_file

    # Option 1: Get parser instance
    parser = get_parser("document.pdf")
    pages = parser.parse("document.pdf")

    # Option 2: One-shot parse
    pages = parse_file("/path/to/document.pptx")
"""

import os
import logging
from typing import Optional, List, Dict, Type
from .base_parser import BaseParser, ParsedPage

logger = logging.getLogger("uvicorn.error")

# ── Registry ─────────────────────────────────────────────────────────────────

_PARSER_REGISTRY: Dict[str, Type[BaseParser]] = {}
_registered = False


def _ensure_registered():
    """Lazy registration — يسجل كل الـ parsers مرة واحدة بس."""
    global _registered
    if _registered:
        return

    from .pdf_parser import PDFParser
    from .docx_parser import DOCXParser
    from .pptx_parser import PPTXParser
    from .xlsx_parser import XLSXParser
    from .html_parser import HTMLParser
    from .text_parser import TextParser, JSONParser

    for parser_class in [PDFParser, DOCXParser, PPTXParser, XLSXParser,
                         HTMLParser, TextParser, JSONParser]:
        instance = parser_class()
        for ext in instance.supported_extensions:
            _PARSER_REGISTRY[ext.lower()] = parser_class

    _registered = True
    logger.info(f"[ParserFactory] Registered parsers for: {list(_PARSER_REGISTRY.keys())}")


# ── Public API ───────────────────────────────────────────────────────────────

def get_parser(file_path: str) -> Optional[BaseParser]:
    """
    ارجع الـ parser المناسب بناءً على امتداد الملف.

    Returns None لو الامتداد مش مدعوم.
    """
    _ensure_registered()
    ext = os.path.splitext(file_path)[-1].lower()

    parser_class = _PARSER_REGISTRY.get(ext)
    if parser_class:
        return parser_class()

    logger.warning(f"[ParserFactory] No parser found for extension: {ext}")
    return None


def parse_file(file_path: str, **kwargs) -> List[ParsedPage]:
    """
    One-shot: detect + parse.

    Returns empty list if file type is unsupported.
    """
    parser = get_parser(file_path)
    if parser is None:
        return []
    return parser.parse(file_path, **kwargs)


def get_supported_extensions() -> List[str]:
    """ارجع كل الامتدادات المدعومة."""
    _ensure_registered()
    return sorted(_PARSER_REGISTRY.keys())


def is_supported(file_path: str) -> bool:
    """هل الملف ده مدعوم؟"""
    _ensure_registered()
    ext = os.path.splitext(file_path)[-1].lower()
    return ext in _PARSER_REGISTRY
