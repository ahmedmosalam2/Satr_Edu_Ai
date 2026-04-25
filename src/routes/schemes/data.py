from pydantic import BaseModel
from typing import Optional

class ProcessRequest(BaseModel):
    file_id: str
    chunk_size: Optional[int] = 1000
    chunk_overlap: Optional[int] = 100
    do_reset: Optional[bool] = False
    use_deepdoc: Optional[bool] = True    # True = Smart chunking (DeepDoc), False = Simple
