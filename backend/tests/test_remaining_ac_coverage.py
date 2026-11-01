# ============================================================
# 剩余 A/C 类覆盖清理（Phase16-C · 107 missed → ≤85）
#
# 来源：task-61 基线 term-missing（49 个模块有 1-5 行缺口）。挑选**可稳定触发**
# 的分支补齐；B 类不可达/D 类破坏性在报告分类表中给证据跳过。本文件覆盖：
#   · 仓库层语义查询：folder / diary / sop / prompt / skill / pet / avatar /
#     notification / document / study_time / base（create_many 空集 + commit）/
#     task（project_id 过滤）；
#   · document_service：删除文件夹失败 rollback、删除文档清反向链接、
#     get_document、_folder_name(None) 收集箱兜底；
#   · conversation_service：AI 流式失败降级（错误事件 + 占位消息 + tokens=0）、
#     _estimate_tokens 空文本；
#   · learning_service：SM-2「忘记」重置（quality<3）与 EF 下限 1.3 钳制、
#     第三次复习 interval 计算；
#   · life_service：习惯日历 12 月分支、日记 identity 归属校验；
#   · settings_service：历史记录失败不阻断写入；
#   · security_service：审计修剪失败被吞（业务不中断）；
#   · identity_service：color_token 校验（# 色值 / 非法 slug）；
#   · growth_service：exp<=0 直接返回未结算；
#   · task_service：daily 未来基准、weekly 无匹配日 target=None 跳过；
#   · avatar_service：update_config 无配置行时自动创建；
#   · encryption：rotate 写密钥环 OSError 被吞（换钥仍成功）；
#   · event_bus：失败率窗口无记录/全部过期 → None；
#   · api/rules 命中领域分支、api/assets 项目记忆列表、api/security 加密不可用。
# ============================================================
from __future__ import annotations

import asyncio
import time
from collections import deque
from datetime import date

import pytest

from app.api import security as security_api
from app.core.encryption import EncryptionManager
from app.core.event_bus import EventBus
from app.core.exceptions import ValidationException
from app.repositories.avatar_repo import AvatarInspirationRepository, AvatarMemoryRepository
from app.repositories.diary_repo import DiaryRepository
from app.repositories.document_repo import DocumentRepository
from app.repositories.folder_repo import FolderRepository
from app.repositories.habit_repo import HabitRepository
from app.repositories.notification_repo import NotificationRepository
from app.repositories.pet_repo import PetAvatarRepository
from app.repositories.project_repo import ProjectRepository
from app.repositories.prompt_repo import PromptRepository
from app.repositories.skill_repo import SkillRepository
from app.repositories.sop_repo import SOPRepository
from app.repositories.study_time_repo import StudyTimeRepository
from app.repositories.task_repo import TaskRepository
from app.repositories.flashcard_repo import FlashcardRepository
from app.repositories.conversation_repo import ConversationRepository, MessageRepository
from app.schemas.avatar import UpdateConfigRequest
from app.schemas.conversation import SendMessageRequest
from app.schemas.document import CreateDocumentRequest
from app.schemas.learning import ReviewSubmitRequest
from app.schemas.life import CreateDiaryRequest
from app.services import conversation_service as conv_service_mod
from app.services import security_service as security_svc_mod
from app.services import vault_service
from app.services.avatar_service import AvatarService
from app.services.conversation_service import ConversationService
from app.services.document_service import DocumentService
from app.services.growth_service import GrowthService
from app.services.identity_service import IdentityService
from app.services.learning_service import LearningService
from app.services.life_service import LifeService
from app.services.settings_service import SettingsService
from app.services.task_service import TaskService
from tests.factories import (
    make_avatar_memory,
    make_diary,
    make_document,
    make_sop,
    make_task,
)


def _boom(*_args, **_kwargs):
    raise RuntimeError("probe: 故障注入")


