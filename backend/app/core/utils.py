# ============================================================
# 通用工具函数（跨模块复用）
# ============================================================
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

WEEKDAYS = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]


def local_day_bounds_utc(day: date) -> tuple[datetime, datetime]:
    """本地「某一天」的 [起始, 结束) 边界，换算为 naive UTC。

    completed_at/created_at 等时间戳以 UTC 存库（models.base.utcnow），
    而统计口径是本地日期。直接用本地 naive 边界比较会错位一个时区
    （UTC+8 下凌晨 00:00-08:00 完成的任务会算错天）。
    """
    start_local = datetime.combine(day, time.min).astimezone()
    start = start_local.astimezone(timezone.utc).replace(tzinfo=None)
    end = start + timedelta(days=1)
    return start, end


def greeting_by_hour(hour: int) -> str:
    """根据小时返回问候语。"""
    if 0 <= hour < 6:
        return "夜深了"
    if 6 <= hour < 12:
        return "早上好"
    if 12 <= hour < 18:
        return "下午好"
    return "晚上好"


def format_date_cn(dt) -> str:
    """格式化日期为中文：2026年8月28日（跨平台，不依赖 strftime %-m）。"""
    return f"{dt.year}年{dt.month}月{dt.day}日"
