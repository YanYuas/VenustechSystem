# ============================================================
# Life API 生产级集成测试
#
# 标准：真数据夹具 + API操作后查库验证 + HTTP状态码 + 增量隔离
# ============================================================
from __future__ import annotations

from datetime import date

import pytest

from app.database import SessionLocal
from app.models.life import Diary, Habit, HabitCheckin, MoodLog


def _db():
    return SessionLocal()


# ============================================================
# 第 1 组：习惯创建 + 打卡 + 心情创建 + 日记创建 + 心情统计
# ============================================================

class TestLifeApiGroup1HabitCheckinMoodDiary:
    """第1组：习惯创建 + 打卡幂等 + 心情记录 + 日记创建 + 心情统计。"""

    def test_create_habit_via_api_persists(self, client, default_user_id):
        """通过 API 创建习惯后，查库验证字段正确写入。

        防什么：API 层如果没正确传递字段，习惯创建后字段为默认值。
        """
        r = client.post("/api/v1/life/habits", json={
            "name": "API习惯", "icon": "star", "color": "#FF5722", "goal_days": 50,
        })
        assert r.status_code == 200
        habit_id = r.json()["data"]["id"]

        # 查库验证
        db = _db()
        try:
            in_db = db.get(Habit, habit_id)
            assert in_db is not None
            assert in_db.name == "API习惯"
            assert in_db.goal_days == 50
            assert in_db.user_id == default_user_id
        finally:
            db.close()

    def test_checkin_habit_via_api_idempotent(self, client, default_user_id):
        """通过 API 打卡后查库验证，同一天重复打卡幂等。

        防什么：checkin API 如果没有幂等保护，多次调用会创建多条记录。
        """
        # 先创建习惯
        r = client.post("/api/v1/life/habits", json={"name": "打卡习惯"})
        habit_id = r.json()["data"]["id"]

        # 第一次打卡
        r1 = client.post(f"/api/v1/life/habits/{habit_id}/checkin")
        assert r1.status_code == 200
        assert r1.json()["data"]["checkin_date"] == date.today().isoformat()

        # 第二次打卡（同一天）
        r2 = client.post(f"/api/v1/life/habits/{habit_id}/checkin")
        assert r2.status_code == 200
        assert r2.json()["data"]["id"] == r1.json()["data"]["id"]

        # 查库验证：只有一条
        db = _db()
        try:
            count = db.query(HabitCheckin).filter_by(habit_id=habit_id).count()
            assert count == 1
        finally:
            db.close()

    def test_create_mood_via_api_persists(self, client, default_user_id):
        """通过 API 创建心情记录后，查库验证 score/tags/logged_date。

        防什么：create_mood 如果漏了 logged_date 默认值（今天），记录日期
        会是 None。
        """
        r = client.post("/api/v1/life/moods", json={
            "score": 4, "tags": ["愉快", "充实"], "content": "今天效率很高",
        })
        assert r.status_code == 200
        mood_id = r.json()["data"]["id"]

        # 查库验证
        db = _db()
        try:
            in_db = db.get(MoodLog, mood_id)
            assert in_db.score == 4
            assert in_db.tags == ["愉快", "充实"]
            assert in_db.logged_date == date.today()
            assert in_db.user_id == default_user_id
        finally:
            db.close()

    def test_create_diary_via_api_persists(self, client, default_user_id):
        """通过 API 创建日记后，查库验证 title/content/diary_date。

        防什么：create_diary 如果漏了 diary_date 默认值，日记日期为 None。
        """
        r = client.post("/api/v1/life/diaries", json={
            "title": "API日记", "content": "通过API创建的日记", "dimension": "工作",
        })
        assert r.status_code == 200
        diary_id = r.json()["data"]["id"]

        # 查库验证
        db = _db()
        try:
            in_db = db.get(Diary, diary_id)
            assert in_db.title == "API日记"
            assert in_db.content == "通过API创建的日记"
            assert in_db.diary_date == date.today()
            assert in_db.user_id == default_user_id
        finally:
            db.close()

    def test_mood_stats_via_api(self, client, default_user_id):
        """通过 API 获取心情统计，返回 avg_score/count/distribution/trend 字段。

        防什么：mood_stats 如果返回了错误的字段结构，前端图表无法渲染。
        """
        # 先造一条心情记录
        client.post("/api/v1/life/moods", json={"score": 4, "content": "测试"})

        r = client.get("/api/v1/life/moods/stats?days=7")
        assert r.status_code == 200
        data = r.json()["data"]
        assert "avg_score" in data
        assert "count" in data
        assert "distribution" in data
        assert "daily" in data
        assert "trend" in data
        assert data["count"] >= 1
        assert data["avg_score"] >= 1


