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
    """请求级事务（架构 v2.0 §5.3 / 审计 D-04）。

    事务边界在**请求**这一层闭合：
      · 路由/服务没有显式 commit 的写入，由这里在响应前统一提交 —— 这是
        repository 去掉内部 commit 后的兜底；
      · 请求过程中抛任何异常（校验失败、业务异常、未捕获异常）都 rollback，
        保证一个请求内的多步写入要么全成、要么全不成；
      · finally 只负责归还连接。

    注意：需要「写完 → commit → publish」语义的用例仍由 service 显式
    commit（事件订阅者用独立 Session，未提交数据读不到）。
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
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
