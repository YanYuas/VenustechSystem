# ============================================================
# 左侧信息面板 API 层测试（聚合 / 快速待办 / 系统提醒）
#
# 路由前缀来自 api/__init__.py：/panel · /quick-todos · /reminders
#
# 重点是把两条 Service 层修复的**对外契约**钉死：
#   显式 null → 400（不是 500）· 非法枚举 → 400（不是静默入库）
# ============================================================
from __future__ import annotations

from datetime import datetime, timedelta

BASE = "/api/v1/panel"
TODOS = "/api/v1/quick-todos"
REMINDERS = "/api/v1/reminders"


def _iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat()


def _soon(hours: int = 2) -> str:
    return _iso(datetime.now() + timedelta(hours=hours))


def _mk_todo(client, title: str = "买牛奶") -> str:
    return client.post(TODOS, json={"title": title}).json()["data"]["id"]


def _mk_reminder(client, **over) -> str:
    body = {"title": "开组会", "remind_at": _soon()}
    body.update(over)
    return client.post(REMINDERS, json=body).json()["data"]["id"]


# ============================================================
# 一、左侧面板聚合
# ============================================================
class TestPanelApi:

    def test_left_panel_shape(self, client):
        r = client.get(BASE)
        assert r.status_code == 200
        d = r.json()["data"]
        assert {"greeting", "date_str", "weekday", "stats", "quick_todos", "reminders"} <= set(d)
        assert set(d["stats"]) == {
            "focus_task", "must_do", "in_progress", "waiting", "completed_today"}

    def test_left_panel_reflects_new_todo(self, client):
        _mk_todo(client, "只此一条")
        d = client.get(BASE).json()["data"]
        assert [t["title"] for t in d["quick_todos"]] == ["只此一条"]

    def test_left_panel_upcoming_window(self, client):
        """未来 7 天窗口端到端：过期与超远都不出现。"""
        _mk_reminder(client, title="过期", remind_at=_iso(datetime.now() - timedelta(hours=1)))
        _mk_reminder(client, title="即将", remind_at=_soon(1))
        _mk_reminder(client, title="太远", remind_at=_soon(24 * 30))
        d = client.get(BASE).json()["data"]
        assert [r["title"] for r in d["reminders"]] == ["即将"]


# ============================================================
# 二、快速待办
# ============================================================
class TestTodoApi:

    def test_create_and_list(self, client):
        _mk_todo(client, "A")
        r = client.get(TODOS)
        assert r.status_code == 200
        assert [t["title"] for t in r.json()["data"]] == ["A"]

    def test_create_assigns_ascending_sort_order(self, client):
        _mk_todo(client, "A")
        _mk_todo(client, "B")
        rows = client.get(TODOS).json()["data"]
        assert [t["sort_order"] for t in rows] == [0, 1]

    def test_create_empty_title_400(self, client):
        """Pydantic min_length=1 → 统一 400/1001 通道（非 FastAPI 默认 422）。"""
        r = client.post(TODOS, json={"title": ""})
        assert r.status_code == 400
        assert r.json()["code"] == 1001

    def test_patch_complete_sets_completed_at(self, client):
        tid = _mk_todo(client)
        d = client.patch(f"{TODOS}/{tid}", json={"completed": True}).json()["data"]
        assert d["completed"] is True
        assert d["completed_at"] is not None

    def test_patch_title_null_400_not_500(self, client):
        """回归：显式 null 曾一路 setattr 到 commit → IntegrityError 未捕获 → 500。"""
        tid = _mk_todo(client)
        r = client.patch(f"{TODOS}/{tid}", json={"title": None})
        assert r.status_code == 400
        assert r.json()["code"] == 1001
        assert "title" in r.json()["message"]
        # 零副作用
        assert client.get(TODOS).json()["data"][0]["title"] == "买牛奶"

    def test_delete_todo(self, client):
        tid = _mk_todo(client)
        assert client.delete(f"{TODOS}/{tid}").status_code == 200
        assert client.get(TODOS).json()["data"] == []

    def test_unknown_todo_404(self, client):
        r = client.patch(f"{TODOS}/no-such-id", json={"title": "x"})
        assert r.status_code == 404
        assert r.json()["code"] == 1002


