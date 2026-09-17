# ============================================================
# 依赖注入（DB Session / 当前用户）
# - get_db：请求级 Session，finally 关闭
# - get_current_user：一期单用户，Request.state 请求级缓存（避免每请求查库）
# ============================================================
from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import Depends, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.repositories import UserRepository


if TYPE_CHECKING:
    from app.models.user import User


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """一期单用户：不存在则自动创建 default_user；同请求内缓存在 request.state。"""
    cached: User | None = getattr(request.state, "current_user", None)
    if cached is not None:
        return cached
    repo = UserRepository(db)
    user = repo.get_by_username("default_user")
    if user is None:
        try:
            user = repo.create(
                username="default_user",
                nickname="启明星用户",
                pet_position={"x": 1770, "y": 880},
            )
        except IntegrityError:
            # 并发场景下用户已被其他请求创建，重新查询
            db.rollback()
            user = repo.get_by_username("default_user")
            if user is None:
                raise
    request.state.current_user = user
    return user
