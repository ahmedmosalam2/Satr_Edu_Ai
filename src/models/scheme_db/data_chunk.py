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

    @validator("chunk_id")
    def validate_chunk_id(cls, v):
        if not v:
            raise ValueError("Chunk ID is required")
        return v
    class Config:
        arbitrary_types_allowed = True
    @classmethod
    def get_indexes(cls):
        return [
            {"key": [
                ("chunk_id", 1)
            
            
            ],
            "name": "chunk_id_name",
             "unique": False
       
            }
        ]