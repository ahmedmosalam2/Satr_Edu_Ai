"""
src/parsers/html_parser.py
──────────────────────────
HTML Parser — بيستخدم BeautifulSoup.

بيستخرج:
  - النص المنظف من HTML tags
  - العناوين (h1-h6)
  - الجداول
  - القوائم (ul/ol)
  - بيتجاهل scripts, styles, navigation
"""

import logging
from typing import List
from .base_parser import BaseParser, ParsedPage

logger = logging.getLogger("uvicorn.error")


class HTMLParser(BaseParser):
    """HTML file parser using BeautifulSoup."""

    @property
    def supported_extensions(self) -> List[str]:
        return [".html", ".htm"]

    def parse(self, file_path: str, **kwargs) -> List[ParsedPage]:
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            # Fallback: basic text extraction
            return self._fallback_parse(file_path)

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                html_content = f.read()

            soup = BeautifulSoup(html_content, "html.parser")

            # Remove non-content elements
            for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
                tag.decompose()

            pages = []
            sections = []
            current_heading = ""
            current_text = []

            # Walk through content elements
            for element in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "table", "ul", "ol", "pre"]):
                tag_name = element.name

                if tag_name.startswith("h"):
                    # Flush previous section
                    if current_text:
                        sections.append((current_heading, "\n".join(current_text)))
                        current_text = []
                    current_heading = element.get_text(strip=True)
                    current_text.append(current_heading)

                elif tag_name == "table":
                    table_text = self._extract_table(element)
                    if table_text:
                        current_text.append(table_text)

                elif tag_name in ("ul", "ol"):
                    items = element.find_all("li")
                    for item in items:
                        current_text.append(f"• {item.get_text(strip=True)}")

                elif tag_name == "pre":
                    current_text.append(element.get_text())

                else:  # p
                    text = element.get_text(strip=True)
                    if text:
                        current_text.append(text)

            # Flush last section
            if current_text:
                sections.append((current_heading, "\n".join(current_text)))

            # Convert sections to pages
            for idx, (heading, content) in enumerate(sections):
                if content.strip():
                    pages.append(ParsedPage(
                        page_content=content,
                        metadata={
                            "source": file_path,
                            "section": idx,
                            "heading": heading,
                            "title": soup.title.string if soup.title else "",
                            "content_type": "html",
                            "parser": "html",
                        }
                    ))

            # If no sections found, get all text
            if not pages:
                all_text = soup.get_text(separator="\n", strip=True)
                if all_text.strip():
                    pages.append(ParsedPage(
                        page_content=all_text,
                        metadata={
                            "source": file_path,
                            "title": soup.title.string if soup.title else "",
                            "content_type": "html",
                            "parser": "html",
                        }
                    ))

            logger.info(f"[HTMLParser] Extracted {len(pages)} sections from {file_path}")
            return pages

        except Exception as e:
            logger.error(f"[HTMLParser] Failed to parse {file_path}: {e}")
            return self._fallback_parse(file_path)

    def _fallback_parse(self, file_path: str) -> List[ParsedPage]:
        """Fallback: read as plain text and strip HTML tags with regex."""
        import re
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            # Strip HTML tags
            clean = re.sub(r"<[^>]+>", " ", content)
            clean = re.sub(r"\s+", " ", clean).strip()
            if clean:
                return [ParsedPage(
                    page_content=clean,
                    metadata={"source": file_path, "parser": "html_fallback"}
                )]
        except Exception:
            pass
        return []

    @staticmethod
    def _extract_table(table_element) -> str:
        """Convert HTML table to readable text."""
        rows = []
        for tr in table_element.find_all("tr"):
            cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
            if any(c for c in cells):
                rows.append(" | ".join(cells))
        return "\n".join(rows) if rows else ""
