# ============================================================
# 通用工具函数（跨模块复用）
# ============================================================
from __future__ import annotations

WEEKDAYS = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]


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