# ================================================================
# 一、Repository 层：语义查询 / 空集 / 简单过滤
# ================================================================
class TestRepositoryQueries:
    def test_folder_repo_roots_children_inbox_and_count(self, db_session, test_user):
        repo = FolderRepository(db_session)
        inbox = repo.create(user_id=test_user.id, name="收集箱", is_inbox=True)
        root = repo.create(user_id=test_user.id, name="根目录", sort_order=1)
        child = repo.create(user_id=test_user.id, name="子目录", parent_id=root.id)
        make_document(db_session, test_user.id, title="夹内文档", folder_id=root.id)
        db_session.commit()

        assert [f.id for f in repo.list_roots(test_user.id)] == [inbox.id, root.id]
        assert [f.id for f in repo.list_children(test_user.id, root.id)] == [child.id]
        assert {f.id for f in repo.list_by_user(test_user.id)} == {
            inbox.id, root.id, child.id
        }
        assert repo.get_inbox(test_user.id).id == inbox.id
        assert repo.count_documents(root.id) == 1

    def test_diary_repo_dimension_and_date_lookup(self, db_session, test_user):
        repo = DiaryRepository(db_session)
        diary = make_diary(db_session, test_user.id, dimension="work",
                           diary_date=date(2026, 1, 2), title="工作日日记")
        make_diary(db_session, test_user.id, dimension="life",
                   diary_date=date(2026, 1, 3), title="生活日记")
        db_session.commit()

        found = repo.list_by_dimension(test_user.id, "work")
        assert [d.id for d in found] == [diary.id]
        assert repo.get_by_date(test_user.id, date(2026, 1, 2)).id == diary.id
        assert repo.get_by_date(test_user.id, date(2026, 1, 5)) is None

    def test_sop_prompt_skill_repos_category_filters(self, db_session, test_user):
        make_sop(db_session, test_user.id, name="SOP-A", category="写作")
        prompt = PromptRepository(db_session).create(
            user_id=test_user.id, name="Prompt-A", category="写作")
        skill = SkillRepository(db_session).create(
            user_id=test_user.id, name="Skill-A", proficiency="expert")
        db_session.commit()

        assert [s.name for s in SOPRepository(db_session).list_by_category(
            test_user.id, "写作")] == ["SOP-A"]
        assert [p.id for p in PromptRepository(db_session).list_by_category(
            test_user.id, "写作")] == [prompt.id]
        assert [s.id for s in SkillRepository(db_session).list_by_proficiency(
            test_user.id, "expert")] == [skill.id]
        assert [s.id for s in SkillRepository(db_session).list_by_user(
            test_user.id)] == [skill.id]

    def test_pet_avatar_repo_get_active(self, db_session, test_user):
        repo = PetAvatarRepository(db_session)
        inactive = repo.create(user_id=test_user.id, name="未启用", is_active=False)
        active = repo.create(user_id=test_user.id, name="正在用", is_active=True)
        db_session.commit()

        assert repo.get_active(test_user.id).id == active.id
        assert repo.get_active(test_user.id).id != inactive.id

    def test_avatar_repo_memory_type_and_inspiration_batch(self, db_session, test_user):
        make_avatar_memory(db_session, test_user.id, memory_type="event", title="事件")
        make_avatar_memory(db_session, test_user.id, memory_type="profile", title="画像")
        inspiration = AvatarInspirationRepository(db_session).create(
            user_id=test_user.id, title="灵感A", batch_id="batch-p16")
        db_session.commit()

        events = AvatarMemoryRepository(db_session).list_by_type(test_user.id, "event")
        assert [m.title for m in events] == ["事件"]
        batch = AvatarInspirationRepository(db_session).list_by_batch("batch-p16")
        assert [i.id for i in batch] == [inspiration.id]

    def test_notification_repo_count_unread(self, db_session, test_user):
        repo = NotificationRepository(db_session)
        repo.create(user_id=test_user.id, type="info", title="未读通知", content="x")
        read = repo.create(user_id=test_user.id, type="info", title="已读通知", content="y")
        db_session.commit()
        repo.update(read, is_read=True)
        db_session.commit()

        assert repo.count_unread(test_user.id) == 1

    def test_document_repo_find_by_title_and_empty_title_map(self, db_session, test_user):
        doc = make_document(db_session, test_user.id, title="唯一标题文档")
        db_session.commit()
        repo = DocumentRepository(db_session)

        assert repo.find_by_title(test_user.id, "唯一标题文档").id == doc.id
        assert repo.find_by_title(test_user.id, "不存在的标题") is None
        assert repo.title_id_map(test_user.id, []) == {}      # 空标题列表短路

    def test_base_repo_create_many_empty_and_commit(self, db_session, test_user):
        repo = TaskRepository(db_session)
        assert repo.create_many([]) == []                      # 空集不产生 SQL
        make_task(db_session, test_user.id, title="待提交任务")
        assert repo.commit() is None                           # 显式提交可用

    def test_task_repo_project_id_filter(self, db_session, test_user):
        project = ProjectRepository(db_session).create(user_id=test_user.id, name="过滤项目")
        db_session.commit()
        task = make_task(db_session, test_user.id, title="项目内任务", project_id=project.id)
        make_task(db_session, test_user.id, title="无项目任务")
        db_session.commit()

        rows = TaskRepository(db_session).list_paginated(
            test_user.id, project_id=project.id)
        assert [t.id for t in rows] == [task.id]

    def test_study_time_repo_list_and_count(self, db_session, test_user):
        repo = StudyTimeRepository(db_session)
        log = repo.create(user_id=test_user.id, duration=30, logged_date=date.today())
        db_session.commit()

        assert [row.id for row in repo.list_by_user(test_user.id)] == [log.id]
        assert repo.count_by_user(test_user.id) == 1


