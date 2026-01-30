from pydantic import BaseModel,Field,validator
from typing import Optional
from bson import ObjectId

class Project(BaseModel):
    _id: Optional[ObjectId] = None
    project_id: str = Field(..., min_length=1, description="Project ID")
    project_name: str = ""
    project_description: str = ""
    project_files: list[str] = []
    project_created_at: str = ""
    project_updated_at: str = ""
    
    class Config:
        arbitrary_types_allowed = True
