import uuid
import logging
from datetime import datetime
from typing import List, Optional

from src.models.BaseDataModel import BaseDataModel
from src.models.scheme_db.conversation import Conversation, ChatMessage

logger = logging.getLogger("uvicorn.error")

COLLECTION_NAME = "conversations"


class ConversationModel(BaseDataModel):
    """
    CRUD operations للمحادثات.
    كل محادثة مرتبطة بـ (user_id + project_id).
    """

    def __init__(self, client: object = None):
        super().__init__(client)
        self.collection = self.db[COLLECTION_NAME] if self.db is not None else None

    # ── Indexes ──────────────────────────────────────────────────────────────
    @classmethod
    async def create_indexes(cls, db_client: object):
        instance = cls(client=db_client)
        if instance.collection is None:
            return instance
        existing = await instance.db.list_collection_names()
        if COLLECTION_NAME not in existing:
            for idx in Conversation.get_indexes():
                await instance.collection.create_index(
                    idx["key"],
                    unique=idx["unique"],
                    name=idx["name"],
                )
            logger.info("✅ Conversation indexes created")
        return instance

    # ── Create ───────────────────────────────────────────────────────────────
    async def create_conversation(
        self,
        project_id: str,
        user_id: str,
        first_message: str = "",
    ) -> Conversation:
        """أنشئ محادثة جديدة وارجع الـ object."""
        now = datetime.now().isoformat()
        conv = Conversation(
            conversation_id=str(uuid.uuid4()),
            project_id=project_id,
            user_id=user_id,
            title=first_message[:60] or "محادثة جديدة",  # أول 60 حرف كعنوان
            messages=[],
            sources=[],
            created_at=now,
            updated_at=now,
        )
        await self.collection.insert_one(conv.dict())
        return conv

    # ── Get one ───────────────────────────────────────────────────────────────
    async def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        doc = await self.collection.find_one({"conversation_id": conversation_id})
        if doc is None:
            return None
        doc.pop("_id", None)
        return Conversation(**doc)

    # ── List by user + project ─────────────────────────────────────────────
    async def list_conversations(
        self,
        user_id: str,
        project_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> List[Conversation]:
        query: dict = {"user_id": user_id}
        if project_id:
            query["project_id"] = project_id

        cursor = (
            self.collection.find(query)
            .sort("updated_at", -1)
            .skip((page - 1) * page_size)
            .limit(page_size)
        )
        docs = await cursor.to_list(length=page_size)
        result = []
        for d in docs:
            d.pop("_id", None)
            result.append(Conversation(**d))
        return result

    # ── Append message ────────────────────────────────────────────────────────
    async def append_turn(
        self,
        conversation_id: str,
        user_text: str,
        assistant_text: str,
        sources: List[dict] = None,
    ) -> bool:
        """
        أضف سؤال المستخدم + إجابة الـ AI في نفس الوقت.
        لازم تحفظها كـ pair عشان التاريخ يبقى مترتب.
        """
        user_msg = ChatMessage.from_user(user_text).dict()
        assistant_msg = ChatMessage.from_assistant(assistant_text).dict()
        now = datetime.now().isoformat()

        result = await self.collection.update_one(
            {"conversation_id": conversation_id},
            {
                "$push": {
                    "messages": {"$each": [user_msg, assistant_msg]}
                },
                "$set": {
                    "updated_at": now,
                    "sources": sources or [],
                },
            },
        )
        return result.modified_count > 0

    # ── Delete ────────────────────────────────────────────────────────────────
    async def delete_conversation(self, conversation_id: str) -> bool:
        result = await self.collection.delete_one({"conversation_id": conversation_id})
        return result.deleted_count > 0

    # ── Clear messages (keep conversation) ────────────────────────────────────
    async def clear_conversation(self, conversation_id: str) -> bool:
        result = await self.collection.update_one(
            {"conversation_id": conversation_id},
            {"$set": {"messages": [], "updated_at": datetime.now().isoformat()}},
        )
        return result.modified_count > 0
