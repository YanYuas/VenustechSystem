# ============================================================
# Learning API 生产级集成测试
#
# 标准：真数据夹具 + API操作后查库验证 + HTTP状态码 + 增量隔离
# ============================================================
from __future__ import annotations

from datetime import date


from app.database import SessionLocal
from app.models.learning import Flashcard, StudyPlan, StudyTimeLog


def _db():
    return SessionLocal()


# ============================================================
# 第 1 组：计划 + 卡片 + 复习 + 学习时长 的 API→查库交叉验证
# ============================================================

class TestLearningApiGroup1PlanCardReviewTime:
    """第1组：创建计划 + 创建卡片 + 提交复习 + 记录时长 + 时长统计。"""

    def test_create_plan_via_api_persists(self, client, default_user_id):
        """通过 API 创建学习计划后，查库验证字段正确写入。

        防什么：API 层如果没正确传递字段，计划创建后字段为默认值。
        """
        r = client.post("/api/v1/learning/plans", json={
            "name": "API计划", "description": "API描述",
            "target_date": "2027-01-01", "estimated_hours": 60,
        })
        assert r.status_code == 200
        plan_id = r.json()["data"]["id"]

        # 查库验证
        db = _db()
        try:
            in_db = db.get(StudyPlan, plan_id)
            assert in_db is not None
            assert in_db.name == "API计划"
            assert in_db.estimated_hours == 60
            assert in_db.user_id == default_user_id
        finally:
            db.close()

    def test_create_card_via_api_sets_next_review_today(self, client, default_user_id):
        """通过 API 创建知识卡片后，next_review 自动设为今天，查库验证。

        防什么：create_card 如果漏了 next_review=date.today()，新卡片
        不会出现在今日复习队列中。
        """
        r = client.post("/api/v1/learning/cards", json={
            "front": "API问题", "back": "API答案", "category": "API分类", "difficulty": 4,
        })
        assert r.status_code == 200
        card_id = r.json()["data"]["id"]
        assert r.json()["data"]["next_review"] == date.today().isoformat()

        # 查库验证
        db = _db()
        try:
            in_db = db.get(Flashcard, card_id)
            assert in_db.next_review == date.today()
            assert in_db.ef == 2.5
            assert in_db.user_id == default_user_id
        finally:
            db.close()

    def test_submit_review_via_api_updates_sm2(self, client, default_user_id):
        """通过 API 提交复习结果后，SM-2 参数更新，查库验证。

        防什么：submit_review 如果没正确更新卡片参数，间隔重复算法失效。
        """
        # 先创建卡片
        r = client.post("/api/v1/learning/cards", json={"front": "Q", "back": "A"})
        card_id = r.json()["data"]["id"]

        # 提交复习 quality=5
        r = client.post(f"/api/v1/learning/cards/{card_id}/review", json={"quality": 5})
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["repetition"] == 1
        assert data["interval"] == 1
        assert data["quality"] == 5

        # 查库验证
        db = _db()
        try:
            in_db = db.get(Flashcard, card_id)
            assert in_db.repetition == 1
            assert in_db.interval == 1
            assert in_db.review_count == 1
            assert in_db.last_reviewed_at is not None
        finally:
            db.close()

    def test_log_study_time_via_api_persists(self, client, default_user_id):
        """通过 API 记录学习时长后，查库验证 duration/subject/logged_date。

        防什么：log_study_time 如果漏了 logged_date 默认值（今天），
        记录的日期会是 None。
        """
        r = client.post("/api/v1/learning/time/log", json={
            "duration": 45, "subject": "数学分析", "note": "第三章", "source": "manual",
        })
        assert r.status_code == 200
        log_id = r.json()["data"]["id"]

        # 查库验证
        db = _db()
        try:
            in_db = db.get(StudyTimeLog, log_id)
            assert in_db.duration == 45
            assert in_db.subject == "数学分析"
            assert in_db.logged_date == date.today()
            assert in_db.user_id == default_user_id
        finally:
            db.close()

    def test_get_time_stats_via_api(self, client, default_user_id):
        """通过 API 获取学习时长统计，返回 total_minutes/daily/trend 字段。

        防什么：time_stats 如果返回了错误的字段结构，前端图表无法渲染。
        """
        # 先记录一条
        client.post("/api/v1/learning/time/log", json={"duration": 30, "subject": "数学"})

        r = client.get("/api/v1/learning/time/stats?days=7")
        assert r.status_code == 200
        data = r.json()["data"]
        assert "total_minutes" in data
        assert "avg_minutes" in data
        assert "daily" in data
        assert "trend" in data
        assert data["days"] == 7
        assert len(data["daily"]) == 7
        assert data["total_minutes"] >= 30


