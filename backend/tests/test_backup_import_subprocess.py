# ============================================================
# BackupService.import_ 安全测试 —— **必须子进程 + 独立数据目录**（Phase10-C）
#
# 为什么不在本进程测：
#   import_() 会 `engine.dispose()` 并**重命名/替换活动数据库文件**
#   （backup_service.py:190-240）。在当前 pytest 进程里调用会毁掉整个
#   测试会话的库与全局引擎（现有 test_backup_production.py 是用「桩 settings」
#   把路径指向 tmp 才敢在进程内跑的，属于特例）。
#
# 本文件的隔离方案（三道保险）：
#   1. `subprocess.run([sys.executable, "-c", script])` —— 子进程独立解释器，
#      dispose 的 engine 只属于子进程；
#   2. 子进程 `VENUSTECH_DATA_DIR=<tmp_path>/data`，`PYTHONPATH=backend`，
#      不继承 pytest 的 VENUSTECH_TEST_DATA_DIR / COV_CORE_* 等变量；
#      子进程里用真实 `run_migrations()` 建全新库 → export → 改库 → import_；
#   3. 子进程最后一行打印 JSON，父进程只做断言（带 120s 超时、stderr 进失败信息）。
#
# 覆盖模式：
#   · success            —— 导入成功：数据回滚到备份时刻、app.db.bak.* 生成、完整性 ok；
#   · version_mismatch   —— 主版本不一致：warning 但仍成功（按实现语义）；
#   · tampered_checksum  —— 篡改 app.db 字节 → 校验和不符 → ValidationException 且库未动；
#   · corrupt_zip        —— 截断 ZIP → BadZipFile→ValidationException 且库未动；
#   · other_user         —— 备份属于他人 → 拒绝且库未动。
#
# 覆盖率说明：父进程 `--cov=app` **不会统计子进程**（隔离的必然代价）。因此
# success / version_mismatch 两个模式在子进程内用 coverage 单独测量 import_ 的
# 执行行，父进程解析后断言「关键行确实被执行」，作为 import_ 覆盖的证据。
# ============================================================
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
CHILD_TIMEOUT = 120  # 秒；迁移 + 导出 + 替换在冷启动下约 2-4s，留足余量

# import_ 的「关键执行行」（backup_service.py 当前行号）：
#   197 verify / 199 读包内 db / 208 checkpoint / 209 commit / 213 dispose /
#   220 改名旧库 / 223 写入恢复库 / 226-228 WAL 扫描 / 231 恢复日志 / 235-239 返回值
#   注：240 是 dict 收尾的 `}`（无语句），coverage 不会记录；205 同理是调用收尾括号。
_IMPORT_CORE_LINES = {197, 199, 208, 209, 213, 220, 223, 226, 228, 231, 235, 236, 237, 238, 239}
_IMPORT_VERSION_WARNING_LINES = {201, 202, 203, 204}


