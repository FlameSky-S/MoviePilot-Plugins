"""播出日历的月历网格构建。

**纯函数**：不 import 任何 `app.*`，可在裸机（无 MoviePilot 环境）直接单测。
把「网格怎么排、事件挂到哪一格」这类容易错日历边界的逻辑从 Vue 里搬出来，
前端只负责渲染。

网格约定：**周一为每周第一天**（中文习惯），覆盖与本月相交的整周 ——
所以至少有前导/后继补位格，`in_month=False` 的那些格必须照样挂事件，
否则跨月的播出会凭空消失。
"""

from __future__ import annotations

import calendar as _calendar
from datetime import date
from typing import Any, Dict, Iterable, List, Optional

WEEKDAY_HEADERS: List[str] = ["一", "二", "三", "四", "五", "六", "日"]


def _shift_month(year: int, month: int, delta: int) -> str:
    """取相邻月份的 `YYYY-MM`，自动跨年。"""
    index = year * 12 + (month - 1) + delta
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


def build_month_grid(
    year: int,
    month: int,
    events: Optional[Iterable[Dict[str, Any]]] = None,
    today: Optional[date] = None,
) -> Dict[str, Any]:
    """把事件铺进 `year-month` 的整月网格。

    返回 `{year, month, month_key, days, prev, next, weekday_headers, weeks, events_total}`；
    `weeks` 是「周 -> 7 个日格」，每格 `{date, day, in_month, is_today, events}`。

    - 落在网格之外的日期直接丢弃（`events_total` 只统计真的挂上去的）
    - 同一天多个事件按 `(title, tmdbid)` 排序，保证渲染顺序稳定
    """
    year, month = int(year), int(month)
    today = today or date.today()

    by_day: Dict[str, List[Dict[str, Any]]] = {}
    for event in events or []:
        if not event:
            continue
        key = str(event.get("date") or "")[:10]
        if len(key) != 10:
            continue
        by_day.setdefault(key, []).append(dict(event))
    for bucket in by_day.values():
        bucket.sort(key=lambda item: (str(item.get("title") or ""), int(item.get("tmdbid") or 0)))

    weeks: List[List[Dict[str, Any]]] = []
    attached = 0
    for week in _calendar.Calendar(firstweekday=0).monthdatescalendar(year, month):
        row: List[Dict[str, Any]] = []
        for day in week:
            key = day.isoformat()
            day_events = by_day.get(key, [])
            attached += len(day_events)
            row.append(
                {
                    "date": key,
                    "day": day.day,
                    "in_month": day.year == year and day.month == month,
                    "is_today": day == today,
                    "events": day_events,
                }
            )
        weeks.append(row)

    return {
        "year": year,
        "month": month,
        "month_key": f"{year:04d}-{month:02d}",
        "days": _calendar.monthrange(year, month)[1],
        "prev": _shift_month(year, month, -1),
        "next": _shift_month(year, month, 1),
        "weekday_headers": list(WEEKDAY_HEADERS),
        "weeks": weeks,
        "events_total": attached,
    }
