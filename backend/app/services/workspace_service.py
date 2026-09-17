# ============================================================
# 工作区服务（三期 C · 可选功能 + 引导部署）
#
# 2026-09-16 用户决策（勿改方向）：
#   1. **可选功能**：settings["workspace.enabled"] 默认 "false"，
#      零预设根。别人的电脑文件夹结构与作者不同，本模块不存在任何
#      内置路径 —— 作者的 D:\YanYuas 只是作者自己的实例。
#   2. **引导部署**：目录结构两条路建立 ——
#      a) 登记用户现有文件夹（register_root）；
#      b) 「按身份生成目录骨架」（build_identity_skeleton）：
#         在登记的根下为每个活跃身份建同名文件夹，让新用户的目录
#         结构像作者一样「一重身份一个文件夹」，但内容是用户自己的
#         身份，不是作者的。
#
# 安全红线（三期规划 §5.3②，一条都不许退）：
#   - 任何路径操作前：resolve() + 必须落在已登记且启用的根内
#   - 拒绝文件系统根（如 D:\）作为工作区根
#   - 终端只允许「打开终端」这一个动作，绝不提供任意命令执行
# ============================================================
from __future__ import annotations

import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundException, ValidationException
from app.models.workspace import WorkspaceFile, WorkspaceRoot
from app.repositories.identity_repo import IdentityRepository
from app.services.settings_service import SettingsService

