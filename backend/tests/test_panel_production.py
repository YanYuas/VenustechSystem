# ============================================================
# 左侧信息面板 Service 层测试（快速待办 / 系统提醒 / 聚合）
#
# 本轮修复的缺陷（测试即回归守护）：
#   D1 update_todo / update_reminder 显式传 null → 写进 NOT NULL 列
#      → SQLAlchemy IntegrityError 未捕获 → 500（应为 400）
#   D2 reminder.type / repeat 有注释枚举但无白名单 → 任意字符串入库，
#      前端按类型渲染图标的分支会静默落到默认分支
# ============================================================
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.core.exceptions import NotFoundException, ValidationException
from app.models.panel import QuickTodo, Reminder
from app.schemas.panel import (
    CreateQuickTodoRequest,
    CreateReminderRequest,
    UpdateQuickTodoRequest,
    UpdateReminderRequest,
)
from app.services.panel_service import PanelService


def _svc(db, user) -> PanelService:
    return PanelService(db, user)


def _todo(svc, **over):
    kw = dict(title="买牛奶")
    kw.update(over)
    return svc.create_todo(CreateQuickTodoRequest(**kw))


def _reminder(svc, **over):
    kw = dict(title="开组会", remind_at=datetime.now() + timedelta(hours=2))
    kw.update(over)
    return svc.create_reminder(CreateReminderRequest(**kw))


# ============================================================
# 一、快速待办 CRUD
# ============================================================
class TestQuickTodoCrud:

    def test_create_returns_out_shape(self, db_session, test_user):
        out = _svc(db_session, test_user).create_todo(CreateQuickTodoRequest(title="买牛奶"))
        assert out.title == "买牛奶"
        assert out.completed is False
        assert out.completed_at is None
        assert out.id and out.created_at

    def test_create_assigns_increasing_sort_order(self, db_session, test_user):
        """新待办排在末尾：sort_order 必须是当前最大值 +1，而不是固定 0。"""
        svc = _svc(db_session, test_user)
        a = _todo(svc, title="A")
        b = _todo(svc, title="B")
        c = _todo(svc, title="C")
        assert [a.sort_order, b.sort_order, c.sort_order] == [0, 1, 2]

    def test_create_persists_to_db(self, db_session, test_user):
        svc = _svc(db_session, test_user)
        out = _todo(svc)
        row = db_session.get(QuickTodo, out.id)
        assert row is not None
        assert row.user_id == test_user.id
        assert row.title == "买牛奶"

    def test_list_ordered_by_sort_order(self, db_session, test_user):
        svc = _svc(db_session, test_user)
        for t in ("C", "A", "B"):
            _todo(svc, title=t)
        assert [x.title for x in svc.list_todos()] == ["C", "A", "B"]

    def test_list_is_scoped_to_user(self, db_session, test_user, other_user):
        mine = _svc(db_session, test_user)
        theirs = _svc(db_session, other_user)
        _todo(mine, title="我的")
        _todo(theirs, title="他的")
        assert [t.title for t in mine.list_todos()] == ["我的"]

    def test_update_title(self, db_session, test_user):
        svc = _svc(db_session, test_user)
        t = _todo(svc)
        out = svc.update_todo(t.id, UpdateQuickTodoRequest(title="买酸奶"))
        assert out.title == "买酸奶"
        assert db_session.get(QuickTodo, t.id).title == "买酸奶"

    def test_complete_sets_completed_at(self, db_session, test_user):
        svc = _svc(db_session, test_user)
        t = _todo(svc)
        out = svc.update_todo(t.id, UpdateQuickTodoRequest(completed=True))
        assert out.completed is True
        assert out.completed_at is not None

    def test_uncomplete_clears_completed_at(self, db_session, test_user):
        """回归：completed_at 必须跟随 completed 一起回退，否则统计"今日完成"会虚高。"""
        svc = _svc(db_session, test_user)
        t = _todo(svc)
        svc.update_todo(t.id, UpdateQuickTodoRequest(completed=True))
        out = svc.update_todo(t.id, UpdateQuickTodoRequest(completed=False))
        assert out.completed is False
        assert out.completed_at is None

    def test_update_only_touches_given_fields(self, db_session, test_user):
        """exclude_unset 语义：只改 title 时 completed 必须原样。"""
        svc = _svc(db_session, test_user)
        t = _todo(svc)
        svc.update_todo(t.id, UpdateQuickTodoRequest(completed=True))
        out = svc.update_todo(t.id, UpdateQuickTodoRequest(title="改名"))
        assert out.title == "改名"
        assert out.completed is True

    def test_delete_removes_row(self, db_session, test_user):
        svc = _svc(db_session, test_user)
        t = _todo(svc)
        svc.delete_todo(t.id)
        assert db_session.get(QuickTodo, t.id) is None
        assert svc.list_todos() == []

    def test_get_unknown_todo_404(self, db_session, test_user):
        with pytest.raises(NotFoundException):
            _svc(db_session, test_user).update_todo(
                "no-such-id", UpdateQuickTodoRequest(title="x"))


