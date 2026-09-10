import io
import logging
import asyncio
from typing import List, Optional

logger = logging.getLogger("uvicorn.error")


class OCRController:

    def __init__(self):
        self._surya_ocr = None
        self._gemini_ocr = None
        self._paddle_ocr = None

    def _get_surya(self):
        if self._surya_ocr is None:
            try:
                from src.helpers.surya_ocr_helper import get_surya_ocr
                helper = get_surya_ocr()
                self._surya_ocr = helper if (helper and helper.is_available()) else False
            except Exception as e:
                logger.warning(f"[OCR] Surya init failed: {e}")
                self._surya_ocr = False
        return self._surya_ocr if self._surya_ocr else None

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

    def _preprocess_for_tesseract(self, image_bytes: bytes):
        from PIL import Image, ImageFilter, ImageEnhance
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode != "RGB":
            img = img.convert("RGB")
        img = img.convert("L")
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(2.0)
        img = img.filter(ImageFilter.SHARPEN)
        w, h = img.size
        if w < 1000 or h < 1000:
            scale = max(1000 / w, 1000 / h, 1.5)
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
        img = img.point(lambda p: 255 if p > 140 else 0)
        return img

    def extract_from_image_bytes(self, image_bytes: bytes, mime_type: str = "image/png") -> str:
        surya = self._get_surya()
        if surya:
            try:
                result = surya.extract_text(image_bytes)
                if result and len(result.strip()) > 5:
                    logger.info(f"[OCR] Surya: {len(result)} chars")
                    return result
            except Exception as e:
                logger.warning(f"[OCR] Surya failed: {e}")

        gemini = self._get_gemini()
        if gemini:
            try:
                result = gemini.extract_text_sync(image_bytes, mime_type)
                if result and len(result.strip()) > 5:
                    logger.info(f"[OCR] Gemini fallback: {len(result)} chars")
                    return result
            except Exception as e:
                logger.warning(f"[OCR] Gemini failed: {e}")

        try:
            from src.helpers.deepseek_ocr import deepseek_ocr_sync
            result = deepseek_ocr_sync(image_bytes, mime_type)
            if result and len(result.strip()) > 5:
                logger.info(f"[OCR] DeepSeek fallback: {len(result)} chars")
                return result
        except Exception as e:
            logger.warning(f"[OCR] DeepSeek: {e}")

        paddle = self._get_paddle()
        if paddle:
            try:
                result = paddle.extract_text(image_bytes)
                if result and len(result.strip()) > 5:
                    logger.info(f"[OCR] PaddleOCR fallback: {len(result)} chars")
                    return result
            except Exception as e:
                logger.warning(f"[OCR] PaddleOCR: {e}")

        logger.info("[OCR] All primary backends failed — using Tesseract")
        return self._tesseract_fallback(image_bytes)

    async def extract_from_image_bytes_async(
        self, image_bytes: bytes, mime_type: str = "image/png"
    ) -> str:
        surya = self._get_surya()
        if surya:
            try:
                result = await asyncio.to_thread(surya.extract_text, image_bytes)
                if result and len(result.strip()) > 5:
                    logger.info(f"[OCR] Surya async: {len(result)} chars")
                    return result
            except Exception as e:
                logger.warning(f"[OCR] Surya async failed: {e}")

        gemini = self._get_gemini()
        if gemini:
            try:
                result = await gemini.extract_text(image_bytes, mime_type)
                if result and len(result.strip()) > 5:
                    logger.info(f"[OCR] Gemini async fallback: {len(result)} chars")
                    return result
            except Exception as e:
                logger.warning(f"[OCR] Gemini async: {e}")

        try:
            from src.helpers.deepseek_ocr import deepseek_ocr
            result = await deepseek_ocr(image_bytes, mime_type)
            if result and len(result.strip()) > 5:
                logger.info(f"[OCR] DeepSeek async fallback: {len(result)} chars")
                return result
        except Exception as e:
            logger.warning(f"[OCR] DeepSeek async: {e}")

        paddle = self._get_paddle()
        if paddle:
            try:
                result = await asyncio.to_thread(paddle.extract_text, image_bytes)
                if result and len(result.strip()) > 5:
                    logger.info(f"[OCR] PaddleOCR async fallback: {len(result)} chars")
                    return result
            except Exception as e:
                logger.warning(f"[OCR] PaddleOCR async: {e}")

        return await asyncio.to_thread(self._tesseract_fallback, image_bytes)

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
                if len(text) > 5:
                    all_text.append(f"[Page {page_num + 1}]\n{text}")
                else:
                    mat = fitz.Matrix(300 / 72, 300 / 72)
                    img_bytes = page.get_pixmap(matrix=mat).tobytes("png")
                    ocr_text = self.extract_from_image_bytes(img_bytes, "image/png")
                    is_error = ocr_text and any(err in ocr_text for err in ["Tesseract error", "OCR unavailable", "Error:"])
                    if ocr_text and not is_error:
                        all_text.append(f"[Page {page_num + 1} — Surya OCR]\n{ocr_text}")
                    elif text:
                        all_text.append(f"[Page {page_num + 1}]\n{text}")
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
                if len(text) > 5:
                    all_text.append(f"[Page {page_num + 1}]\n{text}")
                else:
                    mat = fitz.Matrix(300 / 72, 300 / 72)
                    img_bytes = page.get_pixmap(matrix=mat).tobytes("png")
                    ocr_text = self.extract_from_image_bytes(img_bytes, "image/png")
                    is_error = ocr_text and any(err in ocr_text for err in ["Tesseract error", "OCR unavailable", "Error:"])
                    if ocr_text and not is_error:
                        all_text.append(f"[Page {page_num + 1} — Surya OCR]\n{ocr_text}")
                    elif text:
                        all_text.append(f"[Page {page_num + 1}]\n{text}")
            doc.close()
            return "\n\n".join(all_text)
        except ImportError:
            return self._pdf_fallback_pypdf_bytes(pdf_bytes)
        except Exception as e:
            return f"Error: {e}"

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

    def get_status(self) -> dict:
        surya_info = {"available": False, "reason": "Not checked"}
        try:
            from src.helpers.surya_ocr_helper import get_surya_ocr
            helper = get_surya_ocr()
            if helper:
                surya_info = helper.get_status()
        except Exception as e:
            surya_info = {"available": False, "reason": str(e)}

        from src.helpers.config import get_settings
        s = get_settings()

        return {
            "primary": "Surya OCR",
            "active_chain": [
                "1. Surya OCR (GPU service / local CPU)",
                "2. Gemini Vision API (cloud fallback)",
                "3. DeepSeek-OCR-2 (HF Space fallback)",
                "4. PaddleOCR (local fallback)",
                "5. Tesseract (last resort)",
            ],
            "surya": surya_info,
            "gemini": {
                "available": bool(s.GEMINI_API_KEY),
                "model": s.GEMINI_VISION_MODEL,
                "role": "fallback",
            },
            "tesseract": {
                "available": True,
                "role": "last_resort",
            },
        }

    def _tesseract_fallback(self, image_bytes: bytes) -> str:
        try:
            import pytesseract
            try:
                img = self._preprocess_for_tesseract(image_bytes)
            except Exception:
                from PIL import Image
                img = Image.open(io.BytesIO(image_bytes))

            try:
                result = pytesseract.image_to_string(img, lang="ara+eng", config="--psm 6")
                if result and result.strip():
                    logger.info(f"[OCR] Tesseract: {len(result.strip())} chars (ara+eng)")
                    return result.strip()
            except Exception:
                pass

            result = pytesseract.image_to_string(img, config="--psm 6")
            if result and result.strip():
                logger.info(f"[OCR] Tesseract: {len(result.strip())} chars (eng)")
                return result.strip()

            return ""
        except ImportError:
            return "OCR unavailable — pytesseract not installed"
        except Exception as e:
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
