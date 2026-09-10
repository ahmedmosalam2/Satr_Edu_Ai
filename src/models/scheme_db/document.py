"""
src/models/scheme_db/document.py
────────────────────────────────
Document schema — يتتبع حالة كل ملف مرفوع.

⚠️ ملف جديد تماماً — مش بيأثر على الـ Asset أو Project الموجودين.
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime


class Document(BaseModel):
    """
    ملف مرفوع مع حالته ومعلوماته.

    Lifecycle:
      uploaded → processing → processed → indexed → failed
    """
    _id: Optional[object] = None

    document_id: str = Field(..., description="Unique document ID")
    project_id: str = Field(..., description="Parent project ID")

    # File info
    file_name: str = ""
    file_type: str = ""              # .pdf, .docx, .pptx, ...
    file_size: int = 0               # bytes
    file_path: str = ""              # where it's stored

    # Status tracking
    status: str = "uploaded"         # uploaded | processing | processed | indexed | failed
    error_message: str = ""          # error details if failed

    # Processing config
    chunk_strategy: str = "naive"    # naive | structure | semantic
    chunk_size: int = 500
    chunk_overlap: int = 50

    # Processing results
    pages_count: int = 0
    chunks_count: int = 0
    parse_time_ms: float = 0
    chunk_time_ms: float = 0

    # Parser used
    parser_name: str = ""            # pdf, docx, pptx, ...

    # Feature flags
    is_enabled: bool = True          # يقدر يعطل الملف بدون حذف
    is_ocr: bool = False             # هل استخدم OCR

    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    processed_at: Optional[datetime] = None

    class Config:
        arbitrary_types_allowed = True

    @classmethod
    def get_indexes(cls):
        return [
            {
                "key": [("document_id", 1)],
                "name": "document_id_idx",
                "unique": True,
            },
            {
                "key": [("project_id", 1)],
                "name": "document_project_id_idx",
                "unique": False,
            },
            {
                "key": [("project_id", 1), ("status", 1)],
                "name": "document_project_status_idx",
                "unique": False,
            },
        ]
