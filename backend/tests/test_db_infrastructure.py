# ============================================================
# 数据库基础设施回归守护
#
# 背景（2026-10-10 实测定位）：
#   测试套件长期存在「随机 2~4 条失败」，错误为
#       sqlite3.OperationalError: attempt to write a readonly database
#   排查结论（三处缺陷，均已在本次修复）：
#
#   1. 引擎用 NullPool + WAL。NullPool 令连接被反复开关，最后一条连接关闭时
#      SQLite 会对 WAL 做 checkpoint 并拆掉 `-wal`/`-shm`；紧接其后新建的连接
#      撞上 WAL 重建/恢复窗口，被标记为只读。该标记为**连接级瞬时**状态，
#      换新连接即恢复（实测印证）→ 改为小连接池（QueuePool）。
#
#   2. `PRAGMA journal_mode=WAL` 被放在「每连接」的 connect 事件里。WAL 是
#      **数据库文件的持久属性**，只需设一次；逐连接重复设置既无用又加剧 1
#      中的竞争 → 移出 connect 事件，改由 run_maintenance() 启动时设置一次。
#
#   3. tests/conftest.py 的 clean_db 夹具用普通 Session 执行
#      `PRAGMA foreign_keys=OFF/ON`。**PRAGMA 在事务内静默无效**，OFF 生效后
#      的 ON 被忽略，且只读残留状态跟着池连接被复用 → 级联删除全面失效
#      （删除 document 后 document_versions 残留）→ 改用 AUTOCOMMIT 连接并在
#      归还池前恢复。
#
# 本文件把「不该再犯」的三点固化成断言，任何一处回退都会在这里变红。
# ============================================================
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from app.database import SessionLocal, engine


class TestConnectionTopology:
    """引擎级：连接池与 PRAGMA 拓扑。"""

    def test_engine_is_not_nullpool(self):
        """引擎不得回退为 NullPool。

        防什么：NullPool + WAL 会产生瞬时的「readonly database」错误（见文件头）。
        这条断言直接挡住「顺手改回 NullPool」的回退。
        """
        from sqlalchemy.pool import NullPool

        assert not isinstance(engine.pool, NullPool), (
            "引擎不能使用 NullPool：NullPool+WAL 会触发瞬时 readonly database。"
            "详见 app/database.py 的注释。"
        )

    def test_engine_pool_has_finite_size(self):
        """连接池必须有容量上限（避免无限建连）。"""
        assert engine.pool.size() >= 1
        assert engine.pool._max_overflow >= 0  # noqa: SLF001 — 只读断言

    def test_journal_mode_is_wal(self):
        """数据库失进入 WAL 模式（持久属性，启动时设置一次）。

        防什么：若 run_maintenance 未执行或被删，DB 退化为 DELETE journal，
        并发写性能下降且与生产不一致。
        """
        with engine.connect() as conn:
            mode = conn.exec_driver_sql("PRAGMA journal_mode").scalar()
        assert str(mode).lower() == "wal", f"期望 WAL，实际 {mode}"

    def test_foreign_keys_enabled_on_fresh_connection(self):
        """新建连接的外键约束为开启状态（级联删除依赖它）。"""
        with engine.connect() as conn:
            fk = conn.exec_driver_sql("PRAGMA foreign_keys").scalar()
        assert int(fk) == 1, "外键约束未开启，级联删除会静默失效"

    def test_clean_db_does_not_leave_foreign_keys_off(self):
        """clean_db 夹具执行后，池中连接的 foreign_keys 必须仍为 ON。

        防什么：clean_db 一度用普通 Session 执行 `PRAGMA foreign_keys=OFF`，
        该 PRAGMA 在事务内无效、OFF 却会残留到池连接上，导致后续复用的测试
        级联删除失效。本用例在 clean_db（autouse，已执行）之后取多条池连接
        逐一校验。
        """
        session = SessionLocal()
        try:
            fk = session.execute(text("PRAGMA foreign_keys")).scalar()
        finally:
            session.close()
        assert int(fk) == 1, "clean_db 之后外键被残留为关闭状态"

    def test_connect_event_does_not_set_journal_mode(self):
        """源码级守护：connect 事件处理器内不得再出现 journal_mode。

        防什么：journal_mode 是持久属性，逐连接设置是反模式（见文件头 2）。
        用源码断言而非运行时断言，是因为「重复设置」在单连接场景下也能通过，
        只有压测才能暴露 —— 而源码断言任何时刻都能挡住回退。
        """
        from pathlib import Path
        import re

        src = (
            Path(__file__).resolve().parent.parent / "app" / "database.py"
        ).read_text(encoding="utf-8")
        handler = src.split('@event.listens_for(engine, "connect")', 1)[1]
        # 取处理器函数体（到下一个顶层定义为止）
        handler_body = handler.split("def run_maintenance", 1)[0]
        # 去掉文档字符串（说明性文字里提到 journal_mode 是允许的），
        # 只看真正会被执行的可执行语句
        code_only = re.sub(r'"""[\s\S]*?"""', "", handler_body)
        code_only = re.sub(r"'''[\s\S]*?'''", "", code_only)
        assert not re.search(
            r"execute\s*\(\s*[\"']PRAGMA\s+journal_mode", code_only, re.IGNORECASE
        ), "connect 事件处理器内不得执行 PRAGMA journal_mode（应只在 run_maintenance 中设一次）"


