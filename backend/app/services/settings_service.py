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
}

TRUE_VALUES = {"true", "1", "yes", "on"}


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
