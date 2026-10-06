"""媒体库行解析 —— 纯函数，不 import `app.*`，可裸机单测。

宿主 `mediaserveritem` 表的**真实取值**（实测于 v3.1.0 + Plex，不是推测）：

| 列 | 真实值 |
| --- | --- |
| `item_type` | `"电影"` / `"电视剧"` —— **中文**，就是 `MediaType` 枚举值 |
| `media_source` | `"themoviedb"` / `None` |
| `media_id` | TMDB id，**字符串** |
| `seasoninfo` | **JSON 字符串**，形如 `{"1": [1, 2, 3], "2": [...]}`（季号 -> 集号列表） |

踩过的坑（两条都是实测撞出来的）：

1. 按 `tv` / `series` 过滤 `item_type` → **静默跳过全部剧集**，导入返回 0 条且不报错。
2. 把 `seasoninfo` 当 dict 用 → `isinstance(..., dict)` 恒假，季进度永远读到空。
"""

from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List, Mapping

from .models import MEDIA_TYPE_TV


def _get(row: Any, key: str, default: Any = None) -> Any:
    """同时兼容 dict 行与 ORM 对象行。"""
    if isinstance(row, Mapping):
        return row.get(key, default)
    return getattr(row, key, default)


def parse_seasoninfo(raw: Any) -> Dict[int, int]:
    """`seasoninfo` -> `{季号: 集数}`。

    S0 排除；JSON 字符串 / dict / 对象都能吃；坏数据一律当空，不抛异常。
    """
    if raw is None:
        return {}
    if isinstance(raw, (str, bytes)):
        text = raw.decode("utf-8", "ignore") if isinstance(raw, bytes) else raw
        text = text.strip()
        if not text:
            return {}
        try:
            raw = json.loads(text)
        except (TypeError, ValueError):
            return {}
    if not isinstance(raw, Mapping):
        return {}

    out: Dict[int, int] = {}
    for key, value in raw.items():
        try:
            season = int(key)
        except (TypeError, ValueError):
            continue
        if season <= 0:
            continue
        if isinstance(value, (list, tuple, set, Mapping)):
            out[season] = len(value)
        else:
            out[season] = 0
    return out


def library_candidates(
    rows: Iterable[Any], media_type: str = MEDIA_TYPE_TV
) -> List[Dict[str, Any]]:
    """`mediaserveritem` 行 -> 可追踪的剧集候选。

    返回 `[{tmdbid, title, year, season, seasons}]`；`season` 是库内最高季。
    不可用的行（非剧集、无标题、media_id 不是数字）直接跳过。
    """
    out: List[Dict[str, Any]] = []
    for row in rows or []:
        if str(_get(row, "item_type", "") or "").strip() != media_type:
            continue
        title = _get(row, "title")
        media_id = _get(row, "media_id")
        if not title or media_id in (None, ""):
            continue
        try:
            tmdbid = int(media_id)
        except (TypeError, ValueError):
            continue
        seasons = parse_seasoninfo(_get(row, "seasoninfo"))
        out.append(
            {
                "tmdbid": tmdbid,
                "title": str(title),
                "year": _get(row, "year"),
                "season": max(seasons) if seasons else 1,
                "seasons": seasons,
            }
        )
    return out