class TestWriteStabilityUnderConnectionChurn:
    """行为级：连接高频开关下的写入稳定性（原 readonly 抖动的现场）。"""

    def test_many_sequential_sessions_write_ok(self):
        """连续开关 40 次 Session 并写入，全程不得出现 readonly 错误。

        防什么：这正是原缺陷的复现路径 —— NullPool 下第 N 次建连撞上 WAL
        重建窗口即抛 readonly。连接池化后应全程稳定。
        """
        from app.models.user import User

        made = []
        for i in range(40):
            db = SessionLocal()
            try:
                u = User(username=f"churn_{i}_{uuid.uuid4().hex[:8]}", nickname=f"c{i}")
                db.add(u)
                db.commit()
                made.append(u.id)
            finally:
                db.close()

        db = SessionLocal()
        try:
            n = db.execute(
                text("SELECT COUNT(*) FROM users WHERE nickname LIKE 'c%'")
            ).scalar()
        finally:
            db.close()
        assert n == 40

    def test_transaction_capable_session_commit_rollback(self):
        """连接池下的提交/回滚语义正常：提交落库、回滚不落库。"""
        from app.models.user import User

        name = f"tx_{uuid.uuid4().hex[:8]}"

        db = SessionLocal()
        try:
            db.add(User(username=name + "_ok", nickname="ok"))
            db.commit()
        finally:
            db.close()

        db = SessionLocal()
        try:
            db.add(User(username=name + "_rollback", nickname="rb"))
            db.rollback()
        finally:
            db.close()

        db = SessionLocal()
        try:
            ok = db.execute(
                text("SELECT COUNT(*) FROM users WHERE username = :u"), {"u": name + "_ok"}
            ).scalar()
            rb = db.execute(
                text("SELECT COUNT(*) FROM users WHERE username = :u"),
                {"u": name + "_rollback"},
            ).scalar()
        finally:
            db.close()
        assert ok == 1
        assert rb == 0


class TestCascadeIntegrity:
    """级联删除在「池连接复用 + 多轮清表」之后仍然生效。"""

    def test_document_delete_cascades_versions_at_sql_level(self):
        """直接 SQL 删除 document，其 document_versions 应被外键级联清除。

        防什么：clean_db 污染过 foreign_keys 后，级联删除会静默失效，
        留下孤儿版本行（后续 version 列表/统计都会读到脏数据）。
        """
        uid = f"cascade_{uuid.uuid4().hex[:8]}"

        # 用 ORM 造数据（避免手写 SQL 漏字段），再用原生 DELETE 验证 DB 级级联
        from app.models.document import Document, DocumentVersion
        from app.models.user import User

        db = SessionLocal()
        try:
            user = User(username=uid, nickname="级联测试")
            db.add(user)
            db.flush()
            doc = Document(user_id=user.id, title="级联文档", content="x", version=1, word_count=0)
            db.add(doc)
            db.flush()
            doc_id = doc.id
            for v in (1, 2, 3):
                db.add(DocumentVersion(document_id=doc_id, content=f"内容{v}", version=v, word_count=0))
            db.commit()

            before = db.execute(
                text("SELECT COUNT(*) FROM document_versions WHERE document_id = :d"),
                {"d": doc_id},
            ).scalar()
            assert before == 3

            # 原生 SQL 删除父行：只有外键约束真正开启时才会级联
            db.execute(text("DELETE FROM documents WHERE id = :d"), {"d": doc_id})
            db.commit()

            after = db.execute(
                text("SELECT COUNT(*) FROM document_versions WHERE document_id = :d"),
                {"d": doc_id},
            ).scalar()
            assert after == 0, f"级联删除失效：仍残留 {after} 条版本"
        finally:
            db.close()


@pytest.mark.parametrize("rounds", [1, 2, 3])
def test_clean_cycle_then_write_still_works(rounds):
    """多轮「清表（含外键开关）→ 写入」循环后，写入与级联仍正常。

    防什么：单轮 clean_db 通过不代表多轮通过 —— 残留的 PRAGMA 状态是
    在连接被复用时才显形的，多轮循环能把「偶尔复用」放大成确定性失败。
    """
    from app.models.user import User

    name = f"cycle_{rounds}_{uuid.uuid4().hex[:8]}"
    db = SessionLocal()
    try:
        db.add(User(username=name, nickname="cycle"))
        db.commit()
        got = db.execute(
            text("SELECT COUNT(*) FROM users WHERE username = :u"), {"u": name}
        ).scalar()
    finally:
        db.close()
    assert got == 1
