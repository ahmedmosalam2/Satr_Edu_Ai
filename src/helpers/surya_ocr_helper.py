import io
import json
import logging
import time
from typing import Optional

import httpx
import torch

logger = logging.getLogger("uvicorn.error")


def _get_service_url() -> str:
    try:
        from src.helpers.config import get_settings
        return get_settings().SURYA_SERVICE_URL
    except Exception:
        import os
        return os.environ.get("SURYA_SERVICE_URL", "http://host.docker.internal:8765")


class SuryaOCRHelper:
    def __init__(self, service_url: str = None):
        self._service_url = service_url or _get_service_url()
        self._service_available = None
        self._det_model = None
        self._det_processor = None
        self._rec_model = None
        self._rec_processor = None
        self._local_loaded = False
        self._load_error = None

    def _check_service(self) -> bool:
        if self._service_available:
            return True
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(f"{self._service_url}/health")
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("models_loaded"):
                        logger.info(f"[Surya] Remote service OK @ {self._service_url} — GPU: {data.get('gpu_name', 'N/A')}")
                        self._service_available = True
                        return True
                    else:
                        logger.warning(f"[Surya] Remote service up but models not loaded: {data.get('load_error')}")
        except Exception as e:
            logger.info(f"[Surya] Remote service not reachable at {self._service_url}: {e}")
        self._service_available = False
        return False

    def _load_recognition_model_local(self, checkpoint="vikp/surya_rec2", device="cpu", dtype=torch.float32):
        from surya.model.recognition.model import (
            SuryaOCRConfig, OCREncoderDecoderModel,
            SuryaOCRDecoderConfig, DonutSwinConfig, SuryaOCRTextEncoderConfig,
            load_model,
        )

        try:
            return load_model(checkpoint=checkpoint, device=device, dtype=dtype)
        except Exception as e:
            logger.warning(f"[Surya] Standard local load failed ({e}) — trying manual compat fix")

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
        config.get_text_config = lambda decoder=False: decoder_cfg if decoder else text_encoder_cfg
        config.model_type = "surya_ocr"
        config.tie_word_embeddings = False

        import transformers.modeling_utils
        old_tie = transformers.modeling_utils.PreTrainedModel.tie_weights
        transformers.modeling_utils.PreTrainedModel.tie_weights = lambda self: None
        try:
            model = OCREncoderDecoderModel.from_pretrained(
                checkpoint, config=config, torch_dtype=dtype, ignore_mismatched_sizes=True
            )
        finally:
            transformers.modeling_utils.PreTrainedModel.tie_weights = old_tie

        return model.to(device).eval()

    def _ensure_local_loaded(self) -> bool:
        if self._local_loaded:
            return True
        if self._load_error:
            return False
        try:
            logger.info("[Surya] Loading local models (CPU fallback)...")
            device = "cpu"
            dtype = torch.float32

            from surya.model.detection.model import load_model as load_det, load_processor as load_det_proc
            self._det_model = load_det(device=device, dtype=dtype)
            self._det_processor = load_det_proc()

            self._rec_model = self._load_recognition_model_local(device=device, dtype=dtype)
            from surya.model.recognition.processor import load_processor as load_rec_proc
            self._rec_processor = load_rec_proc()

            self._local_loaded = True
            logger.info("[Surya] Local models ready (CPU)")
            return True
        except Exception as e:
            self._load_error = str(e)
            logger.error(f"[Surya] Failed to load local models: {e}")
            return False

    def extract_text(self, image_bytes: bytes) -> str:
        if self._check_service():
            try:
                with httpx.Client(timeout=120.0) as client:
                    files = {"file": ("image.png", image_bytes, "image/png")}
                    resp = client.post(f"{self._service_url}/ocr", files=files)
                    if resp.status_code == 200:
                        data = resp.json()
                        text = data.get("text", "")
                        if text:
                            return text
            except Exception as e:
                logger.warning(f"[Surya] Remote error: {e}")
                self._service_available = None

        if not self._ensure_local_loaded():
            return ""

        try:
            from PIL import Image
            from surya.ocr import run_ocr
            img = Image.open(io.BytesIO(image_bytes))
            if img.mode != "RGB":
                img = img.convert("RGB")

            results = run_ocr(
                [img], [["ar", "en"]],
                self._det_model, self._det_processor,
                self._rec_model, self._rec_processor,
            )
            return "\n".join([l.text for l in results[0].text_lines]) if results else ""
        except Exception as e:
            logger.error(f"[Surya] Local error: {e}")
            return ""

    def is_available(self) -> bool:
        return self._check_service() or self._ensure_local_loaded()

    def get_status(self) -> dict:
        if self._check_service():
            return {"available": True, "mode": "gpu_service", "service_url": self._service_url}
        if self._local_loaded:
            return {"available": True, "mode": "local_cpu"}
        return {"available": False, "reason": self._load_error or "Service not running"}


_surya_instance: Optional[SuryaOCRHelper] = None


def get_surya_ocr() -> Optional[SuryaOCRHelper]:
    global _surya_instance
    if _surya_instance is None:
        _surya_instance = SuryaOCRHelper()
    return _surya_instance
