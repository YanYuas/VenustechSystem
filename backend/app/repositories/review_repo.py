from __future__ import annotations

from datetime import date

from sqlalchemy import func, select

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

    # ---------- D-06 收口新增 ----------

    def list_project_for_detail(self, project_id: str, limit: int = 50) -> list[Review]:
        """项目详情用：按复盘业务日期倒序。"""
        q = (
            select(Review)
            .where(Review.project_id == project_id)
            .order_by(Review.review_date.desc())
            .limit(limit)
        )
        return list(self.db.scalars(q))

    def list_project_for_timeline(self, project_id: str, limit: int = 20) -> list[Review]:
        """项目时间线用：按创建时间倒序。"""
        q = (
            select(Review)
            .where(Review.project_id == project_id)
            .order_by(Review.created_at.desc())
            .limit(limit)
        )
        return list(self.db.scalars(q))

    def list_all_by_project(self, project_id: str) -> list[Review]:
        """项目导出用：全量（不排序、不分页）。"""
        return list(
            self.db.scalars(select(Review).where(Review.project_id == project_id))
        )

    def list_recent_dates(self, user_id: str, since: date) -> list[date]:
        """首页连续打卡用：某日期之后的复盘日期（倒序）。"""
        q = (
            select(Review.review_date)
            .where(Review.user_id == user_id, Review.review_date >= since)
            .order_by(Review.review_date.desc())
        )
        return [d for d in self.db.scalars(q) if d]

    def identity_counts(self, user_id: str) -> dict[str, int]:
        """按身份分组计数（跳过未归类）。"""
        q = (
            select(Review.identity_id, func.count())
            .where(Review.user_id == user_id, Review.identity_id.is_not(None))
            .group_by(Review.identity_id)
        )
        return {rid: int(count) for rid, count in self.db.execute(q).all()}

    def count_identity_unassigned(self, user_id: str) -> int:
        """未归类复盘数。"""
        q = select(func.count()).select_from(Review).where(
            Review.user_id == user_id,
            Review.identity_id.is_(None),
        )
        return int(self.db.scalar(q) or 0)

    def clear_identity(self, identity_id: str) -> None:
        """把某身份的引用清回「未归类」（身份软删除时用；只 flush）。"""
        self.nullify("identity_id", identity_id=identity_id)

    def clear_project(self, project_id: str) -> None:
        """解除复盘与项目的关联（项目删除时用；只 flush）。"""
        self.nullify("project_id", project_id=project_id)
