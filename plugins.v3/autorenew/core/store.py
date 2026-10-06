"""名单持久化 —— 落在宿主 `plugindata` JSON 键值表上。

只依赖两个可注入的读写函数（`get_data(key)` / `save_data(key, value)`），
所以可以注入内存假实现做单测，不碰宿主运行时。
"""

from __future__ import annotations

import json
from typing import Any, Callable, Dict, Iterable, List, Optional

from .models import SOURCE_LIBRARY, SOURCE_MANUAL, SOURCE_SUBSCRIBE, TrackedShow

WATCHLIST_KEY = "watchlist"


class WatchlistStore:
    """名单读写。整表以 JSON 数组存在一个 key 里（数据量小，读改写最简单）。"""

    def __init__(
        self,
        get_data: Callable[[str], Any],
        save_data: Callable[[str, Any], Any],
        key: str = WATCHLIST_KEY,
    ) -> None:
        self._get_data = get_data
        self._save_data = save_data
        self._key = key

    # ---------- 底层 ----------

    def _read_raw(self) -> List[Dict[str, Any]]:
        raw = self._get_data(self._key)
        if not raw:
            return []
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except (TypeError, ValueError):
                return []
        if not isinstance(raw, list):
            return []
        return [item for item in raw if isinstance(item, dict)]

    def _write_raw(self, items: Iterable[Dict[str, Any]]) -> None:
        payload = json.dumps(list(items), ensure_ascii=False, sort_keys=True)
        self._save_data(self._key, payload)

    # ---------- 公开 API ----------

    def list_all(self) -> List[TrackedShow]:
        return [TrackedShow.from_dict(item) for item in self._read_raw()]

    def get(self, tmdbid: int) -> Optional[TrackedShow]:
        for show in self.list_all():
            if int(show.tmdbid) == int(tmdbid):
                return show
        return None

    def upsert(self, show: TrackedShow) -> TrackedShow:
        """按 tmdbid 覆盖式写入；已存在则保留原有的 added_at。"""
        items = self._read_raw()
        target = int(show.tmdbid)
        for idx, item in enumerate(items):
            if int(item.get("tmdbid") or 0) == target:
                if not show.added_at:
                    show.added_at = item.get("added_at")
                if not show.source:
                    show.source = item.get("source") or SOURCE_MANUAL
                items[idx] = show.to_dict()
                self._write_raw(items)
                return show
        items.append(show.to_dict())
        self._write_raw(items)
        return show

    def remove(self, tmdbid: int) -> bool:
        """只从名单移除，**不动** MP 里的订阅。"""
        items = self._read_raw()
        target = int(tmdbid)
        kept = [item for item in items if int(item.get("tmdbid") or 0) != target]
        if len(kept) == len(items):
            return False
        self._write_raw(kept)
        return True

    def set_season(self, tmdbid: int, season: int) -> bool:
        items = self._read_raw()
        target = int(tmdbid)
        for item in items:
            if int(item.get("tmdbid") or 0) == target:
                item["season"] = int(season)
                self._write_raw(items)
                return True
        return False

    def sources(self) -> Dict[str, int]:
        counts: Dict[str, int] = {SOURCE_MANUAL: 0, SOURCE_SUBSCRIBE: 0, SOURCE_LIBRARY: 0}
        for show in self.list_all():
            counts[show.source] = counts.get(show.source, 0) + 1
        return counts