# 文件系统禁用字符（Windows 为主，兼顾通用）
_UNSAFE_FS_CHARS = re.compile(r'[\\/:*?"<>|]')


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class WorkspaceService:
    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id

    # ---------- 开关（引导流程的第一步） ----------

    def is_enabled(self) -> bool:
        return SettingsService(self.db, self.user_id).get_bool("workspace.enabled")

    def set_enabled(self, enabled: bool) -> dict:
        return SettingsService(self.db, self.user_id).set_many(
            {"workspace.enabled": "true" if enabled else "false"}
        )

    # ---------- 根登记（引导路径 a） ----------

    def list_roots(self) -> list[dict]:
        rows = self.db.scalars(
            select(WorkspaceRoot)
            .where(WorkspaceRoot.user_id == self.user_id)
            .order_by(WorkspaceRoot.created_at)
        ).all()
        return [self._root_out(r) for r in rows]

    def register_root(self, raw_path: str, label: str | None, identity_id: str | None) -> dict:
        path = self._validate_root_path(raw_path)
        if identity_id is not None:
            self._ensure_identity_owned(identity_id)
        exists = self.db.scalar(
            select(WorkspaceRoot).where(
                WorkspaceRoot.user_id == self.user_id, WorkspaceRoot.path == str(path)
            )
        )
        if exists is not None:
            raise ValidationException(f"该路径已登记: {path}")
        row = WorkspaceRoot(
            user_id=self.user_id, path=str(path), label=label,
            identity_id=identity_id, enabled=True,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return self._root_out(row)

    def update_root(self, root_id: str, *, label: str | None = None,
                    enabled: bool | None = None, identity_id: str | None = None) -> dict:
        root = self._owned_root(root_id)
        if label is not None:
            root.label = label
        if enabled is not None:
            root.enabled = enabled
        if identity_id is not None:
            self._ensure_identity_owned(identity_id)
            root.identity_id = identity_id
        self.db.commit()
        self.db.refresh(root)
        return self._root_out(root)

    def delete_root(self, root_id: str) -> dict:
        """删除根并清空其索引（不碰磁盘上的任何文件）。"""
        root = self._owned_root(root_id)
        self.db.execute(delete(WorkspaceFile).where(WorkspaceFile.root_id == root.id))
        self.db.delete(root)
        self.db.commit()
        return {"deleted": True, "id": root_id}

    # ---------- 扫描（噪声过滤 + 只存元数据） ----------

    def scan_root(self, root_id: str) -> dict:
        root = self._owned_root(root_id)
        if not root.enabled:
            raise ValidationException("根已停用，请先启用再扫描")
        base = Path(root.path)
        try:
            entries = self._walk(base)
        except OSError as e:
            root.scan_status = "error"
            root.scan_error = str(e)[:500]
            self.db.commit()
            raise ValidationException(f"扫描失败: {e}")

        # 全量替换（个人规模千级，diff 不值得）；单事务，失败即回滚
        self.db.execute(delete(WorkspaceFile).where(WorkspaceFile.root_id == root.id))
        now = _utcnow()
        total_size = 0
        for rel, is_dir, size, mtime in entries:
            self.db.add(WorkspaceFile(
                root_id=root.id,
                rel_path=rel,
                name=rel.rsplit("/", 1)[-1],
                ext=self._ext_of(rel, is_dir),
                is_dir=is_dir,
                size=size,
                mtime=mtime,
                identity_id=root.identity_id,  # 从根继承（根改身份后重扫即刷新）
                indexed_at=now,
            ))
            total_size += size
        root.file_count = len(entries)
        root.total_size = total_size
        root.scan_status = "ok"
        root.scan_error = None
        root.last_scanned_at = now
        self.db.commit()
        return self._root_out(root)

    def _walk(self, base: Path) -> list[tuple[str, bool, int, float]]:
        """os.scandir 递归 + 噪声剪枝（命中黑名单目录不进入子树）。"""
        noise_dirs = self._noise_set("workspace.noise_dirs")
        noise_exts = self._noise_set("workspace.noise_exts")
        out: list[tuple[str, bool, int, float]] = []

        def rel_str(p: Path) -> str:
            return p.relative_to(base).as_posix()

        def walk(dir_path: Path) -> None:
            with os.scandir(dir_path) as it:
                for entry in it:
                    name = entry.name
                    if name in noise_dirs:
                        continue  # 剪枝：不进入子树
                    full = Path(entry.path)
                    if entry.is_dir(follow_symlinks=False):
                        out.append((rel_str(full), True, 0, entry.stat().st_mtime))
                        walk(full)
                    else:
                        if full.suffix.lower() in noise_exts:
                            continue
                        st = entry.stat()
                        out.append((rel_str(full), False, st.st_size, st.st_mtime))

        walk(base)
        return out

    def _noise_set(self, key: str) -> set[str]:
        raw = SettingsService(self.db, self.user_id).get(key) or ""
        return {s.strip() for s in raw.split(",") if s.strip()}

    @staticmethod
    def _ext_of(rel: str, is_dir: bool) -> str | None:
        if is_dir:
            return None
        name = rel.rsplit("/", 1)[-1]
        return Path(name).suffix.lower() or None

    # ---------- 引导部署：按身份生成目录骨架（引导路径 b） ----------

    def build_identity_skeleton(self, root_id: str) -> dict:
        """在根下为每个活跃身份创建同名文件夹（已存在的跳过）。

        这是「引导他们将文件夹弄成我这样」的正确实现：结构原则相同
        （一重身份一个文件夹），但文件夹名来自**用户自己的身份**，
        而非作者的目录名。
        """
        root = self._owned_root(root_id)
        base = Path(root.path)
        identities = IdentityRepository(self.db).list_user(
            self.user_id, include_archived=False
        )
        created: list[str] = []
        skipped: list[str] = []
        for i in identities:
            safe = _UNSAFE_FS_CHARS.sub("-", i.name).strip().strip(".")
            if not safe:
                skipped.append(i.name)
                continue
            target = base / safe
            if target.exists():
                skipped.append(i.name)
                continue
            target.mkdir(parents=True, exist_ok=False)
            created.append(safe)
        return {"root_id": root.id, "created": created, "skipped": skipped}

    # ---------- 一键开终端（唯一白名单动作） ----------

    def open_terminal(self, raw_path: str) -> dict:
        path = self._ensure_inside_enabled_roots(raw_path)
        terminal = (SettingsService(self.db, self.user_id).get("workspace.terminal") or "cmd").strip()
        creationflags = 0
        if os.name == "nt":
            # 不等待、不捕获输出：后端进程绝不能被终端会话挂住
            creationflags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
        try:
            if terminal == "wt":
                subprocess.Popen(["wt.exe", "-d", str(path)], creationflags=creationflags)
            elif terminal == "powershell":
                subprocess.Popen(
                    ["powershell", "-NoExit", "-Command",
                     f"Set-Location -LiteralPath '{path}'"],
                    creationflags=creationflags,
                )
            else:
                subprocess.Popen(
                    ["cmd.exe", "/K", f'cd /d "{path}"'],
                    creationflags=creationflags,
                )
        except FileNotFoundError as e:
            raise ValidationException(f"无法启动终端（{terminal}）: {e}")
        return {"opened": True, "path": str(path), "terminal": terminal}

    # ---------- 文件检索 ----------

    def list_files(
        self,
        root_id: str,
        search: str | None = None,
        ext: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict:
        root = self._owned_root(root_id)
        q = select(WorkspaceFile).where(WorkspaceFile.root_id == root.id)
        if search:
            q = q.where(WorkspaceFile.name.contains(search))
        if ext:
            q = q.where(WorkspaceFile.ext == ext.lower())
        # 计数下推 SQL（此前 len(.all()) 全量加载行只为计数 —— 大根目录下纯浪费）
        from sqlalchemy import func

        total = int(self.db.scalar(select(func.count()).select_from(WorkspaceFile).where(
            WorkspaceFile.root_id == root.id,
            *([WorkspaceFile.name.contains(search)] if search else []),
            *([WorkspaceFile.ext == ext.lower()] if ext else []),
        )) or 0)
        q = q.order_by(WorkspaceFile.is_dir.desc(), WorkspaceFile.name).offset(
            (page - 1) * page_size
        ).limit(page_size)
        rows = self.db.scalars(q).all()
        return {
            "root": self._root_out(root),
            "items": [self._file_out(f) for f in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    # ---------- 内部：安全校验 ----------

    def _validate_root_path(self, raw: str) -> Path:
        if not raw or not raw.strip():
            raise ValidationException("路径不能为空")
        p = Path(raw.strip()).expanduser()
        if not p.is_absolute():
            raise ValidationException("必须是绝对路径")
        p = p.resolve()
        if p.parent == p:
            raise ValidationException("不能把文件系统根（如 D:\\ 或 C:\\）登记为工作区")
        if not p.exists() or not p.is_dir():
            raise ValidationException("目录不存在")
        # resolve() 已解析符号链接/junction：登记的是真实目标
        return p

    def _ensure_inside_enabled_roots(self, raw: str) -> Path:
        """开终端的唯一关卡：resolve 后必须落在已启用根内（防 .. 与链接穿越）。"""
        if not raw or not raw.strip():
            raise ValidationException("路径不能为空")
        p = Path(raw.strip()).expanduser().resolve()
        roots = self.db.scalars(
            select(WorkspaceRoot).where(
                WorkspaceRoot.user_id == self.user_id, WorkspaceRoot.enabled.is_(True)
            )
        ).all()
        for root in roots:
            base = Path(root.path).resolve()
            if p == base or p.is_relative_to(base):
                return p
        raise ValidationException("路径不在任何已启用的工作区内（安全白名单拦截）")

    def _owned_root(self, root_id: str) -> WorkspaceRoot:
        root = self.db.get(WorkspaceRoot, root_id)
        if root is None or root.user_id != self.user_id or root.deleted_at is not None:
            raise NotFoundException("工作区根不存在")
        return root

    def _ensure_identity_owned(self, identity_id: str) -> None:
        identity = IdentityRepository(self.db).get(identity_id)
        if identity is None or identity.user_id != self.user_id or identity.deleted_at is not None:
            raise ValidationException("身份不存在")

    # ---------- 序列化 ----------

    @staticmethod
    def _root_out(r: WorkspaceRoot) -> dict:
        return {
            "id": r.id, "path": r.path, "label": r.label,
            "identity_id": r.identity_id, "enabled": r.enabled,
            "scan_status": r.scan_status, "scan_error": r.scan_error,
            "last_scanned_at": r.last_scanned_at.isoformat() if r.last_scanned_at else None,
            "file_count": r.file_count, "total_size": r.total_size,
            "created_at": r.created_at.isoformat(), "updated_at": r.updated_at.isoformat(),
        }

    @staticmethod
    def _file_out(f: WorkspaceFile) -> dict:
        return {
            "id": f.id, "root_id": f.root_id, "rel_path": f.rel_path,
            "name": f.name, "ext": f.ext, "is_dir": f.is_dir,
            "size": f.size, "mtime": f.mtime, "identity_id": f.identity_id,
        }