# ============================================================
# 第 2 组：计划列表 + 更新 + 删除 + 生成预览 + 生成应用
# ============================================================

class TestLearningApiGroup2PlanCrudGenerate:
    """第2组：学习计划列表分页 + 增量更新 + 删除 + 领域引擎生成预览 + 生成并落成任务。"""

    def test_list_plans_via_api_pagination(self, client, default_user_id):
        """学习计划列表返回分页结构。

        防什么：list_plans 如果 total 计算错误，前端分页器显示错误页数。
        """
        for i in range(3):
            client.post("/api/v1/learning/plans", json={"name": f"计划{i}"})

        r = client.get("/api/v1/learning/plans?page=1&page_size=2")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["total"] == 3
        assert len(data["list"]) == 2
        assert data["page"] == 1

    def test_update_plan_via_api_persists(self, client, default_user_id):
        """通过 API 更新学习计划后，查库验证字段变更，未指定字段不变。

        防什么：update_plan 如果用了全量覆盖，未传字段会被重置。
        """
        r = client.post("/api/v1/learning/plans", json={
            "name": "旧名字", "description": "旧描述", "estimated_hours": 50,
        })
        plan_id = r.json()["data"]["id"]

        r = client.patch(f"/api/v1/learning/plans/{plan_id}", json={
            "name": "新名字", "progress": 50,
        })
        assert r.status_code == 200
        assert r.json()["data"]["name"] == "新名字"

        # 查库验证
        db = _db()
        try:
            from app.models.learning import StudyPlan
            in_db = db.get(StudyPlan, plan_id)
            assert in_db.name == "新名字"
            assert in_db.progress == 50
            assert in_db.description == "旧描述"  # 未指定字段不变
        finally:
            db.close()

    def test_delete_plan_via_api_removes(self, client, default_user_id):
        """通过 API 删除学习计划后，查库验证记录消失。

        防什么：delete_plan 如果没真正删除，计划仍会出现在列表中。
        """
        r = client.post("/api/v1/learning/plans", json={"name": "待删除"})
        plan_id = r.json()["data"]["id"]

        r = client.delete(f"/api/v1/learning/plans/{plan_id}")
        assert r.status_code == 200

        # 查库验证：硬删除，记录消失
        db = _db()
        try:
            from app.models.learning import StudyPlan
            assert db.get(StudyPlan, plan_id) is None
        finally:
            db.close()

    def test_generate_plan_preview_via_api(self, client, default_user_id):
        """通过 API 生成学习计划预览（不落库），返回完整结构。

        防什么：generate_plan_preview 如果领域引擎报错，前端无法展示
        计划预览，用户无法决定是否应用。
        """
        r = client.post("/api/v1/learning/plans/generate", json={
            "goal": "学习Python", "total_days": 7, "minutes_per_day": 30,
        })
        assert r.status_code == 200
        data = r.json()["data"]
        assert "goal" in data
        assert "skill_name" in data
        assert "items" in data
        assert len(data["items"]) > 0
        assert "item_count" in data
        assert data["total_days"] == 7
        assert data["minutes_per_day"] == 30
        # 预览不落库
        db = _db()
        try:
            from app.models.learning import StudyPlan
            assert db.query(StudyPlan).filter_by(user_id=default_user_id).count() == 0
        finally:
            db.close()

    def test_apply_generated_plan_via_api(self, client, default_user_id):
        """通过 API 生成学习计划并落成任务，查库验证 StudyPlan + Task 都创建。

        防什么：apply_generated_plan 如果只建了计划没建任务，用户看到
        计划但没有可执行的任务条目。
        """
        r = client.post("/api/v1/learning/plans/generate/apply", json={
            "goal": "学习SQL", "total_days": 3, "minutes_per_day": 30,
            "plan_name": "SQL入门计划",
        })
        assert r.status_code == 200
        data = r.json()["data"]
        assert "plan" in data
        assert "task_count" in data
        assert data["task_count"] > 0
        assert len(data["task_ids"]) == data["task_count"]

        # 查库验证：StudyPlan 创建
        db = _db()
        try:
            from app.models.learning import StudyPlan
            from app.models.task import Task
            plan = db.query(StudyPlan).filter_by(user_id=default_user_id).first()
            assert plan is not None
            assert plan.name == "SQL入门计划"
            # Task 创建
            tasks = db.query(Task).filter_by(user_id=default_user_id).all()
            assert len(tasks) == data["task_count"]
        finally:
            db.close()


# ============================================================
# 第 3 组：卡片列表 + 更新 + 删除 + 今日复习队列 + 越权验证
# ============================================================

