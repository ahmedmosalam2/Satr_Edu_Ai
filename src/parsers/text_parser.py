"""
src/parsers/text_parser.py
──────────────────────────
Plain Text & Markdown Parser.

بيدعم:
  - .txt files
  - .md files (Markdown)
  - .csv files (as text)
  - .json files (as text)
  - .log files
"""

import logging
import json
from typing import List
from .base_parser import BaseParser, ParsedPage

logger = logging.getLogger("uvicorn.error")


class TextParser(BaseParser):
    """Plain text file parser."""

    @property
    def supported_extensions(self) -> List[str]:
        return [".txt", ".md", ".csv", ".log", ".rst", ".yaml", ".yml"]

    def parse(self, file_path: str, **kwargs) -> List[ParsedPage]:
        try:
            # Try UTF-8 first, then fallback encodings
            content = None
            for encoding in ["utf-8", "utf-8-sig", "cp1256", "iso-8859-6", "latin-1"]:
                try:
                    with open(file_path, "r", encoding=encoding) as f:
                        content = f.read()
                    break
                except (UnicodeDecodeError, UnicodeError):
                    continue

            if not content or not content.strip():
                logger.warning(f"[TextParser] Empty or unreadable file: {file_path}")
                return []

            import os
            ext = os.path.splitext(file_path)[-1].lower()

            # For Markdown, try to split by headings
            if ext == ".md":
                return self._parse_markdown(content, file_path)

            # For CSV, return as-is (table format)
            if ext == ".csv":
                return [ParsedPage(
                    page_content=content,
                    metadata={
                        "source": file_path,
                        "content_type": "csv",
                        "parser": "text",
                    }
                )]

            # Plain text: split by double newlines into sections
            sections = [s.strip() for s in content.split("\n\n") if s.strip()]
            if not sections:
                sections = [content.strip()]

            pages = []
            current_chunk = []
            chunk_idx = 0

            for section in sections:
                current_chunk.append(section)
                combined = "\n\n".join(current_chunk)

                # If accumulated text is large enough, flush
                if len(combined) > 2000:
                    pages.append(ParsedPage(
                        page_content=combined,
                        metadata={
                            "source": file_path,
                            "section": chunk_idx,
                            "content_type": "text",
                            "parser": "text",
                        }
                    ))
                    current_chunk = []
                    chunk_idx += 1

            # Flush remaining
            if current_chunk:
                pages.append(ParsedPage(
                    page_content="\n\n".join(current_chunk),
                    metadata={
                        "source": file_path,
                        "section": chunk_idx,
                        "content_type": "text",
                        "parser": "text",
                    }
                ))

            logger.info(f"[TextParser] Extracted {len(pages)} sections from {file_path}")
            return pages

        except Exception as e:
            logger.error(f"[TextParser] Failed to parse {file_path}: {e}")
            return []

    def _parse_markdown(self, content: str, file_path: str) -> List[ParsedPage]:
        """Split markdown by headings (# ## ### etc.)."""
        import re
        # Split on heading lines
        parts = re.split(r"(?=^#{1,6}\s)", content, flags=re.MULTILINE)

        pages = []
        for idx, part in enumerate(parts):
            part = part.strip()
            if not part:
                continue

            # Extract heading from first line
            heading = ""
            lines = part.split("\n")
            if lines[0].startswith("#"):
                heading = lines[0].lstrip("#").strip()

            pages.append(ParsedPage(
                page_content=part,
                metadata={
                    "source": file_path,
                    "section": idx,
                    "heading": heading,
                    "content_type": "markdown",
                    "parser": "text",
                }
            ))

        if not pages and content.strip():
            pages.append(ParsedPage(
                page_content=content,
                metadata={"source": file_path, "content_type": "markdown", "parser": "text"}
            ))

        return pages


class JSONParser(BaseParser):
    """JSON file parser — converts JSON to readable text."""

    @property
    def supported_extensions(self) -> List[str]:
        return [".json"]

    def parse(self, file_path: str, **kwargs) -> List[ParsedPage]:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # If it's a list of objects, each object becomes a page
            if isinstance(data, list):
                pages = []
                for idx, item in enumerate(data):
                    text = json.dumps(item, ensure_ascii=False, indent=2)
                    pages.append(ParsedPage(
                        page_content=text,
                        metadata={
                            "source": file_path,
                            "index": idx,
                            "content_type": "json",
                            "parser": "json",
                        }
                    ))
                return pages
            else:
                # Single object
                text = json.dumps(data, ensure_ascii=False, indent=2)
                return [ParsedPage(
                    page_content=text,
                    metadata={
                        "source": file_path,
                        "content_type": "json",
                        "parser": "json",
                    }
                )]

        except Exception as e:
            logger.error(f"[JSONParser] Failed to parse {file_path}: {e}")
            return []