# ================================================================
# 二、document_service：回滚 / 反向链接 / 兜底
# ================================================================
class TestDocumentServiceBranches:
    def test_delete_folder_failure_rolls_back_and_reraises(self, db_session, test_user, monkeypatch):
        folder = FolderRepository(db_session).create(user_id=test_user.id, name="待删文件夹")
        doc = make_document(db_session, test_user.id, title="夹内文档", folder_id=folder.id)
        db_session.commit()
        svc = DocumentService(db_session)
        monkeypatch.setattr(svc.folder_repo, "delete", _boom)

        with pytest.raises(RuntimeError, match="probe: 故障注入"):
            svc.delete_folder(test_user.id, folder.id)

        db_session.expire_all()
        assert FolderRepository(db_session).get(folder.id) is not None
        assert DocumentRepository(db_session).get(doc.id).folder_id == folder.id

    def test_delete_document_cleans_outgoing_backlinks(self, db_session, test_user):
        make_document(db_session, test_user.id, title="目标文档", content="内容")
        db_session.commit()
        svc = DocumentService(db_session)
        source = svc.create_document(
            test_user.id,
            CreateDocumentRequest(title="来源文档", content="见 [[目标文档]]"),
        )
        assert svc.link_repo.list_sources(source.id)            # 出链已建立
        assert svc.get_document(test_user.id, source.id).title == "来源文档"

        svc.delete_document(test_user.id, source.id)

        assert svc.link_repo.list_sources(source.id) == []      # 删除时清理出链

    def test_folder_name_falls_back_to_inbox_label(self, db_session):
        svc = DocumentService(db_session)
        assert svc._folder_name(None) == "收集箱"
        assert svc._folder_name("ghost-folder") == "收集箱"


