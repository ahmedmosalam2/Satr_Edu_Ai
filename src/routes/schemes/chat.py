from pydantic import BaseModel, Field
from typing import Optional, List


class ChatRequest(BaseModel):
    """طلب محادثة — ممكن تبدأ محادثة جديدة أو تكمل واحدة قديمة."""
    text: str = Field(..., min_length=1, description="سؤال المستخدم")
    conversation_id: Optional[str] = Field(
        None,
        description="اتركه فاضي لبدء محادثة جديدة، أو ابعت ID محادثة موجودة للاكمال"
    )
    limit: int = Field(5, ge=1, le=20, description="عدد chunks للاسترجاع")


class MessageResponse(BaseModel):
    role: str
    content: str
    timestamp: str


class ChatResponse(BaseModel):
    """استجابة المحادثة."""
    conversation_id: str
    answer: str
    sources: List[dict] = []
    history: List[MessageResponse] = []
    is_new_conversation: bool


class ConversationSummary(BaseModel):
    """ملخص محادثة في القائمة."""
    conversation_id: str
    project_id: str
    title: str
    message_count: int
    created_at: str
    updated_at: str
