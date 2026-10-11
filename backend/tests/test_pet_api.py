# ============================================================
# 桌宠 API 层测试（配置 / 形象 / 状态感知 / 四维数值）
#
# 单用户模式下无法用两个真实登录态测越权 —— 直接往库里插一条属于
# 「另一个用户」的形象，再请求它的 id，断言 404。
# 这批用例是 D1/D2 修复的**对外契约**：修复前它们会 200 且真的改/删他人数据。
# ============================================================
from __future__ import annotations

import uuid

BASE = "/api/v1/pet"


def _mk_other_user() -> str:
    from app.database import SessionLocal
    from app.models.user import User

    db = SessionLocal()
    try:
        u = User(username=f"other_{uuid.uuid4().hex[:8]}", nickname="他人")
        db.add(u)
        db.commit()
        db.refresh(u)
        return u.id
    finally:
        db.close()


def _insert_foreign_avatar() -> str:
    """插一条属于「另一个用户」的形象，返回 id。"""
    from app.database import SessionLocal
    from app.models.pet import PetAvatar

    other_id = _mk_other_user()
    db = SessionLocal()
    try:
        row = PetAvatar(user_id=other_id, name="他的形象")
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.id
    finally:
        db.close()


def _snapshot(avatar_id: str) -> dict:
    """在独立 Session 内取值快照，避免 DetachedInstanceError。"""
    from app.database import SessionLocal
    from app.models.pet import PetAvatar

    db = SessionLocal()
    try:
        row = db.get(PetAvatar, avatar_id)
        if row is None:
            return {"exists": False}
        return {"exists": True, "user_id": row.user_id, "name": row.name,
                "is_active": row.is_active}
    finally:
        db.close()


def _my_avatar_id(client, name: str = "我的形象") -> str:
    return client.post(f"{BASE}/avatars", json={"name": name}).json()["data"]["id"]


# ============================================================
# 一、配置
# ============================================================
class TestPetConfigApi:

    def test_get_config_creates_default(self, client):
        r = client.get(f"{BASE}/config")
        assert r.status_code == 200
        d = r.json()["data"]
        assert d["enabled"] is True
        assert d["size"] == "medium"
        assert "tts_enabled" in d

    def test_patch_config(self, client):
        r = client.patch(f"{BASE}/config", json={"size": "large", "opacity": 0.5})
        assert r.status_code == 200
        d = r.json()["data"]
        assert d["size"] == "large"
        assert d["opacity"] == 0.5
        # 落库可回读
        assert client.get(f"{BASE}/config").json()["data"]["size"] == "large"


# ============================================================
# 二、形象
# ============================================================
class TestPetAvatarApi:

    def test_list_creates_default_when_empty(self, client):
        r = client.get(f"{BASE}/avatars")
        assert r.status_code == 200
        rows = r.json()["data"]
        assert len(rows) == 1
        assert rows[0]["name"] == "启明星"

    def test_create_avatar(self, client):
        r = client.post(f"{BASE}/avatars", json={"name": "自定义形象"})
        assert r.status_code == 200
        d = r.json()["data"]
        assert d["name"] == "自定义形象"
        assert d["avatar_type"] == "builtin"

    def test_create_rejects_empty_name(self, client):
        r = client.post(f"{BASE}/avatars", json={"name": ""})
        assert r.status_code == 400
        assert r.json()["code"] == 1001

    def test_patch_avatar(self, client):
        aid = _my_avatar_id(client)
        r = client.patch(f"{BASE}/avatars/{aid}", json={"name": "改名", "sort_order": 9})
        assert r.status_code == 200
        d = r.json()["data"]
        assert d["name"] == "改名"
        assert d["sort_order"] == 9

    def test_patch_avatar_cannot_mass_assign_owner(self, client):
        """回归：原实现收裸 dict → 客户端可改 `user_id`，等于把形象送给别人。

        注意 Pydantic 忽略未定义字段（不报 400），所以契约是「200 但字段不变」。
        """
        aid = _my_avatar_id(client)
        r = client.patch(f"{BASE}/avatars/{aid}",
                         json={"name": "改名", "user_id": "someone-else", "id": "hacked"})
        assert r.status_code == 200
        d = r.json()["data"]
        assert d["name"] == "改名"
        assert d["id"] == aid

    def test_delete_avatar(self, client):
        aid = _my_avatar_id(client)
        assert client.delete(f"{BASE}/avatars/{aid}").status_code == 200
        assert _snapshot(aid)["exists"] is False

    def test_activate_avatar(self, client):
        aid = _my_avatar_id(client)
        r = client.post(f"{BASE}/avatars/{aid}/activate")
        assert r.status_code == 200
        assert r.json()["data"]["current_avatar_id"] == aid
        assert _snapshot(aid)["is_active"] is True


