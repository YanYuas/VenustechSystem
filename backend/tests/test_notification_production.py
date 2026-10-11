# ============================================================
# NotificationService 生产级测试（原缺失模块，本轮补齐）
#
# 通知是「30s 轮询必达」端点，正确性直接影响未读红点：
# 列表 / 未读过滤 / 分页 / 统计 / 单条已读 / 全部已读 / 越权。
# ============================================================
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.exceptions import NotFoundException
from app.schemas.notification import CreateNotificationRequest
from app.services.notification_service import NotificationService
from tests.factories import count_rows


def _svc(db, user_id: str) -> NotificationService:
    return NotificationService(db, user_id)


def _create(db, user_id: str, title: str = "通知", ntype: str = "info", content=None):
    return _svc(db, user_id).create(
        CreateNotificationRequest(type=ntype, title=title, content=content)
    )


class TestCreateAndList:
    """创建与列表。"""

    def test_create_persists_to_db(self, db_session, test_user):
        """创建通知后查库核对字段（类型/标题/未读标记）。"""
        out = _create(db_session, test_user.id, title="任务已完成", ntype="success", content="详情")
        assert count_rows(db_session, "notifications", user_id=test_user.id) == 1

        from app.models.notification import Notification
        row = db_session.get(Notification, out.id)
        assert row.title == "任务已完成"
        assert row.type == "success"
        assert row.content == "详情"
        assert row.is_read is False
        assert row.read_at is None

    def test_list_returns_only_own_notifications(self, db_session, test_user, other_user):
        """列表只返回本人通知（越权隔离）。"""
        _create(db_session, test_user.id, title="我的")
        _create(db_session, other_user.id, title="别人的")
        items = _svc(db_session, test_user.id).list()
        assert [n.title for n in items] == ["我的"]

    def test_list_unread_only_filters(self, db_session, test_user):
        """unread_only=True 只返回未读。"""
        a = _create(db_session, test_user.id, title="A")
        _create(db_session, test_user.id, title="B")
        _svc(db_session, test_user.id).mark_read(a.id, read=True)

        unread = _svc(db_session, test_user.id).list(unread_only=True)
        assert [n.title for n in unread] == ["B"]
        assert len(_svc(db_session, test_user.id).list()) == 2

    def test_list_pagination(self, db_session, test_user):
        """分页：page_size 截断、page 越界返回空、总数不受影响。"""
        for i in range(5):
            _create(db_session, test_user.id, title=f"N{i}")
        page1 = _svc(db_session, test_user.id).list(page=1, page_size=2)
        assert len(page1) == 2
        far = _svc(db_session, test_user.id).list(page=99, page_size=2)
        assert far == []

    def test_list_newest_first(self, db_session, test_user):
        """列表按创建时间倒序（最新的在最前）。"""
        _create(db_session, test_user.id, title="旧")
        _create(db_session, test_user.id, title="新")
        titles = [n.title for n in _svc(db_session, test_user.id).list()]
        assert titles[0] == "新"


class TestStats:
    """统计端点。"""

    def test_stats_counts_total_and_unread(self, db_session, test_user):
        """total 计全部、unread 计未读。"""
        a = _create(db_session, test_user.id)
        _create(db_session, test_user.id)
        _create(db_session, test_user.id)
        _svc(db_session, test_user.id).mark_read(a.id, read=True)

        st = _svc(db_session, test_user.id).stats()
        assert st.total == 3
        assert st.unread == 2

    def test_stats_zero_when_empty(self, db_session, test_user):
        """空数据时统计全 0（不得因 COALESCE 缺失返回 None）。"""
        st = _svc(db_session, test_user.id).stats()
        assert st.total == 0 and st.unread == 0

    def test_stats_ignores_other_users(self, db_session, test_user, other_user):
        """统计不串用户。"""
        _create(db_session, test_user.id)
        _create(db_session, other_user.id)
        _create(db_session, other_user.id)
        assert _svc(db_session, test_user.id).stats().total == 1


class TestMarkRead:
    """单条已读 / 全部已读。"""

    def test_mark_read_sets_flag_and_timestamp(self, db_session, test_user):
        """标记已读写入 is_read 与 read_at。"""
        out = _create(db_session, test_user.id)
        res = _svc(db_session, test_user.id).mark_read(out.id, read=True)
        assert res.is_read is True
        assert res.read_at is not None

        from app.models.notification import Notification
        row = db_session.get(Notification, out.id)
        assert row.is_read is True
        assert row.read_at is not None

    def test_mark_unread_clears_timestamp(self, db_session, test_user):
        """标记未读时 read_at 应被清空（否则出现「未读却有已读时间」的脏状态）。"""
        out = _create(db_session, test_user.id)
        _svc(db_session, test_user.id).mark_read(out.id, read=True)
        res = _svc(db_session, test_user.id).mark_read(out.id, read=False)
        assert res.is_read is False
        assert res.read_at is None

    def test_mark_read_unknown_id_raises(self, db_session, test_user):
        """不存在的通知 id 报 NotFound。"""
        with pytest.raises(NotFoundException):
            _svc(db_session, test_user.id).mark_read("no-such-id", read=True)

    def test_mark_read_cannot_touch_other_user(self, db_session, test_user, other_user):
        """不能把别人的通知标记为已读（越权）。"""
        other = _create(db_session, other_user.id, title="别人的")
        with pytest.raises(NotFoundException):
            _svc(db_session, test_user.id).mark_read(other.id, read=True)
        # 查库确认别人的通知未被改动
        from app.models.notification import Notification
        assert db_session.get(Notification, other.id).is_read is False

    def test_mark_all_read_counts_and_is_idempotent(self, db_session, test_user):
        """全部已读返回本次标记数；重复调用返回 0。"""
        for _ in range(3):
            _create(db_session, test_user.id)
        svc = _svc(db_session, test_user.id)
        assert svc.mark_all_read() == 3
        assert svc.stats().unread == 0
        assert svc.mark_all_read() == 0

    def test_mark_all_read_scoped_to_user(self, db_session, test_user, other_user):
        """全部已读只影响本人，不碰别人的通知。"""
        _create(db_session, test_user.id)
        _create(db_session, other_user.id)
        _svc(db_session, test_user.id).mark_all_read()
        assert _svc(db_session, other_user.id).stats().unread == 1


class TestCreateValidation:
    """创建入参校验（Schema 层）。"""

    def test_rejects_overlong_title(self):
        """标题超过 200 字被 Pydantic 拒绝。

        断言具体异常类型（ValidationError）而非宽泛的 Exception：
        后者连"函数根本没跑通、抛了 TypeError"都会算通过。
        并补一条边界值：200 字必须放行 —— 否则是"过严"，同样算缺陷。
        """
        with pytest.raises(ValidationError):
            CreateNotificationRequest(type="info", title="x" * 201)
        assert CreateNotificationRequest(type="info", title="x" * 200).title == "x" * 200

    def test_rejects_invalid_type(self):
        """type 只允许 info/success/warning/error（Literal 约束）。"""
        with pytest.raises(ValidationError):
            CreateNotificationRequest(type="urgent", title="t")
        for ok in ("info", "success", "warning", "error"):
            assert CreateNotificationRequest(type=ok, title="t").type == ok
