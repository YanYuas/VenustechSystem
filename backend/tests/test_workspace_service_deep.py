# ============================================================
# workspace_service 深覆盖（Phase7-D · 覆盖率补缺）
#
# 本文件只测 **service 内部行为**（API 契约已由 test_service_boundaries.py
# 的 TestWorkspaceBoundaries 覆盖）。重点补齐 Phase6 term-missing 里的：
#   · 扫描生命周期：start_scan 校验 / _scan_worker 成功与失败 / scan_progress
#     （含「进程重启导致僵尸扫描」的识别）；
#   · _walk：噪声目录剪枝、噪声扩展名过滤、200 条进度节流、_ext_of；
#   · 引导部署 build_identity_skeleton：新建/已存在跳过/非法名清洗与跳过；
#   · open_terminal：三种终端模板 + 启动失败 + 越界/停用根拦截 + 空路径；
#   · 路径校验 _validate_root_path / _ensure_inside_enabled_roots；
#   · 归属校验（他人/不存在的身份、不存在的根）；
#   · list_files 的搜索/扩展名/分页。
#
# 文件系统铁律：全部落在 VENUSTECH_TEST_DATA_DIR 内的临时子目录，用例结束
# 即删（绝不触碰真实 var/data）。扫描线程用「同步假线程」替换，避免测试
# 依赖后台线程时序（生产代码不变，只是让 Thread.start() 立即执行 target）。
# ============================================================
from __future__ import annotations

import shutil
import uuid
from pathlib import Path

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.core.exceptions import NotFoundException, ValidationException
from app.database import SessionLocal
from app.models.workspace import WorkspaceFile, WorkspaceRoot
from app.repositories import IdentityRepository
from app.services import workspace_service as ws_mod
from app.services.settings_service import SettingsService
from app.services.workspace_service import WorkspaceService


# ---------------------------------------------------------------- helpers
def _data_dir() -> Path:
    return Path(get_settings().data_dir)


def _fresh():
    """独立 Session：复核「真的落库了」，而不是只改了内存对象。"""
    return SessionLocal()


@pytest.fixture()
def root_dir():
    """临时工作区根目录（在测试数据目录内，用例后删除）。"""
    directory = _data_dir() / f"ws-deep-{uuid.uuid4().hex[:8]}"
    directory.mkdir(parents=True, exist_ok=False)
    yield directory
    shutil.rmtree(directory, ignore_errors=True)


@pytest.fixture(autouse=True)
def _clear_progress_registry():
    """扫描进度是**进程内全局注册表**，用例间必须清空（clean_db 管不到）。"""
    ws_mod._SCAN_PROGRESS.clear()
    yield
    ws_mod._SCAN_PROGRESS.clear()


@pytest.fixture()
def svc(db_session, test_user):
    return WorkspaceService(db_session, test_user.id)


@pytest.fixture()
def enable_workspace(db_session, test_user):
    SettingsService(db_session, test_user.id).set_many({"workspace.enabled": "true"})


class _ImmediateThread:
    """同步假线程：start() 立即执行 target（让扫描可确定性断言）。"""

    def __init__(self, target=None, args=(), name=None, daemon=None):
        self._target = target
        self._args = args

    def start(self) -> None:
        self._target(*self._args)


class _NoopThread:
    """空转假线程：只验证 start_scan 的「进入 scanning 态」，不真的扫描。"""

    def __init__(self, target=None, args=(), name=None, daemon=None):
        self.started = 1

    def start(self) -> None:
        pass


class _PopenRecorder:
    """替换 subprocess.Popen：记录参数，绝不真正拉起终端窗口。"""

    def __init__(self):
        self.calls: list[tuple[list[str], dict]] = []
        self.fail_with: Exception | None = None

    def __call__(self, args, **kwargs):
        if self.fail_with is not None:
            raise self.fail_with
        self.calls.append((list(args), kwargs))
        return object()


def _make_files(base: Path, *, names: list[str]) -> None:
    for name in names:
        target = base / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("x", encoding="utf-8")


def _root_row(root_id: str) -> WorkspaceRoot | None:
    db = _fresh()
    try:
        return db.get(WorkspaceRoot, root_id)
    finally:
        db.close()


def _root_count() -> int:
    db = _fresh()
    try:
        return len(db.scalars(select(WorkspaceRoot)).all())
    finally:
        db.close()


