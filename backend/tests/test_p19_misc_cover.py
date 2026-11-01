# ============================================================
# Phase19-B · 剩余 A 类覆盖（sync DERIVED_SKIP 删除传导防御）
#
# 覆盖 `app/services/sync/engine.py:193`：删除传导循环里对
# `SyncPolicy.DERIVED_SKIP` 表的 `continue`。
#
# 为什么需要「桩 snapshot」才能覆盖：
#   `diff()` 的 local 来自 `self.snapshot()`，而 `snapshot()` 只遍历
#   `synced_tables()`（已经把 DERIVED_SKIP 过滤掉）——所以正常路径下 local 里
#   永远不含派生表，193 行的 continue 是**防御分支**。但 `snapshot` 是可覆写
#   的方法（子类/测试注入），防御语义必须成立：若某个 local 快照里混入了
#   `workspace_files`（派生数据），删除传导绝不能把它当"远端已删"发 delete。
#   本文件同时验证：① 真实 snapshot 已排除派生表；② 注入派生表也不会误删；
#   ③ 普通表在缺远端数据时确实会产生 delete（证明循环/对比逻辑本身有效）。
# ============================================================
from __future__ import annotations

import logging
import types

from app.models.workspace import WorkspaceFile
from app.services.sync.engine import SyncEngine
from tests.factories import make_workspace_root


class TestSyncDerivedSkipDeletePropagation:
    def test_delete_propagation_skips_derived_skip_tables(
        self, db_session, test_user, monkeypatch
    ):
        # ① 真实派生数据：workspace_files 有行，但 snapshot 按策略应排除它
        root = make_workspace_root(db_session, test_user.id, path="D:/tmp/ws-p19")
        db_session.flush()
        db_session.add(WorkspaceFile(
            root_id=root.id, rel_path="a.txt", name="a.txt", size=1, mtime=1.0,
        ))
        db_session.commit()
        engine = SyncEngine(db_session, test_user.id)
        assert "workspace_files" not in engine.snapshot()      # 派生表不进同步快照

        # ② 防御分支：注入含派生表的 local 快照 → 删除传导必须跳过它
        #    远端故意「给了 workspace_files 表但缺少 wf-1」：若没有 193 行的
        #    DERIVED_SKIP 跳过，这里会误发 delete；同时远端 tasks 为空不影响。
        monkeypatch.setattr(
            engine, "snapshot",
            lambda since=None: {"workspace_files": {"wf-1": {"id": "wf-1"}},
                                "tasks": {}},
        )
        assert engine.diff(
            {"workspace_files": {"wf-2": {"id": "wf-2"}}},
            propagate_deletes=True,
        ) == []

        # ③ 对照：普通表本地有 task-1、远端有 task-2 → 先 insert(task-2)，
        #    再 delete(task-1)（证明删除传导循环本身生效，跳过只针对派生表）
        monkeypatch.setattr(
            engine, "snapshot",
            lambda since=None: {"tasks": {"task-1": {"id": "task-1"}}},
        )
        assert engine.diff(
            {"tasks": {"task-2": {"id": "task-2"}}},
            propagate_deletes=True,
        ) == [
            {"table": "tasks", "row": {"id": "task-2"}, "op": "insert"},
            {"table": "tasks", "row": {"id": "task-1"}, "op": "delete"},
        ]


# ================================================================
# database.run_maintenance：WAL 降级分支（A 类「可达降级」，mock 连接稳定构造）
# ================================================================
class _FakeCursor:
    def __init__(self, wal_mode="wal", raise_on_wal=False):
        self._wal_mode = wal_mode
        self._raise_on_wal = raise_on_wal

    def scalar(self):
        return self._wal_mode

    def __call__(self):  # pragma: no cover - 兼容上下文用法
        return self


class _FakeConnection:
    def __init__(self, wal_mode="wal", raise_on_wal=False):
        self._wal_mode = wal_mode
        self._raise_on_wal = raise_on_wal
        self.executed: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def exec_driver_sql(self, sql):
        self.executed.append(sql)
        if "journal_mode" in sql:
            if self._raise_on_wal:
                raise RuntimeError("PRAGMA journal_mode failed")
            return types.SimpleNamespace(scalar=lambda: self._wal_mode)
        return types.SimpleNamespace(scalar=lambda: None)


class TestDatabaseWalFallback:
    def test_run_maintenance_warns_when_wal_not_enabled(self, monkeypatch, caplog):
        from app import database as db_mod

        conn = _FakeConnection(wal_mode="delete")
        monkeypatch.setattr(db_mod, "engine",
                            types.SimpleNamespace(connect=lambda: conn))

        with caplog.at_level(logging.WARNING):
            db_mod.run_maintenance()          # 不得抛

        assert "WAL 模式未能启用" in caplog.text
        assert any("wal_checkpoint(TRUNCATE)" in sql for sql in conn.executed)
        assert any("PRAGMA optimize" in sql for sql in conn.executed)

    def test_run_maintenance_swallows_wal_setting_failure(self, monkeypatch, caplog):
        from app import database as db_mod

        conn = _FakeConnection(raise_on_wal=True)
        monkeypatch.setattr(db_mod, "engine",
                            types.SimpleNamespace(connect=lambda: conn))

        with caplog.at_level(logging.ERROR):
            db_mod.run_maintenance()          # 降级不阻断启动

        assert "设置 WAL 模式失败" in caplog.text
        assert any("wal_checkpoint(TRUNCATE)" in sql for sql in conn.executed)
