from __future__ import annotations

from datetime import date

from sqlalchemy import select

from app.models.review import Review
from app.repositories.base import BaseRepository


class ReviewRepository(BaseRepository[Review]):
    model = Review

    def get_by_type_date(self, user_id: str, type_: str, review_date: date) -> Review | None:
        return self.db.scalar(
            select(Review).where(
                Review.user_id == user_id,
                Review.type == type_,
                Review.review_date == review_date,
            )
        )

    def list_user(
        self, user_id: str, type_: str | None = None, skip: int = 0, limit: int = 100
    ) -> list[Review]:
        q = select(Review).where(Review.user_id == user_id)
        if type_:
            q = q.where(Review.type == type_)
        q = q.order_by(Review.review_date.desc()).offset(skip).limit(limit)
        return list(self.db.scalars(q))

    def count_user(self, user_id: str, type_: str | None = None) -> int:
        return self.count(user_id=user_id, type=type_)