# ================================================================
# 一、登记 / 更新 / 删除根
# ================================================================
class TestRootCrud:
    def test_register_root_persists_resolved_path_and_defaults(self, svc, root_dir):
        data = svc.register_root(str(root_dir), "深测根", None)
        assert Path(data["path"]) == root_dir.resolve()
        assert data["label"] == "深测根"
        assert data["identity_id"] is None
        assert data["enabled"] is True
        assert data["scan_status"] == "never"      # 未扫描
        assert data["file_count"] == 0
        assert data["total_size"] == 0
        assert data["scan_error"] is None
        assert data["last_scanned_at"] is None
        assert data["created_at"] and data["updated_at"]

        db = _fresh()
        try:
            row = db.get(WorkspaceRoot, data["id"])
            assert row is not None
            assert row.path == str(root_dir.resolve())
            assert row.enabled is True
        finally:
            db.close()

    def test_register_root_with_own_identity_links_it(self, svc, db_session, test_user, root_dir):
        identity = IdentityRepository(db_session).create(
            user_id=test_user.id, name="开发", slug=f"dev-{uuid.uuid4().hex[:6]}",
            color_token="primary",
        )
        data = svc.register_root(str(root_dir), None, identity.id)
        assert data["identity_id"] == identity.id

    def test_register_root_with_foreign_identity_rejected(
        self, svc, db_session, other_user, root_dir
    ):
        foreign = IdentityRepository(db_session).create(
            user_id=other_user.id, name="别人的", slug=f"other-{uuid.uuid4().hex[:6]}",
            color_token="mint",
        )
        with pytest.raises(ValidationException) as ei:
            svc.register_root(str(root_dir), None, foreign.id)
        assert "身份不存在" in str(ei.value)
        assert _root_count() == 0

    def test_register_root_with_unknown_identity_rejected(self, svc, root_dir):
        with pytest.raises(ValidationException) as ei:
            svc.register_root(str(root_dir), None, "ghost-identity")
        assert "身份不存在" in str(ei.value)

    def test_update_root_sets_label_enabled_and_identity(
        self, svc, db_session, test_user, root_dir
    ):
        identity = IdentityRepository(db_session).create(
            user_id=test_user.id, name="写作", slug=f"write-{uuid.uuid4().hex[:6]}",
            color_token="sky",
        )
        root = svc.register_root(str(root_dir), "旧标签", None)
        updated = svc.update_root(
            root["id"], label="新标签", enabled=False, identity_id=identity.id
        )
        assert updated["label"] == "新标签"
        assert updated["enabled"] is False
        assert updated["identity_id"] == identity.id

    def test_update_root_with_unknown_identity_rejected(self, svc, root_dir):
        root = svc.register_root(str(root_dir), None, None)
        with pytest.raises(ValidationException) as ei:
            svc.update_root(root["id"], identity_id="ghost-identity")
        assert "身份不存在" in str(ei.value)

    def test_delete_root_removes_index_rows_and_root(self, svc, root_dir):
        _make_files(root_dir, names=["a.md", "sub/b.py"])
        root = svc.register_root(str(root_dir), None, None)
        svc._scan_worker(svc.user_id, root["id"])

        db = _fresh()
        try:
            indexed = db.scalars(
                select(WorkspaceFile).where(WorkspaceFile.root_id == root["id"])
            ).all()
            assert len(indexed) >= 2
        finally:
            db.close()

        result = svc.delete_root(root["id"])
        assert result == {"deleted": True, "id": root["id"]}

        db = _fresh()
        try:
            assert db.get(WorkspaceRoot, root["id"]) is None
            assert db.scalars(
                select(WorkspaceFile).where(WorkspaceFile.root_id == root["id"])
            ).all() == []
        finally:
            db.close()

    def test_delete_root_clears_scan_progress_registry(self, svc, root_dir):
        """D-34：删除根必须清掉进程内 _SCAN_PROGRESS（否则同 id 复活带陈旧状态）。"""
        root = svc.register_root(str(root_dir), None, None)
        ws_mod._progress_set(root["id"], phase="walking", found=3)
        assert ws_mod._progress_get(root["id"])["phase"] == "walking"

        svc.delete_root(root["id"])

        assert ws_mod._progress_get(root["id"]) == {}
        with pytest.raises(NotFoundException):
            svc.scan_progress(root["id"])

    def test_list_roots_only_returns_own(self, db_session, test_user, other_user, root_dir):
        mine = WorkspaceService(db_session, test_user.id).register_root(
            str(root_dir), "我的", None
        )
        other_dir = _data_dir() / f"ws-other-{uuid.uuid4().hex[:8]}"
        other_dir.mkdir(parents=True, exist_ok=False)
        try:
            WorkspaceService(db_session, other_user.id).register_root(
                str(other_dir), "别人的", None
            )
            assert [r["id"] for r in WorkspaceService(db_session, test_user.id).list_roots()] == [
                mine["id"]
            ]
        finally:
            shutil.rmtree(other_dir, ignore_errors=True)


