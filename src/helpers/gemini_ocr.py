"""
src/helpers/gemini_ocr.py
──────────────────────────
Gemini Vision OCR — يستخدم Google Gemini لاستخراج النص من الصور.

يستخدم HTTP REST API مباشرة (بدون SDK) لأقصى استقرار وتوافق.
يدعم Multi-key rotation — لو key وصل الحد بيجرب التاني.

الموديل: gemini-2.0-flash (مجاني: 15 req/min, 1500 req/day)
"""

import base64
import logging
import os
from typing import Optional, List

import httpx

logger = logging.getLogger("uvicorn.error")


class GeminiOCRHelper:
    """
    Gemini Vision OCR using the official google.generativeai SDK.
    """

    OCR_PROMPT = (
        "أنت نظام OCR متخصص في استخراج النصوص العربية من الصور والمستندات التعليمية.\n"
        "اتبع هذه القواعد بدقة:\n\n"
        "1. استخرج كل النص الموجود في الصورة بدقة عالية جداً.\n"
        "2. النص العربي يُكتب بالعربي فقط — لا تخلط حروف لاتينية مع الكلمات العربية أبداً.\n"
        "3. إذا وُجد نص إنجليزي حقيقي (مثل مصطلحات علمية)، اكتبه كما هو بالإنجليزية.\n"
        "4. حافظ على هيكل النص الأصلي: العناوين، الفقرات، النقاط المرقمة، التعداد.\n"
        "5. الأرقام تُكتب كما تظهر (عربية ١٢٣ أو هندية 123).\n"
        "6. حافظ على التشكيل والحركات إن وُجدت.\n"
        "7. للجداول: استخدم | كفاصل بين الأعمدة.\n"
        "8. لا تضف أي شرح أو تعليق — فقط النص المستخرج.\n"
        "9. إذا لم يكن هناك نص في الصورة، اكتب بالضبط: [NO_TEXT]\n"
        "10. راجع النص قبل إرساله وتأكد أن كل كلمة عربية مكتوبة بشكل صحيح.\n"
    )

    def __init__(self, api_keys: List[str], model: str = "gemini-2.0-flash"):
        """Accept a list of API keys for automatic rotation."""
        import google.generativeai as genai
        self.api_keys = [k for k in api_keys if k and k.strip()]
        self.model = model
        self._current_key_idx = 0
        if self.api_keys:
            genai.configure(api_key=self.api_keys[0])

    @property
    def api_key(self) -> str:
        if not self.api_keys:
            return ""
        return self.api_keys[self._current_key_idx % len(self.api_keys)]

    def _rotate_key(self):
        import google.generativeai as genai
        if len(self.api_keys) > 1:
            self._current_key_idx = (self._current_key_idx + 1) % len(self.api_keys)
            genai.configure(api_key=self.api_key)
            logger.info(f"[GeminiOCR] Rotated API key to index {self._current_key_idx}")

    async def extract_text(self, image_bytes: bytes, mime_type: str = "image/png") -> Optional[str]:
        """Async OCR via Gemini SDK."""
        return await asyncio.to_thread(self.extract_text_sync, image_bytes, mime_type)

    def extract_text_sync(self, image_bytes: bytes, mime_type: str = "image/png") -> Optional[str]:
        """Sync OCR via Gemini SDK."""
        import google.generativeai as genai
        from PIL import Image
        import io

        if not self.api_keys:
            return None

        for i in range(len(self.api_keys)):
            try:
                img = Image.open(io.BytesIO(image_bytes))
                model = genai.GenerativeModel(self.model)
                response = model.generate_content([img, self.OCR_PROMPT])
                
                text = response.text
                if text and text.strip() != "[NO_TEXT]":
                    logger.info(f"[GeminiOCR] SDK ✅ Extracted {len(text)} chars")
                    return text.strip()
                return ""
            except Exception as e:
                logger.error(f"[GeminiOCR] SDK error (key index {self._current_key_idx}): {e}")
                self._rotate_key()
                continue

        logger.warning("[GeminiOCR] All API keys exhausted or failed")
        return None

    def test_connection(self) -> dict:
        import google.generativeai as genai
        try:
            model = genai.GenerativeModel(self.model)
            response = model.generate_content("Say OK")
            text = response.text.strip()
            return {
                "status": "connected",
                "model": self.model,
                "test_response": text,
                "keys_available": len(self.api_keys),
                "note": "Free tier: 15 req/min, 1500 req/day"
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}


# ── Singleton ─────────────────────────────────────────────────────────────────
_gemini_ocr: Optional[GeminiOCRHelper] = None


def get_gemini_ocr() -> Optional[GeminiOCRHelper]:
    global _gemini_ocr
    if _gemini_ocr is None:
        from src.helpers.config import get_settings
        s = get_settings()

        # Collect all available keys
        keys = []
        if s.GEMINI_API_KEY:
            keys.append(s.GEMINI_API_KEY)

        # Support GEMINI_API_KEY_2, GEMINI_API_KEY_3, etc. via env vars
        for i in range(2, 6):
            extra_key = os.environ.get(f"GEMINI_API_KEY_{i}", "")
            if extra_key:
                keys.append(extra_key)

        if keys:
            _gemini_ocr = GeminiOCRHelper(
                api_keys=keys,
                model=getattr(s, "GEMINI_VISION_MODEL", "gemini-2.0-flash"),
            )
            logger.info(f"[GeminiOCR] Initialized — model: {_gemini_ocr.model}, keys: {len(keys)}")
        else:
            logger.warning("[GeminiOCR] GEMINI_API_KEY not set")
    return _gemini_ocr
