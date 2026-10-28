# ============================================================
# 日志查看 API（M09 P2）
# 供前端设置页展示系统日志
# ============================================================
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Query

from app.config import get_settings
from app.core.response import success

logger = logging.getLogger("app.logs")

router = APIRouter(prefix="/logs", tags=["logs"])

settings = get_settings()


def _get_log_dir() -> Path:
    """获取日志目录"""
    return Path(getattr(settings, "data_dir", ".")) / "logs"


@router.get("")
def list_logs():
    """列出所有日志文件"""
    log_dir = _get_log_dir()
    if not log_dir.exists():
        return success({"files": [], "dir": str(log_dir)})

    files = []
    for f in sorted(log_dir.glob("*.log"), reverse=True):
        stat = f.stat()
        files.append({
            "name": f.name,
            "size_kb": round(stat.st_size / 1024, 2),
            "modified": stat.st_mtime,
            "modified_str": __import__("datetime").datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
        })
    return success({"files": files, "dir": str(log_dir)})


@router.get("/{filename}")
def read_log(
    filename: str,
    tail: int = Query(100, ge=1, le=1000, description="读取最后N行"),
    level: str | None = Query(None, description="按级别过滤（DEBUG/INFO/WARNING/ERROR）"),
):
    """读取日志文件内容"""
    log_dir = _get_log_dir()

    # 安全检查（显式，平台无关）：拒绝分隔符 / 上跳 / 空名。
    # 为什么不能只靠 resolve().is_relative_to()：POSIX 上反斜杠不是分隔符，
    # `..\..\evil.log` 会被当成普通文件名 → 检查通过后落到 404，
    # 与 Windows（400 非法文件名）契约不一致（CI 首跑 Linux 时发现）。
    if (
        not filename
        or filename in {".", ".."}
        or "/" in filename
        or "\\" in filename
        or ".." in filename
    ):
        return {"code": 400, "message": "非法文件名", "data": None}

    log_path = log_dir / filename

    # 纵深防御：解析后仍必须落在日志目录内
    if not log_path.resolve().is_relative_to(log_dir.resolve()):
        return {"code": 400, "message": "非法文件名", "data": None}

    if not log_path.exists():
        return {"code": 404, "message": "日志文件不存在", "data": None}

    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except Exception as e:
        return {"code": 500, "message": f"读取失败: {e}", "data": None}

    # 取最后N行
    lines = lines[-tail:]

    # 按级别过滤
    if level:
        level_upper = level.upper()
        lines = [line for line in lines if level_upper in line.upper()]

    return success({
        "filename": filename,
        "total_lines": len(lines),
        "content": "".join(lines),
    })


@router.post("/clear")
def clear_logs():
    """清空所有日志文件"""
    log_dir = _get_log_dir()
    if not log_dir.exists():
        return success({"cleared": 0, "failed": []})

    count = 0
    failed: list[str] = []
    for f in log_dir.glob("*.log"):
        try:
            f.write_text("")
            count += 1
        except Exception:
            # 文件被占用/权限不足时静默 skip 会让用户以为"已清空"，实为部分失败。
            failed.append(f.name)
            logger.opt(exception=True).warning("日志文件清空失败: {}", f.name)
    return success({"cleared": count, "failed": failed})