# ================================================================
# 二、扫描生命周期
# ================================================================
class TestScanLifecycle:
    def test_start_scan_missing_path_marks_error_and_raises(self, svc, root_dir):
        root = svc.register_root(str(root_dir), None, None)
        shutil.rmtree(root_dir)  # 登记后目录被删（外置盘拔掉/用户挪走）

        with pytest.raises(ValidationException) as ei:
            svc.start_scan(root["id"])
        assert "路径不存在" in str(ei.value)

        row = _root_row(root["id"])
        assert row is not None
        assert row.scan_status == "error"
        assert "路径不存在" in (row.scan_error or "")

    def test_start_scan_returns_scanning_then_worker_indexes_files(
        self, svc, root_dir, monkeypatch
    ):
        _make_files(root_dir, names=["a.md", "sub/b.py"])
        (root_dir / "node_modules").mkdir()
        (root_dir / "node_modules" / "junk.js").write_text("x", encoding="utf-8")
        root = svc.register_root(str(root_dir), None, None)

        monkeypatch.setattr(ws_mod.threading, "Thread", _ImmediateThread)
        returned = svc.start_scan(root["id"])
        # 返回的是「已进入扫描态」的快照（响应语义），扫描本身在后台完成
        assert returned["scan_status"] == "scanning"

        row = _root_row(root["id"])
        assert row.scan_status == "ok"
        assert row.scan_error is None
        assert row.last_scanned_at is not None
        # 2 个文件 + 1 个目录；node_modules 被整棵剪枝（目录本身也不入索引）
        assert row.file_count == 3
        assert row.total_size == 2  # 两个文件各 1 字节

        assert ws_mod._progress_get(root["id"])["phase"] == "done"

    def test_start_scan_rejects_disabled_root(self, svc, root_dir):
        root = svc.register_root(str(root_dir), None, None)
        svc.update_root(root["id"], enabled=False)
        with pytest.raises(ValidationException) as ei:
            svc.start_scan(root["id"])
        assert "根已停用" in str(ei.value)

    def test_start_scan_rejects_repeat_while_scanning(self, svc, root_dir, monkeypatch):
        _make_files(root_dir, names=["a.md"])
        root = svc.register_root(str(root_dir), None, None)
        monkeypatch.setattr(ws_mod.threading, "Thread", _NoopThread)

        svc.start_scan(root["id"])
        with pytest.raises(ValidationException) as ei:
            svc.start_scan(root["id"])
        assert "正在扫描中" in str(ei.value)
        assert _root_row(root["id"]).scan_status == "scanning"

    def test_scan_worker_failure_writes_error_status(self, svc, root_dir, monkeypatch):
        root = svc.register_root(str(root_dir), None, None)

        def _boom(self, base, on_progress=None):
            raise RuntimeError("walk exploded")

        monkeypatch.setattr(WorkspaceService, "_walk", _boom)
        svc._scan_worker(svc.user_id, root["id"])  # 不抛：失败必须落到 DB 状态

        row = _root_row(root["id"])
        assert row.scan_status == "error"
        assert "walk exploded" in (row.scan_error or "")
        prog = ws_mod._progress_get(root["id"])
        assert prog["phase"] == "error"
        assert "walk exploded" in prog["error"]

    def test_scan_worker_missing_root_does_not_raise(self, svc):
        svc._scan_worker(svc.user_id, "ghost-root")  # 根已不存在：只记进度，不抛
        assert ws_mod._progress_get("ghost-root")["phase"] == "error"

    def test_scan_progress_done_then_clears_registry(self, svc, root_dir):
        _make_files(root_dir, names=["a.md", "b.md"])
        root = svc.register_root(str(root_dir), None, None)
        svc._scan_worker(svc.user_id, root["id"])

        first = svc.scan_progress(root["id"])
        assert first["status"] == "ok"
        assert first["phase"] == "done"
        assert first["found"] == 2
        assert first["total"] == 2
        assert first["file_count"] == 2
        assert first["interrupted"] is False

        # done 态已被读取一次 → 注册表清理，第二次不再回放 phase
        assert svc.scan_progress(root["id"])["phase"] is None

    def test_scan_progress_interrupted_zombie_marks_error(self, svc, db_session, root_dir):
        root = svc.register_root(str(root_dir), None, None)
        # 模拟：DB 说在扫描，但进程内注册表没有记录（进程重启过）
        row = svc._owned_root(root["id"])
        row.scan_status = "scanning"
        db_session.commit()
        ws_mod._SCAN_PROGRESS.clear()

        prog = svc.scan_progress(root["id"])
        assert prog["interrupted"] is True
        assert prog["status"] == "error"
        assert prog["phase"] == "error"
        assert "扫描被中断" in (prog["error"] or "")

        assert _root_row(root["id"]).scan_status == "error"

    def test_scan_progress_before_scan_uses_root_counts(self, svc, root_dir):
        root = svc.register_root(str(root_dir), None, None)
        prog = svc.scan_progress(root["id"])
        assert prog["status"] == "never"
        assert prog["phase"] is None
        assert prog["found"] == 0 and prog["total"] == 0


