"""crontab 表达式 -> 中文自然语言（纯函数，可裸机单测）。

只描述「人真的会配」的那几种形态；**认不出来的表达式如实回退**成逐字段说明 ——
猜错的自然语言比裸表达式更误导，所以这里宁可说「分钟 0；小时 */6；…」。

覆盖：`*`、`*/n`、单值、逗号列表、`a-b` 区间（日/月/周/小时）。
"""

from __future__ import annotations

from typing import List, Optional, Tuple

WEEKDAY_NAMES: List[str] = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"]


def _each(field: str) -> Optional[int]:
    """`*/n` -> n；其它返回 None。"""
    if not field.startswith("*/"):
        return None
    try:
        step = int(field[2:])
    except ValueError:
        return None
    return step if step > 0 else None


def _single(field: str) -> Optional[int]:
    try:
        return int(field)
    except (TypeError, ValueError):
        return None


def _int_list(field: str) -> Optional[List[int]]:
    out: List[int] = []
    for chunk in str(field).split(","):
        value = _single(chunk)
        if value is None:
            return None
        out.append(value)
    return out or None


def _span(field: str) -> Optional[Tuple[int, int]]:
    """`a-b` -> (a, b)；其它返回 None。"""
    if "-" not in field:
        return None
    low, _, high = field.partition("-")
    start, end = _single(low), _single(high)
    if start is None or end is None:
        return None
    return start, end


def _hours(step: int) -> List[int]:
    return list(range(0, 24, step))


def _clock(hour: int, minute: int) -> str:
    return f"{hour:02d}:{minute:02d}"


def _time_text(minute: str, hour: str) -> Optional[str]:
    """「时间」那一半是什么意思；认不出来返回 None。"""
    if hour == "*":
        if minute == "*":
            return "每分钟"
        step = _each(minute)
        if step:
            return f"每 {step} 分钟"
        mins = _int_list(minute)
        if not mins:
            return None
        if len(mins) == 1:
            return f"每小时的第 {mins[0]} 分"
        return "每小时的第 " + "、".join(str(m) for m in mins) + " 分"

    step = _each(hour)
    if step:
        stamps = "、".join(str(h) for h in _hours(step))
        mins = _int_list(minute)
        if not mins:
            return None
        return (
            f"每 {step} 小时一次（{stamps} 点的第 "
            + "、".join(str(m) for m in mins)
            + " 分）"
        )

    hours = _int_list(hour)
    if hours:
        mins = _int_list(minute)
        if not mins:
            return None
        return "、".join(_clock(h, m) for h in hours for m in mins)

    span = _span(hour)
    if span:
        mins = _int_list(minute)
        if not mins:
            return None
        low, high = span
        return "、".join(
            f"{low:02d}:{m:02d}–{high:02d}:{m:02d}" for m in mins
        )

    return None


def _day_text(dom: str, month: str, dow: str) -> Optional[str]:
    """「哪一天」那一半是什么意思；认不出来返回 None。"""
    if month != "*":
        months = _int_list(month)
        if not months:
            return None
        month_text = "、".join(f"{m} 月" for m in months)
        if dom == "*":
            return f"每年 {month_text}的每一天"
        days = _int_list(dom)
        if not days:
            return None
        return f"每年 {month_text}" + "、".join(f"{d} 日" for d in days)

    if dom != "*":
        days = _int_list(dom)
        if days:
            return "每月 " + "、".join(f"{d} 日" for d in days)
        span = _span(dom)
        if span:
            return f"每月 {span[0]} 到 {span[1]} 日"
        return None

    if dow != "*":
        if dow in ("0", "7"):
            return "每周日"
        names = _int_list(dow)
        if names:
            return "每" + "、".join(WEEKDAY_NAMES[d % 7] for d in names)
        span = _span(dow)
        if span:
            return f"每{WEEKDAY_NAMES[span[0] % 7]}到{WEEKDAY_NAMES[span[1] % 7]}"
        return None

    return "每天"


def describe_cron(expr: str) -> str:
    """5 段 crontab -> 一句中文。

    非法/认不出的输入返回「逐字段说明」或空串（调用方自行回落展示原表达式）。
    """
    fields = str(expr or "").strip().split()
    if len(fields) != 5:
        return ""
    minute, hour, dom, month, dow = fields
    time_text = _time_text(minute, hour)
    day_text = _day_text(dom, month, dow)
    if time_text is None or day_text is None:
        return f"分钟 {minute}；小时 {hour}；日 {dom}；月 {month}；星期 {dow}"
    if day_text == "每天" and time_text.startswith("每"):
        # 「每 6 小时」「每分钟」本身已跨天，再套「每天」反而别扭
        return time_text
    joiner = "，" if time_text.startswith("每") else " "
    return f"{day_text}{joiner}{time_text}"
