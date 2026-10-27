# ============================================================
# Growth Service 生产级测试
#
# 成长体系（S6-2）：经验值 / 等级 / 技能树 / 四维数值衰减
#
# 标准：真数据夹具 + 写操作后查库验证 + 幂等性验证 + 算法正确性 + 负向断言
# ============================================================
from __future__ import annotations

from datetime import datetime, timedelta, timezone


from app.models.growth import GrowthEvent, GrowthState, SkillStat
from app.services.growth_service import (
    LEVEL_TABLE, GrowthService, apply_stat_decay, auto_classify,
    exp_for_study_minutes, get_exp_progress, get_level,
)


# ============================================================
# 第 1 组：状态初始化 + 经验结算 + 幂等性 + 等级计算 + 数值衰减
# ============================================================

class TestGroup1StateAwardIdempotentLevelDecay:
    """第1组：新用户状态初始化 + award结算 + 幂等 + 等级算法 + 四维衰减。"""

    def test_get_state_creates_default_for_new_user(self, db_session, test_user):
        """新用户首次 get_state 自动创建 GrowthState（exp=0, level=1），查库验证。

        防什么：get_or_create_state 如果没有自动创建，新用户访问成长页会 500。
        """
        svc = GrowthService(db_session)
        state = svc.get_state(test_user.id)

        assert state["exp"] == 0
        assert state["level"] == 1
        assert state["percent"] == 0
        assert state["is_max"] is False
        assert state["total_exp_to_max"] == LEVEL_TABLE[30]

        # 查库验证
        db_session.expire_all()
        in_db = db_session.query(GrowthState).filter_by(user_id=test_user.id).first()
        assert in_db is not None
        assert in_db.exp == 0
        assert in_db.level == 1

    def test_award_grants_exp_and_updates_state(self, db_session, test_user):
        """award 结算经验值后，GrowthState.exp 增加，查库验证。

        防什么：award 如果只写了 GrowthEvent 没更新 GrowthState，用户经验值
        不会增长，等级永远是 1。
        """
        svc = GrowthService(db_session)
        result = svc.award(
            user_id=test_user.id,
            source_key="task:abc123:completed",
            event_type="task.completed",
            exp=5,
            label="完成任务",
        )

        assert result["granted"] is True
        assert result["exp"] == 5
        assert result["level_up"] is False

        # 查库验证
        db_session.expire_all()
        state = db_session.query(GrowthState).filter_by(user_id=test_user.id).first()
        assert state.exp == 5
        assert state.level == 1

        # GrowthEvent 也写入了
        event = db_session.query(GrowthEvent).filter_by(user_id=test_user.id).first()
        assert event is not None
        assert event.source_key == "task:abc123:completed"
        assert event.exp == 5

    def test_award_idempotent_same_source_key(self, db_session, test_user):
        """同一 source_key 重复投递不重复计分（幂等），第二次 granted=False。

        防什么：event_bus 可能重复投递同一事件（网络重试、重启重放），
        如果没有幂等保护，用户会刷经验值。
        """
        svc = GrowthService(db_session)

        # 第一次投递
        r1 = svc.award(test_user.id, "task:xyz:completed", "task.completed", 5)
        assert r1["granted"] is True

        # 第二次投递（同一 source_key）
        r2 = svc.award(test_user.id, "task:xyz:completed", "task.completed", 5)
        assert r2["granted"] is False
        assert r2["exp"] == 5  # 返回已结算的 exp

        # 查库验证：exp 只增加了一次
        db_session.expire_all()
        state = db_session.query(GrowthState).filter_by(user_id=test_user.id).first()
        assert state.exp == 5  # 不是 10

        # GrowthEvent 只有一条
        count = db_session.query(GrowthEvent).filter_by(
            user_id=test_user.id, source_key="task:xyz:completed"
        ).count()
        assert count == 1

    def test_get_level_and_exp_progress_correctness(self):
        """等级计算和进度条：已知 exp 值验证 get_level 和 get_exp_progress 输出。

        防什么：LEVEL_TABLE 索引取错（如用 table[31] 而非 table[30]），
        会让"距离满级还差多少"凭空多出 18056 点。
        """
        # exp=0 → LV1
        assert get_level(0) == 1
        p = get_exp_progress(0)
        assert p["level"] == 1
        assert p["current"] == 0
        assert p["need"] == LEVEL_TABLE[2] - LEVEL_TABLE[1]
        assert p["percent"] == 0
        assert p["is_max"] is False

        # exp 刚好等于 LV2 门槛 → LV2
        lv2_exp = LEVEL_TABLE[2]
        assert get_level(lv2_exp) == 2

        # 满级
        max_exp = LEVEL_TABLE[30]
        assert get_level(max_exp) == 30
        p_max = get_exp_progress(max_exp)
        assert p_max["is_max"] is True
        assert p_max["percent"] == 100
        assert p_max["need"] == 0

    def test_apply_stat_decay_by_hours(self):
        """四维数值按小时衰减：饱食度掉最快（2.0/h），亲密度最慢（0.2/h）。

        防什么：衰减速率如果写反了，亲密度会比饱食度掉得还快，
        宠物体验完全错误。
        """
        stats = {"satiety": 100, "energy": 100, "mood": 100, "intimacy": 100}
        updated_at = datetime.now(timezone.utc) - timedelta(hours=10)

        decayed = apply_stat_decay(stats, updated_at)

        # 10 小时后：饱食度 -20，能量 -15，心情 -10，亲密度 -2
        assert decayed["satiety"] == 80   # 100 - 2.0*10 = 80
        assert decayed["energy"] == 85    # 100 - 1.5*10 = 85
        assert decayed["mood"] == 90      # 100 - 1.0*10 = 90
        assert decayed["intimacy"] == 98  # 100 - 0.2*10 = 98

        # 超过 72 小时封顶（按 72 小时计）
        long_ago = datetime.now(timezone.utc) - timedelta(hours=168)  # 7 天
        decayed_long = apply_stat_decay(stats, long_ago)
        # 72 小时饱食度 -144，但下限是 0
        assert decayed_long["satiety"] == 0
        # 亲密度 72 小时 -14.4 → 86
        assert decayed_long["intimacy"] == 86