# ================================================================
# 三、_walk 边界（噪声剪枝 / 进度节流 / 扩展名）
# ================================================================
class TestWalkBoundaries:
    def test_walk_prunes_custom_noise_dir_and_ext(self, svc, db_session, test_user, root_dir):
        SettingsService(db_session, test_user.id).set_many(
            {"workspace.noise_dirs": "skipme", "workspace.noise_exts": ".tmp"}
        )
        (root_dir / "skipme").mkdir()
        (root_dir / "skipme" / "junk.md").write_text("x", encoding="utf-8")
        (root_dir / "keep.md").write_text("x", encoding="utf-8")
        (root_dir / "drop.tmp").write_text("x", encoding="utf-8")

        entries = svc._walk(root_dir)
        rels = {rel for rel, *_ in entries}
        assert rels == {"keep.md"}

    def test_walk_prunes_default_noise_dirs(self, svc, root_dir):
        (root_dir / "node_modules").mkdir()
        (root_dir / "node_modules" / "left-pad.js").write_text("x", encoding="utf-8")
        (root_dir / "__pycache__").mkdir()
        (root_dir / "__pycache__" / "m.pyc").write_bytes(b"x")
        (root_dir / "real.md").write_text("x", encoding="utf-8")

        rels = {rel for rel, *_ in svc._walk(root_dir)}
        assert rels == {"real.md"}

    def test_walk_emits_progress_every_200_entries(self, svc, root_dir):
        names = [f"f{i:03d}.md" for i in range(210)]
        for name in names:
            (root_dir / name).write_text("x", encoding="utf-8")
        seen: list[int] = []
        entries = svc._walk(root_dir, on_progress=seen.append)

        assert len(entries) == 210
        assert 200 in seen          # 循环内每 200 条回调一次（节流）
        assert seen[-1] == 210      # 收尾必回调一次最终数量

    def test_walk_marks_dirs_and_lowercases_ext(self, svc, root_dir):
        (root_dir / "Sub").mkdir()
        (root_dir / "Sub" / "FILE.TXT").write_text("x", encoding="utf-8")
        entries = svc._walk(root_dir)
        by_rel = {rel: (is_dir, size) for rel, is_dir, size, _ in entries}
        assert by_rel == {"Sub": (True, 0), "Sub/FILE.TXT": (False, 1)}

        assert WorkspaceService._ext_of("Sub/FILE.TXT", False) == ".txt"
        assert WorkspaceService._ext_of("Sub", True) is None
        assert WorkspaceService._ext_of("noext", False) is None


