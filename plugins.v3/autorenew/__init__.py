"""自动续订（AutoRenew）—— 把 Sonarr 式的「整剧长期监控、有下一季就自动订阅」补进 MoviePilot。

宿主原生缺口（已实锤，不是配置问题）：
  * 订阅是**按季**的：一条订阅 = 一季，目标集补齐即完成并进历史，不跨季。
  * 该季在 TMDB 上集数为 0 时**建不出订阅**（`chain/subscribe/create.py` 报「未获取到第 X 季的总集数」）。

所以跨季这件事由本插件自己扛：维护一份长期追踪名单，定时查 TMDB，
发现「比已追踪季更大、且已有集数」的新季就调 `SubscribeChain.add` 建订阅。
"""

from __future__ import annotations

import threading
import time
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
from app.sdk import queries as sdk_queries

from .api import build_api_routes
from .core.calendarview import build_month_grid, merge_day_episodes
from .core.crontext import describe_cron
from .core.library import diff_watchlist, library_candidates
from .core.models import (
    SOURCE_LABELS,
    SOURCE_LIBRARY,
    SOURCE_MANUAL,
    SOURCE_SUBSCRIBE,
    TrackedShow,
    badge_for,
    is_terminal,
    status_label,
)
from .core.renewal import (
    decide_renewal,
    latest_season,
    season_numbers,
    season_stats,
    should_notify,
)
from .core.rules import RULE_FIELDS, merge_rules, rule_payload
from .core.store import WatchlistStore
from .core.tmdb import TmdbSeasonSource

DEFAULT_CRON = "0 */6 * * *"

# 「播出日历」里每一集的缓存时长。宿主的 TmdbApi.get_tv_season_detail **没有缓存**，
# 而翻月份 / 刷新页面都会重新走一遍日历接口 —— 不缓存就是每次几十个 TMDB 请求。
EPISODE_CACHE_TTL = 3 * 3600
# 一部剧最多看几季的集表（从已追踪季起算）。防「追踪 S1、实际 S12」这类极端情况炸请求。
CAL_MAX_SEASONS = 6

# 「续订规则」里画质/分辨率的候选（宿主的合法取值，界面只是给提示，允手填）。
RESOLUTION_CHOICES = ("8K", "4K", "1080P", "720P", "480P")
QUALITY_CHOICES = ("BluRay", "Remux", "WEB-DL", "WEBRip", "UHD", "HDTV", "DVD", "SDTV")


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _as_int_list(raw: Any) -> List[int]:
    """把前端传来的 id 列表归一成 int 列表，脏值丢弃（去重保序）。"""
    out: List[int] = []
    for value in raw or []:
        try:
            number = int(value)
        except (TypeError, ValueError):
            continue
        if number not in out:
            out.append(number)
    return out


