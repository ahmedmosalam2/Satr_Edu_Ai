from fastapi import HTTPException
from transformers import AutoModelForCausalLM, AutoTokenizer
from transformers.generation import GenerationConfig
import torch
from PIL import Image
import io
from src.helpers.config import get_settings
from src.models.enums.Response import Response

class OCRHelper:
    def __init__(self):
        self.model_path = get_settings().OCR_MODEL 
   
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = None
        self.tokenizer = None
        self._initialized = False
    
    def _initialize_model(self):
        """Lazy load the model only when first needed"""
        if self._initialized:
            return
        
        try:
             self.tokenizer = AutoTokenizer.from_pretrained(self.model_path, trust_remote_code=True)
             self.model = AutoModelForCausalLM.from_pretrained(self.model_path, trust_remote_code=True, torch_dtype=torch.bfloat16 if self.device == "cuda" else torch.float32).to(self.device)
             self.model.eval()
             self._initialized = True
             print(f"✅ OCR Model loaded successfully: {self.model_path}")
        except Exception as e:
            print(f"❌ Error loading model {self.model_path}: {e}")
            # Fallback or re-raise
            raise HTTPException(status_code=500, detail=f"OCR model loading failed: {str(e)}")

    def process_image(self, image_bytes: bytes) -> str:
        # Ensure model is loaded before processing
        self._initialize_model()
        
        try:
            pil_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

            from transformers import AutoProcessor
            processor = AutoProcessor.from_pretrained(self.model_path, trust_remote_code=True)
            
            inputs = processor(images=pil_image, text="OCR this image.", return_tensors="pt").to(self.device)
            
            with torch.no_grad():
                outputs = self.model.generate(**inputs, max_new_tokens=1024)
                
            text = processor.decode(outputs[0], skip_special_tokens=True)
            return text

        except Exception as e:
            return f"Error processing image: {str(e)}"

ocr_helper_instance = None
def get_ocr_helper():
    global ocr_helper_instance
    if ocr_helper_instance is None:
        ocr_helper_instance = OCRHelper()
    return ocr_helper_instance
