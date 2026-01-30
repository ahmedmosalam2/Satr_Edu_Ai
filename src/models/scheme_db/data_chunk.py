from pydantic import BaseModel,Field,validator
from typing import Optional
from bson import ObjectId

class DataChunk(BaseModel):
    _id: Optional[ObjectId] = None
    chunk_id: str = ""
    chunk_text: str = ""
    chunk_metadata: dict = {}
    chunk_order: int = 0
    chunk_created_at: str = ""
    chunk_updated_at: str = ""
    chunk_project_id: Optional[str] = None
    class Config:
        arbitrary_types_allowed = True