# ============================================================
# 二、系统提醒 CRUD
# ============================================================
class TestReminderCrud:

    def test_create_defaults(self, db_session, test_user):
        out = _reminder(_svc(db_session, test_user))
        assert out.type == "custom"
        assert out.repeat == "none"
        assert out.dismissed is False
        assert out.description is None

    def test_create_with_all_fields(self, db_session, test_user):
        out = _reminder(_svc(db_session, test_user), title="体检", description="空腹",
                        type="health", repeat="weekly")
        assert (out.title, out.description, out.type, out.repeat) == \
            ("体检", "空腹", "health", "weekly")

    def test_list_ordered_by_remind_at(self, db_session, test_user):
        svc = _svc(db_session, test_user)
        now = datetime.now()
        _reminder(svc, title="晚", remind_at=now + timedelta(days=3))
        _reminder(svc, title="早", remind_at=now + timedelta(hours=1))
        assert [r.title for r in svc.list_reminders()] == ["早", "晚"]

    def test_list_is_scoped_to_user(self, db_session, test_user, other_user):
        _reminder(_svc(db_session, test_user), title="我的")
        _reminder(_svc(db_session, other_user), title="他的")
        assert [r.title for r in _svc(db_session, test_user).list_reminders()] == ["我的"]

    def test_update_dismissed(self, db_session, test_user):
        svc = _svc(db_session, test_user)
        r = _reminder(svc)
        out = svc.update_reminder(r.id, UpdateReminderRequest(dismissed=True))
        assert out.dismissed is True
        assert db_session.get(Reminder, r.id).dismissed is True

    def test_update_remind_at(self, db_session, test_user):
        svc = _svc(db_session, test_user)
        r = _reminder(svc)
        later = datetime.now() + timedelta(days=2)
        out = svc.update_reminder(r.id, UpdateReminderRequest(remind_at=later))
        assert out.remind_at == later

    def test_update_only_touches_given_fields(self, db_session, test_user):
        svc = _svc(db_session, test_user)
        r = _reminder(svc, title="原题", description="原描述")
        out = svc.update_reminder(r.id, UpdateReminderRequest(title="新题"))
        assert out.title == "新题"
        assert out.description == "原描述"

    def test_delete_removes_row(self, db_session, test_user):
        svc = _svc(db_session, test_user)
        r = _reminder(svc)
        svc.delete_reminder(r.id)
        assert db_session.get(Reminder, r.id) is None

    def test_get_unknown_reminder_404(self, db_session, test_user):
        with pytest.raises(NotFoundException):
            _svc(db_session, test_user).delete_reminder("no-such-id")


