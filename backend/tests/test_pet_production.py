# ============================================================
# 桌宠 Service 层测试（配置 / 形象 / 四维数值 / 状态感知引擎）
#
# 本轮修复的缺陷（测试即回归守护）：
#   D1 update_avatar 收裸 dict 且无字段白名单 → mass-assignment
#      （客户端可改 user_id —— 把形象送给别人）
#   D2 update_avatar / delete_avatar / set_active_avatar 只查存在性
#      → IDOR：拿到 avatar_id 即可改 / 删他人形象，或把他人形象设为自己当前形象
# ============================================================
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from app.core.exceptions import NotFoundException
from app.models.life import MoodLog
from app.models.pet import PetAvatar
from app.schemas.pet import (
    CreatePetAvatarRequest,
    UpdatePetAvatarRequest,
    UpdatePetConfigRequest,
    UpdatePetStatsRequest,
)
from app.schemas.task import CreateTaskRequest, UpdateTaskRequest
from app.services.pet_service import PetService
from app.services.task_service import TaskService


def _svc(db) -> PetService:
    return PetService(db)


def _avatar(svc, user_id, name="我的形象"):
    return svc.create_avatar(user_id, CreatePetAvatarRequest(name=name))


def _backdate_stats(db, user_id: str, hours: float) -> None:
    """把 stats_updated_at 回拨若干小时，模拟「很久没打开应用」。"""
    cfg = PetService(db).config_repo.get_by_user(user_id)
    cfg.stats_updated_at = datetime.now(timezone.utc) - timedelta(hours=hours)
    db.commit()


# ============================================================
# 一、配置
# ============================================================
class TestPetConfig:

    def test_get_config_creates_default_on_first_access(self, db_session, test_user):
        cfg = _svc(db_session).get_config(test_user.id)
        assert cfg["user_id"] == test_user.id
        assert cfg["enabled"] is True
        assert cfg["size"] == "medium"
        assert cfg["current_avatar_id"] is None

    def test_get_config_is_idempotent(self, db_session, test_user):
        """单例语义：多次读取不得建出多条配置。"""
        svc = _svc(db_session)
        a = svc.get_config(test_user.id)
        b = svc.get_config(test_user.id)
        assert a["id"] == b["id"]
        from app.models.pet import PetConfig
        rows = db_session.query(PetConfig).filter(PetConfig.user_id == test_user.id).all()
        assert len(rows) == 1

    def test_update_config_writes_and_returns(self, db_session, test_user):
        svc = _svc(db_session)
        out = svc.update_config(test_user.id, UpdatePetConfigRequest(
            size="large", opacity=0.5, position_x=120))
        assert out["size"] == "large"
        assert out["opacity"] == 0.5
        assert out["position_x"] == 120
        assert svc.get_config(test_user.id)["size"] == "large"

    def test_update_config_does_not_null_out_fields(self, db_session, test_user):
        """exclude_none 语义：未提交的字段保持原值。"""
        svc = _svc(db_session)
        svc.update_config(test_user.id, UpdatePetConfigRequest(size="small"))
        out = svc.update_config(test_user.id, UpdatePetConfigRequest(opacity=0.4))
        assert out["size"] == "small"
        assert out["opacity"] == 0.4

    def test_config_is_per_user(self, db_session, test_user, other_user):
        svc = _svc(db_session)
        svc.update_config(test_user.id, UpdatePetConfigRequest(size="large"))
        svc.update_config(other_user.id, UpdatePetConfigRequest(size="small"))
        assert svc.get_config(test_user.id)["size"] == "large"
        assert svc.get_config(other_user.id)["size"] == "small"


