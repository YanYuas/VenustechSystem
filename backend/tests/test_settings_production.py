# ============================================================
# SettingsService 生产级测试（原缺失模块，本轮补齐）
#
# settings 是「用户级键值配置」的单一真相来源：默认值 + 已存值合并读取、
# 白名单校验写入、变更历史 + 单 key 回滚（F6.2）、敏感值脱敏。
#
# 验证原则同其他模块：写操作后**直接查库**核对，不信返回值。
# ============================================================
from __future__ import annotations

import uuid

import pytest

from app.core.exceptions import ValidationException
from app.services.settings_service import DEFAULT_SETTINGS, SettingsService
from tests.factories import count_rows


def _svc(db, user_id: str) -> SettingsService:
    return SettingsService(db, user_id)


class TestReadDefaultsAndStoredValues:
    """读路径：默认值兜底 + 已存值覆盖 + 布尔解析。"""

    def test_all_returns_defaults_for_new_user(self, db_session, test_user):
        """新用户未写任何配置时，all() 必须返回完整默认值字典。

        防什么：新装用户点开设置页若拿到空字典，所有开关会显示为关闭，
        与「默认开启任务提醒」的产品预期不符。
        """
        values = _svc(db_session, test_user.id).all()
        assert values == DEFAULT_SETTINGS
        # 关键默认值显式断言（防止有人顺手改掉默认）
        assert values["notify.task"] == "true"
        assert values["notify.sound"] == "false"
        assert values["workspace.enabled"] == "false"

    def test_get_returns_default_when_unset(self, db_session, test_user):
        """未写入的键，get() 回落到默认值而非 None。"""
        assert _svc(db_session, test_user.id).get("notify.review") == "true"

    def test_get_returns_stored_value_after_set(self, db_session, test_user):
        """写入后 get() 返回已存值。"""
        svc = _svc(db_session, test_user.id)
        svc.set("notify.sound", "true")
        assert svc.get("notify.sound") == "true"

    @pytest.mark.parametrize("raw,expected", [
        ("true", True), ("1", True), ("yes", True), ("on", True), ("TRUE", True),
        ("false", False), ("0", False), ("no", False), ("", False), ("随便", False),
    ])
    def test_get_bool_parses_truthy_values(self, db_session, test_user, raw, expected):
        """get_bool 对 true/1/yes/on（含大小写）判真，其余判假。

        防什么：前端写 '1' 或 'on' 时若只认字面 'true'，开关会「明明开了却判为关」。
        """
        svc = _svc(db_session, test_user.id)
        svc.set("notify.sound", raw)
        assert svc.get_bool("notify.sound") is expected


class TestWriteValidation:
    """写路径：白名单 + 格式 + 长度 + 原子性。"""

    def test_set_many_persists_to_db(self, db_session, test_user):
        """写入后必须落库（查 settings 表核对，而不是看返回值）。"""
        svc = _svc(db_session, test_user.id)
        svc.set_many({"notify.task": "false", "workspace.terminal": "powershell"})

        assert count_rows(db_session, "settings", user_id=test_user.id) == 2
        from sqlalchemy import select
        from app.models.settings import Setting
        rows = {r.key: r.value for r in db_session.scalars(
            select(Setting).where(Setting.user_id == test_user.id)
        ).all()}
        assert rows["notify.task"] == "false"
        assert rows["workspace.terminal"] == "powershell"

    def test_repeated_write_uses_upsert_no_unique_violation(self, db_session, test_user):
        """同一 key 重复写入走 upsert，不得撞唯一约束、不得产生第二行。"""
        svc = _svc(db_session, test_user.id)
        for i in range(5):
            svc.set("notify.task", "false" if i % 2 else "true")
        assert count_rows(db_session, "settings", user_id=test_user.id) == 1

    def test_set_many_rejects_empty_payload(self, db_session, test_user):
        """空字典必须被拒绝（避免前端误调用清空语义）。"""
        with pytest.raises(ValidationException):
            _svc(db_session, test_user.id).set_many({})

    def test_set_many_rejects_more_than_100_items(self, db_session, test_user):
        """单次写入上限 100 项。

        数量校验先于白名单校验，因此用 101 个（格式合法但未登记的）键即可触发。
        """
        payload = {f"zzz_{i}": "x" for i in range(101)}
        with pytest.raises(ValidationException):
            _svc(db_session, test_user.id).set_many(payload)

    @pytest.mark.parametrize("bad_key", [
        "BadKey",      # 大写开头
        "1abc",        # 数字开头
        "a b",         # 含空格
        "a-b",         # 含连字符
        "",            # 空串
        "a" * 101,     # 超长
    ])
    def test_set_many_rejects_bad_key_format(self, db_session, test_user, bad_key):
        """非法 key 格式一律拒绝（正则白名单）。"""
        with pytest.raises(ValidationException):
            _svc(db_session, test_user.id).set_many({bad_key: "x"})

    def test_set_many_rejects_unregistered_key(self, db_session, test_user):
        """格式合法但未登记的键必须拒绝，避免任意键把表写脏。"""
        with pytest.raises(ValidationException):
            _svc(db_session, test_user.id).set_many({"totally_unknown_key": "x"})

    def test_set_many_rejects_overlong_value(self, db_session, test_user):
        """值长度上限 4000。"""
        with pytest.raises(ValidationException):
            _svc(db_session, test_user.id).set_many({"notify.task": "x" * 4001})

    def test_invalid_item_in_batch_writes_nothing(self, db_session, test_user):
        """批量中只要有一项非法，整批不写入（原子性）。

        防什么：若校验与写入交织，「前半批已落库、后半批报错」会留下半成品配置。
        """
        svc = _svc(db_session, test_user.id)
        with pytest.raises(ValidationException):
            svc.set_many({"notify.task": "false", "unregistered_key": "x"})
        assert count_rows(db_session, "settings", user_id=test_user.id) == 0
        assert svc.get("notify.task") == "true"  # 仍是默认值

    def test_settings_are_isolated_per_user(self, db_session, test_user, other_user):
        """一个用户的配置不泄漏给另一个用户。"""
        _svc(db_session, test_user.id).set("notify.task", "false")
        assert _svc(db_session, other_user.id).get("notify.task") == "true"


