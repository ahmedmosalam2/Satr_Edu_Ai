
import base64
import logging
import httpx
from typing import Optional

logger = logging.getLogger("uvicorn.error")

# Real HF Spaces for DeepSeek-OCR (community-hosted)
# These may go offline — that's OK, Gemini picks up automatically
HF_SPACES = [
    "https://deepseek-ai-Janus-Pro-7B.hf.space",
]

# Fast timeout so we don't block the pipeline
SPACE_TIMEOUT = 10.0


async def deepseek_ocr(image_bytes: bytes, mime_type: str = "image/png") -> Optional[str]:
    """Async DeepSeek OCR via HF Spaces. Returns None quickly if unavailable."""

    b64 = base64.b64encode(image_bytes).decode()
    data_url = f"data:{mime_type};base64,{b64}"

    payload = {
        "data": [
            {"path": data_url, "meta": {"_type": "gradio.FileData"}},
            "Markdown",
        ]
    }

    async with httpx.AsyncClient(timeout=SPACE_TIMEOUT) as client:
        for space in HF_SPACES:
            try:
                # Quick health check first (2s timeout)
                health = await client.get(f"{space}/api/status", timeout=2.0)
                if health.status_code != 200:
                    continue

                resp = await client.post(f"{space}/run/predict", json=payload)
                if resp.status_code == 200:
                    result = resp.json()
                    text = result.get("data", [None])[0]
                    if text and len(str(text).strip()) > 5:
                        logger.info(f"[DeepSeekOCR] ✅ {len(str(text))} chars from {space}")
                        return str(text).strip()
            except Exception as e:
                logger.debug(f"[DeepSeekOCR] {space} failed: {e}")
                continue

    logger.warning("[DeepSeekOCR] All spaces unavailable — falling through to Gemini")
    return None


def deepseek_ocr_sync(image_bytes: bytes, mime_type: str = "image/png") -> Optional[str]:
    """Sync version for non-async contexts. Uses httpx sync client to avoid asyncio.run deadlock."""
    b64 = base64.b64encode(image_bytes).decode()
    data_url = f"data:{mime_type};base64,{b64}"

    payload = {
        "data": [
            {"path": data_url, "meta": {"_type": "gradio.FileData"}},
            "Markdown",
        ]
    }

    with httpx.Client(timeout=SPACE_TIMEOUT) as client:
        for space in HF_SPACES:
            try:
                # Quick health check first
                health = client.get(f"{space}/api/status", timeout=2.0)
                if health.status_code != 200:
                    continue

                resp = client.post(f"{space}/run/predict", json=payload)
                if resp.status_code == 200:
                    result = resp.json()
                    text = result.get("data", [None])[0]
                    if text and len(str(text).strip()) > 5:
                        logger.info(f"[DeepSeekOCR] ✅ sync {len(str(text))} chars from {space}")
                        return str(text).strip()
            except Exception as e:
                logger.debug(f"[DeepSeekOCR] sync {space} failed: {e}")
                continue

    logger.warning("[DeepSeekOCR] All spaces unavailable (sync) — falling through to Gemini")
    return None
