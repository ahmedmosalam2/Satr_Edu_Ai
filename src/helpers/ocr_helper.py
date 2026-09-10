from src.helpers.config import get_settings
from src.helpers.surya_ocr_helper import get_surya_ocr
import logging

logger = logging.getLogger("uvicorn.error")


class OCRHelper:
    def __init__(self):
        self._surya = get_surya_ocr()

    def process_image(self, image_bytes: bytes) -> str:
        try:
            text = self._surya.extract_text(image_bytes)
            if text and text.strip():
                logger.info(f"[OCRHelper] Surya extracted {len(text)} chars")
                return text
        except Exception as e:
            logger.error(f"[OCRHelper] Surya error: {e}")

        return ""


ocr_helper_instance = None

def get_ocr_helper():
    global ocr_helper_instance
    if ocr_helper_instance is None:
        ocr_helper_instance = OCRHelper()
    return ocr_helper_instance
