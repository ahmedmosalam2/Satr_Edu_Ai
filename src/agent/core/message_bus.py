"""
src/agent/core/message_bus.py
─────────────────────────────
Agent Communication Bus — الأعصاب بين الـ agents.

كل agent يبعث ويستقبل رسائل من خلال الـ bus.
الـ Orchestrator يشوف كل حاجة ويقرر.

Message Flow:
  User → Orchestrator → [Researcher, Tutor, Examiner, ...] → Orchestrator → User
"""

import logging
import time
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum

logger = logging.getLogger("uvicorn.error")


class MessageType(Enum):
    """أنواع الرسائل بين الـ agents."""
    REQUEST = "request"           # طلب من agent لـ agent تاني
    RESPONSE = "response"         # رد على طلب
    BROADCAST = "broadcast"       # رسالة لكل الـ agents
    CONTEXT = "context"           # معلومات سياقية
    FEEDBACK = "feedback"         # تقييم أو ملاحظة


@dataclass
class AgentMessage:
    """رسالة واحدة بين agents."""
    msg_id: str = ""
    from_agent: str = ""
    to_agent: str = ""
    msg_type: str = MessageType.REQUEST.value
    content: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    priority: int = 0             # 0 = عادي, 1+ = أعلى

    def to_dict(self) -> dict:
        return {
            "from": self.from_agent,
            "to": self.to_agent,
            "type": self.msg_type,
            "content": self.content[:200],
            "priority": self.priority,
        }


class MessageBus:
    """
    قناة التواصل بين الـ agents.

    كل agent يسجّل نفسه والـ bus يوصّل الرسائل.
    """

    def __init__(self):
        self._messages: List[AgentMessage] = []
        self._msg_counter = 0

    def send(
        self,
        from_agent: str,
        to_agent: str,
        content: str,
        msg_type: str = MessageType.REQUEST.value,
        data: dict = None,
        priority: int = 0,
    ) -> str:
        """ابعث رسالة وارجع الـ msg_id."""
        self._msg_counter += 1
        msg_id = f"msg_{self._msg_counter}"

        msg = AgentMessage(
            msg_id=msg_id,
            from_agent=from_agent,
            to_agent=to_agent,
            msg_type=msg_type,
            content=content,
            data=data or {},
            priority=priority,
        )
        self._messages.append(msg)

        logger.debug(f"[MessageBus] {from_agent} → {to_agent}: {content[:80]}")
        return msg_id

    def get_messages_for(self, agent_name: str, msg_type: str = None) -> List[AgentMessage]:
        """ارجع كل الرسائل لـ agent معين."""
        msgs = [m for m in self._messages if m.to_agent == agent_name]
        if msg_type:
            msgs = [m for m in msgs if m.msg_type == msg_type]
        return sorted(msgs, key=lambda m: -m.priority)

    def get_all_messages(self) -> List[AgentMessage]:
        """ارجع كل الرسائل (للـ debugging)."""
        return self._messages.copy()

    def get_conversation_log(self) -> List[dict]:
        """ارجع log مقروء للمحادثة بين الـ agents."""
        return [m.to_dict() for m in self._messages]

    def clear(self):
        """مسح كل الرسائل."""
        self._messages.clear()
        self._msg_counter = 0