# ============================================================
# 第 2 组：升级检测 + 技能归类 + 技能树 + 学习时长折算 + 经验流水
# ============================================================

class TestGroup2LevelUpSkillTreeStudyLogEvents:
    """第2组：跨级升级 + 技能自动归类 + 技能树排序 + 学习时长折算 + 经验流水。"""

    def test_award_triggers_level_up(self, db_session, test_user):
        """一次性授予大量经验值触发升级，level_up=True，查库验证 level 更新。

        防什么：award 如果只更新 exp 不更新 level 字段，用户经验值到了
        但等级显示还是旧的。
        """
        svc = GrowthService(db_session)
        # LV2 门槛 = LEVEL_TABLE[2]，直接授予这么多经验
        lv2_exp = LEVEL_TABLE[2]

        result = svc.award(
            user_id=test_user.id,
            source_key="review:big:created",
            event_type="review.created",
            exp=lv2_exp,
            label="写了一篇超长复盘",
        )

        assert result["granted"] is True
        assert result["level_up"] is True
        assert result["level"] == 2

        # 查库验证
        db_session.expire_all()
        state = db_session.query(GrowthState).filter_by(user_id=test_user.id).first()
        assert state.level == 2
        assert state.exp == lv2_exp

    def test_auto_classify_recognizes_skill_keywords(self):
        """技能自动归类：文本命中关键词时返回对应分类 id，可命中多个。

        防什么：auto_classify 如果大小写不统一或关键词漏配，技能树
        永远是空的，用户看不到自己的能力分布。
        """
        # 命中"数学"相关关键词
        hits = auto_classify("今天学习了数学分析中的极限定理")
        assert len(hits) >= 1
        assert isinstance(hits[0], str)

        # 空文本返回空列表
        assert auto_classify("") == []
        assert auto_classify(None) == []

        # 不命中任何关键词返回空列表
        hits_none = auto_classify("asdfghjkl")
        assert hits_none == []

    def test_award_with_classified_text_bumps_skill_stats(self, db_session, test_user):
        """award 传入 classified_text 时，自动归类并更新 SkillStat 计数，查库验证。

        防什么：award 如果漏了 _bump_skills 调用，技能树不会增长，
        用户做了很多事但技能树是空的。
        """
        svc = GrowthService(db_session)
        # 用包含明确关键词的文本
        result = svc.award(
            user_id=test_user.id,
            source_key="document:math1:created",
            event_type="document.created",
            exp=10,
            label="新建数学笔记",
            classified_text="数学分析 极限 导数 积分",
        )

        assert result["granted"] is True
        assert len(result["skill_cat_ids"]) >= 1

        # 查库验证：SkillStat 有记录
        db_session.expire_all()
        stats = db_session.query(SkillStat).filter_by(user_id=test_user.id).all()
        assert len(stats) >= 1
        # 每个命中的分类 count=1
        for s in stats:
            assert s.count == 1

    def test_get_skill_tree_sorted_by_count_desc(self, db_session, test_user):
        """技能树按 count 降序排列，count 越大等级越高。

        防什么：get_skill_tree 如果没有排序，前端展示的技能顺序随机，
        用户看不出自己最擅长什么。
        """
        svc = GrowthService(db_session)
        # 造两个技能分类，A 计数 3，B 计数 1
        db_session.add(SkillStat(user_id=test_user.id, category_id="math", count=3))
        db_session.add(SkillStat(user_id=test_user.id, category_id="code", count=1))
        db_session.commit()

        tree = svc.get_skill_tree(test_user.id)
        assert len(tree) == 2
        # 按 count 降序
        assert tree[0]["count"] == 3
        assert tree[1]["count"] == 1
        # 等级 = count + 1
        assert tree[0]["level"] == 4
        assert tree[1]["level"] == 2

    def test_exp_for_study_minutes_calculation(self):
        """学习时长折算经验值：每 10 分钟 1 点，向上取整，单次上限 6 点。

        防什么：折算公式如果用了向下取整而非向上取整，学习 9 分钟会得 0 点，
        用户觉得"学了白学"。
        """
        # 边界值
        assert exp_for_study_minutes(0) == 0
        assert exp_for_study_minutes(-5) == 0
        assert exp_for_study_minutes(1) == 1    # 向上取整
        assert exp_for_study_minutes(10) == 1
        assert exp_for_study_minutes(11) == 2   # 向上取整
        assert exp_for_study_minutes(50) == 5
        assert exp_for_study_minutes(60) == 6   # 上限
        assert exp_for_study_minutes(120) == 6  # 超过上限仍为 6

    def test_list_events_returns_recent_first(self, db_session, test_user):
        """经验流水按 created_at 降序排列，limit 限制返回数量。

        防什么：list_events 如果没有排序，流水顺序随机，用户看不到
        最近的成长记录。
        """
        svc = GrowthService(db_session)
        # 造 3 条经验记录
        for i in range(3):
            svc.award(test_user.id, f"task:{i}:completed", "task.completed", 5,
                      label=f"任务{i}")

        events = svc.list_events(test_user.id, limit=2)
        assert len(events) == 2
        # 最新的在前（id 递增，created_at 也递增）
        assert events[0]["label"] == "任务2"
        assert events[1]["label"] == "任务1"
