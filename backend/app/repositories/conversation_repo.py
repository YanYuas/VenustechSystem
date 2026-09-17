from __future__ import annotations

from sqlalchemy import select

from app.models.conversation import Conversation, Message
from app.repositories.base import BaseRepository


class ConversationRepository(BaseRepository[Conversation]):
    model = Conversation

    def list_user(self, user_id: str) -> list[Conversation]:
        q = (
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc())
        )
        return list(self.db.scalars(q))


class MessageRepository(BaseRepository[Message]):
    model = Message

    def list_conversation(self, conversation_id: str) -> list[Message]:
        q = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at)
        )
        return list(self.db.scalars(q))

    def list_recent(self, conversation_id: str, limit: int = 20) -> list[Message]:
        q = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        return list(reversed(list(self.db.scalars(q))))
