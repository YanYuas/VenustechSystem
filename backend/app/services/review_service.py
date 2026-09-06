# ============================================================
# 复盘服务（模板 upsert + 自动数据填充 + 明日计划转任务）
# 对齐 PRD §11 F5.1-F5.5
# ============================================================
from __future__ import annotations

from datetime import date

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundException
from app.core.utils import local_day_bounds_utc
from app.models.document import Document
from app.models.review import Review
from app.models.task import Task
from app.repositories import DocumentRepository, ReviewRepository, TaskRepository
from app.schemas.common import PaginatedData
from app.schemas.review import (
    AutoFillData,
    ConvertTaskRequest,
    ReviewData,
    ReviewListItem,
    ReviewOut,
    UpsertReviewRequest,
)
from app.schemas.task import CreateTaskRequest, TaskOut
from app.services.task_service import TaskService


class ReviewService:
    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id
        self.repo = ReviewRepository(db)
        self.task_repo = TaskRepository(db)
        self.doc_repo = DocumentRepository(db)

    def list(
        self, type_: str | None = None, page: int = 1, page_size: int = 20
    ) -> PaginatedData[ReviewOut]:
        skip = (page - 1) * page_size
        rows = self.repo.list_user(self.user_id, type_=type_, skip=skip, limit=page_size)
        total = self.repo.count_user(self.user_id, type_=type_)
        # 返回完整 ReviewOut（含 data 嵌套），对齐前端 types/review.ts Review
        items = [self._out(r) for r in rows]
        return PaginatedData(list=items, total=total, page=page, page_size=page_size)

    def get(self, review_date: date, type_: str = "daily") -> ReviewOut:
        review = self.repo.get_by_type_date(self.user_id, type_, review_date)
        if review is None:
            raise NotFoundException("该日期暂无复盘")
        return self._out(review)

    def upsert(self, data: UpsertReviewRequest) -> ReviewOut:
        review = self.repo.get_by_type_date(self.user_id, data.type, data.date)
        if review is None:
            review = self.repo.create(
                user_id=self.user_id, type=data.type, review_date=data.date,
                project_id=data.project_id, data=data.data.model_dump(),
            )
        else:
            review.data = data.data.model_dump()
            if "project_id" in data.model_dump(exclude_unset=True):
                review.project_id = data.project_id
            self.db.commit()
            self.db.refresh(review)
        return self._out(review)

    def delete(self, review_id: str) -> None:
        review = self.repo.get(review_id)
        if review is None or review.user_id != self.user_id:
            raise NotFoundException("复盘不存在")
        self.repo.delete(review)

    # ---------- 自动数据填充（PRD F5.2） ----------
    def auto_fill(self, review_date: date, type_: str = "daily") -> AutoFillData:
        today = review_date
        # completed_at/created_at 为 naive UTC，本地日边界须换算成 UTC 再比较（否则错位一个时区）
        day_start, day_end = local_day_bounds_utc(today)

        # SQL 层按日期过滤，避免全量查询
        # 今天完成的任务 + 今天到期的未完成任务
        task_rows = self.db.scalars(
            select(Task).where(
                Task.user_id == self.user_id,
                or_(
                    and_(Task.status == "completed", Task.completed_at >= day_start, Task.completed_at < day_end),
                    and_(Task.status != "completed", Task.due_date == today),
                ),
            )
        )
        completed = []
        unfinished = []
        for t in task_rows:
            if t.status == "completed":
                completed.append({
                    "id": t.id, "title": t.title, "completed_at": t.completed_at, "due_date": t.due_date,
                })
            else:
                unfinished.append({
                    "id": t.id, "title": t.title, "completed_at": None, "due_date": t.due_date,
                })

        # 今天创建的文档
        doc_rows = self.db.scalars(
            select(Document).where(
                Document.user_id == self.user_id,
                Document.created_at >= day_start,
                Document.created_at < day_end,
            )
        )
        docs_created = [
            {"id": d.id, "title": d.title, "created_at": d.created_at} for d in doc_rows
        ]

        # 逾期任务数
        overdue = self.db.scalar(
            select(func.count()).select_from(Task).where(
                Task.user_id == self.user_id,
                Task.status != "completed",
                Task.due_date < today,
            )
        ) or 0

        return AutoFillData(
            completed_tasks=completed,
            unfinished_tasks=unfinished,
            documents_created=docs_created,
            stats={
                "tasks_completed": len(completed),
                "documents_created": len(docs_created),
                "tasks_overdue": overdue,
            },
        )

    # ---------- 明日计划转任务（PRD F5.5） ----------
    def convert_task(self, review_id: str, data: ConvertTaskRequest) -> dict:
        review = self.repo.get(review_id)
        if review is None or review.user_id != self.user_id:
            raise NotFoundException("复盘不存在")
        svc = TaskService(self.db)
        task = svc.create(
            self.user_id,
            CreateTaskRequest(
                title=data.content,
                priority=data.priority or "medium",
                due_date=data.due_date,
            ),
        )
        return {"task_id": task.id}

    # ---------- 内部 ----------
    @staticmethod
    def _out(r: Review) -> ReviewOut:
        return ReviewOut(
            id=r.id, type=r.type, review_date=r.review_date, project_id=r.project_id,
            data=ReviewData(**(r.data or {})),
            created_at=r.created_at, updated_at=r.updated_at,
        )

    @staticmethod
    def _list_item(r: Review) -> ReviewListItem:
        d = r.data or {}
        return ReviewListItem(
            id=r.id, type=r.type, review_date=r.review_date,
            mood=d.get("mood"), energy=d.get("energy"),
            summary=(d.get("gains") or "")[:60],
            created_at=r.created_at, updated_at=r.updated_at,
        )
