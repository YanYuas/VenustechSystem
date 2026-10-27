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

    # ---------- D-06 收口新增：供 project/document 服务用 ----------

    def count_by_user(self, user_id: str) -> int:
        return self.count(user_id=user_id)

    def list_project_by_updated(self, project_id: str, limit: int = 50) -> list[Conversation]:
        """项目详情用：按最近更新排序。"""
        q = (
            select(Conversation)
            .where(Conversation.project_id == project_id)
            .order_by(Conversation.updated_at.desc())
            .limit(limit)
        )
        return list(self.db.scalars(q))

    def list_project_by_created(self, project_id: str, limit: int = 20) -> list[Conversation]:
        """项目时间线用：按创建时间倒序。"""
        q = (
            select(Conversation)
            .where(Conversation.project_id == project_id)
            .order_by(Conversation.created_at.desc())
            .limit(limit)
        )
        return list(self.db.scalars(q))

    def list_all_by_project(self, project_id: str) -> list[Conversation]:
        """项目导出用：全量（不排序、不分页）。"""
        return list(
            self.db.scalars(select(Conversation).where(Conversation.project_id == project_id))
        )

    def search_by_title(self, user_id: str, keyword: str, limit: int = 10) -> list[Conversation]:
        """全局搜索：标题包含关键字。"""
        like = f"%{keyword}%"
        q = (
            select(Conversation)
            .where(Conversation.user_id == user_id, Conversation.title.like(like))
            .limit(limit)
        )
        return list(self.db.scalars(q))

    def clear_project(self, project_id: str) -> None:
        """解除对话与项目的关联（项目删除时用；只 flush）。"""
        self.nullify("project_id", project_id=project_id)


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
