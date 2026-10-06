"""TMDB 适配层 —— core 里唯一 import `app.*` 的子模块。

宿主事实（已实锤）：`TmdbApi.get_info(MediaType.TV, tmdbid)` 返回的 TV 详情含
`status / number_of_seasons / seasons[]{season_number, episode_count, air_date} /
next_episode_to_air / in_production`。`status` 是裸字符串，没有枚举。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.modules.themoviedb.tmdbapi import TmdbApi
from app.schemas.types import MediaType
from app.sdk.logging import logger


class TmdbSeasonSource:
    """薄封装：把宿主 TMDB 客户端收敛成一个可替换对象，便于实例内探针验证。"""

    def __init__(self, api: Optional[Any] = None) -> None:
        self._api = api

    @property
    def api(self) -> Any:
        if self._api is None:
            self._api = TmdbApi()
        return self._api

    def tv_detail(self, tmdbid: int) -> Optional[Dict[str, Any]]:
        try:
            return self.api.get_info(MediaType.TV, tmdbid)
        except Exception as err:  # noqa: BLE001
            logger.error(f"自动续订：拉取 TMDB 剧集详情失败 tmdbid={tmdbid}：{err}")
            return None

    def seasons(self, tmdbid: int) -> List[Dict[str, Any]]:
        detail = self.tv_detail(tmdbid) or {}
        seasons = detail.get("seasons") or []
        return [s for s in seasons if isinstance(s, dict)]

    def snapshot(self, tmdbid: int) -> Dict[str, Any]:
        """一次取用时前端/判定都需要的字段。"""
        detail = self.tv_detail(tmdbid) or {}
        next_episode = detail.get("next_episode_to_air") or {}
        return {
            "status": detail.get("status"),
            "seasons": [s for s in (detail.get("seasons") or []) if isinstance(s, dict)],
            "number_of_seasons": detail.get("number_of_seasons"),
            "in_production": detail.get("in_production"),
            "next_episode_air_date": next_episode.get("air_date"),
            "poster_path": detail.get("poster_path"),
        }
