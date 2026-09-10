"""
surya_service.py
Surya OCR Microservice — GPU host service.

Usage:
    conda activate gradution-project
    python surya_service.py
"""

import io
import json
import logging
import time
from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
import uvicorn
import torch

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("surya-service")

_det_model = None
_det_processor = None
_rec_model = None
_rec_processor = None
_loaded = False
_load_error = None


def _load_recognition_model(checkpoint="vikp/surya_rec2", device="cuda", dtype=torch.float16):
    from surya.model.recognition.model import (
        SuryaOCRConfig, OCREncoderDecoderModel,
        SuryaOCRDecoderConfig, DonutSwinConfig, SuryaOCRTextEncoderConfig,
        load_model,
    )

    try:
        return load_model(checkpoint=checkpoint, device=device, dtype=dtype)
    except (KeyError, AttributeError, TypeError) as e:
        logger.warning(f"[Surya] Standard load_model failed ({e})")
        logger.info("[Surya] Loading recognition model manually (transformers compat fix)...")

    from huggingface_hub import hf_hub_download

    config_path = hf_hub_download(checkpoint, "config.json")
    with open(config_path) as f:
        config_dict = json.load(f)

    decoder_cfg = SuryaOCRDecoderConfig(**config_dict["decoder"])
    encoder_cfg = DonutSwinConfig(**config_dict["encoder"])
    text_encoder_cfg = SuryaOCRTextEncoderConfig(**config_dict["text_encoder"])

    config = SuryaOCRConfig(
        decoder=decoder_cfg.to_dict(),
        encoder=encoder_cfg.to_dict(),
        text_encoder=text_encoder_cfg.to_dict(),
    )
    config.decoder = decoder_cfg
    config.encoder = encoder_cfg
    config.text_encoder = text_encoder_cfg
    
    # Monkey patch عشان نخلص من وجع دماغ transformers
    # هنجبرها ترجع الـ config الصح لما تطلب get_text_config
    def manual_get_text_config(decoder=False):
        return decoder_cfg if decoder else text_encoder_cfg
    
    config.get_text_config = manual_get_text_config
    config.model_type = "surya_ocr"
    config.tie_word_embeddings = False

    # حركة انتحارية: هنعطل الـ tie_weights في الـ transformers نفسها مؤقتاً
    import transformers.modeling_utils
    old_tie_weights = transformers.modeling_utils.PreTrainedModel.tie_weights
    transformers.modeling_utils.PreTrainedModel.tie_weights = lambda self: None

    try:
        model = OCREncoderDecoderModel.from_pretrained(
            checkpoint, config=config, torch_dtype=dtype,
            ignore_mismatched_sizes=True
        )
    finally:
        # نرجعها زي ما كانت عشان متبوظش بقية السيستم
        transformers.modeling_utils.PreTrainedModel.tie_weights = old_tie_weights

    model = model.to(device).eval()
    logger.info(f"[Surya] Recognition model loaded manually on {device}")
    return model


def _ensure_loaded() -> bool:
    global _det_model, _det_processor, _rec_model, _rec_processor, _loaded, _load_error

    if _loaded:
        return True

    try:
        start = time.time()
        device = "cuda" if torch.cuda.is_available() else "cpu"
        dtype = torch.float16 if device == "cuda" else torch.float32

        logger.info("[Surya] Loading detection model...")
        from surya.model.detection.model import load_model as load_det, load_processor as load_det_proc
        _det_model = load_det(device=device, dtype=dtype)
        _det_processor = load_det_proc()
        logger.info(f"[Surya] Detection ready ({time.time()-start:.1f}s)")

        logger.info("[Surya] Loading recognition model...")
        _rec_model = _load_recognition_model(device=device, dtype=dtype)

        from surya.model.recognition.processor import load_processor as load_rec_proc
        _rec_processor = load_rec_proc()
        logger.info(f"[Surya] Recognition ready ({time.time()-start:.1f}s)")

        _loaded = True

        if torch.cuda.is_available():
            logger.info(f"[Surya] GPU: {torch.cuda.get_device_name(0)}")

        logger.info(f"[Surya] All models loaded in {time.time()-start:.1f}s — ready!")
        return True

    except Exception as e:
        _load_error = str(e)
        logger.error(f"[Surya] FAILED: {e}", exc_info=True)
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    _ensure_loaded()
    yield


app = FastAPI(title="Surya OCR Service", version="3.2", lifespan=lifespan)


@app.post("/ocr")
async def ocr_image(file: UploadFile = File(...)):
    if not _loaded:
        return JSONResponse(
            status_code=503,
            content={"error": _load_error or "Models not loaded"}
        )

    try:
        from PIL import Image
        from surya.ocr import run_ocr

        image_bytes = await file.read()
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode != "RGB":
            img = img.convert("RGB")

        start = time.time()

        results = run_ocr(
            [img],
            [["ar", "en"]],
            _det_model,
            _det_processor,
            _rec_model,
            _rec_processor,
        )

        lines = []
        if results and len(results) > 0:
            for text_line in results[0].text_lines:
                text = text_line.text.strip()
                if text:
                    lines.append(text)

        result_text = "\n".join(lines)
        elapsed = time.time() - start

        logger.info(f"[Surya] {len(result_text)} chars / {len(lines)} lines in {elapsed:.2f}s")

        return {
            "text": result_text,
            "chars": len(result_text),
            "lines": len(lines),
            "time_seconds": round(elapsed, 2),
        }

    except Exception as e:
        logger.error(f"[Surya] OCR error: {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"error": str(e)})


@app.get("/health")
async def health():
    gpu = torch.cuda.is_available()
    gpu_name = torch.cuda.get_device_name(0) if gpu else "N/A"

    return {
        "status": "ok" if _loaded else "failed",
        "models_loaded": _loaded,
        "load_error": _load_error,
        "gpu": gpu,
        "gpu_name": gpu_name,
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8765)
