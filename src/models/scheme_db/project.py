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

    @validator("project_id")
    def validate_project_id(cls, v):
        if not v:
            raise ValueError("Project ID is required")
        return v
    
    class Config:
        arbitrary_types_allowed = True
    @classmethod
    def get_indexes(cls):
        return [
            {"key": [
                ("project_id", 1)
            ],
            "name":"project_id_name",
             "unique": True           

            }
        ]
