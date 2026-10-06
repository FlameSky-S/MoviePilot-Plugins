"""自动续订（AutoRenew）—— 把 Sonarr 式的「整剧长期监控、有下一季就自动订阅」补进 MoviePilot。

宿主原生缺口（已实锤，不是配置问题）：
  * 订阅是**按季**的：一条订阅 = 一季，目标集补齐即完成并进历史，不跨季。
  * 该季在 TMDB 上集数为 0 时**建不出订阅**（`chain/subscribe/create.py` 报「未获取到第 X 季的总集数」）。

所以跨季这件事由本插件自己扛：维护一份长期追踪名单，定时查 TMDB，
发现「比已追踪季更大、且已有集数」的新季就调 `SubscribeChain.add` 建订阅。
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from apscheduler.triggers.cron import CronTrigger

from app.chain.subscribe import SubscribeChain
from app.core.config import settings
from app.db import SessionFactory
from app.db.models.mediaserver import MediaServerItem
from app.schemas.types import EventType, MediaType, MediaSource
from app.sdk.events import Event, eventmanager
from app.sdk.logging import logger
from app.sdk.plugin import _PluginBase

from .api import build_api_routes
from .core.library import library_candidates, parse_seasoninfo
from .core.models import (
    SOURCE_LABELS,
    SOURCE_LIBRARY,
    SOURCE_MANUAL,
    SOURCE_SUBSCRIBE,
    MEDIA_TYPE_TV,
    TrackedShow,
    badge_for,
    is_terminal,
    status_label,
)
from .core.renewal import decide_renewal, latest_season
from .core.store import WatchlistStore
from .core.tmdb import TmdbSeasonSource

DEFAULT_CRON = "0 */6 * * *"


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class AutoRenew(_PluginBase):
    # ---------------------------------------------------------------- 元数据
    plugin_name = "自动续订"
    plugin_desc = "长期追踪电视剧：TMDB 上出现新一季就自动建订阅。提供 Sonarr 式状态标签、季进度与播出日历。"
    plugin_icon = "AutoRenew.png"
    plugin_version = "1.0.1"
    plugin_author = "FlameSky-S"
    author_url = "https://github.com/FlameSky-S"
    plugin_config_prefix = "autorenew_"
    plugin_order = 51
    auth_level = 2

    # -------------------------------------------------------------- 运行态
    _enabled: bool = False
    _notify: bool = True
    _auto_subscribe: bool = True
    _cron: str = DEFAULT_CRON
    _max_actions: int = 5
    _show_sidebar_nav: bool = True

    _store: Optional[WatchlistStore] = None
    _tmdb: Optional[TmdbSeasonSource] = None
    _last_run: Optional[str] = None
    _last_result: Optional[Dict[str, Any]] = None

    # ------------------------------------------------------------ 生命周期
    def init_plugin(self, config: Optional[dict] = None) -> None:
        config = config or {}
        self._enabled = bool(config.get("enabled", False))
        self._notify = bool(config.get("notify", True))
        self._auto_subscribe = bool(config.get("auto_subscribe", True))
        self._cron = str(config.get("poll_cron") or DEFAULT_CRON).strip() or DEFAULT_CRON
        self._show_sidebar_nav = bool(config.get("show_sidebar_nav", True))
        try:
            self._max_actions = max(1, int(config.get("max_actions_per_run") or 5))
        except (TypeError, ValueError):
            self._max_actions = 5

        self._store = WatchlistStore(self.get_data, self.save_data)
        self._tmdb = TmdbSeasonSource()

        logger.info(
            f"自动续订：初始化完成 enabled={self._enabled} 名单={len(self._store.list_all())} 部 "
            f"cron={self._cron} 自动建订阅={self._auto_subscribe} 每轮上限={self._max_actions}"
        )

    def get_state(self) -> bool:
        return bool(self._enabled)

    def stop_service(self) -> None:
        # 定时任务由宿主调度器托管，这里没有自起的线程/进程需要收尾。
        pass

    # ---------------------------------------------------------------- 配置页
    def get_form(self) -> Tuple[List[dict], Dict[str, Any]]:
        return [
            {
                "component": "VRow",
                "content": [
                    {
                        "component": "VCol",
                        "props": {"cols": 12, "md": 4},
                        "content": [
                            {
                                "component": "VSwitch",
                                "props": {"model": "enabled", "label": "启用插件"},
                            }
                        ],
                    },
                    {
                        "component": "VCol",
                        "props": {"cols": 12, "md": 4},
                        "content": [
                            {
                                "component": "VSwitch",
                                "props": {"model": "auto_subscribe", "label": "发现新季时自动建订阅"},
                            }
                        ],
                    },
                    {
                        "component": "VCol",
                        "props": {"cols": 12, "md": 4},
                        "content": [
                            {
                                "component": "VSwitch",
                                "props": {"model": "notify", "label": "发送通知"},
                            }
                        ],
                    },
                ],
            },
            {
                "component": "VRow",
                "content": [
                    {
                        "component": "VCol",
                        "props": {"cols": 12, "md": 6},
                        "content": [
                            {
                                "component": "VTextField",
                                "props": {
                                    "model": "poll_cron",
                                    "label": "检测周期（crontab）",
                                    "hint": "默认 0 */6 * * *，即每 6 小时查一次 TMDB",
                                    "persistent-hint": True,
                                },
                            }
                        ],
                    },
                    {
                        "component": "VCol",
                        "props": {"cols": 12, "md": 3},
                        "content": [
                            {
                                "component": "VTextField",
                                "props": {
                                    "model": "max_actions_per_run",
                                    "label": "每轮最多建几条订阅",
                                    "type": "number",
                                    "hint": "限速，防止一次对站点发起过多搜索",
                                    "persistent-hint": True,
                                },
                            }
                        ],
                    },
                    {
                        "component": "VCol",
                        "props": {"cols": 12, "md": 3},
                        "content": [
                            {
                                "component": "VSwitch",
                                "props": {"model": "show_sidebar_nav", "label": "显示侧边菜单入口"},
                            }
                        ],
                    },
                ],
            },
            {
                "component": "VRow",
                "content": [
                    {
                        "component": "VCol",
                        "props": {"cols": 12},
                        "content": [
                            {
                                "component": "VAlert",
                                "props": {
                                    "type": "info",
                                    "variant": "tonal",
                                    "text": (
                                        "关闭「自动建订阅」后进入仅提醒模式：仍会追踪并推送新季消息，"
                                        "但不会自动创建订阅。名单增删只影响本插件，不会动 MoviePilot 里的订阅。"
                                    ),
                                },
                            }
                        ],
                    }
                ],
            },
        ], {
            "enabled": False,
            "auto_subscribe": True,
            "notify": True,
            "poll_cron": DEFAULT_CRON,
            "max_actions_per_run": 5,
            "show_sidebar_nav": True,
        }

    def get_page(self) -> List[dict]:
        return [
            {
                "component": "VRow",
                "content": [
                    {
                        "component": "VCol",
                        "props": {"cols": 12},
                        "content": [
                            {
                                "component": "VAlert",
                                "props": {
                                    "type": "info",
                                    "variant": "tonal",
                                    "text": "本插件的工作台在侧边菜单「自动续订」中打开。",
                                },
                            }
                        ],
                    }
                ],
            }
        ]

    # ------------------------------------------------- 侧边菜单（Vue 联邦）
    @staticmethod
    def get_render_mode() -> Tuple[str, str]:
        return "vue", "dist/assets"

    def get_sidebar_nav(self) -> List[Dict[str, Any]]:
        if not self.get_state() or not self._show_sidebar_nav:
            return []
        return [
            {
                "nav_key": "main",
                "title": "自动续订",
                "icon": "mdi-autorenew",
                "section": "subscribe",
                "permission": "subscribe",
                "order": 50,
            }
        ]

    # ------------------------------------------------------------------ API
    def get_api(self) -> List[Dict[str, Any]]:
        return build_api_routes(self)

    # ------------------------------------------------------------ 定时检测
    def get_service(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": "AutoRenewCheck",
                "name": "自动续订检测",
                "trigger": CronTrigger.from_crontab(self._cron),
                "func": self.check_renewals,
                "kwargs": {},
                "func_kwargs": {},
            }
        ]

    # ------------------------------------------------------------ 事件监听
    @eventmanager.register(EventType.SubscribeAdded)
    def on_subscribe_added(self, event: Event) -> None:
        """MP 新建的订阅默认纳入追踪名单（来源 = 订阅同步）。"""
        if not self._enabled or not self._store:
            return
        data = getattr(event, "event_data", None)
        mediainfo = None
        season = None
        if isinstance(data, dict):
            mediainfo = data.get("mediainfo") or data.get("media_info")
            season = data.get("season")
        else:
            mediainfo = getattr(data, "mediainfo", None)
            season = getattr(data, "season", None)
        if mediainfo is None:
            return

        media_type = getattr(mediainfo, "type", None)
        if media_type is not None and str(getattr(media_type, "value", media_type)) != "电视剧":
            return

        tmdbid = getattr(mediainfo, "tmdb_id", None)
        title = getattr(mediainfo, "title", None)
        if not tmdbid or not title:
            return
        try:
            season_no = int(season) if season is not None else int(getattr(mediainfo, "season", 1) or 1)
        except (TypeError, ValueError):
            season_no = 1

        existing = self._store.get(int(tmdbid))
        if existing:
            # 订阅可能追上了更高的季，同步过去
            if season_no > existing.season:
                self._store.set_season(int(tmdbid), season_no)
            return

        self._store.upsert(
            TrackedShow(
                tmdbid=int(tmdbid),
                title=str(title),
                year=getattr(mediainfo, "year", None),
                season=season_no,
                source=SOURCE_SUBSCRIBE,
                added_at=_now(),
            )
        )
        logger.info(f"自动续订：订阅事件纳入追踪「{title}」第 {season_no} 季")

    # ------------------------------------------------------- 核心：新季检测
    def check_renewals(self, force: bool = False) -> Dict[str, Any]:
        if not self._enabled and not force:
            return {"skipped": "插件未启用"}
        if not self._store or not self._tmdb:
            return {"skipped": "插件尚未初始化"}

        shows = self._store.list_all()
        renewed: List[Dict[str, Any]] = []
        waiting: List[Dict[str, Any]] = []
        actions = 0

        for show in shows:
            show, seasons = self.__refresh_show(show)

            if is_terminal(show.tmdb_status) and not any(
                int(s.get("season_number") or 0) > show.season for s in seasons
            ):
                # 已完结/已砍且没有更新的季 -> 停止轮询
                self._store.upsert(show)
                continue

            decision = decide_renewal(show, seasons)
            if not decision.should_renew:
                self._store.upsert(show)
                if decision.season:
                    waiting.append(
                        {"title": show.title, "season": decision.season, "reason": decision.reason}
                    )
                continue

            if actions >= self._max_actions:
                self._store.upsert(show)
                waiting.append(
                    {"title": show.title, "season": decision.season, "reason": "已达本轮限速上限"}
                )
                continue

            if not self._auto_subscribe:
                self._store.upsert(show)
                waiting.append(
                    {"title": show.title, "season": decision.season, "reason": "仅提醒模式"}
                )
                self.__notify_renewal(show, decision.season, created=False)
                continue

            ok, message = self.__create_subscription(show, decision.season)
            if ok:
                actions += 1
                show.season = int(decision.season)
                show.renew_count = int(show.renew_count or 0) + 1
                self._store.upsert(show)
                renewed.append({"title": show.title, "season": decision.season, "message": message})
                self.__notify_renewal(show, decision.season, created=True)
            else:
                self._store.upsert(show)
                waiting.append(
                    {"title": show.title, "season": decision.season, "reason": f"建订阅失败：{message}"}
                )

        if renewed:
            self.__notify_summary(renewed)

        self._last_run = _now()
        self._last_result = {
            "checked": len(shows),
            "renewed": renewed,
            "waiting": waiting,
            "at": self._last_run,
        }
        logger.info(
            f"自动续订：检测完成，检查 {len(shows)} 部，新建订阅 {len(renewed)} 条，待观察 {len(waiting)} 条"
        )
        return self._last_result

    def __create_subscription(self, show: TrackedShow, season: Optional[int]) -> Tuple[bool, str]:
        if not season:
            return False, "缺少季号"
        media_source = getattr(MediaSource, "TMDB", None) or getattr(MediaSource, "THETMDB", None)
        try:
            sid, message = SubscribeChain().add(
                title=show.title,
                year=str(show.year or ""),
                mtype=MediaType.TV,
                season=int(season),
                media_source=media_source,
                media_id=str(show.tmdbid),
                message=self._notify,
            )
        except Exception as err:  # noqa: BLE001
            logger.error(f"自动续订：为「{show.title}」第 {season} 季建订阅异常：{err}")
            return False, str(err)
        if sid is None:
            logger.warn(f"自动续订：为「{show.title}」第 {season} 季建订阅未成功：{message}")
            return False, str(message)
        logger.info(f"自动续订：已为「{show.title}」创建第 {season} 季订阅（id={sid}）：{message}")
        return True, str(message)

    # ------------------------------------------------------------ 通知
    def __post(self, title: str, text: str) -> None:
        if not self._notify:
            return
        try:
            from app.schemas.types import NotificationType

            self.post_message(mtype=NotificationType.Plugin, title=title, text=text)
        except Exception as err:  # noqa: BLE001
            logger.warn(f"自动续订：通知发送失败（不影响主流程）：{err}")

    def __notify_renewal(self, show: TrackedShow, season: Optional[int], created: bool) -> None:
        verb = "已自动创建订阅" if created else "检测到新季（仅提醒）"
        self.__post(f"【自动续订】{show.title}", f"{show.title} 第 {season} 季{verb}")

    def __notify_summary(self, renewed: List[Dict[str, Any]]) -> None:
        lines = [f"{item['title']} → 第 {item['season']} 季" for item in renewed]
        self.__post("【自动续订】本轮续订汇总", "\n".join(lines))

    # ------------------------------------------------------- 媒体库 / TMDB
    def __library_seasons(self, tmdbid: int) -> Dict[int, int]:
        """从宿主 `mediaserveritem` 读某剧各季的入库集数（in-process ORM）。

        ⚠️ 该表真实取值：`item_type` 是**中文**「电视剧」，`seasoninfo` 是
        **JSON 字符串**而不是 dict —— 解析逻辑集中在 `core/library.py`。
        """
        try:
            with SessionFactory() as db:
                items = MediaServerItem.list(db)
        except Exception as err:  # noqa: BLE001
            logger.error(f"自动续订：读取媒体库失败：{err}")
            return {}

        target = str(tmdbid)
        for item in items:
            if str(getattr(item, "item_type", "") or "").strip() != MEDIA_TYPE_TV:
                continue
            if str(getattr(item, "media_id", "") or "") != target:
                continue
            return parse_seasoninfo(getattr(item, "seasoninfo", None))
        return {}

    def __refresh_show(self, show: TrackedShow) -> Tuple[TrackedShow, List[Dict[str, Any]]]:
        """拉一次 TMDB，把元数据写回追踪记录，并返回季列表。

        列表接口因此可以**纯本地渲染**：不这样做的话 `/shows` 会变成
        「每部剧一次 TMDB 调用」（实测 38 部 ≈ 10.7s，页面加载不可接受）。
        """
        if not self._tmdb:
            return show, []
        snapshot = self._tmdb.snapshot(show.tmdbid)
        seasons = snapshot.get("seasons") or []
        show.tmdb_status = snapshot.get("status")
        show.next_episode_air_date = snapshot.get("next_episode_air_date")
        show.poster_path = snapshot.get("poster_path") or show.poster_path
        latest = latest_season(seasons)
        show.latest_season = (latest or {}).get("season_number")
        show.latest_season_episodes = (latest or {}).get("episode_count")
        show.last_checked_at = _now()
        return show, seasons

    def __poster_url(self, poster_path: Optional[str]) -> Optional[str]:
        if not poster_path:
            return None
        try:
            return settings.TMDB_IMAGE_URL(poster_path)
        except Exception:  # noqa: BLE001
            return None

    def __decorate(self, show: TrackedShow) -> Dict[str, Any]:
        """纯本地组装视图字段 —— **不调 TMDB**，元数据由导入 / 检测时写入。"""
        payload = show.to_dict()
        payload["status_label"] = status_label(show.tmdb_status)
        payload["source_label"] = SOURCE_LABELS.get(show.source, show.source)
        payload["poster_url"] = self.__poster_url(show.poster_path)
        payload["terminated"] = is_terminal(show.tmdb_status)
        payload["badge"] = badge_for(
            tmdb_status=show.tmdb_status,
            tracked_season=show.season,
            latest_season=show.latest_season,
            latest_season_episodes=show.latest_season_episodes,
            auto_renew=show.auto_renew,
        )
        return payload

    # ------------------------------------------------------------- API 实现
    def api_status(self) -> Dict[str, Any]:
        shows = self._store.list_all() if self._store else []
        return {
            "enabled": self._enabled,
            "auto_subscribe": self._auto_subscribe,
            "notify": self._notify,
            "cron": self._cron,
            "max_actions_per_run": self._max_actions,
            "tracked": len(shows),
            "sources": self._store.sources() if self._store else {},
            "terminated": sum(1 for s in shows if is_terminal(s.tmdb_status)),
            "last_run": self._last_run,
            "last_result": self._last_result,
        }

    def api_list_shows(self, sort: str = "next_airing") -> List[Dict[str, Any]]:
        shows = self._store.list_all() if self._store else []
        payload = [self.__decorate(show) for show in shows]

        if sort == "recent":
            payload.sort(key=lambda item: item.get("added_at") or "", reverse=True)
        else:
            # 默认 Next Airing：没有下一集的沉到「已完结」区
            payload.sort(
                key=lambda item: (
                    item.get("next_episode_air_date") is None,
                    item.get("next_episode_air_date") or "9999-99-99",
                )
            )
        return payload

    def api_add_show(self, payload: dict = None) -> Dict[str, Any]:
        payload = payload or {}
        tmdbid = payload.get("tmdbid")
        title = payload.get("title")
        if not tmdbid or not title:
            return {"success": False, "message": "缺少 tmdbid 或 title"}
        season = payload.get("season")
        try:
            season_no = int(season) if season else 1
        except (TypeError, ValueError):
            season_no = 1
        existing = self._store.get(int(tmdbid))
        if existing:
            return {"success": False, "message": f"「{existing.title}」已在追踪名单中"}
        self._store.upsert(
            self.__refresh_show(
                TrackedShow(
                    tmdbid=int(tmdbid),
                    title=str(title),
                    year=payload.get("year"),
                    season=season_no,
                    source=SOURCE_MANUAL,
                    poster_path=payload.get("poster_path"),
                    added_at=_now(),
                )
            )[0]
        )
        logger.info(f"自动续订：手动加入追踪「{title}」第 {season_no} 季")
        return {"success": True, "message": f"已加入追踪：{title}"}

    def api_remove_show(self, payload: dict = None) -> Dict[str, Any]:
        payload = payload or {}
        tmdbid = payload.get("tmdbid")
        if not tmdbid:
            return {"success": False, "message": "缺少 tmdbid"}
        removed = self._store.remove(int(tmdbid))
        return {
            "success": removed,
            "message": "已移出追踪名单（MoviePilot 里的订阅未改动）" if removed else "不在名单中",
        }

    def api_toggle_show(self, payload: dict = None) -> Dict[str, Any]:
        payload = payload or {}
        tmdbid = payload.get("tmdbid")
        if not tmdbid:
            return {"success": False, "message": "缺少 tmdbid"}
        show = self._store.get(int(tmdbid))
        if not show:
            return {"success": False, "message": "不在名单中"}
        show.auto_renew = bool(payload.get("auto_renew", not show.auto_renew))
        self._store.upsert(show)
        return {"success": True, "auto_renew": show.auto_renew}

    def api_show_seasons(self, tmdbid: int = 0) -> Dict[str, Any]:
        if not tmdbid or not self._tmdb:
            return {"success": False, "message": "缺少 tmdbid"}
        show = self._store.get(int(tmdbid))
        tracked_season = show.season if show else 0
        library = self.__library_seasons(int(tmdbid))
        seasons = []
        for item in self._tmdb.seasons(int(tmdbid)):
            try:
                number = int(item.get("season_number"))
            except (TypeError, ValueError):
                continue
            if number <= 0:
                continue
            in_library = library.get(number, 0)
            seasons.append(
                {
                    "season_number": number,
                    "episode_count": int(item.get("episode_count") or 0),
                    "air_date": item.get("air_date"),
                    "in_library": in_library,
                    "state": (
                        "已入库"
                        if in_library
                        else ("未播出" if not item.get("air_date") else "待下载")
                    ),
                    "tracked": number <= tracked_season,
                }
            )
        seasons.sort(key=lambda s: s["season_number"])
        return {
            "success": True,
            "tmdbid": int(tmdbid),
            "title": show.title if show else None,
            "tracked_season": tracked_season,
            "seasons": seasons,
        }

    def api_search(self, keyword: str = "") -> List[Dict[str, Any]]:
        if not keyword or not self._tmdb:
            return []
        try:
            results = self._tmdb.api.search(MediaType.TV, keyword)
        except Exception as err:  # noqa: BLE001
            logger.error(f"自动续订：搜索失败：{err}")
            return []
        out = []
        for item in results or []:
            if str(item.get("media_type") or "tv") != "tv":
                continue
            out.append(
                {
                    "tmdbid": item.get("id"),
                    "title": item.get("name") or item.get("title"),
                    "year": (item.get("first_air_date") or "")[:4],
                    "overview": item.get("overview"),
                    "poster_path": item.get("poster_path"),
                    "poster_url": self.__poster_url(item.get("poster_path")),
                    "tracked": bool(self._store.get(int(item.get("id") or 0))),
                }
            )
        return out

    def api_import_library(self, payload: dict = None) -> Dict[str, Any]:
        """冷启动用：把媒体库里的剧集批量纳入追踪，**不建任何订阅**。"""
        payload = payload or {}
        try:
            with SessionFactory() as db:
                rows = MediaServerItem.list(db)
        except Exception as err:  # noqa: BLE001
            return {"success": False, "message": f"读取媒体库失败：{err}"}

        candidates = library_candidates(rows)
        added, skipped = 0, 0
        for candidate in candidates:
            tmdbid = candidate["tmdbid"]
            existing = self._store.get(tmdbid)
            if existing:
                if candidate["season"] > existing.season:
                    self._store.set_season(tmdbid, candidate["season"])
                    added += 1
                else:
                    skipped += 1
                continue
            self._store.upsert(
                self.__refresh_show(
                    TrackedShow(
                        tmdbid=tmdbid,
                        title=candidate["title"],
                        year=candidate["year"],
                        season=candidate["season"],
                        source=SOURCE_LIBRARY,
                        added_at=_now(),
                    )
                )[0]
            )
            added += 1

        logger.info(
            f"自动续订：媒体库导入完成（库内剧集 {len(candidates)} 部），新增/升级 {added} 部，跳过 {skipped} 部"
        )
        return {
            "success": True,
            "added": added,
            "skipped": skipped,
            "candidates": len(candidates),
            "message": f"导入完成：新增 {added} 部，跳过 {skipped} 部（未创建任何订阅）",
        }

    def api_calendar(self, days: int = 30) -> Dict[str, Any]:
        try:
            window = max(1, int(days))
        except (TypeError, ValueError):
            window = 30
        today = date.today()
        end = today + timedelta(days=window)
        events: List[Dict[str, Any]] = []
        for show in self._store.list_all() if self._store else []:
            air = show.next_episode_air_date
            if not air:
                continue
            try:
                air_date = date.fromisoformat(str(air)[:10])
            except ValueError:
                continue
            if today <= air_date <= end:
                events.append(
                    {
                        "date": air_date.isoformat(),
                        "title": show.title,
                        "tmdbid": show.tmdbid,
                        "season": show.season,
                        "status_label": status_label(show.tmdb_status),
                    }
                )
        events.sort(key=lambda event: event["date"])
        return {"days": window, "events": events}

    def api_check(self) -> Dict[str, Any]:
        return {"success": True, "result": self.check_renewals(force=True)}
