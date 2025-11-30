import torch
from transformers import AutoModel, AutoTokenizer
from huggingface_hub import login
import os
from dotenv import load_dotenv
from ..helper.config import OCRConfig


load_dotenv()
class OCREngine:
    def __init__(self, config):
        self.cfg = config
        self._authenticate()
        self.tokenizer, self.model = self._load_model()

    def _authenticate(self):
        token = os.getenv("HF_TOKEN")
        if not token:
            raise ValueError("HF_TOKEN not found in .env file")
        login(token=token)

    def _load_model(self):
        print(f" Loading {self.cfg.model_name}...")
        tokenizer = AutoTokenizer.from_pretrained(self.cfg.model_name, trust_remote_code=True)
        model = AutoModel.from_pretrained(
            self.cfg.model_name,
            trust_remote_code=True,
            use_safetensors=True,
            torch_dtype=getattr(torch, self.cfg.dtype),
            device_map="auto"
        )
        model = model.eval().to(self.cfg.device)
        if self.cfg.dtype == "bfloat16":
            model = model.to(torch.bfloat16)
        return tokenizer, model

    def process_image(self, image_path, prompt="<image>\nPlease extract all the text clearly from the image."):
        print(f"📷 Processing: {image_path}")
        result = self.model.infer(
            self.tokenizer,
            prompt=prompt,
            image_file=image_path,
            output_path=self.cfg.output_path,
            base_size=self.cfg.base_size,
            image_size=self.cfg.image_size,
            crop_mode=False,
            save_results=True,
            test_compress=False
        )
        return result
engine = OCREngine(OCRConfig())
