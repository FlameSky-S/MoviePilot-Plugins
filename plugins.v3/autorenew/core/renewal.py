"""续订判定 —— 纯函数，不 import `app.*`，可裸机单测。

宿主侧的两条硬约束（已实锤，决定了本模块的形状）：

1. 订阅是**按季**的：一条订阅 = 一季，目标集补齐即完成，不跨季。
2. 该季在 TMDB 上**集数为 0 时建不出订阅**（`chain/subscribe/create.py` 报
   「未获取到第 X 季的总集数」）→ 只能在新季已有集数之后才触发。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

from .models import TrackedShow


@dataclass
class RenewalDecision:
    should_renew: bool
    season: Optional[int]
    episode_count: int
    reason: str


def _normalize_seasons(seasons: Optional[Sequence[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """去掉特别季 S0，并按季号升序。"""
    out: List[Dict[str, Any]] = []
    for item in seasons or []:
        try:
            number = int(item.get("season_number"))
        except (TypeError, ValueError):
            continue
        if number <= 0:
            continue
        out.append(
            {
                "season_number": number,
                "episode_count": int(item.get("episode_count") or 0),
                "air_date": item.get("air_date"),
            }
        )
    out.sort(key=lambda s: s["season_number"])
    return out


def latest_season(seasons: Optional[Sequence[Dict[str, Any]]]) -> Optional[Dict[str, Any]]:
    normalized = _normalize_seasons(seasons)
    return normalized[-1] if normalized else None


def first_uncovered_season(
    tracked_season: int, seasons: Optional[Sequence[Dict[str, Any]]]
) -> Optional[Dict[str, Any]]:
    """已追踪季之后**最小**的一季（不跳季：先补 S(tracked+1)）。"""
    for item in _normalize_seasons(seasons):
        if item["season_number"] > tracked_season:
            return item
    return None


def decide_renewal(
    show: TrackedShow,
    seasons: Optional[Sequence[Dict[str, Any]]],
) -> RenewalDecision:
    """给定一条追踪记录和 TMDB 的季列表，判定这次要不要建订阅。"""
    if not show.auto_renew:
        return RenewalDecision(False, None, 0, "该剧已关闭自动续订")

    candidate = first_uncovered_season(show.season, seasons)
    if candidate is None:
        return RenewalDecision(False, None, 0, "没有已追踪季之后的新季")

    number = candidate["season_number"]
    episodes = candidate["episode_count"]
    if episodes <= 0:
        return RenewalDecision(
            False, number, 0, f"第 {number} 季已确认但 TMDB 上尚无集数，暂不能建订阅"
        )
    return RenewalDecision(True, number, episodes, f"发现第 {number} 季，共 {episodes} 集")