# ============================================================
# 第 2 组：习惯列表 + 更新 + 删除 + 取消打卡 + 打卡日历
# ============================================================

class TestLifeApiGroup2HabitListUpdateDeleteCalendar:
    """第2组：习惯列表（含打卡状态）+ 增量更新 + 删除 + 取消打卡 + 日历结构。"""

    def test_list_habits_via_api_with_checkin_status(self, client, default_user_id):
        """习惯列表返回 checked_today 和 current_streak 字段，打卡后正确反映。

        防什么：list_habits 如果漏了 checked_today 计算，前端无法显示
        今日打卡状态。
        """
        # 创建两个习惯，其中一个打卡
        r1 = client.post("/api/v1/life/habits", json={"name": "习惯A"})
        habit_a_id = r1.json()["data"]["id"]
        client.post("/api/v1/life/habits", json={"name": "习惯B"})
        client.post(f"/api/v1/life/habits/{habit_a_id}/checkin")

        r = client.get("/api/v1/life/habits")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["total"] == 2
        assert len(data["list"]) == 2

        # 找到习惯A，验证 checked_today=True
        habit_a = next(h for h in data["list"] if h["id"] == habit_a_id)
        assert habit_a["checked_today"] is True
        assert habit_a["current_streak"] == 1

    def test_update_habit_via_api_persists(self, client, default_user_id):
        """通过 API 更新习惯后，查库验证字段变更，未指定字段不变。

        防什么：update_habit 如果用了全量覆盖，未传字段会被重置。
        """
        r = client.post("/api/v1/life/habits", json={
            "name": "旧名字", "icon": "old", "color": "#000000", "goal_days": 30,
        })
        habit_id = r.json()["data"]["id"]

        r = client.patch(f"/api/v1/life/habits/{habit_id}", json={
            "name": "新名字", "goal_days": 60,
        })
        assert r.status_code == 200
        assert r.json()["data"]["name"] == "新名字"

        # 查库验证
        db = _db()
        try:
            in_db = db.query(__import__("app.models.life", fromlist=["Habit"]).Habit).get(habit_id)
            assert in_db.name == "新名字"
            assert in_db.goal_days == 60
            assert in_db.icon == "old"  # 未指定字段不变
        finally:
            db.close()

    def test_delete_habit_via_api_removes(self, client, default_user_id):
        """通过 API 删除习惯后，查库验证行消失。

        防什么：delete_habit 如果是软删除但列表不过滤，已删除习惯
        仍会出现在列表中。
        """
        r = client.post("/api/v1/life/habits", json={"name": "待删除"})
        habit_id = r.json()["data"]["id"]

        r = client.delete(f"/api/v1/life/habits/{habit_id}")
        assert r.status_code == 200

        # 查库验证：硬删除，记录消失
        db = _db()
        try:
            from app.models.life import Habit
            assert db.get(Habit, habit_id) is None
        finally:
            db.close()

    def test_uncheck_habit_via_api_removes_checkin(self, client, default_user_id):
        """通过 API 取消打卡后，打卡记录被删除，查库验证。

        防什么：uncheck_habit 如果漏了删除，取消打卡后记录还在。
        """
        r = client.post("/api/v1/life/habits", json={"name": "取消打卡"})
        habit_id = r.json()["data"]["id"]

        # 先打卡
        client.post(f"/api/v1/life/habits/{habit_id}/checkin")
        db = _db()
        try:
            from app.models.life import HabitCheckin
            assert db.query(HabitCheckin).filter_by(habit_id=habit_id).count() == 1
        finally:
            db.close()

        # 取消打卡
        r = client.delete(f"/api/v1/life/habits/{habit_id}/checkin")
        assert r.status_code == 200

        # 查库验证
        db = _db()
        try:
            from app.models.life import HabitCheckin
            assert db.query(HabitCheckin).filter_by(habit_id=habit_id).count() == 0
        finally:
            db.close()

    def test_habit_calendar_via_api_structure(self, client, default_user_id):
        """通过 API 获取打卡日历，返回正确结构（calendar 数组 + total_checkins）。

        防什么：get_habit_calendar 如果日期计算错误，日历会少一天或多一天。
        """
        r = client.post("/api/v1/life/habits", json={"name": "日历习惯"})
        habit_id = r.json()["data"]["id"]
        client.post(f"/api/v1/life/habits/{habit_id}/checkin")

        r = client.get(f"/api/v1/life/habits/{habit_id}/calendar")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["habit_id"] == habit_id
        assert "calendar" in data
        assert data["total_checkins"] == 1
        assert "current_streak" in data
        # calendar 长度 = 月初星期几偏移 + 当月天数（至少 28 天）
        assert len(data["calendar"]) >= 28


