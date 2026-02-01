from pydantic import BaseModel,Field,validator
from typing import Optional
from bson import ObjectId
from datetime import datetime

class Asset(BaseModel):
    _id: Optional[ObjectId] = None
    asset_id: str = Field(..., min_length=1)
    asset_project_id: str
    asset_type: str = Field(..., min_length=1)
    asset_name: str = Field(..., min_length=1)
    asset_size: int = Field(default=0, ge=0)
    asset_created_at: datetime = Field(default_factory=datetime.now)
   
   

    @validator("asset_id")
    def validate_asset_id(cls, v):
        if not v:
            raise ValueError("Asset ID is required")
        return v
    
    class Config:
        arbitrary_types_allowed = True
    @classmethod
    def get_indexes(cls):
        return [
            {"key": [
                ("asset_id", 1)
            ],
            "name":"asset_id_name",
             "unique": False          

            },{
            "key": [
                ("asset_project_id", 1),
                ("asset_name", 1)
            ],
            "name":"asset_project_id_asset_name_index1",
             "unique": True          

            }
        ]