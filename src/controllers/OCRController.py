"""
OCR Controller — handles text extraction from:
- Images (JPG, PNG, etc.)
- PDFs (converts pages to images, then OCR)
- Video frames (extracts key frames, then OCR)

Uses the existing OCRHelper for single-image processing.
Falls back to PyMuPDF for PDF text extraction if OCR model not available.
"""

import os
import io
import logging
from typing import List, Optional

logger = logging.getLogger("uvicorn.error")


class OCRController:

    def __init__(self):
        self._ocr_helper = None

    def _get_ocr_helper(self):
        """Lazy-load OCR model only when needed."""
        if self._ocr_helper is None:
            try:
                from src.helpers.ocr_helper import get_ocr_helper
                self._ocr_helper = get_ocr_helper()
            except Exception as e:
                logger.warning(f"OCR model not available: {e}. Will use fallback.")
                self._ocr_helper = None
        return self._ocr_helper

    # ─────────────────────────────────────────────
    # IMAGE → TEXT
    # ─────────────────────────────────────────────
    def extract_from_image_bytes(self, image_bytes: bytes) -> str:
        """Extract text from raw image bytes."""
        helper = self._get_ocr_helper()
        if helper:
            try:
                return helper.process_image(image_bytes)
            except Exception as e:
                logger.error(f"OCR model failed on image: {e}")
        # Fallback: pytesseract (if installed)
        return self._tesseract_fallback(image_bytes)

    # ─────────────────────────────────────────────
    # PDF → TEXT
    # ─────────────────────────────────────────────
    def extract_from_pdf(self, file_path: str) -> str:
        """
        Extract all text from a PDF file.
        Strategy:
          1. Try PyMuPDF (fitz) — fast, gets embedded text
          2. If page has no text, render it as image and run OCR
        """
        all_text = []
        try:
            import fitz  # PyMuPDF
        except ImportError:
            logger.error("PyMuPDF (fitz) not installed. Run: pip install pymupdf")
            return self._pdf_fallback_pypdf(file_path)

        try:
            doc = fitz.open(file_path)
            logger.info(f"PDF has {doc.page_count} pages: {file_path}")

            for page_num, page in enumerate(doc):
                # Try direct text extraction first (fast)
                text = page.get_text("text").strip()

                if len(text) > 50:
                    all_text.append(f"[Page {page_num + 1}]\n{text}")
                    logger.info(f"Page {page_num + 1}: got {len(text)} chars via text extraction")
                else:
                    # Page is likely a scanned image → render and OCR
                    logger.info(f"Page {page_num + 1}: no embedded text, running OCR...")
                    mat = fitz.Matrix(2, 2)          # 2x zoom = 144 dpi
                    clip = page.get_pixmap(matrix=mat)
                    img_bytes = clip.tobytes("png")

                    ocr_text = self.extract_from_image_bytes(img_bytes)
                    if ocr_text:
                        all_text.append(f"[Page {page_num + 1} - OCR]\n{ocr_text}")

            doc.close()

        except Exception as e:
            logger.error(f"PDF extraction error: {e}")
            return f"Error extracting PDF: {str(e)}"

        return "\n\n".join(all_text)

    # ─────────────────────────────────────────────
    # PDF (bytes) → TEXT
    # ─────────────────────────────────────────────
    def extract_from_pdf_bytes(self, pdf_bytes: bytes) -> str:
        """Extract text from PDF provided as bytes (e.g., from UploadFile)."""
        try:
            import fitz
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            all_text = []

            for page_num, page in enumerate(doc):
                text = page.get_text("text").strip()
                if len(text) > 50:
                    all_text.append(f"[Page {page_num + 1}]\n{text}")
                else:
                    mat = fitz.Matrix(2, 2)
                    clip = page.get_pixmap(matrix=mat)
                    img_bytes = clip.tobytes("png")
                    ocr_text = self.extract_from_image_bytes(img_bytes)
                    if ocr_text:
                        all_text.append(f"[Page {page_num + 1} - OCR]\n{ocr_text}")

            doc.close()
            return "\n\n".join(all_text)

        except ImportError:
            return self._pdf_fallback_pypdf_bytes(pdf_bytes)
        except Exception as e:
            logger.error(f"PDF bytes extraction error: {e}")
            return f"Error: {str(e)}"

    # ─────────────────────────────────────────────
    # VIDEO → TEXT (frame sampling)
    # ─────────────────────────────────────────────
    def extract_from_video(self, file_path: str, sample_fps: float = 0.5) -> List[dict]:
        """
        Extract text from video by sampling frames.
        sample_fps: frames per second to sample (0.5 = one frame every 2 seconds)
        Returns list of {timestamp, text} dicts.
        """
        results = []
        try:
            import cv2
        except ImportError:
            logger.error("OpenCV not installed. Run: pip install opencv-python")
            return [{"timestamp": 0, "text": "OpenCV not installed — cannot process video"}]

        cap = cv2.VideoCapture(file_path)
        if not cap.isOpened():
            return [{"timestamp": 0, "text": f"Cannot open video: {file_path}"}]

        fps = cap.get(cv2.CAP_PROP_FPS) or 25
        frame_interval = int(fps / sample_fps)  # sample every N frames
        frame_num = 0

        logger.info(f"Video FPS: {fps}, sampling every {frame_interval} frames")

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_num % frame_interval == 0:
                timestamp = frame_num / fps  # seconds

                # Convert frame to PNG bytes
                _, buf = cv2.imencode(".png", frame)
                img_bytes = buf.tobytes()

                text = self.extract_from_image_bytes(img_bytes)
                if text and len(text.strip()) > 10:
                    results.append({
                        "timestamp": round(timestamp, 2),
                        "text": text.strip()
                    })
                    logger.info(f"Frame at {timestamp:.1f}s: {len(text)} chars")

            frame_num += 1

        cap.release()
        return results

    # ─────────────────────────────────────────────
    # FALLBACKS
    # ─────────────────────────────────────────────
    def _tesseract_fallback(self, image_bytes: bytes) -> str:
        try:
            import pytesseract
            from PIL import Image
            img = Image.open(io.BytesIO(image_bytes))
            return pytesseract.image_to_string(img)
        except ImportError:
            return "OCR not available: install pytesseract or configure OCR model"
        except Exception as e:
            return f"Tesseract error: {str(e)}"

    def _pdf_fallback_pypdf(self, file_path: str) -> str:
        try:
            from pypdf import PdfReader
            reader = PdfReader(file_path)
            texts = [page.extract_text() or "" for page in reader.pages]
            return "\n\n".join(texts)
        except ImportError:
            return "PDF extraction failed: install pymupdf or pypdf"
        except Exception as e:
            return f"PDF fallback error: {str(e)}"

    def _pdf_fallback_pypdf_bytes(self, pdf_bytes: bytes) -> str:
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(pdf_bytes))
            texts = [page.extract_text() or "" for page in reader.pages]
            return "\n\n".join(texts)
        except ImportError:
            return "PDF extraction failed: install pymupdf or pypdf"
        except Exception as e:
            return f"PDF fallback error: {str(e)}"
