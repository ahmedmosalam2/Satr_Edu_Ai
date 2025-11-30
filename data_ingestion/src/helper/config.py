import os
from pydantic import BaseModel, Field

class OCRConfig(BaseModel):
    model_name: str = Field(default="deepseek-ai/DeepSeek-OCR")
    device: str = Field(default="cuda", description="غير لـ cpu لو مفيش كارت شاشة")
    dtype: str = Field(default="bfloat16", description="لو الكارت قديم خليها float16")
    output_path: str = Field(default="./output_arabic")
    image_size: int = Field(default=1024)
    base_size: int = Field(default=1024)

config = OCRConfig(dict(
    model_name="deepseek-ai/DeepSeek-OCR",
    device="cuda",
    dtype="bfloat16",
    output_path="./output_arabic",
    image_size=1024,
    base_size=1024
))
