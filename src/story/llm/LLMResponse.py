from pydantic import BaseModel
from LLMEnums import LLMModel

class LLMResponse(BaseModel):
    text: str
    model: LLMModel
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    embedding: list[float]
    