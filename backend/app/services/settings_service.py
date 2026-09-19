# ============================================================
# 用户配置服务（PRD §15.11）
# ------------------------------------------------------------
# 定位：settings 是「用户级键值配置」的单一真相来源。此前设置页的 4 个
# 通知开关只是前端 ref()，刷新即失效；现在改为读写 settings 表。
#
# 设计取舍：
#   1. 值统一存字符串（与 Setting.value 的 Text 列一致），布尔用
#      'true'/'false'，避免引入 JSON 列带来迁移成本；
#   2. 读时「默认值 + 已存值」合并，保证新用户/新开关无需迁移即有值；
#   3. 写入前校验 key 格式，防止前端误传把整张表写脏（白名单 + 正则）。
# ============================================================
from __future__ import annotations

import re

from sqlalchemy.orm import Session

from app.core.exceptions import ValidationException
from app.core.logger import get_logger
from app.repositories import SettingRepository

# key 格式：小写字母开头，允许小写字母/数字/下划线，可用点号分层
KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z0-9_]+)*$")

# 已登记的配置项默认值。新增开关只需在此登记，读取端自动获得默认值。
DEFAULT_SETTINGS: dict[str, str] = {
    "notify.task": "true",     # 任务提醒
    "notify.review": "true",   # 复盘提醒
    "notify.system": "true",   # 系统通知
    "notify.sound": "false",   # 提示音
    # ---------- 工作区（三期 C · 可选功能） ----------
    # 默认关闭：别人的电脑文件夹结构与作者不同，目录结构必须由引导
    # 流程建立，不存在任何内置路径。noise_* 为逗号分隔的规则，可改。
    "workspace.enabled": "false",
    "workspace.terminal": "cmd",  # cmd / powershell / wt
    "workspace.noise_dirs": "node_modules,venv,.venv,__pycache__,.git,dist,build,.idea,.vscode,site-packages,.pytest_cache,.mypy_cache,.ruff_cache",
    "workspace.noise_exts": ".pyc,.pyo,.log,.tmp,.swp,.DS_Store,.egg-info",
    # ---------- AI 行程助理（移动端方案 M2） ----------
    # deepseek_key 存的是 encryption 加密后的密文，明文永不落库不回显
    "assistant.deepseek_key": "",
    "assistant.deepseek_model": "deepseek-chat",
}

TRUE_VALUES = {"true", "1", "yes", "on"}


logger = get_logger("settings")


class SettingsService:
    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id
        self.repo = SettingRepository(db)

    # ---------- 读 ----------

    def all(self) -> dict[str, str]:
        """返回「默认值 + 用户已存值」合并后的完整配置字典。"""
        values = dict(DEFAULT_SETTINGS)
        for row in self.repo.list_user(self.user_id):
            values[row.key] = row.value or ""
        return values

    def get(self, key: str) -> str | None:
        self._validate_key(key)
        row = self.repo.get_by_key(self.user_id, key)
        if row is not None:
            return row.value
        return DEFAULT_SETTINGS.get(key)

    def get_bool(self, key: str) -> bool:
        raw = (self.get(key) or "").strip().lower()
        return raw in TRUE_VALUES

    # ---------- 写 ----------

    def set(self, key: str, value: str) -> None:
        """单键写入便捷方法（内部仍走批量校验）。"""
        self.set_many({key: value})

    # ---------- 变更历史（F6.2） ----------

    HISTORY_LIMIT = 200

    def _record_history(self, key: str, old_value: str | None,
                        new_value: str | None) -> None:
        from app.models.settings_history import SettingHistory, mask_value

        if old_value == new_value:
            return
        self.db.add(SettingHistory(
            user_id=self.user_id, key=key,
            old_value=mask_value(key, old_value),
            new_value=mask_value(key, new_value),
        ))
        # 保留最近 200 条：超出即删最旧
        from sqlalchemy import delete, func, select

        total = self.db.scalar(
            select(func.count()).select_from(SettingHistory)
            .where(SettingHistory.user_id == self.user_id)
        ) or 0
        if total > self.HISTORY_LIMIT:
            oldest = self.db.scalars(
                select(SettingHistory)
                .where(SettingHistory.user_id == self.user_id)
                .order_by(SettingHistory.created_at.asc())
                .limit(total - self.HISTORY_LIMIT)
            ).all()
            for row in oldest:
                self.db.execute(delete(SettingHistory).where(SettingHistory.id == row.id))

    def history(self, limit: int = 50) -> list[dict]:
        from sqlalchemy import select

        from app.models.settings_history import SettingHistory

        rows = self.db.scalars(
            select(SettingHistory)
            .where(SettingHistory.user_id == self.user_id,
                   SettingHistory.deleted_at.is_(None))
            .order_by(SettingHistory.created_at.desc())
            .limit(min(limit, self.HISTORY_LIMIT))
        ).all()
        return [
            {"id": r.id, "key": r.key, "old_value": r.old_value,
             "new_value": r.new_value,
             "created_at": r.created_at.isoformat() if r.created_at else None}
            for r in rows
        ]

    def rollback(self, history_id: str) -> dict:
        """单 key 回滚到该记录之前的旧值（F6.2）。"""
        from sqlalchemy import select

        from app.models.settings_history import SettingHistory

        row = self.db.scalars(
            select(SettingHistory).where(
                SettingHistory.id == history_id,
                SettingHistory.user_id == self.user_id,
            )
        ).first()
        if row is None:
            raise ValidationException("历史记录不存在")
        # 脱敏值不可回滚（否则会把 *** 写回配置）
        if row.old_value is not None and row.old_value.endswith("***"):
            raise ValidationException("该记录含敏感值（已脱敏），不支持回滚")
        self.set_many({row.key: row.old_value or ""})
        return {"key": row.key, "restored": row.old_value}

    def set_many(self, values: dict[str, str]) -> dict[str, str]:
        """批量写入，返回写入后的完整配置字典。"""
        if not values:
            raise ValidationException("配置项不能为空")
        if len(values) > 100:
            raise ValidationException("单次最多写入 100 个配置项")

        for key, value in values.items():
            self._validate_key(key)
            if value is not None and len(str(value)) > 4000:
                raise ValidationException(f"配置项 {key} 的值过长")

        # 校验通过后再记历史（F6.2）：历史失败不影响本次写入
        for key, value in values.items():
            try:
                self._record_history(key, self.get(key), str(value))
            except Exception:
                logger.exception("设置历史记录失败: %s", key)

        for key, value in values.items():
            self.repo.upsert(self.user_id, key, str(value))
        return self.all()

    # ---------- 内部 ----------

    @staticmethod
    def _validate_key(key: str) -> None:
        if not isinstance(key, str) or not key:
            raise ValidationException("配置键不能为空")
        if len(key) > 100:
            raise ValidationException("配置键长度不能超过 100")
        if not KEY_PATTERN.match(key):
            raise ValidationException(f"非法的配置键: {key}")
        # 只允许已登记的配置项，避免任意键落库把表写脏
        if key not in DEFAULT_SETTINGS:
            raise ValidationException(f"未登记的配置项: {key}")
