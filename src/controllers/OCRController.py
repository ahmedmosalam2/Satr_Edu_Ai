import io
import logging
import asyncio
from typing import List, Optional

logger = logging.getLogger("uvicorn.error")


class OCRController:

    def __init__(self):
        self._gemini_ocr = None    # Gemini Vision
        self._paddle_ocr = None    # PaddleOCR
        self._backend = self._load_backend()

    def _load_backend(self) -> str:
        try:
            from src.helpers.config import get_settings
            return get_settings().OCR_BACKEND.lower()
        except Exception:
            return "gemini"

    # ── Lazy loaders ──────────────────────────────────────────────────────────

    def _get_gemini(self):
        if self._gemini_ocr is None:
            try:
                from src.helpers.gemini_ocr import get_gemini_ocr
                self._gemini_ocr = get_gemini_ocr() or False
            except Exception as e:
                logger.warning(f"[OCR] Gemini init: {e}")
                self._gemini_ocr = False
        return self._gemini_ocr if self._gemini_ocr else None

    def _get_paddle(self):
        if self._paddle_ocr is None:
            try:
                from src.helpers.paddle_ocr import get_paddle_helper
                self._paddle_ocr = get_paddle_helper() or False
            except Exception as e:
                logger.warning(f"[OCR] PaddleOCR init: {e}")
                self._paddle_ocr = False
        return self._paddle_ocr if self._paddle_ocr else None

    # ── Image Preprocessing ───────────────────────────────────────────────────

    def _preprocess_for_tesseract(self, image_bytes: bytes) -> "Image":
        """Enhance image for better Tesseract results (especially for Arabic)."""
        from PIL import Image, ImageFilter, ImageEnhance
        img = Image.open(io.BytesIO(image_bytes))

        # Convert to RGB if needed
        if img.mode != "RGB":
            img = img.convert("RGB")

        # Convert to grayscale
        img = img.convert("L")

        # Increase contrast
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(2.0)

        # Sharpen
        img = img.filter(ImageFilter.SHARPEN)

        # Upscale small images for better OCR
        w, h = img.size
        if w < 1000 or h < 1000:
            scale = max(1000 / w, 1000 / h, 1.5)
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

        # Binarize (adaptive threshold via simple threshold)
        threshold = 140
        img = img.point(lambda p: 255 if p > threshold else 0)

        return img

    # ── IMAGE → TEXT ──────────────────────────────────────────────────────────

    def extract_from_image_bytes(self, image_bytes: bytes, mime_type: str = "image/png") -> str:
        """
        OCR Pipeline (sync):
          1. Gemini Vision   (Cloud API — مجاني، أقوى)
          2. DeepSeek-OCR-2  (HF Space — fallback cloud)
          3. PaddleOCR       (Local CPU)
          4. Tesseract       (Last resort — with preprocessing)
        """
        # 1. Gemini Vision (primary — most reliable)
        gemini = self._get_gemini()
        if gemini:
            try:
                result = gemini.extract_text_sync(image_bytes, mime_type)
                if result and len(result.strip()) > 5:
                    logger.info(f"[OCR] ✅ Gemini extracted {len(result)} chars")
                    return result
            except Exception as e:
                logger.warning(f"[OCR] Gemini: {e}")

        # 2. DeepSeek-OCR-2 (cloud fallback)
        try:
            from src.helpers.deepseek_ocr import deepseek_ocr_sync
            result = deepseek_ocr_sync(image_bytes, mime_type)
            if result and len(result.strip()) > 5:
                logger.info(f"[OCR] ✅ DeepSeek extracted {len(result)} chars")
                return result
        except Exception as e:
            logger.warning(f"[OCR] DeepSeek: {e}")

        # 3. PaddleOCR
        paddle = self._get_paddle()
        if paddle:
            try:
                result = paddle.extract_text(image_bytes)
                if result and len(result.strip()) > 5:
                    logger.info(f"[OCR] ✅ PaddleOCR extracted {len(result)} chars")
                    return result
            except Exception as e:
                logger.warning(f"[OCR] PaddleOCR: {e}")

        # 4. Tesseract (enhanced with preprocessing)
        logger.info("[OCR] Tesseract fallback (with preprocessing)")
        return self._tesseract_fallback(image_bytes)

    async def extract_from_image_bytes_async(
        self, image_bytes: bytes, mime_type: str = "image/png"
    ) -> str:
        """
        OCR Pipeline (async):
          1. Gemini → 2. DeepSeek → 3. PaddleOCR → 4. Tesseract
        """
        # 1. Gemini (primary)
        gemini = self._get_gemini()
        if gemini:
            try:
                result = await gemini.extract_text(image_bytes, mime_type)
                if result and len(result.strip()) > 5:
                    logger.info(f"[OCR] ✅ Gemini async extracted {len(result)} chars")
                    return result
            except Exception as e:
                logger.warning(f"[OCR] Gemini async: {e}")

        # 2. DeepSeek-OCR-2
        try:
            from src.helpers.deepseek_ocr import deepseek_ocr
            result = await deepseek_ocr(image_bytes, mime_type)
            if result and len(result.strip()) > 5:
                logger.info(f"[OCR] ✅ DeepSeek async extracted {len(result)} chars")
                return result
        except Exception as e:
            logger.warning(f"[OCR] DeepSeek async: {e}")

        # 3. PaddleOCR
        paddle = self._get_paddle()
        if paddle:
            try:
                result = await asyncio.to_thread(paddle.extract_text, image_bytes)
                if result and len(result.strip()) > 5:
                    logger.info(f"[OCR] ✅ PaddleOCR async extracted {len(result)} chars")
                    return result
            except Exception as e:
                logger.warning(f"[OCR] PaddleOCR async: {e}")

        # 4. Tesseract (enhanced)
        return await asyncio.to_thread(self._tesseract_fallback, image_bytes)

    # ── PDF → TEXT ────────────────────────────────────────────────────────────

    def extract_from_pdf(self, file_path: str) -> str:
        all_text = []
        try:
            import fitz
        except ImportError:
            return self._pdf_fallback_pypdf(file_path)

        try:
            doc = fitz.open(file_path)
            logger.info(f"[OCR] PDF: {doc.page_count} pages")
            for page_num, page in enumerate(doc):
                text = page.get_text("text").strip()
                if len(text) > 50:
                    all_text.append(f"[Page {page_num + 1}]\n{text}")
                else:
                    mat = fitz.Matrix(200 / 72, 200 / 72)
                    img_bytes = page.get_pixmap(matrix=mat).tobytes("png")
                    ocr_text = self.extract_from_image_bytes(img_bytes, "image/png")
                    if ocr_text:
                        all_text.append(f"[Page {page_num + 1} — OCR]\n{ocr_text}")
            doc.close()
        except Exception as e:
            logger.error(f"[OCR] PDF error: {e}")
            return f"Error: {e}"

        return "\n\n".join(all_text)

    def extract_from_pdf_bytes(self, pdf_bytes: bytes) -> str:
        try:
            import fitz
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            all_text = []
            for page_num, page in enumerate(doc):
                text = page.get_text("text").strip()
                if len(text) > 50:
                    all_text.append(f"[Page {page_num + 1}]\n{text}")
                else:
                    mat = fitz.Matrix(200 / 72, 200 / 72)
                    img_bytes = page.get_pixmap(matrix=mat).tobytes("png")
                    ocr_text = self.extract_from_image_bytes(img_bytes, "image/png")
                    if ocr_text:
                        all_text.append(f"[Page {page_num + 1} — OCR]\n{ocr_text}")
            doc.close()
            return "\n\n".join(all_text)
        except ImportError:
            return self._pdf_fallback_pypdf_bytes(pdf_bytes)
        except Exception as e:
            return f"Error: {e}"

    # ── VIDEO → TEXT ──────────────────────────────────────────────────────────

    def extract_from_video(self, file_path: str, sample_fps: float = 0.5) -> List[dict]:
        results = []
        try:
            import cv2
        except ImportError:
            return [{"timestamp": 0, "text": "OpenCV not available"}]

        cap = cv2.VideoCapture(file_path)
        if not cap.isOpened():
            return [{"timestamp": 0, "text": f"Cannot open: {file_path}"}]

        fps = cap.get(cv2.CAP_PROP_FPS) or 25
        frame_interval = max(1, int(fps / sample_fps))
        frame_num = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if frame_num % frame_interval == 0:
                timestamp = frame_num / fps
                _, buf = cv2.imencode(".png", frame)
                text = self.extract_from_image_bytes(buf.tobytes(), "image/png")
                if text and len(text.strip()) > 10:
                    results.append({"timestamp": round(timestamp, 2), "text": text.strip()})
            frame_num += 1

        cap.release()
        return results

    # ── Status ────────────────────────────────────────────────────────────────

    def get_status(self) -> dict:
        from src.helpers.config import get_settings
        s = get_settings()

        paddle_info = {"available": False, "reason": "Not initialized"}
        try:
            from src.helpers.paddle_ocr import get_paddle_helper
            helper = get_paddle_helper()
            if helper is not None:
                paddle_info = helper.test_available()
        except Exception as e:
            paddle_info = {"available": False, "reason": str(e)}

        # Count available Gemini keys
        gemini_keys = 1 if s.GEMINI_API_KEY else 0
        import os
        for i in range(2, 6):
            if os.environ.get(f"GEMINI_API_KEY_{i}", ""):
                gemini_keys += 1

        return {
            "active_chain": [
                "1. Gemini Vision API (Cloud — primary, multi-key)",
                "2. DeepSeek-OCR-2 (HF Space — cloud fallback)",
                "3. PaddleOCR (Local CPU)",
                "4. Tesseract (last resort — enhanced preprocessing)",
            ],
            "gemini": {
                "available": bool(s.GEMINI_API_KEY),
                "model": s.GEMINI_VISION_MODEL,
                "keys_available": gemini_keys,
                "note": "Free 1500 req/day per key",
            },
            "deepseek_ocr2": {
                "available": True,
                "note": "Via HuggingFace Spaces — community-hosted",
            },
            "paddleocr": paddle_info,
            "tesseract": {
                "available": True,
                "note": "Enhanced preprocessing for Arabic — last resort",
            },
        }

    # ── Fallbacks ─────────────────────────────────────────────────────────────

    def _tesseract_fallback(self, image_bytes: bytes) -> str:
        try:
            import pytesseract

            # Try enhanced preprocessing first
            try:
                img = self._preprocess_for_tesseract(image_bytes)
            except Exception:
                from PIL import Image
                img = Image.open(io.BytesIO(image_bytes))

            # Try Arabic+English first
            try:
                result = pytesseract.image_to_string(img, lang="ara+eng", config="--psm 6")
                if result and result.strip():
                    logger.info(f"[OCR] ✅ Tesseract extracted {len(result.strip())} chars (ara+eng)")
                    return result.strip()
            except Exception:
                pass

            # Fallback to English only
            result = pytesseract.image_to_string(img, config="--psm 6")
            if result and result.strip():
                logger.info(f"[OCR] ✅ Tesseract extracted {len(result.strip())} chars (eng)")
                return result.strip()

            return ""

        except ImportError:
            logger.error("[OCR] pytesseract not installed")
            return "OCR unavailable — pytesseract not installed"
        except Exception as e:
            logger.error(f"[OCR] Tesseract error: {e}")
            return f"Tesseract error: {e}"

    def _pdf_fallback_pypdf(self, file_path: str) -> str:
        try:
            from pypdf import PdfReader
            return "\n\n".join(p.extract_text() or "" for p in PdfReader(file_path).pages)
        except Exception as e:
            return f"PDF error: {e}"

    def _pdf_fallback_pypdf_bytes(self, pdf_bytes: bytes) -> str:
        try:
            from pypdf import PdfReader
            return "\n\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(pdf_bytes)).pages)
        except Exception as e:
            return f"PDF error: {e}"
