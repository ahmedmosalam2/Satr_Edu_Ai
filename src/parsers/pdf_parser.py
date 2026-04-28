"""
src/parsers/pdf_parser.py
─────────────────────────
PDF Parser — بيحاول أكتر من طريقة:
  1. PyMuPDF (fitz) — الأسرع والأدق
  2. pdfplumber — كويس للجداول
  3. pypdf — fallback أخير

متوافق مع النظام القديم (DirectPDFLoader) بس بـ interface جديد.
"""

import logging
from typing import List
from .base_parser import BaseParser, ParsedPage

logger = logging.getLogger("uvicorn.error")


class PDFParser(BaseParser):
    """Multi-backend PDF parser with Arabic text fixing."""

    @property
    def supported_extensions(self) -> List[str]:
        return [".pdf"]

    def parse(self, file_path: str, **kwargs) -> List[ParsedPage]:
        """
        استخراج النص من PDF بأفضل طريقة متاحة.
        لو فيه ocr_controller، الصفحات المسحوبة (scanned) هتتعمل OCR تلقائياً.
        """
        ocr_controller = kwargs.get("ocr_controller", None)

        pages = self._try_fitz(file_path, ocr_controller=ocr_controller)
        if pages:
            return pages

        pages = self._try_pdfplumber(file_path)
        if pages:
            return pages

        pages = self._try_pypdf(file_path)
        if pages:
            return pages

        logger.warning(f"[PDFParser] No backend could extract text from: {file_path}")
        return []

    # ── Backend 1: PyMuPDF (fitz) ────────────────────────────────────────────

    def _try_fitz(self, file_path: str, ocr_controller=None) -> List[ParsedPage]:
        try:
            import fitz
            pages = []
            doc = fitz.open(file_path)
            total_pages = len(doc)
            ocr_count = 0

            for i in range(total_pages):
                page = doc.load_page(i)
                text = page.get_text("text").strip()

                # Fallback to blocks mode for complex layouts
                if not text:
                    blocks = page.get_text("blocks")
                    text = "\n".join([b[4] for b in blocks if b[4].strip()])

                # ── Smart Detection: هل الصفحة مسحوبة (scanned)؟ ──
                is_scanned = len(text.strip()) < 50
                extraction_method = "text"

                if is_scanned and ocr_controller:
                    # الصفحة فيها نص قليل جداً → غالباً scanned → OCR
                    try:
                        mat = fitz.Matrix(300 / 72, 300 / 72)  # 300 DPI
                        pix = page.get_pixmap(matrix=mat)
                        img_bytes = pix.tobytes("png")

                        ocr_text = ocr_controller.extract_from_image_bytes(
                            img_bytes, "image/png"
                        )
                        if ocr_text and len(ocr_text.strip()) > len(text.strip()):
                            text = ocr_text
                            extraction_method = "ocr"
                            ocr_count += 1
                            logger.info(
                                f"[PDFParser] Page {i+1}/{total_pages}: "
                                f"scanned → OCR extracted {len(text)} chars"
                            )
                    except Exception as e:
                        logger.warning(f"[PDFParser] OCR failed for page {i+1}: {e}")

                if text and text.strip():
                    text = self._fix_arabic(text)
                    pages.append(ParsedPage(
                        page_content=text,
                        metadata={
                            "source": file_path,
                            "page": i,
                            "parser": "fitz",
                            "extraction_method": extraction_method,
                            "is_scanned": is_scanned,
                        }
                    ))

            doc.close()
            if pages:
                text_count = len(pages) - ocr_count
                logger.info(
                    f"[PDFParser] fitz extracted {len(pages)} pages "
                    f"({text_count} text + {ocr_count} OCR)"
                )
            return pages
        except ImportError:
            return []
        except Exception as e:
            logger.debug(f"[PDFParser] fitz failed: {e}")
            return []

    # ── Backend 2: pdfplumber ────────────────────────────────────────────────

    def _try_pdfplumber(self, file_path: str) -> List[ParsedPage]:
        try:
            import pdfplumber
            pages = []
            with pdfplumber.open(file_path) as pdf:
                for i, page in enumerate(pdf.pages):
                    text = page.extract_text()
                    if text and text.strip():
                        text = self._fix_arabic(text)
                        pages.append(ParsedPage(
                            page_content=text,
                            metadata={"source": file_path, "page": i, "parser": "pdfplumber"}
                        ))

                    # Try extracting tables too
                    tables = page.extract_tables()
                    if tables:
                        for t_idx, table in enumerate(tables):
                            table_text = self._table_to_text(table)
                            if table_text.strip():
                                pages.append(ParsedPage(
                                    page_content=table_text,
                                    metadata={
                                        "source": file_path,
                                        "page": i,
                                        "parser": "pdfplumber",
                                        "content_type": "table",
                                        "table_index": t_idx,
                                    }
                                ))

            if pages:
                logger.info(f"[PDFParser] pdfplumber extracted {len(pages)} pages/tables")
            return pages
        except ImportError:
            return []
        except Exception as e:
            logger.debug(f"[PDFParser] pdfplumber failed: {e}")
            return []

    # ── Backend 3: pypdf ─────────────────────────────────────────────────────

    def _try_pypdf(self, file_path: str) -> List[ParsedPage]:
        try:
            import pypdf
            pages = []
            reader = pypdf.PdfReader(file_path)
            for i, page in enumerate(reader.pages):
                text = page.extract_text()
                if text and text.strip():
                    text = self._fix_arabic(text)
                    pages.append(ParsedPage(
                        page_content=text,
                        metadata={"source": file_path, "page": i, "parser": "pypdf"}
                    ))
            if pages:
                logger.info(f"[PDFParser] pypdf extracted {len(pages)} pages")
            return pages
        except ImportError:
            return []
        except Exception as e:
            logger.debug(f"[PDFParser] pypdf failed: {e}")
            return []

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _fix_arabic(text: str) -> str:
        """Fix reversed/garbled Arabic text from old PDFs."""
        try:
            import arabic_reshaper
            from bidi.algorithm import get_display
            reshaped = arabic_reshaper.reshape(text)
            return get_display(reshaped)
        except Exception:
            return text

    @staticmethod
    def _table_to_text(table: list) -> str:
        """Convert pdfplumber table (list of rows) to readable text."""
        if not table:
            return ""
        rows = []
        for row in table:
            cells = [str(c).strip() if c else "" for c in row]
            rows.append(" | ".join(cells))
        return "\n".join(rows)
