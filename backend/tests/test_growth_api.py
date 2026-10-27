# ============================================================
# Growth API 生产级集成测试
#
# 标准：真数据夹具 + API操作后查库验证 + HTTP状态码 + 静态元数据完整性
# ============================================================
from __future__ import annotations


from app.database import SessionLocal
from app.models.growth import GrowthState, SkillStat
from app.services.growth_service import GrowthService


def _db():
    return SessionLocal()


# ============================================================
# 第 1 组：状态 + 流水 + 技能树 + 等级表 + award后状态验证
# ============================================================

class TestGrowthApiGroup1StateEventsSkillsLevels:
    """第1组：成长状态 + EXP流水 + 技能树 + 等级门槛表 + award后状态交叉验证。"""

    def test_get_state_via_api_returns_200(self, client):
        """获取成长状态返回 200，新用户默认 exp=0, level=1。

        防什么：get_state 如果对新用户没有自动创建 GrowthState，会 500。
        """
        r = client.get("/api/v1/growth/state")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["exp"] == 0
        assert data["level"] == 1
        assert data["percent"] == 0
        assert data["is_max"] is False
        assert "total_exp_to_max" in data
        assert "next_level_exp" in data

    def test_get_state_after_award_cross_check(self, client, default_user_id):
        """通过 service award 后，API 获取的状态和查库交叉验证。

        防什么：API 层如果返回了缓存或错误的数据，成长状态和实际数据库
        不一致。
        """
        # 先通过 service 授予经验值
        db = _db()
        try:
            svc = GrowthService(db)
            svc.award(default_user_id, "task:api_test:completed", "task.completed", 5)
        finally:
            db.close()

        # 通过 API 获取状态
        r = client.get("/api/v1/growth/state")
        assert r.status_code == 200
        assert r.json()["data"]["exp"] == 5

        # 查库交叉验证
        db = _db()
        try:
            state = db.query(GrowthState).filter_by(user_id=default_user_id).first()
            assert state.exp == 5
        finally:
            db.close()

    def test_list_events_via_api(self, client, default_user_id):
        """EXP 流水 API 返回列表，按时间降序。

        防什么：list_events 如果没有排序，流水顺序随机。
        """
        # 造 2 条经验记录
        db = _db()
        try:
            svc = GrowthService(db)
            svc.award(default_user_id, "task:e1:completed", "task.completed", 5, label="第一条")
            svc.award(default_user_id, "task:e2:completed", "task.completed", 5, label="第二条")
        finally:
            db.close()

        r = client.get("/api/v1/growth/events?limit=10")
        assert r.status_code == 200
        events = r.json()["data"]["list"]
        assert len(events) == 2
        # 最新的在前
        assert events[0]["label"] == "第二条"
        assert events[1]["label"] == "第一条"

    def test_get_skills_via_api(self, client, default_user_id):
        """技能树 API 返回有计数的分类，按 count 降序。

        防什么：get_skill_tree 如果返回了 count=0 的分类，技能树会
        显示一堆空技能。
        """
        # 造技能计数
        db = _db()
        try:
            db.add(SkillStat(user_id=default_user_id, category_id="math", count=5))
            db.add(SkillStat(user_id=default_user_id, category_id="code", count=2))
            db.commit()
        finally:
            db.close()

        r = client.get("/api/v1/growth/skills")
        assert r.status_code == 200
        skills = r.json()["data"]["list"]
        assert len(skills) == 2
        assert skills[0]["count"] == 5  # 降序
        assert skills[1]["count"] == 2
        # 每个技能有 id/name/count/level
        for s in skills:
            assert "id" in s
            assert "name" in s
            assert "level" in s

    def test_get_levels_via_api_static_metadata(self, client):
        """等级门槛表 API 返回完整静态元数据（max_level/table/exp_rules/skill_categories）。

        防什么：levels 接口如果漏了某个字段，前端进度条或技能选择器
        无法渲染。
        """
        r = client.get("/api/v1/growth/levels")
        assert r.status_code == 200
        data = r.json()["data"]

        assert data["max_level"] == 30
        assert "total_exp_to_max" in data
        assert isinstance(data["table"], list)
        assert len(data["table"]) == 32  # index 0 占位 + 30 级 + 末尾总经验
        assert isinstance(data["exp_rules"], dict)
        assert len(data["exp_rules"]) > 0
        assert isinstance(data["skill_categories"], list)
        assert len(data["skill_categories"]) > 0
        # 每个技能分类有 id 和 name
        for cat in data["skill_categories"]:
            assert "id" in cat
            assert "name" in cat