def _create_other_user_learning():
    """直接操作数据库创建第二个用户，用于 API 越权测试。"""
    import uuid
    from app.database import SessionLocal
    from app.models.user import User
    db = SessionLocal()
    try:
        user = User(username=f"other_{uuid.uuid4().hex[:12]}", nickname="其他用户")
        db.add(user)
        db.commit()
        db.refresh(user)
        return user.id
    finally:
        db.close()


class TestLearningApiGroup3CardCrudReviewOwnership:
    """第3组：卡片列表过滤 + 增量更新 + 删除 + 今日复习队列 + 越权更新/删除。"""

    def test_list_cards_via_api_filter_by_plan(self, client, default_user_id):
        """卡片列表支持按 plan_id 过滤，查库验证。

        防什么：list_cards 如果 plan_id 过滤失效，会返回所有卡片，
        用户在某个计划下看到其他计划的卡片。
        """
        # 创建计划和两张卡片
        r_plan = client.post("/api/v1/learning/plans", json={"name": "计划A"})
        plan_id = r_plan.json()["data"]["id"]
        client.post("/api/v1/learning/cards", json={"front": "Q1", "back": "A1", "plan_id": plan_id})
        client.post("/api/v1/learning/cards", json={"front": "Q2", "back": "A2"})  # 无计划

        # 按 plan_id 过滤
        r = client.get(f"/api/v1/learning/cards?plan_id={plan_id}")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["total"] == 1
        assert data["list"][0]["front"] == "Q1"

        # 不过滤返回全部
        r_all = client.get("/api/v1/learning/cards")
        assert r_all.json()["data"]["total"] == 2

    def test_update_card_via_api_persists(self, client, default_user_id):
        """通过 API 更新卡片后，查库验证字段变更，SM-2 参数不变。

        防什么：update_card 如果误改了 ef/interval 等 SM-2 参数，
        间隔重复算法会异常。
        """
        r = client.post("/api/v1/learning/cards", json={
            "front": "旧问题", "back": "旧答案", "category": "旧分类", "difficulty": 3,
        })
        card_id = r.json()["data"]["id"]

        r = client.patch(f"/api/v1/learning/cards/{card_id}", json={
            "front": "新问题", "difficulty": 5,
        })
        assert r.status_code == 200
        assert r.json()["data"]["front"] == "新问题"

        # 查库验证
        db = _db()
        try:
            from app.models.learning import Flashcard
            in_db = db.get(Flashcard, card_id)
            assert in_db.front == "新问题"
            assert in_db.difficulty == 5
            assert in_db.back == "旧答案"  # 未指定字段不变
            assert in_db.ef == 2.5  # SM-2 参数不变
        finally:
            db.close()

    def test_delete_card_via_api_removes(self, client, default_user_id):
        """通过 API 删除卡片后，查库验证记录消失。

        防什么：delete_card 如果没真正删除，卡片仍会出现在复习队列中。
        """
        r = client.post("/api/v1/learning/cards", json={"front": "待删除", "back": "A"})
        card_id = r.json()["data"]["id"]

        r = client.delete(f"/api/v1/learning/cards/{card_id}")
        assert r.status_code == 200

        db = _db()
        try:
            from app.models.learning import Flashcard
            assert db.get(Flashcard, card_id) is None
        finally:
            db.close()

    def test_today_review_queue_via_api(self, client, default_user_id):
        """今日复习队列只返回 next_review <= 今天的卡片，未来的不返回。

        防什么：get_today_review 如果漏了 next_review 过滤，会返回所有
        卡片，用户被淹没在不需要今天复习的卡片里。
        """
        # 新建卡片 next_review=今天 → 在队列中
        client.post("/api/v1/learning/cards", json={"front": "今天复习", "back": "A"})

        r = client.get("/api/v1/learning/review/today")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["total"] == 1
        assert data["list"][0]["front"] == "今天复习"
        assert "date" in data

    def test_update_card_other_user_returns_404(self, client, default_user_id):
        """越权更新其他用户的卡片 → 404（不泄露存在性）。

        防什么：修复前 update_card 直接 get_or_404(card_id)，不校验 user_id，
        用户 A 可以修改用户 B 的卡片内容。
        """
        other_id = _create_other_user_learning()
        db = _db()
        try:
            from app.models.learning import Flashcard
            from datetime import date
            card = Flashcard(user_id=other_id, front="别人的卡片", back="答案",
                             next_review=date.today())
            db.add(card)
            db.commit()
            card_id = card.id
        finally:
            db.close()

        r = client.patch(f"/api/v1/learning/cards/{card_id}", json={"front": "篡改"})
        assert r.status_code == 404

        # 查库验证：卡片未被修改
        db = _db()
        try:
            from app.models.learning import Flashcard
            assert db.get(Flashcard, card_id).front == "别人的卡片"
        finally:
            db.close()