# ================================================================
# 三、conversation_service：AI 流式失败降级
# ================================================================
class TestConversationServiceFailurePath:
    def test_stream_ai_failure_yields_error_and_saves_placeholder(
        self, db_session, test_user, monkeypatch
    ):
        conv = ConversationRepository(db_session).create(user_id=test_user.id, title="故障对话")

        class _FakeClient:
            async def stream_chat(self, messages, temperature=0.7):
                raise RuntimeError("模型挂了")
                yield ""  # pragma: no cover - 让函数成为 async generator

        monkeypatch.setattr(conv_service_mod, "get_llm_client", lambda user: _FakeClient())
        svc = ConversationService(db_session, test_user)

        async def _collect():
            return [event async for event in svc.stream_messages(
                conv.id, SendMessageRequest(content="你好"))]

        events = asyncio.run(_collect())
        assert events == [{"type": "error", "error": "模型挂了"}]

        msgs = MessageRepository(db_session).list_conversation(conv.id)
        assert [m.role for m in msgs] == ["user", "assistant"]
        assert msgs[1].content == "[AI 服务异常] 模型挂了"
        assert msgs[1].tokens == 0
        # _estimate_tokens 空文本分支
        assert ConversationService._estimate_tokens([], "") == 0


# ================================================================
# 四、learning_service：SM-2 边界
# ================================================================
class TestLearningServiceSm2:
    def test_forgot_resets_repetition_and_clamps_ease_factor(self, db_session, test_user):
        card = FlashcardRepository(db_session).create(
            user_id=test_user.id, front="问", back="答",
            ef=1.4, repetition=2, interval=10, next_review=date.today(),
        )
        db_session.commit()

        result = LearningService(db_session).submit_review(
            test_user.id, card.id, ReviewSubmitRequest(quality=1))

        assert result["ef"] == 1.3          # EF 下限钳制（1.4 - 0.8 = 0.6 → 1.3）
        assert result["repetition"] == 0    # 忘记 → 重置
        assert result["interval"] == 1

    def test_third_successful_review_multiplies_interval_by_ef(self, db_session, test_user):
        card = FlashcardRepository(db_session).create(
            user_id=test_user.id, front="问2", back="答2",
            ef=2.5, repetition=2, interval=10, next_review=date.today(),
        )
        db_session.commit()

        result = LearningService(db_session).submit_review(
            test_user.id, card.id, ReviewSubmitRequest(quality=5))

        assert result["repetition"] == 3
        assert result["interval"] == round(10 * 2.6)   # quality=5 → EF 升至 2.6


# ================================================================
# 五、life_service：12 月日历 / 日记身份校验
# ================================================================
class TestLifeServiceBranches:
    def test_habit_calendar_december_includes_31_days(self, db_session, test_user):
        habit = HabitRepository(db_session).create(user_id=test_user.id, name="跑步")
        db_session.commit()

        calendar = LifeService(db_session).get_habit_calendar(habit.id, 2026, 12)

        assert calendar["month"] == 12
        assert len(calendar["calendar"]) - date(2026, 12, 1).weekday() == 31
        assert calendar["total_checkins"] == 0

    def test_create_diary_with_foreign_identity_is_rejected(self, db_session, test_user):
        svc = LifeService(db_session)
        with pytest.raises(ValidationException, match="身份不存在"):
            svc.create_diary(test_user.id, CreateDiaryRequest(
                content="越权身份", identity_id="ghost-identity"))


