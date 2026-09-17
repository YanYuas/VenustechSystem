# ============================================================
# 保险箱路由（三期 D）
#
# 明文出系统的唯一出口：GET /vault/items/{id}/secret（要求解锁态）。
# 所有凭据端点都要求解锁；setup/unlock/lock/status 不要求。
# ============================================================
from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.response import success
from app.services.vault_service import VaultService

if TYPE_CHECKING:
    from app.models.user import User

router = APIRouter(prefix="/vault", tags=["vault"])


def _svc(db: Session, user: User) -> VaultService:
    return VaultService(db, user.id)


# ---------- 请求体 ----------

class SetupRequest(BaseModel):
    master_password: str = Field(..., min_length=8, max_length=128)


class UnlockRequest(BaseModel):
    master_password: str = Field(..., min_length=1, max_length=128)


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)


class CreateItemRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    category: Literal["login", "note"] = "login"
    username: str | None = Field(None, max_length=200)
    url: str | None = Field(None, max_length=500)
    secret: str | None = Field(None, max_length=10000)
    notes: str | None = Field(None, max_length=10000)
    identity_id: str | None = None
    # 终端动作（D 收尾）：白名单模板，禁止任意命令
    action_type: Literal["none", "ssh"] = "none"
    action_host: str | None = Field(None, max_length=255)
    action_user: str | None = Field(None, max_length=255)
    action_port: str | None = Field(None, max_length=10)


class UpdateItemRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    category: Literal["login", "note"] | None = None
    username: str | None = Field(None, max_length=200)
    url: str | None = Field(None, max_length=500)
    secret: str | None = Field(None, max_length=10000)
    notes: str | None = Field(None, max_length=10000)
    identity_id: str | None = None
    action_type: Literal["none", "ssh"] | None = None
    action_host: str | None = Field(None, max_length=255)
    action_user: str | None = Field(None, max_length=255)
    action_port: str | None = Field(None, max_length=10)


# ---------- 状态与主密码 ----------

@router.get("/status", summary="保险箱状态")
def status(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return success(_svc(db, user).status())


@router.put("/setup", summary="初始化主密码（仅首次）")
def setup(data: SetupRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return success(_svc(db, user).setup(data.master_password))


@router.post("/unlock", summary="解锁")
def unlock(data: UnlockRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return success(_svc(db, user).unlock(data.master_password))


@router.post("/lock", summary="上锁")
def lock(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return success(_svc(db, user).lock())


@router.post("/change-password", summary="更换主密码（重加密全部凭据）")
def change_password(
    data: ChangePasswordRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db, user).change_master_password(data.old_password, data.new_password))


# ---------- 凭据 ----------

@router.get("/items", summary="凭据列表（不含密文）")
def list_items(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return success(_svc(db, user).list_items())


@router.post("/items", summary="新增凭据")
def create_item(data: CreateItemRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return success(_svc(db, user).create_item(**data.model_dump()))


@router.patch("/items/{item_id}", summary="更新凭据")
def update_item(
    item_id: str, data: UpdateItemRequest,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    return success(_svc(db, user).update_item(item_id, **data.model_dump(exclude_unset=True)))


@router.delete("/items/{item_id}", summary="删除凭据")
def delete_item(item_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return success(_svc(db, user).delete_item(item_id))


@router.get("/items/{item_id}/secret", summary="查看密文对应的明文（唯一出口，要求解锁）")
def reveal(item_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return success(_svc(db, user).reveal_secret(item_id))


@router.post("/items/{item_id}/run-action", summary="执行终端动作（白名单模板：ssh -i 密钥路径）")
def run_action(
    item_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db, user).run_action(item_id))