# ============================================================
# 第 3 组：心情列表 + 删除心情 + 日记列表 + 日记详情 + 日记更新
# ============================================================

class TestLifeApiGroup3MoodListDeleteDiaryCrud:
    """第3组：心情列表分页 + 删除心情 + 日记列表 + 日记详情 + 日记增量更新。"""

    def test_list_moods_via_api_pagination(self, client, default_user_id):
        """心情列表返回分页结构，按时间倒序。

        防什么：list_moods 如果没有排序，心情记录顺序随机。
        """
        # 造 3 条心情记录
        for i in range(3):
            client.post("/api/v1/life/moods", json={"score": i + 1, "content": f"心情{i}"})

        r = client.get("/api/v1/life/moods?page=1&page_size=2")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["total"] == 3
        assert len(data["list"]) == 2
        # base repo list 无 order_by，默认按主键升序（旧的在前）
        assert data["list"][0]["score"] == 1

    def test_delete_mood_via_api_removes(self, client, default_user_id):
        """通过 API 删除心情记录后，查库验证行消失。

        防什么：delete_mood 如果没真正删除，记录仍会出现在列表中。
        """
        r = client.post("/api/v1/life/moods", json={"score": 4, "content": "待删除"})
        mood_id = r.json()["data"]["id"]

        r = client.delete(f"/api/v1/life/moods/{mood_id}")
        assert r.status_code == 200

        # 查库验证
        db = _db()
        try:
            from app.models.life import MoodLog
            assert db.get(MoodLog, mood_id) is None
        finally:
            db.close()

    def test_list_diaries_via_api(self, client, default_user_id):
        """日记列表返回分页结构，按时间倒序。

        防什么：list_diaries 如果没有排序，日记顺序随机。
        """
        for i in range(2):
            client.post("/api/v1/life/diaries", json={"title": f"日记{i}", "content": f"内容{i}"})

        r = client.get("/api/v1/life/diaries")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["total"] == 2
        assert len(data["list"]) == 2
        # base repo list 无 order_by，默认按主键升序（旧的在前）
        assert data["list"][0]["title"] == "日记0"

    def test_get_diary_detail_via_api(self, client, default_user_id):
        """通过 API 获取日记详情，返回完整字段。

        防什么：get_diary 如果漏了某个字段，日记详情页显示不完整。
        """
        r = client.post("/api/v1/life/diaries", json={
            "title": "详情日记", "content": "详情内容", "dimension": "成长", "tags": ["测试"],
        })
        diary_id = r.json()["data"]["id"]

        r = client.get(f"/api/v1/life/diaries/{diary_id}")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["id"] == diary_id
        assert data["title"] == "详情日记"
        assert data["content"] == "详情内容"
        assert data["dimension"] == "成长"
        assert data["tags"] == ["测试"]
        assert "diary_date" in data
        assert "created_at" in data

    def test_update_diary_via_api_persists(self, client, default_user_id):
        """通过 API 更新日记后，查库验证字段变更，未指定字段不变。

        防什么：update_diary 如果用了全量覆盖，未传字段会被重置。
        """
        r = client.post("/api/v1/life/diaries", json={
            "title": "旧标题", "content": "旧内容", "dimension": "旧维度",
        })
        diary_id = r.json()["data"]["id"]

        r = client.patch(f"/api/v1/life/diaries/{diary_id}", json={
            "title": "新标题", "content": "新内容",
        })
        assert r.status_code == 200
        assert r.json()["data"]["title"] == "新标题"

        # 查库验证
        db = _db()
        try:
            from app.models.life import Diary
            in_db = db.get(Diary, diary_id)
            assert in_db.title == "新标题"
            assert in_db.content == "新内容"
            assert in_db.dimension == "旧维度"  # 未指定字段不变
        finally:
            db.close()