class AutoRenew(_PluginBase):
    # ---------------------------------------------------------------- 元数据
    plugin_name = "自动续订"
    plugin_desc = "长期追踪电视剧：TMDB 上出现新一季就自动建订阅。提供 Sonarr 式状态标签、季进度与播出日历。"
    plugin_icon = "AutoRenew.png"
    plugin_version = "1.0.8"
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
    _rule_defaults: Optional[Dict[str, Any]] = None
    _last_run: Optional[str] = None
    _last_result: Optional[Dict[str, Any]] = None
    _config: Dict[str, Any] = {}
    _cron_text: str = ""
    # {(tmdbid, season): (写入时间, 集列表)} —— 见 EPISODE_CACHE_TTL
    _episode_cache: Dict[Tuple[int, int], Tuple[float, List[Dict[str, Any]]]] = {}

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
        # 原样留一份配置：设置入口要在页面里回显，POST /config 也要拿它做整份覆盖
        self._config = dict(config)
        self._cron_text = describe_cron(self._cron)
        self._episode_cache = {}
        # 续订规则第二级：插件设置（空项会被 rule_payload 丢掉，即「交给宿主全局」）
        self._rule_defaults = rule_payload(config)
        # 上次检测时间持久化在 plugindata 里（宿主重载会重建插件实例）
        self._last_run = self.get_data("last_run") or None

        logger.info(
            f"自动续订：初始化完成 enabled={self._enabled} 名单={len(self._store.list_all())} 部 "
            f"cron={self._cron} 自动建订阅={self._auto_subscribe} 每轮上限={self._max_actions}"
        )

        self.__maybe_kick_check()

    def __maybe_kick_check(self) -> None:
        """「启用 / 自动建订阅」从关拨到开时，立刻补跑一次检测。

        没这一步的话，用户拨完开关要**干等到下一个 cron 点**（默认 6h）才看得到
        任何动作 —— 实测被当成「开关没生效」。上一份配置存在 `plugindata` 里，
        因为宿主重载会**重建插件实例**，内存态拿不到上一份配置。
        """
        snapshot = {
            "enabled": bool(self._enabled),
            "auto_subscribe": bool(self._auto_subscribe),
        }
        try:
            previous = self.get_data("config_snapshot") or {}
            self.save_data("config_snapshot", snapshot)
        except Exception:  # noqa: BLE001
            previous = {}

        if not (self._enabled and self._auto_subscribe):
            return
        turned_on = (
            not previous
            or not previous.get("enabled")
            or not previous.get("auto_subscribe")
        )
        if not turned_on or not self._store or not self._store.list_all():
            return

        logger.info("自动续订：「自动建订阅」刚打开，立即补跑一次新季检测")
        threading.Thread(target=self.__kick_run, name="autorenew-kick", daemon=True).start()

    def __kick_run(self) -> None:
        """后台线程里跑一次检测 —— 真建订阅是 10s 量级，不能占着宿主保存配置的请求。"""
        try:
            result = self.check_renewals()
            logger.info(
                f"自动续订：补跑检测完成，新建订阅 {len((result or {}).get('renewed') or [])} 条"
            )
        except Exception as err:  # noqa: BLE001
            logger.error(f"自动续订：补跑检测失败（下一个 cron 点仍会跑）：{err}")

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
        # 库信息读一次、循环里复用（每部单独读会把整张表扫几十遍）
        library = self.__library_map()

        for show in shows:
            show, seasons = self.__refresh_show(show, library)

            if is_terminal(show.tmdb_status):
                # 硬门槛：已完结 / 已砍永不自动续订（除非 TMDB 把状态改回连载中）。
                # 别再按「有没有更新的季」放行 —— 那正是「绝望写手」被连建
                # S2、S3 并真下载的原因（用户是故意只留前几季）。
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
                # 仅提醒模式下 show.season 永不推进（不建订阅就不 advance），
                # 没有水位线的话每轮都会把同一部剧重发一遍
                if should_notify(decision.season, show.notified_season):
                    show.notified_season = int(decision.season or 0)
                    self.__notify_reminder(show, decision.season)
                self._store.upsert(show)
                waiting.append(
                    {"title": show.title, "season": decision.season, "reason": "仅提醒模式"}
                )
                continue

            ok, message = self.__create_subscription(show, decision.season)
            if ok:
                actions += 1
                show.season = int(decision.season)
                show.renew_count = int(show.renew_count or 0) + 1
                # 建了订阅也算「这一季已提醒过」，免得以后切回仅提醒模式时重发
                show.notified_season = int(decision.season or 0)
                self._store.upsert(show)
                renewed.append({"title": show.title, "season": decision.season, "message": message})
                # 不在这里逐条发通知：循环结束后的 __notify_summary 统一发一条
            else:
                self._store.upsert(show)
                waiting.append(
                    {"title": show.title, "season": decision.season, "reason": f"建订阅失败：{message}"}
                )

        if renewed:
            self.__notify_summary(renewed)

        self._last_run = _now()
        try:
            # 持久化：宿主重载会重建插件实例，内存态留不住「上次检测时间」
            self.save_data("last_run", self._last_run)
        except Exception:  # noqa: BLE001
            pass
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
        rules = self.__rule_kwargs(show)
        try:
            sid, message = SubscribeChain().add(
                title=show.title,
                year=str(show.year or ""),
                mtype=MediaType.TV,
                season=int(season),
                media_source=media_source,
                media_id=str(show.tmdbid),
                message=False,  # 通知由插件自己发（避免与宿主那条「订阅成功」重复）
                # 续订规则：宿主会把 kwargs 直接当成订阅行字段，
                # 没出现在这里的字段它才会走自己的全局默认。
                **rules,
            )
        except Exception as err:  # noqa: BLE001
            logger.error(f"自动续订：为「{show.title}」第 {season} 季建订阅异常：{err}")
            return False, str(err)
        if sid is None:
            logger.warn(f"自动续订：为「{show.title}」第 {season} 季建订阅未成功：{message}")
            return False, str(message)
        logger.info(
            f"自动续订：已为「{show.title}」创建第 {season} 季订阅（id={sid}）：{message}"
            + (f" 规则={rules}" if rules else " 规则=跟随宿主全局")
        )
        return True, str(message)

    def __show_existing_rules(self, show: TrackedShow) -> Dict[str, Any]:
        """一级回退：这部剧**已有订阅**里配的规则。

        用户手动建订阅时带的偏好应当被沿用。⚠️ 订阅一旦完成就会从 `subscribe`
        表移进历史表，所以只查活跃表会大量漏掉 —— 两张都要看。
        SDK 查询门面只在宿主进程内可用（独立进程里抛
        `插件数据查询服务尚未配置`），拿不到就当没有这一级，绝不能因此中断建订阅。
        """
        target = str(show.tmdbid)
        # ⚠️ SDK 过滤器要求 media_source 与 media_id **必须同时提供**，
        # 只给 media_id 会直接 pydantic validation error（实测踩过：这一级等于永远失效）。
        # 本插件建的订阅 media_source 固定是 TMDB。
        media_source = getattr(MediaSource, "TMDB", None) or getattr(MediaSource, "THETMDB", None)
        query = {"media_source": media_source, "media_id": target}
        for label, fetch in (
            ("活跃订阅", sdk_queries.list_subscriptions),
            ("订阅历史", sdk_queries.list_subscription_history),
        ):
            try:
                page = fetch(query)
            except Exception as err:  # noqa: BLE001
                logger.warn(f"自动续订：读取{label}失败，跳过该级回退：{err}")
                continue
            best: Dict[str, Any] = {}
            for item in list(getattr(page, "items", None) or []):
                payload = {
                    field: getattr(item, field, None)
                    for field in RULE_FIELDS
                    if getattr(item, field, None) not in (None, "")
                }
                # 同一部剧可能有多季，取参数最全的那条
                if len(payload) > len(best):
                    best = payload
            if best:
                return best
        return {}

    def __rule_kwargs(self, show: TrackedShow) -> Dict[str, Any]:
        """建订阅时下发的规则：该剧已有订阅 → 插件设置 → （不传 = 宿主全局）。"""
        return merge_rules([self.__show_existing_rules(show), self._rule_defaults])

    # ------------------------------------------------------------ 通知
    def __post(self, title: str, text: str) -> None:
        if not self._notify:
            return
        try:
            from app.schemas.types import NotificationType

            # ⚠️ 用「订阅」而不是「插件」：宿主 `NotificationSwitchs` 里
            # 「插件」的 action 是 admin（只推给管理员），「订阅」才是 all。
            # 用 Plugin 的话，即便 notify 开着也可能推不到你手机上。
            self.post_message(mtype=NotificationType.Subscribe, title=title, text=text)
        except Exception as err:  # noqa: BLE001
            logger.warn(f"自动续订：通知发送失败（不影响主流程）：{err}")

    def __notify_reminder(self, show: TrackedShow, season: Optional[int]) -> None:
        self.__post(
            f"【自动续订】{show.title}",
            f"检测到《{show.title}》第 {season} 季，当前为「仅提醒」模式，未自动创建订阅。",
        )

    def __notify_summary(self, renewed: List[Dict[str, Any]]) -> None:
        """自动建订阅后**只发这一条**。

        建订阅时给宿主传了 `message=False`，宿主自己那条「订阅成功」通知会被压掉，
        所以这里不会再重复；反过来也别在循环里逐条发 —— 一轮建 5 条就是 5 条消息。
        """
        if not renewed:
            return
        lines = [f"《{item['title']}》→ 第 {item['season']} 季" for item in renewed]
        if len(lines) == 1:
            self.__post("【自动续订】已自动创建订阅", lines[0])
        else:
            self.__post(f"【自动续订】本轮新建 {len(lines)} 条订阅", "\n".join(lines))

    # ------------------------------------------------------- 媒体库 / TMDB
    def __library_map(self) -> Dict[str, Dict[int, int]]:
        """一次性读出全库剧集：`{tmdbid: {季号: 集数}}`。

        名单有几十部时，若每部都单独 `MediaServerItem.list(db)`，就会把整张表
        扫几十遍 —— 这是 `/shows` 变慢的主因之一。调用方**读一次、循环里复用**。

        ⚠️ 该表真实取值：`item_type` 是**中文**「电视剧」，`seasoninfo` 是
        **JSON 字符串**而不是 dict —— 解析逻辑集中在 `core/library.py`。
        """
        try:
            with SessionFactory() as db:
                items = MediaServerItem.list(db)
        except Exception as err:  # noqa: BLE001
            logger.error(f"自动续订：读取媒体库失败：{err}")
            return {}
        return {str(c["tmdbid"]): c["seasons"] for c in library_candidates(items)}

    def __library_seasons(self, tmdbid: int) -> Dict[int, int]:
        """单剧查询（详情弹窗用）；循环里请用 `__library_map()` 读一次复用。"""
        return self.__library_map().get(str(tmdbid), {})

    def __refresh_show(
        self,
        show: TrackedShow,
        library: Optional[Dict[str, Dict[int, int]]] = None,
    ) -> Tuple[TrackedShow, List[Dict[str, Any]]]:
        """拉一次 TMDB，把元数据写回追踪记录，并返回季列表。

        列表接口因此可以**纯本地渲染**：不这样做的话 `/shows` 会变成
        「每部剧一次 TMDB 调用」（实测 38 部 ≈ 10.7s，页面加载不可接受）。

        `library` 传 `__library_map()` 的结果（批量场景复用同一次库读取），
        顺手算出已完结卡片要显示的「x/y 季」。
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
        stats = season_stats(seasons, library=(library or {}).get(str(show.tmdbid), {}))
        show.library_seasons = stats["library"]
        show.total_seasons = stats["total"]
        # 存下季号列表，之后每次渲染都不用联网就能重算「x/y 季」
        show.tmdb_seasons = season_numbers(seasons)
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
        active = [s for s in shows if not is_terminal(s.tmdb_status)]
        return {
            "enabled": self._enabled,
            "auto_subscribe": self._auto_subscribe,
            "notify": self._notify,
            "cron": self._cron,
            # cron 的自然语言说明（后端算，前端只展示 —— 这样才能进单测）
            "cron_text": self._cron_text or describe_cron(self._cron),
            "max_actions_per_run": self._max_actions,
            # tracked 保留为「名单总数」；tracking 是「正在追踪」= 不含已完结/已砍
            "tracked": len(shows),
            "tracking": len(active),
            "auto_renew_on": sum(1 for s in active if s.auto_renew),
            "sources": self._store.sources() if self._store else {},
            "terminated": len(shows) - len(active),
            "last_run": self._last_run,
            "last_result": self._last_result,
        }

    # ---------------------------------------------------- 设置页（页面内入口）
    def api_get_config(self) -> Dict[str, Any]:
        """页面右上「设置」按钮回显用：原样返回插件自己的配置。"""
        return dict(self.get_config() or self._config or {})

    def api_save_config(self, payload: dict = None) -> Dict[str, Any]:
        """页面内保存设置。

        走 `_PluginBase.update_config`（宿主官方入口，写 `plugininstance`），
        再 `init_plugin` 让**当前实例**立刻用上新配置 —— 否则要等宿主下次重载，
        用户会以为「保存了没生效」。顺带 `__maybe_kick_check` 会在
        「自动建订阅」被打开时补跑一次检测。
        """
        payload = payload if isinstance(payload, dict) else {}
        if not payload:
            return {"success": False, "message": "配置为空"}
        # 保留宿主侧的非表单字段（如 enabled 由列表页开关控制），整份覆盖前先合并
        merged = dict(self.get_config() or {})
        merged.update(payload)
        try:
            self.update_config(merged)
        except Exception as err:  # noqa: BLE001
            logger.error(f"自动续订：保存配置失败：{err}")
            return {"success": False, "message": f"保存失败：{err}"}
        try:
            self.init_plugin(merged)
        except Exception as err:  # noqa: BLE001
            logger.error(f"自动续订：保存后重载配置失败：{err}")
            return {"success": False, "message": f"已保存，但重载失败：{err}"}
        logger.info("自动续订：设置已通过页面保存并生效")
        return {"success": True, "message": "设置已保存并生效"}

    def api_list_shows(self, sort: str = "next_airing") -> List[Dict[str, Any]]:
        shows = self._store.list_all() if self._store else []
        # 「x/y 季」现场重算：x 取自宿主的媒体库缓存，缓存一变页面就该跟上，
        # 不能等下一次 TMDB 刷新（持久化的 tmdb_seasons 让这一步不用联网）。
        library = self.__library_map()
        for show in shows:
            if show.tmdb_seasons:
                stats = season_stats(
                    [{"season_number": n} for n in show.tmdb_seasons],
                    (library or {}).get(str(show.tmdbid), {}),
                )
                show.library_seasons = stats["library"]
                show.total_seasons = stats["total"]
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
                ),
                self.__library_map(),
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

    # -------------------------------------------- 媒体库导入（先预览，再执行）
    def __library_rows(self) -> Tuple[List[Any], str, str]:
        """读宿主媒体库行。返回 (行, 错误, 最近同步时间)。"""
        try:
            with SessionFactory() as db:
                rows = MediaServerItem.list(db)
        except Exception as err:  # noqa: BLE001
            logger.error(f"自动续订：读取媒体库失败：{err}")
            return [], f"读取媒体库失败：{err}"
        marks = [str(getattr(row, "lst_mod_date", "") or "") for row in rows]
        return rows, "", max([m for m in marks if m] or [""])

    def __sync_media_library(self) -> Tuple[bool, str]:
        """强制跑一次宿主媒体库同步，让 `mediaserveritem` 立刻反映真实的库内容。

        宿主只在调度器里按 `MEDIASERVER_SYNC_INTERVAL`（默认 6h）同步，**没有**任何
        HTTP 接口能手动触发；但插件跑在宿主进程内，可以直接调 `MediaServerChain.sync`。
        同步收尾会 `delete_stale` 清掉本轮没更新的行 —— 这正是「从库里删掉的剧能被
        识别为建议移除」的前提。
        """
        try:
            from app.chain.mediaserver import MediaServerChain

            MediaServerChain().sync()
        except Exception as err:  # noqa: BLE001
            logger.error(f"自动续订：强制同步媒体库失败：{err}")
            return False, f"媒体库同步失败：{err}"
        logger.info("自动续订：已强制同步媒体库")
        return True, "媒体库同步完成"

    def api_import_preview(self, sync: bool = False) -> Dict[str, Any]:
        """导入前的比对：算出「将新增 / 将移除」，交给用户逐条确认。"""
        sync_note = ""
        if sync:
            ok, sync_note = self.__sync_media_library()
            if not ok:
                return {"success": False, "message": sync_note}

        rows, error, last_sync = self.__library_rows()
        if error:
            return {"success": False, "message": error}

        candidates = library_candidates(rows)
        tracked = self._store.list_all() if self._store else []
        diff = diff_watchlist(tracked, candidates)
        logger.info(
            f"自动续订：导入预览 —— 库内 {len(candidates)} 部，将新增 {len(diff['added'])} 部，"
            f"将移除 {len(diff['removed'])} 部，名单内已有 {len(diff['kept'])} 部"
        )
        return {
            "success": True,
            "library_total": len(candidates),
            "kept": len(diff["kept"]),
            "added": diff["added"],
            "removed": diff["removed"],
            "last_sync": last_sync,
            "sync_note": sync_note,
        }

    def api_import_apply(self, payload: dict = None) -> Dict[str, Any]:
        """按确认弹窗里勾选的结果执行。**不创建任何订阅。**

        - 勾中的新增 → 纳入名单（来源 = 媒体库导入）
        - 勾中的移除 → **只对来源 = 媒体库导入的条目生效**，其它来源一律拒绝
        """
        payload = payload or {}
        add_ids = _as_int_list(payload.get("add"))
        remove_ids = _as_int_list(payload.get("remove"))

        rows, error, _ = self.__library_rows()
        if error:
            return {"success": False, "message": error}
        candidates = library_candidates(rows)
        by_id = {c["tmdbid"]: c for c in candidates}
        # 库信息这份就已经拿到了，顺手复用给 x/y 季的统计，别再去读一次表
        library = {str(c["tmdbid"]): c["seasons"] for c in candidates}

        added, upgraded, skipped = 0, 0, 0
        for tmdbid in add_ids:
            candidate = by_id.get(tmdbid)
            if not candidate:
                skipped += 1
                continue
            existing = self._store.get(tmdbid)
            if existing:
                if candidate["season"] > existing.season:
                    self._store.set_season(tmdbid, candidate["season"])
                    upgraded += 1
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
                    ),
                    library,
                )[0]
            )
            added += 1

        removed, refused = 0, 0
        for tmdbid in remove_ids:
            show = self._store.get(tmdbid)
            if not show:
                continue
            if show.source != SOURCE_LIBRARY:
                # 安全边界：手动添加 / 订阅同步进来的绝不允许被导入流程删掉
                refused += 1
                logger.warning(f"自动续订：拒绝移除「{show.title}」（来源={show.source}）")
                continue
            if self._store.remove(tmdbid):
                removed += 1

        logger.info(
            f"自动续订：媒体库导入完成 —— 新增 {added} 部，升级季号 {upgraded} 部，"
            f"跳过 {skipped} 部，移除 {removed} 部，拒绝移除 {refused} 部"
        )
        return {
            "success": True,
            "added": added,
            "upgraded": upgraded,
            "skipped": skipped,
            "removed": removed,
            "refused": refused,
            "message": (
                f"导入完成：新增 {added} 部（升级 {upgraded} 部），移除 {removed} 部"
                f"（未创建任何订阅）"
            ),
        }

    def api_refresh(self, payload: dict = None) -> Dict[str, Any]:
        """重新拉 TMDB 元数据并写回追踪记录，顺带重读媒体库算「x/y 季」。

        `scope=ended`（默认）只刷已完结/已砍的，`scope=all` 刷全部。

        `sync=true` 时**先强制跑一次宿主媒体库同步**再刷。为什么需要：
        「x/y 季」里的 x 来自宿主的 `mediaserveritem` **缓存**，而那份缓存每
        `MEDIASERVER_SYNC_INTERVAL`（默认 6h）才更新一次 —— 刚下载入库的剧会一直显示
        旧数字。实测：绝望写手 S2/S3 于 09:32 入库，而当时的缓存快照是 04:22，
        页面仍旧显示「1/5」。宿主**没有**任何 HTTP 接口能手动触发同步，但插件跑在宿主
        进程内，可以直接调 `MediaServerChain.sync()`。
        """
        payload = payload or {}
        scope = str(payload.get("scope") or "ended").strip().lower()
        raw_sync = payload.get("sync")
        do_sync = raw_sync is True or str(raw_sync).strip().lower() in ("1", "true", "yes", "on")
        sync_note = ""
        synced = False
        if do_sync:
            synced, note = self.__sync_media_library()
            sync_note = f"；{note}" if synced else f"；{note}（改按现有缓存刷新）"

        shows = self._store.list_all() if self._store else []
        targets = shows if scope == "all" else [s for s in shows if is_terminal(s.tmdb_status)]

        # 注意顺序：同步之后再读库，否则拿到的还是同一份旧缓存
        library = self.__library_map()
        refreshed, failed = 0, 0
        for show in targets:
            try:
                updated, _ = self.__refresh_show(show, library)
                self._store.upsert(updated)
                refreshed += 1
            except Exception as err:  # noqa: BLE001
                failed += 1
                logger.error(f"自动续订：刷新「{show.title}」失败：{err}")

        logger.info(
            f"自动续订：刷新 TMDB 元数据 scope={scope} 成功 {refreshed} 部，失败 {failed} 部"
        )
        return {
            "success": True,
            "scope": scope,
            "synced": synced,
            "refreshed": refreshed,
            "failed": failed,
            "message": (
                f"已刷新 {refreshed} 部的 TMDB 信息" + (f"，{failed} 部失败" if failed else "")
            )
            + sync_note,
        }

    def api_rule_options(self) -> Dict[str, Any]:
        """给设置界面用的候选项：站点 / 过滤规则组 / 下载器 + 画质分辨率提示值。

        全部**从宿主现读**，别在插件里硬编码站点 id 之类会漂移的东西。
        """
        sites: List[Dict[str, Any]] = []
        try:
            from app.db.models.site import Site

            with SessionFactory() as db:
                rows = db.query(Site).all()
            for row in rows:
                sites.append(
                    {
                        "id": int(getattr(row, "id", 0) or 0),
                        "name": str(getattr(row, "name", "") or ""),
                        "domain": str(getattr(row, "domain", "") or ""),
                        "public": bool(getattr(row, "public", False)),
                    }
                )
        except Exception as err:  # noqa: BLE001
            logger.warn(f"自动续订：读取站点列表失败（设置页站点项会为空）：{err}")

        def systemconfig(key: str) -> Any:
            try:
                return self.systemconfig.get(key)
            except Exception as err:  # noqa: BLE001
                logger.warn(f"自动续订：读取系统设置 {key} 失败：{err}")
                return None

        groups = [
            str(g.get("name"))
            for g in (systemconfig("UserFilterRuleGroups") or [])
            if isinstance(g, dict) and g.get("name")
        ]
        downloaders = [
            str(d.get("name"))
            for d in (systemconfig("Downloaders") or [])
            if isinstance(d, dict) and d.get("name")
        ]
        return {
            "sites": sites,
            "filter_groups": groups,
            "downloaders": downloaders,
            "resolution_choices": list(RESOLUTION_CHOICES),
            "quality_choices": list(QUALITY_CHOICES),
            "current": dict(self._rule_defaults or {}),
        }

    def __season_episodes(self, tmdbid: int, season: int) -> List[Dict[str, Any]]:
        """某一季的集表，带进程内缓存（宿主的 TMDB 客户端没有缓存）。"""
        cache = getattr(self, "_episode_cache", None)
        if cache is None:
            cache = self._episode_cache = {}
        key = (int(tmdbid), int(season))
        hit = cache.get(key)
        now = time.time()
        if hit and now - hit[0] < EPISODE_CACHE_TTL:
            return hit[1]
        episodes = self._tmdb.season_episodes(tmdbid, season) if self._tmdb else []
        cache[key] = (now, episodes)
        return episodes

    def __calendar_seasons(self, show: TrackedShow) -> List[int]:
        """该剧哪些季的集表值得拉。

        从「已追踪季」到「TMDB 最新季」；跨度太大时保留已追踪季 + 最新的几季
        （一部剧的播出安排只可能落在最新那几季）。
        """
        first = max(1, int(show.season or 1))
        last = max(first, int(show.latest_season or first))
        seasons = list(range(first, last + 1))
        if len(seasons) > CAL_MAX_SEASONS:
            seasons = sorted({first, *seasons[-(CAL_MAX_SEASONS - 1):]})
        return seasons

    def api_calendar(self, month: Optional[str] = None) -> Dict[str, Any]:
        """播出日历：按月返回一张周一起始的月历网格，**事件精确到集**。

        - 数据源是 TMDB 的每季集表（不是 host 的 `next_episode_to_air`），
          所以能看到 `S02E01`；同一天连播多集由 `merge_day_episodes` 合并成
          `S02E01-E08`。
        - 已完结 / 已砍的剧直接跳过：它们不会再有新集，没必要为它们拉 TMDB。
        - 网格由纯函数 `build_month_grid` 排（含跨月补位格），前端只渲染不计算。
        """
        today = date.today()
        raw = str(month or "").strip()[:7]
        year, month_no = today.year, today.month
        if len(raw) == 7 and raw[4] == "-" and raw[:4].isdigit() and raw[5:].isdigit():
            candidate = int(raw[5:])
            if 1 <= candidate <= 12:
                year, month_no = int(raw[:4]), candidate

        raw_episodes: List[Dict[str, Any]] = []
        for show in self._store.list_all() if self._store else []:
            if is_terminal(show.tmdb_status):
                continue
            for season in self.__calendar_seasons(show):
                for episode in self.__season_episodes(show.tmdbid, season):
                    air = str(episode.get("air_date") or "")[:10]
                    if len(air) != 10:
                        continue
                    raw_episodes.append(
                        {
                            "date": air,
                            "title": show.title,
                            "tmdbid": show.tmdbid,
                            "season": int(episode.get("season") or season),
                            "episode": episode.get("episode"),
                            "name": episode.get("name"),
                            "poster_url": self.__poster_url(show.poster_path),
                            "status_label": status_label(show.tmdb_status),
                        }
                    )

        events = merge_day_episodes(raw_episodes)
        grid = build_month_grid(year, month_no, events, today=today)
        upcoming = [event for event in events if event["date"] >= today.isoformat()]
        upcoming.sort(key=lambda event: (event["date"], event["title"], event["episode_start"]))
        return {
            "month": grid["month_key"],
            "grid": grid,
            "upcoming": upcoming[:12],
            # 是「集」不是「事件」：S02E01-E08 算 8 集
            "upcoming_total": sum(int(event.get("episode_count") or 1) for event in upcoming),
            "today": today.isoformat(),
        }

    def api_check(self) -> Dict[str, Any]:
        return {"success": True, "result": self.check_renewals(force=True)}
