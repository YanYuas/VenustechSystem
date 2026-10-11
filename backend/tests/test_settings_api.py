# ============================================================
# Settings API 集成测试（原缺失模块，本轮补齐）
#
# 覆盖：读取/批量写入/变更历史/回滚 的路由 + 参数校验 + 落库核对。
# ============================================================
from __future__ import annotations

from app.database import SessionLocal


def _settings_rows(user_id: str) -> dict[str, str]:
    """直接查库取该用户的配置行（不信响应体）。"""
    from sqlalchemy import select
    from app.models.settings import Setting

    db = SessionLocal()
    try:
        return {
            r.key: r.value
            for r in db.scalars(select(Setting).where(Setting.user_id == user_id)).all()
        }
    finally:
        db.close()


class TestSettingsApiGroup1ReadWrite:
    """第1组：读取默认值 + 批量写入落库 + 非法键拒绝。"""

    def test_get_settings_returns_defaults(self, client):
        """GET /settings 返回含默认值的完整字典。"""
        r = client.get("/api/v1/settings")
        assert r.status_code == 200
        body = r.json()
        assert body["code"] == 0
        values = body["data"]["values"]
        assert values["notify.task"] == "true"
        assert "workspace.noise_dirs" in values

    def test_put_settings_persists_and_returns_merged(self, client, default_user_id):
        """PUT /settings 落库，且返回值是「默认值 + 已写值」的合并字典。"""
        r = client.put("/api/v1/settings", json={"values": {
            "notify.sound": "true",
            "workspace.terminal": "wt",
        }})
        assert r.status_code == 200
        assert r.json()["code"] == 0
        values = r.json()["data"]["values"]
        assert values["notify.sound"] == "true"
        assert values["workspace.terminal"] == "wt"
        # 未写的键仍回落默认
        assert values["notify.task"] == "true"

        # 查库核对：只有写的两个键落库
        rows = _settings_rows(default_user_id)
        assert rows == {"notify.sound": "true", "workspace.terminal": "wt"}

    def test_put_settings_rejects_unregistered_key(self, client, default_user_id):
        """未登记的键返回 400 + 业务码 1001，且不落库。"""
        r = client.put("/api/v1/settings", json={"values": {"evil_key": "x"}})
        assert r.status_code == 400
        assert r.json()["code"] == 1001
        assert _settings_rows(default_user_id) == {}

    def test_put_settings_rejects_bad_format_key(self, client):
        """非法 key 格式返回 400。"""
        r = client.put("/api/v1/settings", json={"values": {"Bad-Key": "x"}})
        assert r.status_code == 400
        assert r.json()["code"] == 1001

    def test_put_settings_rejects_empty_payload(self, client):
        """空 values 返回 400。"""
        r = client.put("/api/v1/settings", json={"values": {}})
        assert r.status_code == 400
        assert r.json()["code"] == 1001

    def test_put_settings_missing_values_field_is_400(self, client):
        """缺少 values 字段由 Pydantic 拦截，返回 400 + 1001。"""
        r = client.put("/api/v1/settings", json={})
        assert r.status_code == 400
        assert r.json()["code"] == 1001


class TestSettingsApiGroup2HistoryRollback:
    """第2组：变更历史列表 + 单 key 回滚。"""

    def test_history_returns_recorded_changes(self, client):
        """写入一次后，历史接口返回该条变更。"""
        client.put("/api/v1/settings", json={"values": {"notify.task": "false"}})
        r = client.get("/api/v1/settings/history")
        assert r.status_code == 200
        items = r.json()["data"]["items"]
        assert len(items) == 1
        assert items[0]["key"] == "notify.task"
        assert items[0]["old_value"] == "true"
        assert items[0]["new_value"] == "false"

    def test_history_respects_limit_param(self, client):
        """limit 参数生效。"""
        for i in range(4):
            client.put("/api/v1/settings", json={
                "values": {"notify.task": "false" if i % 2 else "true"}
            })
        r = client.get("/api/v1/settings/history", params={"limit": 2})
        assert len(r.json()["data"]["items"]) == 2

    def test_rollback_via_api_restores_value(self, client):
        """回滚接口把 key 恢复到旧值。"""
        client.put("/api/v1/settings", json={"values": {"notify.task": "false"}})
        hist = client.get("/api/v1/settings/history").json()["data"]["items"]
        hid = hist[0]["id"]

        client.put("/api/v1/settings", json={"values": {"notify.task": "true"}})
        r = client.post(f"/api/v1/settings/history/{hid}/rollback")
        assert r.status_code == 200
        assert r.json()["data"]["key"] == "notify.task"

        # 读取确认已恢复
        cur = client.get("/api/v1/settings").json()["data"]["values"]
        assert cur["notify.task"] == "true"

    def test_rollback_unknown_id_returns_400(self, client):
        """未知历史 id 回滚返回 400 + 1001。"""
        r = client.post("/api/v1/settings/history/does-not-exist/rollback")
        assert r.status_code == 400
        assert r.json()["code"] == 1001
