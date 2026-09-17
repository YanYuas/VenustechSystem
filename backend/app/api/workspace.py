# ============================================================
# 工作区路由（三期 C · 可选功能 + 引导部署）
#
# 默认关闭（settings["workspace.enabled"]="false"）。前端在引导
# 流程完成前不展示入口；后端各端点仍要求登录。
#
# GET    /api/v1/workspace/status              开关 + 根概况（引导页首屏）
# PUT    /api/v1/workspace/enabled             启用/停用整个功能
# GET    /api/v1/workspace/roots               根列表
# POST   /api/v1/workspace/roots               登记根（引导路径 a）
# PATCH  /api/v1/workspace/roots/{id}          改标签/启停/换身份
# DELETE /api/v1/workspace/roots/{id}          删根 + 清索引（不碰磁盘）
# POST   /api/v1/workspace/roots/{id}/scan     扫描（噪声过滤，只存元数据）
# POST   /api/v1/workspace/roots/{id}/skeleton 按身份生成目录骨架（引导路径 b）
# GET    /api/v1/workspace/files               索引检索
# POST   /api/v1/workspace/open-terminal       一键开终端（唯一白名单动作）
# ============================================================
from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.response import success
from app.services.settings_service import SettingsService
from app.services.workspace_service import WorkspaceService

if TYPE_CHECKING:
    from app.models.user import User

router = APIRouter(prefix="/workspace", tags=["workspace"])


def _svc(db: Session, user: User) -> WorkspaceService:
    return WorkspaceService(db, user.id)


# ---------- 请求体 ----------

class RegisterRootRequest(BaseModel):
    path: str = Field(..., min_length=1, max_length=500)
    label: str | None = Field(None, max_length=100)
    identity_id: str | None = None


class UpdateRootRequest(BaseModel):
    label: str | None = Field(None, max_length=100)
    enabled: bool | None = None
    identity_id: str | None = None


class OpenTerminalRequest(BaseModel):
    path: str = Field(..., min_length=1, max_length=500)


class EnabledRequest(BaseModel):
    enabled: bool


# ---------- 开关与引导 ----------

@router.get("/status", summary="功能状态（开关 + 根概况）")
def status(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    svc = _svc(db, user)
    roots = svc.list_roots()
    return success({
        "enabled": svc.is_enabled(),
        "roots_count": len(roots),
        "scanned_count": sum(1 for r in roots if r["scan_status"] == "ok"),
        "terminal": (SettingsService(db, user.id).get("workspace.terminal") or "cmd"),
    })


@router.put("/enabled", summary="启用/停用整个工作区功能")
def set_enabled(
    data: EnabledRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db, user).set_enabled(data.enabled))


# ---------- 根管理 ----------

@router.get("/roots", summary="根列表")
def list_roots(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return success(_svc(db, user).list_roots())


@router.post("/roots", summary="登记根（引导路径 a：登记现有文件夹）")
def register_root(
    data: RegisterRootRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db, user).register_root(data.path, data.label, data.identity_id))


@router.patch("/roots/{root_id}", summary="更新根")
def update_root(
    root_id: str,
    data: UpdateRootRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db, user).update_root(root_id, **data.model_dump(exclude_unset=True)))


@router.delete("/roots/{root_id}", summary="删除根（清索引，不碰磁盘文件）")
def delete_root(
    root_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db, user).delete_root(root_id))


@router.post("/roots/{root_id}/scan", summary="扫描根（噪声过滤，只存元数据）")
def scan_root(
    root_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db, user).scan_root(root_id))


@router.post("/roots/{root_id}/skeleton", summary="按身份生成目录骨架（引导路径 b）")
def build_skeleton(
    root_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db, user).build_identity_skeleton(root_id))


# ---------- 检索与终端 ----------

@router.get("/files", summary="索引检索")
def list_files(
    root_id: str,
    search: str | None = None,
    ext: str | None = None,
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db, user).list_files(root_id, search, ext, page, page_size))


@router.post("/open-terminal", summary="一键开终端（唯一白名单动作）")
def open_terminal(
    data: OpenTerminalRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return success(_svc(db, user).open_terminal(data.path))