# ================================================================
# 子进程脚本（父进程通过 `python -c` 执行）
# ================================================================
_CHILD_SCRIPT_TEMPLATE = r'''
import io
import json
import os
import sqlite3
import sys
import traceback
import zipfile
from pathlib import Path

MODE = __MODE__


def emit(payload):
    """最后一行必须是机器可读 JSON。"""
    print(json.dumps(payload, ensure_ascii=False, default=str), flush=True)


def rewrite_zip(src_bytes, replacements):
    """重写 zip：替换指定条目的内容（用于篡改备份包）。"""
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(src_bytes)) as zin, \
            zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = replacements.get(item.filename, zin.read(item.filename))
            zout.writestr(item.filename, data)
    return out.getvalue()


def zip_without(src_bytes, drop_names):
    """重写 zip：删除指定条目（用于模拟旧包/缺清单的包）。"""
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(src_bytes)) as zin, \
            zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            if item.filename in drop_names:
                continue
            zout.writestr(item.filename, zin.read(item.filename))
    return out.getvalue()


def main():
    from app.config import get_settings
    from app.migrate import run_migrations

    settings = get_settings()
    expected_dir = Path(os.environ["VENUSTECH_DATA_DIR"])
    assert Path(settings.data_dir).resolve() == expected_dir.resolve(), (
        f"数据目录未隔离: {settings.data_dir} != {expected_dir}")
    db_preexisting = Path(settings.db_path).exists()

    run_migrations()

    from app.database import SessionLocal
    from app.models.user import User
    from app.repositories import SettingRepository, UserRepository
    from app.services.backup_service import MANIFEST_NAME, BackupService

    db = SessionLocal()
    user = UserRepository(db).create(username="subproc-user", nickname="子进程用户")
    db.commit()
    svc = BackupService(db, user.id)
    SettingRepository(db).upsert(user.id, "subproc.before", "before-import")
    db.commit()

    # 备份时刻快照（之后的所有写入，导入后都必须消失）
    export_info = svc.export(tag="subproc")
    backup_path = Path(export_info["path"])
    package_bytes = backup_path.read_bytes()
    with zipfile.ZipFile(io.BytesIO(package_bytes)) as zf:
        package_db_bytes = zf.read("app.db")

    # 备份之后继续改库 → 导入成功应回滚掉这些改动
    SettingRepository(db).upsert(user.id, "subproc.after", "must-disappear")
    db.commit()

    payload = {
        "mode": MODE,
        "data_dir": str(settings.data_dir),
        "db_preexisting": db_preexisting,
        "python": sys.version.split()[0],
        "export_ok": export_info["sha256"] == _sha256(package_db_bytes),
        "backup_zip_exists": backup_path.exists(),
        "package_app_db_size": len(package_db_bytes),
    }

    if MODE in ("success", "version_mismatch", "legacy_package"):
        if MODE == "version_mismatch":
            # 只改 MANIFEST 的 app_version（app.db 与 SHA 不动）→ 触发 warning 分支
            with zipfile.ZipFile(io.BytesIO(package_bytes)) as zf:
                manifest = json.loads(zf.read(MANIFEST_NAME))
            manifest["app_version"] = "9.9.9"
            package_bytes = rewrite_zip(
                package_bytes, {MANIFEST_NAME: json.dumps(manifest).encode("utf-8")})
        elif MODE == "legacy_package":
            # 去掉 MANIFEST.json，只留旧 manifest.json → verify 走兼容分支
            package_bytes = zip_without(package_bytes, [MANIFEST_NAME])

        payload["verify_sha256_checked"] = (
            svc.verify(package_bytes, "package.zip")["sha256_checked"])

        warning_logs = []
        from loguru import logger as loguru_logger
        sink_id = loguru_logger.add(
            lambda m: warning_logs.append(m.record["message"]), level="WARNING")

        cov = None
        if os.environ.get("SUBCOV_DATA_FILE"):
            try:
                from coverage import Coverage
                cov = Coverage(source=["app"],
                               data_file=os.environ["SUBCOV_DATA_FILE"])
                cov.start()
            except Exception:
                cov = None
        try:
            result = svc.import_(package_bytes, "backup.zip")
        finally:
            if cov is not None:
                cov.stop()
                cov.save()
            loguru_logger.remove(sink_id)

        # 子进程内覆盖证据：直接取本次测量的 backup_service 已执行行
        executed_backup_lines = []
        if cov is not None:
            try:
                data = cov.get_data()
                executed_backup_lines = sorted(
                    line
                    for name in data.measured_files()
                    if name.endswith("backup_service.py")
                    for line in (data.lines(name) or [])
                )
            except Exception as exc:  # pragma: no cover - 诊断信息
                executed_backup_lines = [f"ERR:{exc}"]

        # 旧引擎已 dispose：必须新开 Session 才能读到替换后的库
        check = SessionLocal()
        try:
            repo = SettingRepository(check)
            marker_after = repo.get_by_key(user.id, "subproc.after")
            before_row = repo.get_by_key(user.id, "subproc.before")
            from sqlalchemy import func, select
            user_count = int(check.scalar(select(func.count()).select_from(User)) or 0)
        finally:
            check.close()

        conn = sqlite3.connect(str(settings.db_path))
        try:
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        finally:
            conn.close()

        baks = sorted(p.name for p in Path(settings.data_dir).glob("app.db.bak.*"))
        bak_path = Path(result["backup_of_original"])
        payload.update({
            "imported": result,
            "restart_required": result["restart_required"],
            "backup_of_original_exists": bak_path.exists(),
            "backup_of_original_size": bak_path.stat().st_size if bak_path.exists() else 0,
            "backup_of_original_is_sqlite": (
                bak_path.read_bytes()[:16].startswith(b"SQLite format 3")
                if bak_path.exists() else False),
            "baks": baks,
            "current_db_bytes_eq_package": (
                Path(settings.db_path).read_bytes() == package_db_bytes),
            "current_db_size": Path(settings.db_path).stat().st_size,
            "marker_after": marker_after.value if marker_after is not None else None,
            "before_row": before_row.value if before_row is not None else None,
            "user_count": user_count,
            "integrity": integrity,
            "version_warning_logged": any(
                "主版本号不同" in message for message in warning_logs),
            "warning_logs": warning_logs,
            "executed_backup_lines": executed_backup_lines,
        })
        emit(payload)
        return

    # ---------- 失败路径：import_ 必须拒绝，且活动库一个字节都不能动 ----------
    if MODE == "tampered_checksum":
        with zipfile.ZipFile(io.BytesIO(package_bytes)) as zf:
            # 只翻转一个字节：长度不变 → 绕过 "大小不符"，精确命中 "校验和不符"
            original_db = bytearray(zf.read("app.db"))
            original_db[100] ^= 0xFF
        package_bytes = rewrite_zip(package_bytes, {"app.db": bytes(original_db)})
    elif MODE == "corrupt_zip":
        package_bytes = package_bytes[: len(package_bytes) // 2]
    elif MODE == "no_manifest":
        package_bytes = zip_without(package_bytes, [MANIFEST_NAME, "manifest.json"])
    elif MODE == "other_user":
        other = UserRepository(db).create(
            username="subproc-other", nickname="别的用户")
        db.commit()
        svc = BackupService(db, other.id)   # 备份归属第一个用户 → 必须拒绝
    else:
        raise AssertionError(f"未知 MODE: {MODE}")

    # 失败断言用「此刻」的库字节做基准（上面的 other_user 分支也改过库）
    current_db_bytes = Path(settings.db_path).read_bytes()

    error = None
    try:
        svc.import_(package_bytes, "backup.zip")
    except Exception as exc:  # noqa: BLE001 - 子进程把异常类型/信息交给父进程断言
        error = {"type": type(exc).__name__, "message": str(exc),
                 "traceback_tail": traceback.format_exc().splitlines()[-3:]}

    check = SessionLocal()
    try:
        repo = SettingRepository(check)
        marker_after = repo.get_by_key(user.id, "subproc.after")
    finally:
        check.close()

    payload.update({
        "error": error,
        "baks": sorted(p.name for p in Path(settings.data_dir).glob("app.db.bak.*")),
        "db_bytes_unchanged": Path(settings.db_path).read_bytes() == current_db_bytes,
        "marker_after": marker_after.value if marker_after is not None else None,
        "current_db_size": Path(settings.db_path).stat().st_size,
    })
    emit(payload)


def _sha256(data):
    import hashlib
    return hashlib.sha256(data).hexdigest()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        emit({"fatal": traceback.format_exc()})
        raise
'''