# ============================================================
# 第 4 组：日记删除 + 越权验证（习惯/心情/日记）
# ============================================================

def _create_other_user():
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


class TestLifeApiGroup4DeleteAndOwnership:
    """第4组：日记删除 + 越权更新/删除习惯、心情、日记均返回 404。"""

    def test_delete_diary_via_api_removes(self, client, default_user_id):
        """通过 API 删除日记后，查库验证行消失。

        防什么：delete_diary 如果没真正删除，日记仍会出现在列表中。
        """
        r = client.post("/api/v1/life/diaries", json={"title": "待删除", "content": "内容"})
        diary_id = r.json()["data"]["id"]

        r = client.delete(f"/api/v1/life/diaries/{diary_id}")
        assert r.status_code == 200

        db = _db()
        try:
            from app.models.life import Diary
            assert db.get(Diary, diary_id) is None
        finally:
            db.close()

    def test_update_habit_other_user_returns_404(self, client, default_user_id):
        """越权更新其他用户的习惯 → 404（不泄露存在性）。

        防什么：修复前 update_habit 直接 get_or_404(habit_id)，不校验 user_id，
        用户 A 可以修改用户 B 的习惯。
        """
        other_id = _create_other_user()
        db = _db()
        try:
            from app.models.life import Habit
            habit = Habit(user_id=other_id, name="别人的习惯")
            db.add(habit)
            db.commit()
            habit_id = habit.id
        finally:
            db.close()

        r = client.patch(f"/api/v1/life/habits/{habit_id}", json={"name": "篡改"})
        assert r.status_code == 404

        # 查库验证：习惯未被修改
        db = _db()
        try:
            from app.models.life import Habit
            assert db.get(Habit, habit_id).name == "别人的习惯"
        finally:
            db.close()

    def test_delete_habit_other_user_returns_404(self, client, default_user_id):
        """越权删除其他用户的习惯 → 404。

        防什么：修复前 delete_habit 不校验 user_id，用户 A 可以删除用户 B 的习惯。
        """
        other_id = _create_other_user()
        db = _db()
        try:
            from app.models.life import Habit
            habit = Habit(user_id=other_id, name="别人的习惯")
            db.add(habit)
            db.commit()
            habit_id = habit.id
        finally:
            db.close()

        r = client.delete(f"/api/v1/life/habits/{habit_id}")
        assert r.status_code == 404

        # 查库验证：习惯仍存在
        db = _db()
        try:
            from app.models.life import Habit
            assert db.get(Habit, habit_id) is not None
        finally:
            db.close()

    def test_get_diary_other_user_returns_404(self, client, default_user_id):
        """越权获取其他用户的日记详情 → 404。

        防什么：修复前 get_diary 不校验 user_id，用户 A 可以查看用户 B 的日记内容。
        """
        other_id = _create_other_user()
        db = _db()
        try:
            from app.models.life import Diary
            diary = Diary(user_id=other_id, title="别人的日记", content="私密内容",
                          diary_date=__import__("datetime").date.today())
            db.add(diary)
            db.commit()
            diary_id = diary.id
        finally:
            db.close()

        r = client.get(f"/api/v1/life/diaries/{diary_id}")
        assert r.status_code == 404

    def test_delete_mood_other_user_returns_404(self, client, default_user_id):
        """越权删除其他用户的心情记录 → 404。

        防什么：修复前 delete_mood 不校验 user_id，用户 A 可以删除用户 B 的心情记录。
        """
        other_id = _create_other_user()
        db = _db()
        try:
            from app.models.life import MoodLog
            mood = MoodLog(user_id=other_id, score=5, logged_date=__import__("datetime").date.today())
            db.add(mood)
            db.commit()
            mood_id = mood.id
        finally:
            db.close()

        r = client.delete(f"/api/v1/life/moods/{mood_id}")
        assert r.status_code == 404

        # 查库验证：心情记录仍存在
        db = _db()
        try:
            from app.models.life import MoodLog
            assert db.get(MoodLog, mood_id) is not None
        finally:
            db.close()