# ============================================================
# 三、NOT NULL 防线（D1）
# ============================================================
class TestNotNullGuard:
    """回归：显式传 null 到非空列，原实现会一路 setattr 到 commit，
    抛 SQLAlchemy IntegrityError（无 handler 识别）→ 500。

    契约应当是「客户端传了非法值 → 400」，而不是把数据库约束异常抛成服务端错误。
    """

    def test_update_todo_title_null_rejected(self, db_session, test_user):
        svc = _svc(db_session, test_user)
        t = _todo(svc)
        with pytest.raises(ValidationException) as ei:
            svc.update_todo(t.id, UpdateQuickTodoRequest(title=None))
        assert "title" in str(ei.value)
        # 零副作用：原标题仍在
        db_session.expire_all()
        assert db_session.get(QuickTodo, t.id).title == "买牛奶"

    def test_update_reminder_title_null_rejected(self, db_session, test_user):
        svc = _svc(db_session, test_user)
        r = _reminder(svc, title="原题")
        with pytest.raises(ValidationException) as ei:
            svc.update_reminder(r.id, UpdateReminderRequest(title=None))
        assert "title" in str(ei.value)
        db_session.expire_all()
        assert db_session.get(Reminder, r.id).title == "原题"

    def test_update_reminder_remind_at_null_rejected(self, db_session, test_user):
        """remind_at 是 NOT NULL 且参与排序/窗口筛选，置空必须先拦下。"""
        svc = _svc(db_session, test_user)
        r = _reminder(svc)
        with pytest.raises(ValidationException):
            svc.update_reminder(r.id, UpdateReminderRequest(remind_at=None))
        db_session.expire_all()
        assert db_session.get(Reminder, r.id).remind_at is not None

    def test_update_reminder_type_null_rejected(self, db_session, test_user):
        svc = _svc(db_session, test_user)
        r = _reminder(svc)
        with pytest.raises(ValidationException):
            svc.update_reminder(r.id, UpdateReminderRequest(type=None))
        db_session.expire_all()
        assert db_session.get(Reminder, r.id).type == "custom"

    def test_update_reminder_description_null_allowed(self, db_session, test_user):
        """description 是真正的可空列 —— 置空是合法操作，不能被守卫误拦。"""
        svc = _svc(db_session, test_user)
        r = _reminder(svc, description="原描述")
        out = svc.update_reminder(r.id, UpdateReminderRequest(description=None))
        assert out.description is None


# ============================================================
# 四、提醒枚举白名单（D2）
# ============================================================
class TestReminderEnums:

    def test_create_accepts_whitelisted_types(self, db_session, test_user):
        svc = _svc(db_session, test_user)
        for t in ("meeting", "study", "health", "custom"):
            assert _reminder(svc, type=t).type == t

    def test_create_rejects_unknown_type(self, db_session, test_user):
        """回归：原实现 `type: str = "custom"` 无约束，任意字符串都能入库。

        缺陷是什么：模型注释声明 `meeting/study/health/custom`，前端按类型渲染
        图标；写入 `meetting`（拼错）不报错，但图标永远落到默认分支 —— 静默失败。
        """
        svc = _svc(db_session, test_user)
        for bad in ("meetting", "MEETING", "会议"):
            with pytest.raises(ValidationException) as ei:
                _reminder(svc, type=bad)
            assert "type" in str(ei.value) or "类型" in str(ei.value)
        assert svc.list_reminders() == []

    def test_create_accepts_whitelisted_repeats(self, db_session, test_user):
        svc = _svc(db_session, test_user)
        for rep in ("none", "daily", "weekly"):
            assert _reminder(svc, repeat=rep).repeat == rep

    def test_create_rejects_unknown_repeat(self, db_session, test_user):
        svc = _svc(db_session, test_user)
        for bad in ("yearly", "NONE", "每天"):
            with pytest.raises(ValidationException):
                _reminder(svc, repeat=bad)
        assert svc.list_reminders() == []

    def test_update_rejects_unknown_type(self, db_session, test_user):
        svc = _svc(db_session, test_user)
        r = _reminder(svc)
        with pytest.raises(ValidationException):
            svc.update_reminder(r.id, UpdateReminderRequest(type="bogus"))
        db_session.expire_all()
        assert db_session.get(Reminder, r.id).type == "custom"

    def test_update_rejects_unknown_repeat(self, db_session, test_user):
        svc = _svc(db_session, test_user)
        r = _reminder(svc)
        with pytest.raises(ValidationException):
            svc.update_reminder(r.id, UpdateReminderRequest(repeat="hourly"))