# ================================================================
# 父进程：执行子进程 + 解析 JSON + 覆盖率证据
# ================================================================
def _child_env(data_dir: Path, cov_data: Path | None = None) -> dict[str, str]:
    """构造子进程环境：隔离数据目录，剔除会干扰它的 pytest/coverage 变量。"""
    env = {
        key: value for key, value in os.environ.items()
        if not key.startswith("COV_CORE")
        and key not in {
            "VENUSTECH_TEST_DATA_DIR", "PYTEST_DEBUG_TEMPROOT",
            "PYTEST_CURRENT_TEST", "COVERAGE_PROCESS_START", "COVERAGE_FILE",
            "VENUSTECH_DATA_DIR",
        }
    }
    env["VENUSTECH_DATA_DIR"] = str(data_dir)
    env["VENUSTECH_DEV"] = "false"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONPATH"] = str(BACKEND_DIR) + (
        os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )
    if cov_data is not None:
        env["SUBCOV_DATA_FILE"] = str(cov_data)
    return env


def _run_child(mode: str, data_dir: Path, cov_data: Path | None = None) -> dict:
    script = _CHILD_SCRIPT_TEMPLATE.replace("__MODE__", repr(mode))
    try:
        proc = subprocess.run(
            [sys.executable, "-c", script],
            cwd=str(BACKEND_DIR),
            env=_child_env(data_dir, cov_data),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=CHILD_TIMEOUT,
        )
    except subprocess.TimeoutExpired as exc:  # pragma: no cover - 防御性
        raise AssertionError(f"子进程超时（>{CHILD_TIMEOUT}s）: mode={mode}\n{exc}") from exc

    output_lines = [line for line in proc.stdout.splitlines() if line.strip()]
    last = output_lines[-1] if output_lines else ""
    try:
        payload = json.loads(last)
    except ValueError as exc:
        raise AssertionError(
            f"子进程未打印 JSON（mode={mode}, rc={proc.returncode}）\n"
            f"stdout={proc.stdout!r}\nstderr={proc.stderr}"
        ) from exc

    assert proc.returncode == 0, (
        f"子进程失败（mode={mode}, rc={proc.returncode}）:\n"
        f"payload={payload}\nstderr={proc.stderr}"
    )
    assert "fatal" not in payload, f"子进程 fatal（mode={mode}）:\n{payload['fatal']}"
    assert payload["mode"] == mode
    return payload