# ============================================================
# 二、四维陪伴数值（含惰性衰减）
# ============================================================
class TestPetStats:

    def test_default_stats_are_60_and_not_decayed(self, db_session, test_user):
        s = _svc(db_session).get_stats(test_user.id)
        assert (s["intimacy"], s["satiety"], s["mood"], s["energy"]) == (60, 60, 60, 60)
        assert s["decayed"] is False
        assert s["updated_at"] is None

    def test_update_stats_is_incremental(self, db_session, test_user):
        svc = _svc(db_session)
        svc.get_stats(test_user.id)
        s = svc.update_stats(test_user.id, UpdatePetStatsRequest(intimacy=10, satiety=-20))
        assert s["intimacy"] == 70
        assert s["satiety"] == 40
        assert s["updated_at"] is not None

    def test_update_stats_clamps_at_bounds(self, db_session, test_user):
        """上下限 0-100：互动不能把数值推出边界。"""
        svc = _svc(db_session)
        assert svc.update_stats(test_user.id, UpdatePetStatsRequest(intimacy=100))["intimacy"] == 100
        assert svc.update_stats(test_user.id, UpdatePetStatsRequest(intimacy=-100))["intimacy"] == 0

    def test_decay_after_24h(self, db_session, test_user):
        """惰性衰减：读取时按时间差现算（2.0/1.5/1.0/0.2 点每小时）。"""
        svc = _svc(db_session)
        svc.get_stats(test_user.id)
        _backdate_stats(db_session, test_user.id, 24)
        s = svc.get_stats(test_user.id)
        assert s["decayed"] is True
        assert s["satiety"] == 12      # 60 - 2.0*24
        assert s["energy"] == 24       # 60 - 1.5*24
        assert s["mood"] == 36         # 60 - 1.0*24
        assert s["intimacy"] == 55     # 60 - 0.2*24 = 55.2 → round 55

    def test_decay_capped_at_72h(self, db_session, test_user):
        """封顶 72 小时：出差一周回来不该看到归零的宠物（数值仍受 0 下限保护）。"""
        svc = _svc(db_session)
        svc.get_stats(test_user.id)
        _backdate_stats(db_session, test_user.id, 500)
        s = svc.get_stats(test_user.id)
        assert s["satiety"] == 0 and s["energy"] == 0 and s["mood"] == 0
        assert s["intimacy"] == 46     # 60 - 0.2*72 = 45.6 → round 46

    def test_read_does_not_write_back(self, db_session, test_user):
        """关键语义：衰减是「现算」而不是「落库」。连续两次读取结果必须一致。"""
        svc = _svc(db_session)
        svc.get_stats(test_user.id)
        _backdate_stats(db_session, test_user.id, 24)
        first = svc.get_stats(test_user.id)["satiety"]
        second = svc.get_stats(test_user.id)["satiety"]
        assert first == second == 12

    def test_interaction_does_not_refill_decayed_part(self, db_session, test_user):
        """先衰减、再叠加增量 —— 否则隔几天摸一下，衰减掉的部分会被凭空补回来。"""
        svc = _svc(db_session)
        svc.get_stats(test_user.id)
        _backdate_stats(db_session, test_user.id, 24)     # satiety 60 → 12
        s = svc.update_stats(test_user.id, UpdatePetStatsRequest(satiety=5))
        assert s["satiety"] == 17     # 12 + 5，而不是 60 + 5


