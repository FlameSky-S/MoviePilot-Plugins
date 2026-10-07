"""纯数据模型与状态映射。

本模块**不 import 任何 `app.*`**，因此可以在裸机（无 MoviePilot 运行环境）直接单测。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

MEDIA_TYPE_TV = "电视剧"

# TMDB `status` 是裸字符串，宿主没有枚举 —— 映射由本插件自己维护。
TMDB_STATUS_LABELS: Dict[str, str] = {
    "Returning Series": "连载中",
    "Planned": "已续订",
    "In Production": "制作中",
    "Pilot": "试播集",
    "Ended": "已完结",
    "Canceled": "已砍",
}

# 还在推进：继续轮询、继续尝试续订。
ACTIVE_STATUSES = frozenset({"Returning Series", "Planned", "In Production", "Pilot"})
# 已终止：停轮询，页面折叠灰显。
TERMINAL_STATUSES = frozenset({"Ended", "Canceled"})

SOURCE_MANUAL = "manual"
SOURCE_SUBSCRIBE = "subscribe"
SOURCE_LIBRARY = "library"

SOURCE_LABELS: Dict[str, str] = {
    SOURCE_MANUAL: "手动添加",
    SOURCE_SUBSCRIBE: "订阅同步",
    SOURCE_LIBRARY: "媒体库导入",
}


def status_label(tmdb_status: Optional[str]) -> str:
    """TMDB 状态 -> 中文标签（未知状态原样透出，便于发现新取值）。"""
    if not tmdb_status:
        return "未知"
    return TMDB_STATUS_LABELS.get(tmdb_status, tmdb_status)


def is_terminal(tmdb_status: Optional[str]) -> bool:
    return bool(tmdb_status) and tmdb_status in TERMINAL_STATUSES


@dataclass
class TrackedShow:
    """名单里的一条剧集。`season` 是已追踪到的最高季。"""

    tmdbid: int
    title: str
    year: Optional[int] = None
    season: int = 1
    media_type: str = MEDIA_TYPE_TV
    source: str = SOURCE_MANUAL
    auto_renew: bool = True
    tmdb_status: Optional[str] = None
    poster_path: Optional[str] = None
    latest_season: Optional[int] = None
    latest_season_episodes: Optional[int] = None
    # 已完结区「x/y 季」：x=库内已有季数，y=TMDB 总季数（都不含特别季 S0）
    library_seasons: int = 0
    total_seasons: int = 0
    # TMDB 的季号列表（不含 S0）。持久化它，「x/y」才能每次渲染离线重算，
    # 而不是只在联网刷新时才更新一次。
    tmdb_seasons: List[int] = field(default_factory=list)
    # 通知水位线：已经提醒过的最高季，避免仅提醒模式下每轮重发
    notified_season: Optional[int] = None
    next_episode_air_date: Optional[str] = None
    last_checked_at: Optional[str] = None
    added_at: Optional[str] = None
    renew_count: int = 0
    note: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: Dict[str, Any]) -> "TrackedShow":
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        payload = {k: v for k, v in (raw or {}).items() if k in known}
        if "tmdbid" in payload and payload["tmdbid"] is not None:
            payload["tmdbid"] = int(payload["tmdbid"])
        if "season" in payload and payload["season"] is not None:
            payload["season"] = int(payload["season"])
        return cls(**payload)


def badge_for(
    *,
    tmdb_status: Optional[str],
    tracked_season: int,
    latest_season: Optional[int],
    latest_season_episodes: Optional[int],
    auto_renew: bool,
) -> str:
    """派生徽标：比 TMDB 状态更贴近「我该做什么」。"""
    if not auto_renew:
        return "已暂停续订"
    if is_terminal(tmdb_status) and (latest_season or 0) <= tracked_season:
        return "已完结"
    if latest_season and latest_season > tracked_season:
        if (latest_season_episodes or 0) > 0:
            return "有新季可订阅"
        return "新季已确认待开播"
    return "已追平"
