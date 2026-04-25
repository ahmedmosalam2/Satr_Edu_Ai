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
    Gemini Vision OCR via REST API مباشرة.
    No SDK dependency — يعمل مع أي Python version.
    Supports multiple API keys with automatic rotation on rate-limit.
    """

    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

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
        self.api_keys = [k for k in api_keys if k and k.strip()]
        self.model = model
        self._current_key_idx = 0

    @property
    def api_key(self) -> str:
        """Current active key."""
        if not self.api_keys:
            return ""
        return self.api_keys[self._current_key_idx % len(self.api_keys)]

    def _rotate_key(self):
        """Move to next API key after rate-limit."""
        if len(self.api_keys) > 1:
            old_idx = self._current_key_idx
            self._current_key_idx = (self._current_key_idx + 1) % len(self.api_keys)
            logger.info(f"[GeminiOCR] Rotated API key {old_idx} → {self._current_key_idx}")

    def _get_url(self, key: str = None) -> str:
        k = key or self.api_key
        return self.BASE_URL.format(model=self.model) + f"?key={k}"

    def _build_payload(self, image_bytes: bytes, mime_type: str) -> dict:
        image_b64 = base64.b64encode(image_bytes).decode("utf-8")
        return {
            "contents": [{
                "parts": [
                    {"inline_data": {"mime_type": mime_type, "data": image_b64}},
                    {"text": self.OCR_PROMPT}
                ]
            }],
            "generationConfig": {"temperature": 0, "maxOutputTokens": 4096}
        }

    def _extract_text_from_response(self, data: dict) -> str:
        text = (
            data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text", "")
        )
        if text and text.strip() != "[NO_TEXT]":
            return text.strip()
        return ""

    async def extract_text(self, image_bytes: bytes, mime_type: str = "image/png") -> Optional[str]:
        """Async OCR via Gemini REST API. Tries all available keys."""
        if not self.api_keys:
            return None

        payload = self._build_payload(image_bytes, mime_type)

        for i in range(len(self.api_keys)):
            key = self.api_keys[(self._current_key_idx + i) % len(self.api_keys)]
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(self._get_url(key), json=payload)

                    if resp.status_code == 429:
                        logger.warning(f"[GeminiOCR] Rate limit on key #{(self._current_key_idx + i) % len(self.api_keys)} — trying next")
                        continue

                    if resp.status_code != 200:
                        logger.error(f"[GeminiOCR] API error {resp.status_code}: {resp.text[:200]}")
                        continue

                    data = resp.json()
                    text = self._extract_text_from_response(data)
                    if text:
                        # Remember this working key
                        self._current_key_idx = (self._current_key_idx + i) % len(self.api_keys)
                        logger.info(f"[GeminiOCR] ✅ Extracted {len(text)} chars")
                        return text
                    return ""

            except httpx.TimeoutException:
                logger.error("[GeminiOCR] Timeout after 30s")
                continue
            except Exception as e:
                logger.error(f"[GeminiOCR] Error: {e}")
                continue

        logger.warning("[GeminiOCR] All API keys exhausted (rate-limited)")
        return None

    def extract_text_sync(self, image_bytes: bytes, mime_type: str = "image/png") -> Optional[str]:
        """Sync version using httpx sync client. Tries all available keys."""
        if not self.api_keys:
            return None

        payload = self._build_payload(image_bytes, mime_type)

        for i in range(len(self.api_keys)):
            key = self.api_keys[(self._current_key_idx + i) % len(self.api_keys)]
            try:
                with httpx.Client(timeout=30.0) as client:
                    resp = client.post(self._get_url(key), json=payload)

                    if resp.status_code == 429:
                        logger.warning(f"[GeminiOCR] Rate limit on key #{(self._current_key_idx + i) % len(self.api_keys)} — trying next")
                        continue

                    if resp.status_code != 200:
                        logger.error(f"[GeminiOCR] {resp.status_code}: {resp.text[:200]}")
                        continue

                    data = resp.json()
                    text = self._extract_text_from_response(data)
                    if text:
                        self._current_key_idx = (self._current_key_idx + i) % len(self.api_keys)
                        return text
                    return ""

            except Exception as e:
                logger.error(f"[GeminiOCR] Sync error: {e}")
                continue

        logger.warning("[GeminiOCR] All API keys exhausted (rate-limited)")
        return None

    def test_connection(self) -> dict:
        """اختبار الـ API key والاتصال."""
        try:
            with httpx.Client(timeout=15.0) as client:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
                payload = {
                    "contents": [{"parts": [{"text": "Say OK"}]}],
                    "generationConfig": {"maxOutputTokens": 5}
                }
                resp = client.post(url, json=payload)

                if resp.status_code == 200:
                    data = resp.json()
                    text = self._extract_text_from_response(data) or "OK"
                    return {
                        "status": "connected",
                        "model": self.model,
                        "test_response": text,
                        "keys_available": len(self.api_keys),
                        "note": "Free tier: 15 req/min, 1500 req/day"
                    }
                elif resp.status_code == 429:
                    return {"status": "rate_limited", "model": self.model, "keys_available": len(self.api_keys), "note": "All keys rate-limited. Wait or add new key."}
                else:
                    return {"status": "error", "code": resp.status_code, "error": resp.text[:200]}

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