# ============================================================
# 三、IDOR 对外契约
# ============================================================
class TestPetIdorBlockedAtApi:
    """回归：原实现只查存在性 → 修复前这些请求全部 200 并真的改到他人数据。"""

    def test_patch_foreign_avatar_404_no_side_effect(self, client):
        fid = _insert_foreign_avatar()
        r = client.patch(f"{BASE}/avatars/{fid}", json={"name": "被夺取"})
        assert r.status_code == 404
        assert r.json()["code"] == 1002
        snap = _snapshot(fid)
        assert snap["name"] == "他的形象"
        assert snap["user_id"] != client.get(f"{BASE}/config").json()["data"]["user_id"]

    def test_delete_foreign_avatar_404_no_side_effect(self, client):
        fid = _insert_foreign_avatar()
        r = client.delete(f"{BASE}/avatars/{fid}")
        assert r.status_code == 404
        assert r.json()["code"] == 1002
        assert _snapshot(fid)["exists"] is True

    def test_activate_foreign_avatar_404(self, client):
        """回归：原实现会把他人形象 id 写进自己的 current_avatar_id（跨用户引用）。"""
        fid = _insert_foreign_avatar()
        r = client.post(f"{BASE}/avatars/{fid}/activate")
        assert r.status_code == 404
        assert r.json()["code"] == 1002
        assert client.get(f"{BASE}/config").json()["data"]["current_avatar_id"] is None

    def test_patch_config_foreign_avatar_404(self, client):
        fid = _insert_foreign_avatar()
        r = client.patch(f"{BASE}/config", json={"current_avatar_id": fid})
        assert r.status_code == 404
        assert client.get(f"{BASE}/config").json()["data"]["current_avatar_id"] is None

    def test_unknown_avatar_404(self, client):
        r = client.delete(f"{BASE}/avatars/no-such-avatar")
        assert r.status_code == 404
        assert r.json()["code"] == 1002


# ============================================================
# 四、四维陪伴数值
# ============================================================
class TestPetStatsApi:

    def test_get_default_stats(self, client):
        r = client.get(f"{BASE}/stats")
        assert r.status_code == 200
        d = r.json()["data"]
        assert (d["intimacy"], d["satiety"], d["mood"], d["energy"]) == (60, 60, 60, 60)
        assert d["decayed"] is False

    def test_put_stats_is_incremental(self, client):
        client.get(f"{BASE}/stats")
        d = client.put(f"{BASE}/stats", json={"intimacy": 10, "satiety": -20}).json()["data"]
        assert d["intimacy"] == 70
        assert d["satiety"] == 40

    def test_put_stats_clamps_at_bounds(self, client):
        d = client.put(f"{BASE}/stats", json={"intimacy": 100}).json()["data"]
        assert d["intimacy"] == 100
        d = client.put(f"{BASE}/stats", json={"intimacy": -100}).json()["data"]
        assert d["intimacy"] == 0

    def test_put_stats_rejects_out_of_range_delta(self, client):
        """schema 限定增量在 -100..100，越界走统一 400 通道。"""
        r = client.put(f"{BASE}/stats", json={"intimacy": 500})
        assert r.status_code == 400
        assert r.json()["code"] == 1001


# ============================================================
# 五、状态感知
# ============================================================
class TestPetStateApi:

    def test_state_shape(self, client):
        r = client.get(f"{BASE}/state")
        assert r.status_code == 200
        d = r.json()["data"]
        assert {"time_state", "time_label", "action", "action_label",
                "mood", "mood_label", "has_todo_tasks", "todo_count"} <= set(d)
        assert d["time_state"] in {
            "morning", "work", "noon", "afternoon", "evening", "night", "late_night"}
        assert d["mood"] in {"happy", "sad", "anxious", "angry", "neutral"}

    def test_state_reflects_new_task(self, client):
        """今日到期未完成 → has_todo_tasks 为真（端到端验证任务感知链路）。"""
        from datetime import date

        r = client.post("/api/v1/tasks", json={
            "title": "今天要交", "due_date": date.today().isoformat()})
        assert r.status_code == 200, r.text
        d = client.get(f"{BASE}/state").json()["data"]
        assert d["has_todo_tasks"] is True
        assert d["todo_count"] == 1
