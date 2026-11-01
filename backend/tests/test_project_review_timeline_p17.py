# ============================================================
# D-65 回归（2026-11-01）：项目时间线 / 导出访问 Review.title / content
#
# 缺陷：Review 模型只有 data(JSON) 列，没有 title/content；project_service 的
# timeline() 与 export() 直接 r.title / r.content → 项目一旦关联复盘，
# GET 项目时间线 / 导出 必抛 AttributeError 500。
# 修复：从 data 派生摘要（gains / key_gains / monthly_summary / completed_tasks），
# 无可用摘要时以「<date> 复盘」兜底；导出正文按字段生成 Markdown。
# ============================================================
from __future__ import annotations

from datetime import date

from app.schemas.project import ProjectCreate
from app.services.project_service import ProjectService
from tests.factories import make_review


def _make_project(name: str = "复盘项目") -> ProjectCreate:
    return ProjectCreate(
        name=name, description="项目描述", color="#ff0000",
        status="active", due_date=date(2026, 12, 31),
    )


class TestProjectReviewTimeline:
    def test_timeline_derives_review_title_from_gains(self, db_session, test_user):
        svc = ProjectService(db_session)
        project = svc.create(test_user.id, _make_project())
        review = make_review(
            db_session, test_user.id,
            data={"gains": "学会了 SQLAlchemy 2.1 升级\n第二行不该出现在标题"},
        )
        review.project_id = project["id"]
        db_session.commit()

        events = svc.timeline(test_user.id, project["id"])
        review_events = [e for e in events if e["type"] == "review"]

        assert len(review_events) == 1, events
        assert "学会了 SQLAlchemy 2.1 升级" in review_events[0]["title"]
        assert "\n" not in review_events[0]["title"]
        assert review_events[0]["icon"] == "refresh"

    def test_timeline_review_without_known_summary_falls_back_to_date(self, db_session, test_user):
        svc = ProjectService(db_session)
        project = svc.create(test_user.id, _make_project())
        review = make_review(db_session, test_user.id, data={"mood": 4})
        review.project_id = project["id"]
        db_session.commit()

        events = svc.timeline(test_user.id, project["id"])
        titles = [e["title"] for e in events if e["type"] == "review"]

        assert titles == [f"复盘记录：{date.today()} 复盘"], titles

    def test_export_review_fields_are_derived_from_data(self, db_session, test_user):
        svc = ProjectService(db_session)
        project = svc.create(test_user.id, _make_project())
        review = make_review(
            db_session, test_user.id,
            data={
                "gains": "收获A",
                "completed_tasks": "完成了迁移",
                "tomorrow_plan": "计划B",
                "reflections": [{"question": "Q1 做得好吗", "answer": "A1 不错"}],
            },
        )
        review.project_id = project["id"]
        db_session.commit()

        exported = svc.export(test_user.id, project["id"])
        reviews = exported["reviews"]

        assert len(reviews) == 1
        assert "收获A" in reviews[0]["title"]
        content = reviews[0]["content"]
        assert "## 收获\n收获A" in content
        assert "计划B" in content
        assert "Q1 做得好吗" in content and "A1 不错" in content
        assert reviews[0]["review_date"] == str(date.today())

    def test_timeline_handles_multiple_review_types_without_attribute_error(self, db_session, test_user):
        svc = ProjectService(db_session)
        project = svc.create(test_user.id, _make_project())
        weekly = make_review(db_session, test_user.id, type_="weekly", data={"key_gains": "周收获"})
        monthly = make_review(
            db_session, test_user.id, type_="monthly",
            review_date=date(2026, 10, 31), data={"monthly_summary": "十月总结"},
        )
        weekly.project_id = monthly.project_id = project["id"]
        db_session.commit()

        events = svc.timeline(test_user.id, project["id"])
        titles = sorted(e["title"] for e in events if e["type"] == "review")

        assert len(titles) == 2
        assert any("周收获" in t for t in titles)
        assert any("十月总结" in t for t in titles)
