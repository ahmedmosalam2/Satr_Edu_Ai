from pydantic import BaseModel,Field,validator
from typing import Optional
from bson import ObjectId

class DataChunk(BaseModel):
    _id: Optional[ObjectId] = None
    
    chunk_id: str
    chunk_text: str=Field(...,min_length=1)
    chunk_metadata: dict
    chunk_order: int=Field(...,gt=0)
    chunk_created_at: str
    chunk_updated_at: str
    chunk_project_id: ObjectId
    @validator('chunk_id'):
        def chunk_id_must_be_unique(cls, v):
            if v in cls._id:
                raise ValueError('chunk_id must be unique')
            return v

class Config:
    arbitrary_types_allowed = True
