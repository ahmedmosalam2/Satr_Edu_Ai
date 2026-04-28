"""
src/models/DocumentModel.py
───────────────────────────
Document Model — CRUD operations للـ documents.

⚠️ ملف جديد تماماً — مش بيأثر على AssetModel أو أي model موجود.
"""

from .BaseDataModel import BaseDataModel
from src.models.scheme_db.document import Document
from datetime import datetime
import math
import logging

logger = logging.getLogger("uvicorn.error")

# Collection name
DOCUMENT_COLLECTION = "documents"


class DocumentModel(BaseDataModel):
    def __init__(self, client: object = None):
        super().__init__(client)
        self.collection = self.db[DOCUMENT_COLLECTION] if self.db is not None else None

    @classmethod
    async def create_index(cls, db_client: object):
        instance = cls(client=db_client)
        await instance.init_collection()
        return instance

    async def init_collection(self):
        if self.db is None:
            return
        all_collections = await self.db.list_collection_names()
        if DOCUMENT_COLLECTION not in all_collections:
            self.collection = self.db[DOCUMENT_COLLECTION]
            indexes = Document.get_indexes()
            for index in indexes:
                await self.collection.create_index(
                    index["key"],
                    unique=index["unique"],
                    name=index["name"],
                )

    # ── CRUD ──────────────────────────────────────────────────────────────────

    async def create_document(self, document: Document) -> str:
        """إنشاء document جديد أو update لو موجود."""
        doc = document.dict(exclude={"_id"})
        await self.collection.update_one(
            {"document_id": document.document_id},
            {"$set": doc},
            upsert=True,
        )
        return document.document_id

    async def get_document(self, document_id: str) -> Document | None:
        result = await self.collection.find_one({"document_id": document_id})
        if result is None:
            return None
        result.pop("_id", None)
        return Document(**result)

    async def update_document(self, document_id: str, updates: dict):
        """Update specific fields."""
        updates["updated_at"] = datetime.now()
        result = await self.collection.update_one(
            {"document_id": document_id},
            {"$set": updates},
        )
        return result.modified_count

    async def update_status(self, document_id: str, status: str, error: str = ""):
        """Update document status."""
        updates = {
            "status": status,
            "updated_at": datetime.now(),
        }
        if error:
            updates["error_message"] = error
        if status == "processed":
            updates["processed_at"] = datetime.now()
        return await self.collection.update_one(
            {"document_id": document_id},
            {"$set": updates},
        )

    async def delete_document(self, document_id: str) -> bool:
        result = await self.collection.delete_one({"document_id": document_id})
        return result.deleted_count > 0

    # ── Queries ───────────────────────────────────────────────────────────────

    async def get_project_documents(
        self,
        project_id: str,
        status: str = None,
        page: int = 1,
        page_size: int = 20,
    ) -> dict:
        """Get all documents for a project with optional status filter."""
        query = {"project_id": project_id}
        if status:
            query["status"] = status

        total = await self.collection.count_documents(query)
        total_pages = math.ceil(total / page_size) if total > 0 else 0

        cursor = (
            self.collection
            .find(query)
            .sort("created_at", -1)
            .skip((page - 1) * page_size)
            .limit(page_size)
        )
        docs = await cursor.to_list(length=page_size)

        documents = []
        for d in docs:
            d.pop("_id", None)
            documents.append(Document(**d))

        return {
            "total": total,
            "total_pages": total_pages,
            "page": page,
            "documents": documents,
        }

    async def get_project_stats(self, project_id: str) -> dict:
        """إحصائيات الملفات لمشروع."""
        if self.collection is None:
            return {}

        pipeline = [
            {"$match": {"project_id": project_id}},
            {"$group": {
                "_id": "$status",
                "count": {"$sum": 1},
                "total_chunks": {"$sum": "$chunks_count"},
                "total_pages": {"$sum": "$pages_count"},
                "total_size": {"$sum": "$file_size"},
            }},
        ]
        results = {}
        async for doc in self.collection.aggregate(pipeline):
            results[doc["_id"]] = {
                "count": doc["count"],
                "total_chunks": doc["total_chunks"],
                "total_pages": doc["total_pages"],
                "total_size": doc["total_size"],
            }
        return results

    async def toggle_document(self, document_id: str, enabled: bool) -> bool:
        """تفعيل/تعطيل ملف بدون حذف."""
        result = await self.collection.update_one(
            {"document_id": document_id},
            {"$set": {"is_enabled": enabled, "updated_at": datetime.now()}},
        )
        return result.modified_count > 0

    async def get_enabled_documents(self, project_id: str) -> list:
        """Get only enabled documents."""
        cursor = self.collection.find({
            "project_id": project_id,
            "is_enabled": True,
            "status": {"$in": ["processed", "indexed"]},
        })
        docs = await cursor.to_list(length=1000)
        return [Document(**{k: v for k, v in d.items() if k != "_id"}) for d in docs]
