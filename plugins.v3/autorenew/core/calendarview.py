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
from typing import Any, Dict, Iterable, List, Optional, Tuple

WEEKDAY_HEADERS: List[str] = ["一", "二", "三", "四", "五", "六", "日"]


def _shift_month(year: int, month: int, delta: int) -> str:
    """取相邻月份的 `YYYY-MM`，自动跨年。"""
    index = year * 12 + (month - 1) + delta
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


def episode_code(season: int, episode: int) -> str:
    """`S02E01`（季/集都补零到两位）。"""
    return f"S{int(season):02d}E{int(episode):02d}"


def episode_label(season: int, start: int, end: int) -> str:
    """一集 `S02E01`；连续多集 `S02E01-E08`（尾号只写一次 E）。"""
    if int(start) == int(end):
        return episode_code(season, start)
    return f"{episode_code(season, start)}-E{int(end):02d}"


def merge_day_episodes(items: Optional[Iterable[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """把「同一部剧、同一季、同一天的集」合并成事件，按连续段拆开。

    Sonarr 的播出日历一天一格，同一天连播多集时用 `S02E01-E08` 表示。
    **只合并连续集号**：同一天出现 E01 和 E05（不连续）就拆成两个事件 ——
    合并成 `S02E01-E05` 会让人以为中间几集也在那天播。

    入参每项至少要有 `date` / `tmdbid` / `season` / `episode`；
    返回项额外带 `episode_start` / `episode_end` / `episode_count` /
    `episodes` / `episode_names` / `label`。
    """
    buckets: Dict[Tuple[int, int, str], List[Dict[str, Any]]] = {}
    for item in items or []:
        if not item:
            continue
        key_date = str(item.get("date") or "")[:10]
        if len(key_date) != 10:
            continue
        try:
            episode = int(item.get("episode"))
            season = int(item.get("season"))
        except (TypeError, ValueError):
            continue
        bucket = (int(item.get("tmdbid") or 0), season, key_date)
        row = dict(item)
        row["season"] = season
        row["episode"] = episode
        buckets.setdefault(bucket, []).append(row)

    events: List[Dict[str, Any]] = []
    for (tmdbid, season, key_date), rows in buckets.items():
        rows.sort(key=lambda row: row["episode"])
        run: List[Dict[str, Any]] = [rows[0]]
        for row in rows[1:]:
            if row["episode"] == run[-1]["episode"] + 1:
                run.append(row)
                continue
            events.append(_span_event(season, run))
            run = [row]
        events.append(_span_event(season, run))

    events.sort(key=lambda event: (event["date"], event["title"], event["episode_start"]))
    return events


def _span_event(season: int, run: List[Dict[str, Any]]) -> Dict[str, Any]:
    """一段连续集 -> 一个日历事件。"""
    first, last = run[0], run[-1]
    start, end = first["episode"], last["episode"]
    event = {key: value for key, value in first.items() if key != "episode"}
    event.update(
        {
            "season": season,
            "episode_start": start,
            "episode_end": end,
            "episode_count": len(run),
            "episodes": [row["episode"] for row in run],
            "episode_names": [row.get("name") for row in run if row.get("name")],
            "label": episode_label(season, start, end),
        }
    )
    return event


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
        bucket.sort(
            key=lambda item: (
                str(item.get("title") or ""),
                int(item.get("tmdbid") or 0),
                int(item.get("episode_start") or 0),
            )
        )

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