# ============================================================
# 三、系统提醒
# ============================================================
class TestReminderApi:

    def test_create_defaults(self, client):
        _mk_reminder(client, title="体检")
        rows = client.get(REMINDERS).json()["data"]
        assert len(rows) == 1
        assert rows[0]["title"] == "体检"
        assert rows[0]["type"] == "custom"
        assert rows[0]["repeat"] == "none"
        assert rows[0]["dismissed"] is False

    def test_create_accepts_whitelisted_enums(self, client):
        _mk_reminder(client, title="会", type="meeting", repeat="weekly")
        rows = client.get(REMINDERS).json()["data"]
        assert rows[0]["type"] == "meeting"
        assert rows[0]["repeat"] == "weekly"

    def test_create_rejects_unknown_type_400(self, client):
        """回归：`type` 原无白名单 → 任意字符串入库，图标分支静默失效。"""
        r = client.post(REMINDERS, json={"title": "x", "remind_at": _soon(), "type": "bogus"})
        assert r.status_code == 400
        assert r.json()["code"] == 1001
        assert "type" in r.json()["message"]
        assert client.get(REMINDERS).json()["data"] == []

    def test_create_rejects_unknown_repeat_400(self, client):
        r = client.post(REMINDERS, json={"title": "x", "remind_at": _soon(), "repeat": "yearly"})
        assert r.status_code == 400
        assert r.json()["code"] == 1001

    def test_create_requires_remind_at(self, client):
        r = client.post(REMINDERS, json={"title": "没有时间"})
        assert r.status_code == 400
        assert r.json()["code"] == 1001

    def test_patch_dismissed(self, client):
        rid = _mk_reminder(client)
        d = client.patch(f"{REMINDERS}/{rid}", json={"dismissed": True}).json()["data"]
        assert d["dismissed"] is True

    def test_patch_title_null_400_not_500(self, client):
        rid = _mk_reminder(client)
        r = client.patch(f"{REMINDERS}/{rid}", json={"title": None})
        assert r.status_code == 400
        assert r.json()["code"] == 1001
        assert "title" in r.json()["message"]

    def test_patch_remind_at_null_400(self, client):
        """remind_at 是 NOT NULL 且参与窗口筛选，置空必须被拦。"""
        rid = _mk_reminder(client)
        r = client.patch(f"{REMINDERS}/{rid}", json={"remind_at": None})
        assert r.status_code == 400
        assert r.json()["code"] == 1001

    def test_patch_type_null_400(self, client):
        rid = _mk_reminder(client)
        r = client.patch(f"{REMINDERS}/{rid}", json={"type": None})
        assert r.status_code == 400
        assert r.json()["code"] == 1001

    def test_patch_description_null_allowed(self, client):
        """description 真可空 —— 置空不得被守卫误拦。"""
        rid = _mk_reminder(client, description="原描述")
        r = client.patch(f"{REMINDERS}/{rid}", json={"description": None})
        assert r.status_code == 200
        assert r.json()["data"]["description"] is None

    def test_patch_rejects_unknown_repeat_400(self, client):
        rid = _mk_reminder(client)
        r = client.patch(f"{REMINDERS}/{rid}", json={"repeat": "hourly"})
        assert r.status_code == 400
        assert r.json()["code"] == 1001

    def test_patch_rejects_unknown_type_400(self, client):
        rid = _mk_reminder(client)
        r = client.patch(f"{REMINDERS}/{rid}", json={"type": "meetting"})
        assert r.status_code == 400
        assert r.json()["code"] == 1001
        # 零副作用：仍是原值
        assert client.get(REMINDERS).json()["data"][0]["type"] == "custom"

    def test_delete_reminder(self, client):
        rid = _mk_reminder(client)
        assert client.delete(f"{REMINDERS}/{rid}").status_code == 200
        assert client.get(REMINDERS).json()["data"] == []

    def test_unknown_reminder_404(self, client):
        r = client.patch(f"{REMINDERS}/no-such-id", json={"dismissed": True})
        assert r.status_code == 404
        assert r.json()["code"] == 1002