# ================================================================
# 六、settings / security / identity / growth / task / avatar / encryption / event_bus
# ================================================================
class TestServiceStragglers:
    def test_settings_history_failure_does_not_block_write(
        self, db_session, test_user, monkeypatch, caplog
    ):
        import logging

        svc = SettingsService(db_session, test_user.id)
        monkeypatch.setattr(svc, "_record_history", _boom)
        with caplog.at_level(logging.ERROR):
            values = svc.set_many({"notify.task": "false"})

        assert values["notify.task"] == "false"     # 写入仍成功
        assert "设置历史记录失败: notify.task" in caplog.text

    def test_audit_trim_failure_is_swallowed(self, db_session, test_user, monkeypatch):
        from app.repositories.audit_repo import AuditLogRepository

        monkeypatch.setattr(AuditLogRepository, "stale_ids", _boom)
        security_svc_mod.audit(db_session, test_user.id, "auth.login", ok=True)

        rows = AuditLogRepository(db_session).list_user(test_user.id)
        assert len(rows) == 1                       # 审计仍写入，修剪失败不影响

    @pytest.mark.parametrize(("token", "message"), [
        ("#ff0000", "color_token 必须是设计令牌名"),
        ("UPPER", "非法的 color_token"),
    ])
    def test_identity_color_token_validation(self, token, message):
        with pytest.raises(ValidationException, match=message):
            IdentityService._validate_color(token)

    def test_growth_award_non_positive_exp_is_noop(self, db_session, test_user):
        result = GrowthService(db_session).award(
            test_user.id, "p16:noop", "task.completed", exp=0)

        assert result == {"granted": False, "exp": 0, "level_up": False,
                          "level": None, "skill_cat_ids": []}

    def test_daily_future_base_and_weekly_no_match_are_skipped(self, db_session, test_user):
        today = date.today()
        assert TaskService._next_occurrence(today, today, "daily", {}) == today
        future = today.fromordinal(today.toordinal() + 100)
        assert TaskService._next_occurrence(future, today, "daily", {}) == future

        make_task(db_session, test_user.id, title="未来周任务", due_date=future,
                  recurrence={"type": "weekly", "days": []})
        db_session.commit()
        assert TaskService(db_session).generate_recurring_instances(test_user.id) == 0

    def test_avatar_update_config_creates_missing_row(self, db_session, other_user):
        svc = AvatarService(db_session)
        updated = svc.update_config(other_user.id, UpdateConfigRequest(persona_name="新分身"))

        assert updated["persona_name"] == "新分身"
        assert updated["user_id"] == other_user.id      # 自动建行后再更新

    def test_rotate_keyring_write_oserror_is_swallowed(self, tmp_path, monkeypatch):
        from pathlib import Path

        def _disk_full(*_args, **_kwargs):
            raise OSError("disk full")

        manager = EncryptionManager(tmp_path)
        token_before = manager.encrypt("换钥前")
        monkeypatch.setattr(Path, "write_text", _disk_full)

        manager.rotate_key()                            # 不得因写密钥环失败而抛

        assert manager.decrypt(manager.encrypt("换钥后")) == "换钥后"
        assert manager.decrypt(token_before) == "换钥前"

    def test_window_failure_rate_returns_none_for_missing_and_stale(self):
        assert EventBus._window_failure_rate("p16.no.such.event") is None
        stale_key = "p16.stale.event"
        EventBus._window[stale_key] = deque([(time.time() - 3600, True)])
        try:
            assert EventBus._window_failure_rate(stale_key) is None
        finally:
            EventBus._window.pop(stale_key, None)


# ================================================================
# 七、API 层剩余单行分支
# ================================================================
class TestApiStragglers:
    def test_rules_preview_matched_domain_branch(self, client):
        r = client.post("/api/v1/rules/preview", json={"text": "我想学雅思"})
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        assert data["matched"] is True
        assert data["fallback"] is False
        assert data["domain_key"] == "ielts"
        assert data["plan_count"] > 0

    def test_assets_memories_list_endpoint(self, client):
        r = client.get("/api/v1/assets/memories")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["code"] == 0
        assert body["data"]["total"] == 0

    def test_security_decrypt_without_encryption_returns_500_envelope(
        self, client, default_user_id, monkeypatch
    ):
        vault_service._session_keys[default_user_id] = b"unlocked"
        monkeypatch.setattr(security_api, "get_encryption", lambda: None)
        try:
            r = client.post("/api/v1/security/decrypt", json={"token": "abc"})
        finally:
            vault_service._session_keys.pop(default_user_id, None)

        assert r.status_code == 500
        body = r.json()
        assert body["code"] == 5000
        assert "加密功能不可用" in body["message"]
