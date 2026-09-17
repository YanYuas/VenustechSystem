# ============================================================
# 工作区模型（三期 C · 可选功能）
#
# 定位（2026-09-16 用户决策，勿改方向）：
#   工作区是**可选功能** —— 默认关闭、零预设。别人的电脑上文件夹
#   结构与作者不同，不存在"内置 D:\YanYuas"这种东西；目录结构通过
#   引导流程建立（登记现有文件夹，或按用户自己的身份一键生成骨架）。
#   作者的 D:\YanYuas 只是作者自己的实例，不是产品的默认值。
#
# 数据主权铁律：只索引路径，不复制内容。
# ============================================================
from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin


class WorkspaceRoot(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    """已登记的工作区根（用户自己的真实文件夹）。"""

    __tablename__ = "workspace_roots"
    __table_args__ = (
        UniqueConstraint("user_id", "path", name="uq_workspace_roots_user_path"),
    )

    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    path: Mapped[str] = mapped_column(String(500), nullable=False)  # 已 resolve 的绝对路径
    label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    identity_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True, index=True
    )  # 应用层关联（同 identity_id 全局约定，不加外键）
    enabled: Mapped[bool] = mapped_column(default=True)
    # never / ok / error
    scan_status: Mapped[str] = mapped_column(String(10), nullable=False, default="never")
    scan_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_scanned_at: Mapped[datetime | None] = mapped_column(nullable=True)
    file_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class WorkspaceFile(UUIDMixin, TimestampMixin, SoftDeleteMixin, Base):
    """索引条目：只存路径元数据，绝不复制文件内容。"""

    __tablename__ = "workspace_files"

    root_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workspace_roots.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rel_path: Mapped[str] = mapped_column(String(500), nullable=False)  # 相对 root 的路径（POSIX 风格）
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    ext: Mapped[str | None] = mapped_column(String(30), nullable=True)  # 小写含点，如 ".py"
    is_dir: Mapped[bool] = mapped_column(default=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    mtime: Mapped[float] = mapped_column(nullable=False, default=0.0)
    # 扫描时从根继承（根改身份后重扫即刷新）；为将来逐文件改身份留位
    identity_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    indexed_at: Mapped[datetime | None] = mapped_column(nullable=True)
