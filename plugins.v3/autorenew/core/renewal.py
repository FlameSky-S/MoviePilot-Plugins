"""续订判定 —— 纯函数，不 import `app.*`，可裸机单测。

宿主侧的两条硬约束（已实锤，决定了本模块的形状）：

1. 订阅是**按季**的：一条订阅 = 一季，目标集补齐即完成，不跨季。
2. 该季在 TMDB 上**集数为 0 时建不出订阅**（`chain/subscribe/create.py` 报
   「未获取到第 X 季的总集数」）→ 只能在新季已有集数之后才触发。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence

from .models import TrackedShow, is_terminal, status_label


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


def season_stats(
    seasons: Optional[Sequence[Dict[str, Any]]],
    library: Optional[Iterable[Any]] = None,
) -> Dict[str, int]:
    """算「库内已有季数 x / TMDB 总季数 y」，用于已完结卡片的「x/y 季」。

    两个容易答错的点（都已用测试钉死）：

    - **y 是「季的个数」而不是最大季号** —— 缺号时两者不等（1/2/5 应为 3）。
      别拿 `latest_season()` 的结果当总季数。
    - **x 只统计 TMDB 也认可的季**：库里的特别季 S0、以及 TMDB 上不存在的
      幽灵季都不算，且天然以 y 为上限（x ≤ y）。
    """
    numbers = {int(item["season_number"]) for item in _normalize_seasons(seasons)}
    have: set[int] = set()
    for raw in library or ():
        try:
            have.add(int(raw))
        except (TypeError, ValueError):
            continue
    return {"library": len(numbers & have), "total": len(numbers)}


def season_numbers(seasons: Optional[Sequence[Dict[str, Any]]]) -> List[int]:
    """TMDB 季号列表（已去掉特别季 S0）。

    把它持久化到追踪记录上，就能**离线重算** `season_stats` —— 页面上「x/y 季」的 x
    依赖宿主媒体库缓存，那份缓存随时会变；没有这个就不能在每次渲染时重算，
    只能等下一次联网刷新。
    """
    return [item["season_number"] for item in _normalize_seasons(seasons)]


def should_notify(season: Optional[int], notified_season: Optional[int]) -> bool:
    """同一部剧的同一季只提醒一次。

    必要性：**仅提醒模式下 `show.season` 永不推进**（不建订阅就不会 advance），
    没有这个水位线的话每次轮询都会把同一部剧重发一遍。
    """
    try:
        target = int(season)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False
    if target <= 0:
        return False
    try:
        done = int(notified_season)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        done = 0
    return target > done


def decide_renewal(
    show: TrackedShow,
    seasons: Optional[Sequence[Dict[str, Any]]],
) -> RenewalDecision:
    """给定一条追踪记录和 TMDB 的季列表，判定这次要不要建订阅。"""
    # ⚠️ 硬门槛，**优先于单剧开关**：已终结的剧永不自动续订。
    # 反例（真实踩过）：TMDB 状态 Ended 但季数比磁盘多（用户故意只留前几季）——
    # 旧逻辑判成「有新季」，连着建了 S2、S3 两条订阅并真的下载了。
    if is_terminal(show.tmdb_status):
        return RenewalDecision(False, None, 0, f"{status_label(show.tmdb_status)}，不参与自动续订")

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