# ============================================================
# 五、左侧面板聚合
# ============================================================
class TestLeftPanel:

    def test_shape_and_base_fields(self, db_session, test_user):
        data = _svc(db_session, test_user).get_left_panel()
        assert data.greeting and isinstance(data.greeting, str)
        assert data.date_str and isinstance(data.date_str, str)
        assert data.weekday and isinstance(data.weekday, str)
        assert data.quick_todos == [] and data.reminders == []

    def test_only_active_todos_shown(self, db_session, test_user):
        """面板只展示未完成待办；已完成的不能占位。"""
        svc = _svc(db_session, test_user)
        done = _todo(svc, title="已完成")
        _todo(svc, title="未完成")
        svc.update_todo(done.id, UpdateQuickTodoRequest(completed=True))
        assert [t.title for t in svc.get_left_panel().quick_todos] == ["未完成"]

    def test_upcoming_window_excludes_past_and_far(self, db_session, test_user):
        """未来 7 天窗口：过期与超 7 天都不进"即将到来"。"""
        svc = _svc(db_session, test_user)
        now = datetime.now()
        _reminder(svc, title="过期", remind_at=now - timedelta(hours=1))
        _reminder(svc, title="即将", remind_at=now + timedelta(hours=1))
        _reminder(svc, title="太远", remind_at=now + timedelta(days=30))
        assert [r.title for r in svc.get_left_panel().reminders] == ["即将"]

    def test_dismissed_reminder_excluded(self, db_session, test_user):
        svc = _svc(db_session, test_user)
        r = _reminder(svc, title="已忽略", remind_at=datetime.now() + timedelta(hours=1))
        svc.update_reminder(r.id, UpdateReminderRequest(dismissed=True))
        assert svc.get_left_panel().reminders == []

    def test_stats_count_open_tasks(self, db_session, test_user):
        """stats 的五项计数来自 task 表，不是 quick_todos —— 需交叉验证。"""
        from app.schemas.task import CreateTaskRequest
        from app.services.task_service import TaskService

        task_svc = TaskService(db_session)
        task_svc.create(test_user.id, CreateTaskRequest(title="进行中", status="in_progress"))
        task_svc.create(test_user.id, CreateTaskRequest(title="等待中", status="waiting"))
        stats = _svc(db_session, test_user).get_left_panel().stats
        assert stats.in_progress == 1
        assert stats.waiting == 1
        assert stats.focus_task == 0
        assert stats.completed_today == 0


# ============================================================
# 六、归属隔离
# ============================================================
class TestOwnershipIsolation:
    """快速待办与提醒都必须按 user_id 隔离，且越权一律 404（不泄漏存在性）。"""

    def test_update_foreign_todo_404_no_side_effect(self, db_session, test_user, other_user):
        victim = _todo(_svc(db_session, other_user), title="他的待办")
        with pytest.raises(NotFoundException):
            _svc(db_session, test_user).update_todo(
                victim.id, UpdateQuickTodoRequest(title="被篡改"))
        db_session.expire_all()
        assert db_session.get(QuickTodo, victim.id).title == "他的待办"

    def test_delete_foreign_todo_404_no_side_effect(self, db_session, test_user, other_user):
        victim = _todo(_svc(db_session, other_user), title="他的待办")
        with pytest.raises(NotFoundException):
            _svc(db_session, test_user).delete_todo(victim.id)
        assert db_session.get(QuickTodo, victim.id) is not None

    def test_update_foreign_reminder_404_no_side_effect(self, db_session, test_user, other_user):
        victim = _reminder(_svc(db_session, other_user), title="他的提醒")
        with pytest.raises(NotFoundException):
            _svc(db_session, test_user).update_reminder(
                victim.id, UpdateReminderRequest(title="被篡改"))
        db_session.expire_all()
        assert db_session.get(Reminder, victim.id).title == "他的提醒"

    def test_delete_foreign_reminder_404_no_side_effect(self, db_session, test_user, other_user):
        victim = _reminder(_svc(db_session, other_user), title="他的提醒")
        with pytest.raises(NotFoundException):
            _svc(db_session, test_user).delete_reminder(victim.id)
        assert db_session.get(Reminder, victim.id) is not None

    def test_foreign_records_never_in_panel(self, db_session, test_user, other_user):
        _todo(_svc(db_session, other_user), title="他的待办")
        _reminder(_svc(db_session, other_user), title="他的提醒",
                  remind_at=datetime.now() + timedelta(hours=1))
        panel = _svc(db_session, test_user).get_left_panel()
        assert panel.quick_todos == []
        assert panel.reminders == []
