# ============================================================
# 同步适配器契约（mod-platform O10 · F2.5）
#
# 目的：把"本地 JSON 包"这一实现抽象成**冻结的契约**，未来接云（对象存储 /
# 自建服务）时只需新增一个实现，SyncEngine 与前端无需改动。
#
# 设计约束（不可削弱）：
#   1. 适配器只负责**搬运字节**，不做 diff / 合并（那是 SyncEngine 的职责）
#   2. 每个包必须自带 user_id 与清单，适配器不得改写包内容
#   3. 适配器方法必须幂等：同一 key 重复 push 不产生重复对象
#   4. 适配器不得读取业务库（保持无状态、可单测）
# ============================================================
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import json


@dataclass(frozen=True)
class RemoteObject:
    """远端对象描述（契约的一部分，字段不得随意增删）。"""
    key: str            # 唯一键，建议 qimingxing-sync-<stamp>.json
    size: int
    modified_at: str    # ISO8601
    user_id: str | None = None


class SyncAdapter(ABC):
    """同步适配器契约（F2.5 冻结版）。

    任何实现（本地目录 / S3 / WebDAV / 自建 HTTP 服务）都必须满足：
    - push(payload: bytes, key: str) -> RemoteObject
    - pull(key: str) -> bytes
    - list_objects() -> list[RemoteObject]
    - delete(key: str) -> bool
    """
    name: str = "abstract"

    @abstractmethod
    def push(self, payload: bytes, key: str) -> RemoteObject:
        """写入一个同步包（幂等：同 key 覆盖写）。"""

    @abstractmethod
    def pull(self, key: str) -> bytes:
        """读取同步包原始字节。key 不存在时抛 KeyError。"""

    @abstractmethod
    def list_objects(self) -> list[RemoteObject]:
        """列出全部同步包（按 modified_at 倒序）。"""

    @abstractmethod
    def delete(self, key: str) -> bool:
        """删除同步包；返回是否真的删除了对象。"""


class LocalDirAdapter(SyncAdapter):
    """本地目录适配器（P0 已有实现的契约化封装）。"""

    name = "local-dir"

    def __init__(self, directory: Path):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def push(self, payload: bytes, key: str) -> RemoteObject:
        path = self.directory / key
        path.write_bytes(payload)
        return self._describe(path)

    def pull(self, key: str) -> bytes:
        path = self.directory / key
        if not path.is_file():
            raise KeyError(key)
        return path.read_bytes()

    def list_objects(self) -> list[RemoteObject]:
        items = [self._describe(p) for p in self.directory.glob("*.json")]
        return sorted(items, key=lambda o: o.modified_at, reverse=True)

    def delete(self, key: str) -> bool:
        path = self.directory / key
        if path.is_file():
            path.unlink()
            return True
        return False

    def _describe(self, path: Path) -> RemoteObject:
        stat = path.stat()
        user_id = None
        try:
            head = json.loads(path.read_text(encoding="utf-8"))
            user_id = head.get("user_id")
        except Exception:
            pass
        return RemoteObject(
            key=path.name,
            size=stat.st_size,
            modified_at=__import__("datetime").datetime.fromtimestamp(
                stat.st_mtime).isoformat(),
            user_id=user_id,
        )


# ---------- 云适配器注册点（F2.5：契约已冻结，实现待接） ----------
_ADAPTERS: dict[str, type[SyncAdapter]] = {"local-dir": LocalDirAdapter}


def register_adapter(name: str, cls: type[SyncAdapter]) -> None:
    """注册新的适配器实现（云适配器接入时调用）。"""
    if not issubclass(cls, SyncAdapter):
        raise TypeError("适配器必须实现 SyncAdapter 契约")
    _ADAPTERS[name] = cls


def available_adapters() -> list[str]:
    return sorted(_ADAPTERS)


def get_adapter(name: str, **kwargs: Any) -> SyncAdapter:
    cls = _ADAPTERS.get(name)
    if cls is None:
        raise ValueError(f"未注册的适配器: {name}（可用: {available_adapters()}）")
    return cls(**kwargs)