def _executed_backup_service_lines(cov_data: Path) -> set[int]:
    """（保留工具）读取子进程 coverage 数据里的 backup_service 已执行行。

    当前实现改由子进程自己 emit，父进程无需再解析 coverage JSON；
    保留此函数便于将来调试子进程 coverage 数据（不参与断言）。
    """
    json_path = cov_data.with_suffix(".json")
    proc = subprocess.run(
        [sys.executable, "-m", "coverage", "json",
         "--data-file", str(cov_data), "-o", str(json_path)],
        cwd=str(BACKEND_DIR),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    assert proc.returncode == 0, f"coverage json 失败:\n{proc.stdout}\n{proc.stderr}"
    data = json.loads(json_path.read_text(encoding="utf-8"))
    key = next(k for k in data["files"] if k.endswith("backup_service.py"))
    return set(data["files"][key]["executed_lines"])


@pytest.fixture()
def isolated_data_dir(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=False)
    return data_dir


# ================================================================
# 一、导入成功：数据回滚 + 回滚副本 + 完整性
# ================================================================
class TestImportSuccessSubprocess:
    def test_import_swaps_database_and_restores_snapshot(self, isolated_data_dir):
        result = _run_child(
            "success", isolated_data_dir,
            cov_data=isolated_data_dir.parent / "child-cov-success",
        )

        # 隔离前提：子进程真的在用独立目录、且库是新建的（不是仓库真实库）
        assert Path(result["data_dir"]).resolve() == isolated_data_dir.resolve()
        assert result["db_preexisting"] is False
        assert result["export_ok"] is True
        assert result["backup_zip_exists"] is True
        assert result["verify_sha256_checked"] is True

        # 返回语义
        imported = result["imported"]
        assert imported["success"] is True
        assert result["restart_required"] is True
        assert imported["manifest_version"] == "0.7.0"

        # 数据回滚：备份之后的 marker 必须消失，备份时刻的数据必须回来
        assert result["marker_after"] is None
        assert result["before_row"] == "before-import"
        assert result["user_count"] == 1

        # 库文件已替换成包内 app.db（字节一致），且 SQLite 完整性 ok
        assert result["current_db_bytes_eq_package"] is True
        assert result["current_db_size"] == result["package_app_db_size"]
        assert result["integrity"] == "ok"

        # 原库作为可回滚副本保留（真实 SQLite 文件、非空）
        assert result["backup_of_original_exists"] is True
        assert result["backup_of_original_size"] > 0
        assert result["backup_of_original_is_sqlite"] is True
        baks = [name for name in result["baks"] if name.startswith("app.db.bak.")]
        assert len(baks) == 1
        assert Path(imported["backup_of_original"]).name == baks[0]

        # 子进程内覆盖证据：import_ 的核心行确实执行了
        executed = set(result["executed_backup_lines"])
        assert _IMPORT_CORE_LINES <= executed, (
            f"import_ 关键行未全部执行: {sorted(_IMPORT_CORE_LINES - executed)}；"
            f"实际 executed={sorted(executed)}")

    def test_legacy_package_without_checksum_manifest_imports(self, isolated_data_dir):
        """旧包（只有 manifest.json、无 SHA256 清单）也能恢复 —— 兼容分支真实跑通。"""
        result = _run_child("legacy_package", isolated_data_dir)

        assert result["verify_sha256_checked"] is False   # 走的是旧清单分支
        assert result["imported"]["success"] is True
        assert result["marker_after"] is None             # 数据照常回滚
        assert result["current_db_bytes_eq_package"] is True
        assert result["integrity"] == "ok"
        assert len([n for n in result["baks"] if n.startswith("app.db.bak.")]) == 1

    def test_import_does_not_touch_repo_real_data(self, isolated_data_dir):
        """旁证：子进程跑完后，仓库真实 var/data 未被创建/改动（隔离生效）。"""
        real_data = Path(__file__).resolve().parents[2] / "var" / "data"
        before = {
            p.name: p.stat().st_mtime for p in real_data.glob("app.db*")
        } if real_data.is_dir() else {}

        result = _run_child("success", isolated_data_dir)
        assert result["imported"]["success"] is True

        after = {
            p.name: p.stat().st_mtime for p in real_data.glob("app.db*")
        } if real_data.is_dir() else {}
        assert after == before


# ================================================================
# 二、版本不一致：warning 但按实现语义仍成功
# ================================================================
class TestImportVersionMismatchSubprocess:
    def test_major_version_mismatch_warns_but_succeeds(self, isolated_data_dir):
        result = _run_child(
            "version_mismatch", isolated_data_dir,
            cov_data=isolated_data_dir.parent / "child-cov-mismatch",
        )

        imported = result["imported"]
        assert imported["success"] is True
        assert imported["manifest_version"] == "9.9.9"
        assert result["version_warning_logged"] is True
        assert any("主版本号不同" in message for message in result["warning_logs"])
        # 注：告警文案里版本号用的是 %-占位符（loguru 下不会被填充，见报告「发现的问题」），
        # 所以这里只断言「告警确实出现」，不绑定具体版本号文本。
        assert result["current_db_bytes_eq_package"] is True
        assert result["integrity"] == "ok"
        assert result["marker_after"] is None
        assert len([n for n in result["baks"] if n.startswith("app.db.bak.")]) == 1

        executed = set(result["executed_backup_lines"])
        assert _IMPORT_VERSION_WARNING_LINES <= executed, (
            f"版本 warning 分支未执行: "
            f"{sorted(_IMPORT_VERSION_WARNING_LINES - executed)}；"
            f"实际 executed={sorted(executed)}")


# ================================================================
# 三、恶意/损坏备份：必须拒绝，且活动库一个字节都不动
# ================================================================
# ================================================================
# 四、红线守卫：父进程源码里绝不允许出现 import_ 作为代码标识符
# ================================================================
class TestIsolationGuard:
    def test_parent_process_source_never_calls_import(self):
        """本文件是唯一测 import_ 的地方：父进程只能通过子进程脚本调用它。

        用 tokenize 而非字符串匹配：子进程脚本文本里的 `svc.import_(...)`
        是 STRING token，不会被误判；一旦有人把调用搬到父进程（或改回
        in-process），这里立即变红 —— 防止「测试自己炸掉测试会话」回归。
        """
        import io
        import tokenize

        source = Path(__file__).read_text(encoding="utf-8")
        offenders = [
            (token.start[0], token.string)
            for token in tokenize.generate_tokens(io.StringIO(source).readline)
            if token.type == tokenize.NAME and token.string == "import_"
        ]
        assert offenders == [], (
            f"父进程测试文件出现了 import_ 代码标识符（必须只在子进程脚本文本里）: "
            f"{offenders}")

    def test_child_script_text_contains_the_import_call(self):
        """反向确认：子进程脚本里确实调用了 import_（否则上面的守卫是空转）。"""
        assert "svc.import_(package_bytes" in _CHILD_SCRIPT_TEMPLATE
        assert "engine.dispose" not in _CHILD_SCRIPT_TEMPLATE  # dispose 由实现内部完成


class TestImportRejectsBadPackageSubprocess:
    def test_tampered_checksum_is_rejected_and_db_untouched(self, isolated_data_dir):
        result = _run_child("tampered_checksum", isolated_data_dir)

        error = result["error"]
        assert error is not None
        assert error["type"] == "ValidationException"
        assert "校验和不符" in error["message"]
        assert result["db_bytes_unchanged"] is True
        assert result["baks"] == []
        assert result["marker_after"] == "must-disappear"   # 库仍是导入前状态

    def test_corrupt_zip_is_rejected_and_db_untouched(self, isolated_data_dir):
        result = _run_child("corrupt_zip", isolated_data_dir)

        error = result["error"]
        assert error is not None
        assert error["type"] == "ValidationException"
        assert "不是有效的 ZIP 包" in error["message"]
        assert result["db_bytes_unchanged"] is True
        assert result["baks"] == []
        assert result["marker_after"] == "must-disappear"

    def test_package_without_any_manifest_is_rejected(self, isolated_data_dir):
        result = _run_child("no_manifest", isolated_data_dir)

        error = result["error"]
        assert error is not None
        assert error["type"] == "ValidationException"
        assert "缺少清单文件" in error["message"]
        assert result["db_bytes_unchanged"] is True
        assert result["baks"] == []
        assert result["marker_after"] == "must-disappear"

    def test_backup_owned_by_other_user_is_rejected(self, isolated_data_dir):
        result = _run_child("other_user", isolated_data_dir)

        error = result["error"]
        assert error is not None
        assert error["type"] == "ValidationException"
        assert "备份属于其他用户" in error["message"]
        assert result["db_bytes_unchanged"] is True
        assert result["baks"] == []
        assert result["marker_after"] == "must-disappear"