# ============================================================
# 三、形象管理
# ============================================================
class TestPetAvatar:

    def test_list_avatars_creates_default_when_empty(self, db_session, test_user):
        avatars = _svc(db_session).list_avatars(test_user.id)
        assert len(avatars) == 1
        assert avatars[0]["name"] == "启明星"
        assert avatars[0]["avatar_type"] == "builtin"
        assert avatars[0]["is_active"] is True

    def test_create_avatar(self, db_session, test_user):
        svc = _svc(db_session)
        av = _avatar(svc, test_user.id, name="自定义")
        assert av["name"] == "自定义"
        assert av["user_id"] == test_user.id
        assert av["avatar_type"] == "builtin"

    def test_update_avatar_writes_whitelisted_fields(self, db_session, test_user):
        svc = _svc(db_session)
        av = _avatar(svc, test_user.id)
        out = svc.update_avatar(test_user.id, av["id"], UpdatePetAvatarRequest(
            name="新名字", description="描述", sort_order=7))
        assert out["name"] == "新名字"
        assert out["description"] == "描述"
        assert out["sort_order"] == 7

    def test_update_avatar_cannot_change_owner(self, db_session, test_user, other_user):
        """回归：原实现收裸 dict 直接 setattr → 客户端可把 user_id 改成别人。

        实证（修复前探针）：他人的 PetAvatar.user_id 真的被改成了调用者 id，
        等于**把形象送给别人 / 抢走别人的形象**。现在该字段不在白名单里。
        """
        svc = _svc(db_session)
        av = _avatar(svc, test_user.id, name="我的")
        req = UpdatePetAvatarRequest(**{"name": "改名", "user_id": other_user.id})
        out = svc.update_avatar(test_user.id, av["id"], req)
        assert out["name"] == "改名"          # 合法字段生效
        assert out["user_id"] == test_user.id  # 归属字段纹丝不动

    def test_update_avatar_cannot_change_id(self, db_session, test_user):
        svc = _svc(db_session)
        av = _avatar(svc, test_user.id)
        req = UpdatePetAvatarRequest(**{"id": "hacked-id", "name": "x"})
        out = svc.update_avatar(test_user.id, av["id"], req)
        assert out["id"] == av["id"]

    def test_delete_avatar(self, db_session, test_user):
        svc = _svc(db_session)
        av = _avatar(svc, test_user.id)
        svc.delete_avatar(test_user.id, av["id"])
        assert db_session.get(PetAvatar, av["id"]) is None

    def test_set_active_avatar_switches_previous_off(self, db_session, test_user):
        """激活语义：同一时刻只能有一个 is_active。"""
        svc = _svc(db_session)
        a = _avatar(svc, test_user.id, name="A")
        b = _avatar(svc, test_user.id, name="B")
        cfg = svc.set_active_avatar(test_user.id, b["id"])
        assert cfg["current_avatar_id"] == b["id"]
        rows = {x["id"]: x["is_active"] for x in svc.list_avatars(test_user.id)}
        assert rows[b["id"]] is True
        assert rows[a["id"]] is False


# ============================================================
# 四、形象归属隔离（IDOR）
# ============================================================
class TestPetAvatarOwnership:
    """回归：三个方法原用 `get_or_404`（只查存在性），任何登录用户拿到 id 即可操作他人形象。

    归属不符统一 404（与 asset / resource 一致：不泄漏存在性）。
    """

    def test_update_foreign_avatar_404_no_side_effect(self, db_session, test_user, other_user):
        victim = _avatar(_svc(db_session), other_user.id, name="他的形象")
        with pytest.raises(NotFoundException):
            _svc(db_session).update_avatar(
                test_user.id, victim["id"], UpdatePetAvatarRequest(name="被夺取"))
        db_session.expire_all()
        assert db_session.get(PetAvatar, victim["id"]).name == "他的形象"

    def test_delete_foreign_avatar_404_no_side_effect(self, db_session, test_user, other_user):
        victim = _avatar(_svc(db_session), other_user.id, name="他的形象")
        with pytest.raises(NotFoundException):
            _svc(db_session).delete_avatar(test_user.id, victim["id"])
        assert db_session.get(PetAvatar, victim["id"]) is not None

    def test_set_active_foreign_avatar_404(self, db_session, test_user, other_user):
        """回归：原实现会把**他人形象 id** 写进自己的 current_avatar_id（跨用户引用）。"""
        victim = _avatar(_svc(db_session), other_user.id, name="他的形象")
        svc = _svc(db_session)
        svc.get_config(test_user.id)  # 先建配置，确保原实现真的会写进去
        with pytest.raises(NotFoundException):
            svc.set_active_avatar(test_user.id, victim["id"])
        assert svc.get_config(test_user.id)["current_avatar_id"] is None

    def test_update_config_foreign_avatar_404(self, db_session, test_user, other_user):
        """配置侧同一入口也必须校验归属（否则可绕过 set_active_avatar）。"""
        victim = _avatar(_svc(db_session), other_user.id, name="他的形象")
        svc = _svc(db_session)
        svc.get_config(test_user.id)
        with pytest.raises(NotFoundException):
            svc.update_config(test_user.id, UpdatePetConfigRequest(current_avatar_id=victim["id"]))
        assert svc.get_config(test_user.id)["current_avatar_id"] is None

    def test_unknown_avatar_404(self, db_session, test_user):
        svc = _svc(db_session)
        with pytest.raises(NotFoundException):
            svc.delete_avatar(test_user.id, "no-such-avatar")

    def test_avatar_lists_are_per_user(self, db_session, test_user, other_user):
        _avatar(_svc(db_session), test_user.id, name="我的")
        _avatar(_svc(db_session), other_user.id, name="他的")
        assert [a["name"] for a in _svc(db_session).list_avatars(test_user.id)] == ["我的"]


