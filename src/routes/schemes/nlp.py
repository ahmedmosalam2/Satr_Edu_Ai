from pydantic import BaseModel
from typing import List, Optional

class PushRequest(BaseModel):
    do_reset: Optional[int] = 0

class SearchRequest(BaseModel):
    text: str
    limit: Optional[int] = 10

class MultiSearchRequest(BaseModel):
    text: str
    project_ids: List[str]
    limit_per_project: Optional[int] = 5

