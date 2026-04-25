from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class ChatMessage(BaseModel):
    """رسالة واحدة في المحادثة."""
    role: str           # "user" أو "assistant"
    content: str
    timestamp: str = ""

    @classmethod
    def from_user(cls, text: str) -> "ChatMessage":
        return cls(role="user", content=text, timestamp=datetime.now().isoformat())

    @classmethod
    def from_assistant(cls, text: str) -> "ChatMessage":
        return cls(role="assistant", content=text, timestamp=datetime.now().isoformat())


class Conversation(BaseModel):
    """محادثة كاملة بين مستخدم ومشروع معين."""
    conversation_id: str
    project_id: str
    user_id: str
    title: str = "محادثة جديدة"         # أول سؤال هيبقى العنوان
    messages: List[ChatMessage] = []
    sources: List[dict] = []             # مصادر آخر إجابة
    created_at: str = ""
    updated_at: str = ""

    @classmethod
    def get_indexes(cls):
        return [
            {
                "key": [("conversation_id", 1)],
                "name": "conversation_id_unique",
                "unique": True,
            },
            {
                "key": [("user_id", 1), ("project_id", 1)],
                "name": "user_project_idx",
                "unique": False,
            },
        ]