# ============================================================
# 五、状态感知引擎
# ============================================================
def _freeze_hour(monkeypatch, hour: int):
    """把 pet_service 内部的 datetime.now() 固定在指定小时（其余日期字段无关紧要）。"""
    import app.services.pet_service as ps

    class _FakeDT(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 10, 11, hour, 30, 0)

    monkeypatch.setattr(ps, "datetime", _FakeDT)


class TestPetState:

    @pytest.mark.parametrize("hour,expected", [
        (7, "morning"), (10, "work"), (13, "noon"), (15, "afternoon"),
        (18, "evening"), (20, "night"), (23, "late_night"), (3, "late_night"),
    ])
    def test_time_state_by_hour(self, db_session, test_user, monkeypatch, hour, expected):
        _freeze_hour(monkeypatch, hour)
        state = _svc(db_session).get_current_state(test_user.id)
        assert state["time_state"] == expected
        assert state["time_label"] and state["action"] and state["action_label"]
        assert state["bubble_text"]

    def test_without_todo_and_mood_defaults(self, db_session, test_user, monkeypatch):
        _freeze_hour(monkeypatch, 10)   # work 时段
        state = _svc(db_session).get_current_state(test_user.id)
        assert state["has_todo_tasks"] is False
        assert state["todo_count"] == 0
        assert state["mood"] == "neutral"
        assert state["recent_mood"] is None
        assert state["action"] == "typing"   # 无待办时不进入「专注中」

    def test_todo_awareness_switches_action_to_focused(self, db_session, test_user, monkeypatch):
        """今日到期未完成的任务 → work/afternoon 时段切到「专注中」。"""
        TaskService(db_session).create(test_user.id, CreateTaskRequest(
            title="今天必须交", due_date=date.today()))
        _freeze_hour(monkeypatch, 10)
        state = _svc(db_session).get_current_state(test_user.id)
        assert state["has_todo_tasks"] is True
        assert state["todo_count"] == 1
        assert state["action"] == "focused"
        assert "1" in state["bubble_text"]

    def test_completed_due_task_not_counted(self, db_session, test_user, monkeypatch):
        """已完成的不算「待完成」—— 与首页 must_do 同口径。"""
        t = TaskService(db_session).create(test_user.id, CreateTaskRequest(
            title="已完成", due_date=date.today()))
        TaskService(db_session).update(test_user.id, t.id, UpdateTaskRequest(status="completed"))
        _freeze_hour(monkeypatch, 10)
        state = _svc(db_session).get_current_state(test_user.id)
        assert state["has_todo_tasks"] is False

    def test_mood_awareness_from_recent_score(self, db_session, test_user, monkeypatch):
        """心情来自最近一条 MoodLog 的 score（原实现读不存在的 log.mood 列，永久失效）。"""
        db_session.add(MoodLog(user_id=test_user.id, score=5, logged_date=date.today()))
        db_session.commit()
        _freeze_hour(monkeypatch, 10)
        state = _svc(db_session).get_current_state(test_user.id)
        assert state["recent_mood"] == "happy"
        assert state["mood"] == "happy"
        assert state["mood_label"] == "开心"

    @pytest.mark.parametrize("score,expected", [(5, "happy"), (4, "happy"), (3, "neutral"),
                                                (2, "anxious"), (1, "sad")])
    def test_mood_score_mapping(self, db_session, test_user, monkeypatch, score, expected):
        db_session.add(MoodLog(user_id=test_user.id, score=score, logged_date=date.today()))
        db_session.commit()
        _freeze_hour(monkeypatch, 10)
        assert _svc(db_session).get_current_state(test_user.id)["recent_mood"] == expected

    def test_mood_is_per_user(self, db_session, test_user, other_user, monkeypatch):
        db_session.add(MoodLog(user_id=other_user.id, score=1, logged_date=date.today()))
        db_session.commit()
        _freeze_hour(monkeypatch, 10)
        assert _svc(db_session).get_current_state(test_user.id)["recent_mood"] is None
