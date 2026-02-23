from pydantic import BaseModel
from typing import List,Optional

class NLPRequest(BaseModel):
    project_id:str
    text:str