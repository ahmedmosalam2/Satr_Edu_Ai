from pydantic import BaseModel
from typing import List,Optional

class PushRequest(BaseModel):
    do_reset:Optional[int]=0
    