# ================================================================
# 四、身份骨架 / 文件列表 / 开关
# ================================================================
class TestSkeletonAndFiles:
    def test_build_identity_skeleton_creates_skips_and_sanitizes(
        self, svc, db_session, test_user, root_dir
    ):
        repo = IdentityRepository(db_session)
        normal = repo.create(
            user_id=test_user.id, name="工作", slug=f"work-{uuid.uuid4().hex[:6]}",
            color_token="primary",
        )
        unsafe = repo.create(
            user_id=test_user.id, name="a/b:c", slug=f"unsafe-{uuid.uuid4().hex[:6]}",
            color_token="mint",
        )
        blank = repo.create(
            user_id=test_user.id, name="...", slug=f"blank-{uuid.uuid4().hex[:6]}",
            color_token="gold",
        )
        (root_dir / "工作").mkdir()  # 已存在的目录 → skipped
        root = svc.register_root(str(root_dir), None, None)

        result = svc.build_identity_skeleton(root["id"])
        assert set(result["created"]) == {"a-b-c"}
        assert set(result["skipped"]) == {"工作", "..."}
        assert (root_dir / "a-b-c").is_dir()
        assert normal.id and unsafe.id and blank.id  # 三者都真实存在（仅目录行为不同）

    def test_build_identity_skeleton_unknown_root_404(self, svc):
        with pytest.raises(NotFoundException) as ei:
            svc.build_identity_skeleton("ghost-root")
        assert "工作区根不存在" in str(ei.value)

    def test_list_files_search_ext_pagination(self, svc, root_dir):
        _make_files(root_dir, names=["docs/a.md", "docs/b.md", "img/c.png"])
        root = svc.register_root(str(root_dir), None, None)
        svc._scan_worker(svc.user_id, root["id"])

        all_files = svc.list_files(root["id"], page=1, page_size=50)
        assert all_files["total"] == 5  # 3 文件 + docs/img 两个目录
        assert Path(all_files["root"]["path"]) == root_dir.resolve()
        assert {"rel_path", "name", "ext", "is_dir", "size", "mtime"} <= set(
            all_files["items"][0]
        )

        md = svc.list_files(root["id"], ext=".md")
        assert md["total"] == 2
        assert {i["name"] for i in md["items"]} == {"a.md", "b.md"}

        searched = svc.list_files(root["id"], search="c.p")
        assert [i["name"] for i in searched["items"]] == ["c.png"]

        page1 = svc.list_files(root["id"], page=1, page_size=2)
        page2 = svc.list_files(root["id"], page=2, page_size=2)
        assert len(page1["items"]) == 2 and len(page2["items"]) == 2
        assert {i["id"] for i in page1["items"]}.isdisjoint(
            {i["id"] for i in page2["items"]}
        )

    def test_list_files_unknown_root_404(self, svc):
        with pytest.raises(NotFoundException):
            svc.list_files("ghost-root")

    def test_is_enabled_and_set_enabled_roundtrip(self, svc, db_session, test_user):
        assert svc.is_enabled() is False  # 默认关闭（可选功能）
        svc.set_enabled(True)
        assert svc.is_enabled() is True
        svc.set_enabled(False)
        assert svc.is_enabled() is False


