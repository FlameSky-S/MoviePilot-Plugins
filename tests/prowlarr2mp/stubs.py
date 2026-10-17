"""Minimal stubs so the Prowlarr2MP plugin can be imported outside MoviePilot.

Installed on import: fake `app.*`, `apscheduler.*`, `pydantic`.
"""
import sys, types, enum, logging

logging.basicConfig(level=logging.CRITICAL)


def _ensure(name):
    if name in sys.modules:
        return sys.modules[name]
    m = types.ModuleType(name)
    m.__path__ = []
    sys.modules[name] = m
    if "." in name:
        parent, child = name.rsplit(".", 1)
        _ensure(parent)
        setattr(sys.modules[parent], child, m)
    return m


def _set(name, **attrs):
    m = _ensure(name)
    for k, v in attrs.items():
        setattr(m, k, v)
    return m


# ---------- pydantic ----------
class BaseModel:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


def Field(default=..., **kw):
    return default


_set("pydantic", BaseModel=BaseModel, Field=Field)


# ---------- apscheduler ----------
class BackgroundScheduler:
    def __init__(self, *a, **k): self.running = False
    def add_job(self, *a, **k): pass
    def start(self): self.running = True
    def remove_all_jobs(self): pass
    def shutdown(self, wait=False): self.running = False


class CronTrigger:
    def __init__(self, *a, **k): pass
    @classmethod
    def from_crontab(cls, expr): return cls()


_set("apscheduler.schedulers.background", BackgroundScheduler=BackgroundScheduler)
_set("apscheduler.triggers.cron", CronTrigger=CronTrigger)


# ---------- app.schemas.types ----------
class MediaType(enum.Enum):
    MOVIE = "电影"
    TV = "电视剧"
    UNKNOWN = "未知"


class EventType(enum.Enum):
    PluginAction = "plugin_action"


class SystemConfigKey(enum.Enum):
    IndexerSites = "IndexerSites"


_set("app.schemas.types", MediaType=MediaType, EventType=EventType, SystemConfigKey=SystemConfigKey)


# ---------- app.sdk.logging ----------
logger = logging.getLogger("moviepilot")
logger.setLevel(logging.CRITICAL)
_set("app.sdk.logging", logger=logger)


# ---------- app.sdk.media ----------
class TorrentInfo:
    # Explicit signature mirroring MoviePilot v3.1.0 (app.sdk.media.TorrentInfo).
    # Strict on purpose: an unknown kwarg (e.g. imdbid) must raise TypeError, so the
    # stub catches the same class of bug the real runtime does.
    def __init__(self, site=None, site_name=None, site_cookie=None, site_ua=None, site_proxy=False,
                 site_order=0, site_downloader=None, title=None, description=None, media_source=None,
                 media_id=None, enclosure=None, page_url=None, size=0.0, seeders=0, peers=0, grabs=0,
                 pubdate=None, date_elapsed=None, freedate=None, uploadvolumefactor=None,
                 downloadvolumefactor=None, hit_and_run=False, labels=None, pri_order=0, category=None):
        self.site = site
        self.site_name = site_name
        self.title = title
        self.description = description
        self.enclosure = enclosure
        self.page_url = page_url
        self.size = size
        self.seeders = seeders
        self.peers = peers
        self.grabs = grabs
        self.pubdate = pubdate
        self.uploadvolumefactor = uploadvolumefactor
        self.downloadvolumefactor = downloadvolumefactor
        self.category = category
        self.labels = labels if labels is not None else []


_set("app.sdk.media", TorrentInfo=TorrentInfo)


# ---------- app.sdk.events ----------
class Event:
    def __init__(self, **kw):
        self.event_data = kw.get("event_data", {})


class _EventManager:
    def register(self, *a, **k):
        def deco(fn): return fn
        return deco


eventmanager = _EventManager()
_set("app.sdk.events", Event=Event, eventmanager=eventmanager)


# ---------- app.sdk.network ----------
class RequestUtils:
    RESPONDER = None  # callable(url, timeout) -> resp | None

    def __init__(self, headers=None, proxies=None, **k): pass

    def get_res(self, url, timeout=None):
        return RequestUtils.RESPONDER(url, timeout) if RequestUtils.RESPONDER else None


class SitesHelper:
    _store = {}
    def add_indexer(self, domain, indexer): SitesHelper._store[domain] = indexer
    def get_indexer(self, domain): return SitesHelper._store.get(domain)
    def get_indexers(self): return list(SitesHelper._store.values())


_set("app.sdk.network", RequestUtils=RequestUtils, SitesHelper=SitesHelper)


# ---------- app.sdk.utilities ----------
class StringUtils:
    @staticmethod
    def is_chinese(text):
        return any("\u4e00" <= c <= "\u9fff" for c in (text or ""))


_set("app.sdk.utilities", StringUtils=StringUtils)


# ---------- app.sdk.plugin ----------
class _PluginBase:
    def __init__(self, *a, **k): pass
    def update_config(self, cfg=None): self._cfg = cfg
    def post_message(self, *a, **k): pass


_set("app.sdk.plugin", _PluginBase=_PluginBase)


class PluginManager:
    running_plugins = {}


_set("app.sdk.plugin.manager", PluginManager=PluginManager)


# ---------- app.agent.tools.base ----------
class MoviePilotTool(BaseModel):
    pass


_set("app.agent.tools.base", MoviePilotTool=MoviePilotTool)


# ---------- app.chain.search ----------
class SearchChain:
    @staticmethod
    def _SearchChain__search_all_sites(chain_self, keyword, mediainfo=None, sites=None, page=0, area="title", mtype=None):
        return []

    @staticmethod
    def _SearchChain__async_search_all_sites(chain_self, keyword, mediainfo=None, sites=None, page=0, area="title", mtype=None):
        return []


_set("app.chain.search", SearchChain=SearchChain)


# ---------- app.db.oper.systemconfig ----------
class SystemConfigOper:
    RETURN = None  # tests may set this to simulate stored config values

    def get(self, key=None):
        return SystemConfigOper.RETURN


_set("app.db.oper.systemconfig", SystemConfigOper=SystemConfigOper)


class Resp:
    def __init__(self, status_code=200, data=None, text=""):
        self.status_code = status_code
        self._data = data
        self.text = text

    def json(self):
        return self._data


def _repo_root(start):
    """从 tests/ 往上层找到带 `plugins.v3` 的仓根（本仓是多插件仓，测试在 tests/<id>/ 下）。"""
    import os

    cur = os.path.abspath(start)
    while True:
        if os.path.isdir(os.path.join(cur, "plugins.v3")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            raise RuntimeError("找不到仓根（含 plugins.v3 的目录）")
        cur = parent


def load_plugin(repo_root=None):
    import os, importlib.util
    if repo_root is None:
        repo_root = _repo_root(os.path.dirname(os.path.abspath(__file__)))
    pkg_dir = os.path.join(repo_root, "plugins.v3", "prowlarr2mp")
    spec = importlib.util.spec_from_file_location(
        "prowlarr2mp", os.path.join(pkg_dir, "__init__.py"),
        submodule_search_locations=[pkg_dir])
    mod = importlib.util.module_from_spec(spec)
    sys.modules["prowlarr2mp"] = mod
    spec.loader.exec_module(mod)
    return mod
