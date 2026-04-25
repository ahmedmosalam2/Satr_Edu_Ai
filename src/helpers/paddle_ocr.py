
import io
import logging
from typing import Optional

logger = logging.getLogger("uvicorn.error")

_paddle_instance = None


def get_paddle_ocr():
    """
    PaddleOCR is DISABLED on WSL2.
    It causes a fatal SIGBUS (C++ memory error) that kills the entire server process.
    This is a known incompatibility between PaddleOCR native libs and WSL2 memory model.
    Use Gemini or DeepSeek instead — they are superior anyway.
    """
    return None


class PaddleOCRHelper:
    """
    Wrapper لـ PaddleOCR يتعامل مع images كـ bytes.
    """

    def extract_text(self, image_bytes: bytes) -> Optional[str]:

        ocr = get_paddle_ocr()
        if not ocr:
            return None

        try:
            import numpy as np
            from PIL import Image

            # Convert bytes → PIL → numpy array (PaddleOCR يقبل numpy)
            img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            img_array = np.array(img)

            # Run OCR
            result = ocr.ocr(img_array, cls=True)

            if not result or not result[0]:
                logger.info("[PaddleOCR] No text detected in image")
                return ""

            # Extract text from results
            # result structure: [[[box_coords], (text, confidence)], ...]
            lines = []
            for line in result[0]:
                if line and len(line) >= 2:
                    text_info = line[1]
                    if isinstance(text_info, (list, tuple)) and len(text_info) >= 1:
                        text = text_info[0]
                        confidence = text_info[1] if len(text_info) > 1 else 1.0
                        # فقط نص confidence > 0.5
                        if confidence > 0.5 and text and text.strip():
                            lines.append(text.strip())

            extracted = "\n".join(lines)
            if extracted:
                logger.info(f"[PaddleOCR] ✅ Extracted {len(extracted)} chars ({len(lines)} lines)")
            return extracted

        except Exception as e:
            logger.error(f"[PaddleOCR] Error: {e}")
            return None

    def extract_text_with_layout(self, image_bytes: bytes) -> list:
        """
        مثل RAGFlow — يرجع النص مع موضعه في الصفحة.

        Returns:
            List of {text, confidence, bbox: [x1,y1,x2,y2]}
        """
        ocr = get_paddle_ocr()
        if not ocr:
            return []

        try:
            import numpy as np
            from PIL import Image

            img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            img_array = np.array(img)
            result = ocr.ocr(img_array, cls=True)

            elements = []
            if result and result[0]:
                for line in result[0]:
                    if line and len(line) >= 2:
                        box = line[0]      # [[x1,y1],[x2,y1],[x2,y2],[x1,y2]]
                        text_info = line[1]
                        text = text_info[0] if text_info else ""
                        confidence = text_info[1] if len(text_info) > 1 else 0

                        if text and text.strip() and confidence > 0.5:
                            # Convert box to simple bbox
                            xs = [p[0] for p in box]
                            ys = [p[1] for p in box]
                            elements.append({
                                "text": text.strip(),
                                "confidence": round(confidence, 3),
                                "bbox": [min(xs), min(ys), max(xs), max(ys)],
                            })

            # Sort by vertical position (top to bottom — reading order)
            elements.sort(key=lambda e: e["bbox"][1])
            return elements

        except Exception as e:
            logger.error(f"[PaddleOCR] Layout error: {e}")
            return []

    def test_available(self) -> dict:
        """اختبار إن PaddleOCR شغال."""
        return {
            "available": False,
            "reason": "Disabled on WSL2 — causes fatal SIGBUS C++ crash",
            "note": "Use Gemini Vision or DeepSeek OCR instead (both are superior)",
        }


# ── Singleton ──────────────────────────────────────────────────────────────
_helper: Optional[PaddleOCRHelper] = None


def get_paddle_helper() -> Optional[PaddleOCRHelper]:
    global _helper
    if _helper is None:
        _helper = PaddleOCRHelper()
    return _helper