# ================================================================
# 五、开放终端（安全关卡 + 模板）
# ================================================================
class TestOpenTerminal:
    def test_open_terminal_cmd_default(self, svc, root_dir, monkeypatch):
        root = svc.register_root(str(root_dir), None, None)
        recorder = _PopenRecorder()
        monkeypatch.setattr(ws_mod.subprocess, "Popen", recorder)

        result = svc.open_terminal(str(root_dir))
        assert result["opened"] is True
        assert result["terminal"] == "cmd"
        assert Path(result["path"]) == root_dir.resolve()
        args, kwargs = recorder.calls[0]
        assert args[0] == "cmd.exe" and args[1] == "/K"
        assert str(root_dir.resolve()) in args[2]
        assert kwargs["creationflags"] >= 0
        assert root["id"]

    def test_open_terminal_powershell_variant(self, svc, db_session, test_user, root_dir, monkeypatch):
        SettingsService(db_session, test_user.id).set_many({"workspace.terminal": "powershell"})
        svc.register_root(str(root_dir), None, None)
        recorder = _PopenRecorder()
        monkeypatch.setattr(ws_mod.subprocess, "Popen", recorder)

        result = svc.open_terminal(str(root_dir))
        assert result["terminal"] == "powershell"
        args, _ = recorder.calls[0]
        assert args[0] == "powershell"
        assert "-NoExit" in args
        assert str(root_dir.resolve()) in " ".join(args)

    def test_open_terminal_wt_variant(self, svc, db_session, test_user, root_dir, monkeypatch):
        SettingsService(db_session, test_user.id).set_many({"workspace.terminal": "wt"})
        svc.register_root(str(root_dir), None, None)
        recorder = _PopenRecorder()
        monkeypatch.setattr(ws_mod.subprocess, "Popen", recorder)

        result = svc.open_terminal(str(root_dir))
        assert result["terminal"] == "wt"
        args, _ = recorder.calls[0]
        assert args[:2] == ["wt.exe", "-d"]

    def test_open_terminal_spawn_failure_raises_validation(self, svc, root_dir, monkeypatch):
        svc.register_root(str(root_dir), None, None)
        recorder = _PopenRecorder()
        recorder.fail_with = FileNotFoundError("wt.exe missing")
        monkeypatch.setattr(ws_mod.subprocess, "Popen", recorder)

        with pytest.raises(ValidationException) as ei:
            svc.open_terminal(str(root_dir))
        assert "无法启动终端" in str(ei.value)

    def test_open_terminal_empty_path_rejected(self, svc):
        with pytest.raises(ValidationException) as ei:
            svc.open_terminal("  ")
        assert "路径不能为空" in str(ei.value)

    def test_open_terminal_subdir_of_enabled_root_allowed(self, svc, root_dir, monkeypatch):
        sub = root_dir / "sub"
        sub.mkdir()
        svc.register_root(str(root_dir), None, None)
        recorder = _PopenRecorder()
        monkeypatch.setattr(ws_mod.subprocess, "Popen", recorder)

        result = svc.open_terminal(str(sub))
        assert Path(result["path"]) == sub.resolve()

    def test_open_terminal_disabled_root_rejected(self, svc, root_dir):
        root = svc.register_root(str(root_dir), None, None)
        svc.update_root(root["id"], enabled=False)
        with pytest.raises(ValidationException) as ei:
            svc.open_terminal(str(root_dir))
        assert "安全白名单拦截" in str(ei.value)

    def test_open_terminal_outside_roots_rejected(self, svc, root_dir):
        outside = _data_dir() / f"outside-{uuid.uuid4().hex[:8]}"
        outside.mkdir(parents=True, exist_ok=False)
        try:
            svc.register_root(str(root_dir), None, None)
            with pytest.raises(ValidationException) as ei:
                svc.open_terminal(str(outside))
            assert "安全白名单拦截" in str(ei.value)
        finally:
            shutil.rmtree(outside, ignore_errors=True)


# ================================================================
# 六、路径校验与归属
# ================================================================
class TestPathValidation:
    def test_validate_root_path_rejects_empty_string(self, svc):
        with pytest.raises(ValidationException) as ei:
            svc._validate_root_path("   ")
        assert "路径不能为空" in str(ei.value)

    def test_validate_root_path_rejects_relative(self, svc):
        with pytest.raises(ValidationException) as ei:
            svc._validate_root_path("relative/dir")
        assert "必须是绝对路径" in str(ei.value)

    def test_validate_root_path_rejects_missing_dir(self, svc):
        missing = _data_dir() / f"missing-{uuid.uuid4().hex[:8]}"
        with pytest.raises(ValidationException) as ei:
            svc._validate_root_path(str(missing))
        assert "目录不存在" in str(ei.value)

    def test_validate_root_path_rejects_filesystem_root(self, svc):
        with pytest.raises(ValidationException) as ei:
            svc._validate_root_path(str(Path.cwd().anchor))
        assert "文件系统根" in str(ei.value)

    def test_validate_root_path_resolves_symlink_free_absolute(self, svc, root_dir):
        resolved = svc._validate_root_path(str(root_dir))
        assert resolved == root_dir.resolve() and resolved.is_dir()

    def test_owned_root_rejects_unknown_and_foreign(
        self, db_session, test_user, other_user, root_dir
    ):
        other_service = WorkspaceService(db_session, other_user.id)
        foreign_root = other_service.register_root(str(root_dir), "别人的", None)

        mine = WorkspaceService(db_session, test_user.id)
        with pytest.raises(NotFoundException):
            mine._owned_root(foreign_root["id"])  # 他人的根 → 404（不泄漏存在性）
        with pytest.raises(NotFoundException):
            mine._owned_root("ghost-root")