class TestHistoryAndRollback:
    """变更历史（F6.2）：记录、去抖、脱敏、上限、回滚。"""

    def test_history_recorded_on_change(self, db_session, test_user):
        """值发生变化时写入一条历史（旧值/新值均记录）。"""
        svc = _svc(db_session, test_user.id)
        svc.set("notify.task", "false")
        items = svc.history()
        assert len(items) == 1
        assert items[0]["key"] == "notify.task"
        assert items[0]["old_value"] == "true"   # 默认值
        assert items[0]["new_value"] == "false"

    def test_history_skipped_when_value_unchanged(self, db_session, test_user):
        """值没变的重复写入不产生历史（避免刷屏）。"""
        svc = _svc(db_session, test_user.id)
        svc.set("notify.task", "true")   # 与默认值相同
        svc.set("notify.task", "true")
        assert svc.history() == []

    def test_history_masks_sensitive_value(self, db_session, test_user):
        """含 key/secret/token 等子串的键，其历史值必须脱敏。

        防什么：deepseek_key 之类的密钥若原样进历史表，等于密钥明文落库。
        """
        svc = _svc(db_session, test_user.id)
        svc.set("assistant.deepseek_key", "sk-abcdefghijklmnop")
        items = svc.history()
        assert len(items) == 1
        assert items[0]["new_value"].endswith("***")
        assert "abcdefghijklmnop" not in items[0]["new_value"]
        assert items[0]["new_value"].startswith("sk-")

    def test_history_is_bounded(self, db_session, test_user):
        """连续大量变更后历史条数必须有界（上限 200 量级），不得无限增长。"""
        svc = _svc(db_session, test_user.id)
        for i in range(260):
            svc.set("notify.task", "false" if i % 2 else "true")
        n = count_rows(db_session, "settings_history", user_id=test_user.id)
        assert n <= 205, f"历史未收敛，实际 {n} 条"

    def test_history_respects_limit_argument(self, db_session, test_user):
        """history(limit) 生效，且不超过上限。"""
        svc = _svc(db_session, test_user.id)
        for i in range(5):
            svc.set("notify.task", "false" if i % 2 else "true")
        assert len(svc.history(limit=2)) == 2

    def test_rollback_restores_previous_value(self, db_session, test_user):
        """回滚把 key 恢复到该记录之前的旧值。"""
        svc = _svc(db_session, test_user.id)
        svc.set("notify.task", "false")
        record = svc.history()[0]
        svc.set("notify.task", "true")           # 再改一次
        result = svc.rollback(record["id"])
        assert result["key"] == "notify.task"
        assert svc.get("notify.task") == "true"  # 恢复到旧值

    def test_rollback_unknown_history_raises(self, db_session, test_user):
        """不存在的历史 id 回滚应报错。"""
        with pytest.raises(ValidationException):
            _svc(db_session, test_user.id).rollback(str(uuid.uuid4()))

    def test_rollback_rejects_masked_value(self, db_session, test_user):
        """脱敏过的历史不可回滚（否则会把 *** 写回配置）。

        防什么：密钥轮换后回滚会把掩码串写进配置，密钥直接损坏。
        """
        svc = _svc(db_session, test_user.id)
        svc.set("assistant.deepseek_key", "sk-abcdefghijklmnop")  # 产生脱敏历史
        record = svc.history()[0]
        with pytest.raises(ValidationException):
            svc.rollback(record["id"])

    def test_rollback_cannot_cross_users(self, db_session, test_user, other_user):
        """回滚只能作用于本人的历史记录。"""
        svc_a = _svc(db_session, test_user.id)
        svc_a.set("notify.task", "false")
        record = svc_a.history()[0]
        with pytest.raises(ValidationException):
            _svc(db_session, other_user.id).rollback(record["id"])
