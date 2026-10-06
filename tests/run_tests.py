#!/usr/bin/env python3
"""裸机单测：只覆盖 `plugins.v3/autorenew/core/` 下的纯逻辑。

跑法：`python tests/run_tests.py`（不需要 pytest / MoviePilot 运行环境）
失败会打印断言落差并以非 0 退出。
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORE_DIR = os.path.join(ROOT, "plugins.v3", "autorenew", "core")


def _load_core() -> None:
    """目录名 `plugins.v3` 带点、不是合法包名，必须按路径加载。"""
    spec = importlib.util.spec_from_file_location(
        "autorenew_core",
        os.path.join(CORE_DIR, "__init__.py"),
        submodule_search_locations=[CORE_DIR],
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["autorenew_core"] = module
    spec.loader.exec_module(module)


_load_core()

from autorenew_core.models import (  # noqa: E402
    SOURCE_LIBRARY,
    SOURCE_MANUAL,
    SOURCE_SUBSCRIBE,
    TrackedShow,
    badge_for,
    is_terminal,
    status_label,
)
from autorenew_core.renewal import (  # noqa: E402
    decide_renewal,
    first_uncovered_season,
    latest_season,
)
from autorenew_core.store import WatchlistStore  # noqa: E402

CASES = []


def case(fn):
    CASES.append(fn)
    return fn


def _seasons(*pairs):
    return [{"season_number": n, "episode_count": e, "air_date": None} for n, e in pairs]


# --------------------------------------------------------------------------
# models
# --------------------------------------------------------------------------

@case
def test_status_label_maps_known_tmdb_status():
    assert status_label("Returning Series") == "连载中", status_label("Returning Series")
    assert status_label("Planned") == "已续订"
    assert status_label("In Production") == "制作中"
    assert status_label("Ended") == "已完结"
    assert status_label("Canceled") == "已砍"


@case
def test_status_label_passes_through_unknown_and_none():
    # TMDB 新增取值时要能看见，而不是被吞成「未知」
    assert status_label("Brand New Status") == "Brand New Status"
    assert status_label(None) == "未知"
    assert status_label("") == "未知"


@case
def test_is_terminal_only_for_ended_and_canceled():
    assert is_terminal("Ended") is True
    assert is_terminal("Canceled") is True
    assert is_terminal("Returning Series") is False
    assert is_terminal(None) is False


@case
def test_tracked_show_round_trip():
    show = TrackedShow(tmdbid=1234, title="某人", year=2020, season=3, source=SOURCE_LIBRARY)
    restored = TrackedShow.from_dict(json.loads(json.dumps(show.to_dict())))
    assert restored == show, (restored, show)


@case
def test_tracked_show_from_dict_ignores_unknown_and_coerces_types():
    restored = TrackedShow.from_dict(
        {"tmdbid": "1234", "title": "某人", "season": "2", "unknown_field": "drop me"}
    )
    assert restored.tmdbid == 1234 and isinstance(restored.tmdbid, int)
    assert restored.season == 2 and isinstance(restored.season, int)
    assert not hasattr(restored, "unknown_field")


@case
def test_badge_marks_renewable_when_new_season_has_episodes():
    assert (
        badge_for(
            tmdb_status="Returning Series",
            tracked_season=1,
            latest_season=2,
            latest_season_episodes=10,
            auto_renew=True,
        )
        == "有新季可订阅"
    )


@case
def test_badge_waits_when_new_season_has_no_episodes_yet():
    assert (
        badge_for(
            tmdb_status="Planned",
            tracked_season=1,
            latest_season=2,
            latest_season_episodes=0,
            auto_renew=True,
        )
        == "新季已确认待开播"
    )


@case
def test_badge_terminal_only_when_nothing_newer():
    assert (
        badge_for(
            tmdb_status="Ended",
            tracked_season=3,
            latest_season=3,
            latest_season_episodes=12,
            auto_renew=True,
        )
        == "已完结"
    )
    # 状态 Ended 但 TMDB 还有更新的季 -> 不是「已完结」，是「有新季可订阅」
    assert (
        badge_for(
            tmdb_status="Ended",
            tracked_season=1,
            latest_season=2,
            latest_season_episodes=8,
            auto_renew=True,
        )
        == "有新季可订阅"
    )


@case
def test_badge_paused_wins():
    assert (
        badge_for(
            tmdb_status="Returning Series",
            tracked_season=1,
            latest_season=2,
            latest_season_episodes=10,
            auto_renew=False,
        )
        == "已暂停续订"
    )


# --------------------------------------------------------------------------
# renewal
# --------------------------------------------------------------------------

@case
def test_specials_season_zero_is_excluded():
    assert [s["season_number"] for s in _norm(_seasons((0, 5), (1, 10), (2, 8)))] == [1, 2]
    assert first_uncovered_season(0, _seasons((0, 5), (1, 10)))["season_number"] == 1


def _norm(seasons):
    from autorenew_core.renewal import _normalize_seasons

    return _normalize_seasons(seasons)


@case
def test_normalize_skips_garbage_rows():
    got = _norm([{"season_number": "x"}, {"season_number": None}, {"season_number": 2}, {}])
    assert [s["season_number"] for s in got] == [2], got


@case
def test_latest_season_picks_highest_and_none_when_empty():
    assert latest_season(_seasons((1, 10), (3, 6), (2, 8)))["season_number"] == 3
    assert latest_season([]) is None
    assert latest_season(None) is None


@case
def test_decide_renewal_true_on_smallest_uncovered_season():
    decision = decide_renewal(TrackedShow(tmdbid=1, title="A", season=1), _seasons((1, 10), (2, 8), (3, 6)))
    assert decision.should_renew is True, decision
    assert decision.season == 2, decision  # 不跳季
    assert decision.episode_count == 8


@case
def test_decide_renewal_false_without_newer_season():
    decision = decide_renewal(TrackedShow(tmdbid=1, title="A", season=2), _seasons((1, 10), (2, 8)))
    assert decision.should_renew is False
    assert decision.season is None
    assert "没有" in decision.reason


@case
def test_decide_renewal_blocks_when_new_season_has_zero_episodes():
    # 宿主事实：该季集数为 0 时 create.py 直接报「未获取到第 X 季的总集数」
    decision = decide_renewal(TrackedShow(tmdbid=1, title="A", season=1), _seasons((1, 10), (2, 0)))
    assert decision.should_renew is False
    assert decision.season == 2
    assert "尚无集数" in decision.reason, decision.reason


@case
def test_decide_renewal_respects_auto_renew_toggle():
    show = TrackedShow(tmdbid=1, title="A", season=1, auto_renew=False)
    decision = decide_renewal(show, _seasons((1, 10), (2, 8)))
    assert decision.should_renew is False
    assert "关闭" in decision.reason


@case
def test_decide_renewal_handles_empty_tmdb_payload():
    decision = decide_renewal(TrackedShow(tmdbid=1, title="A", season=1), None)
    assert decision.should_renew is False


# --------------------------------------------------------------------------
# store
# --------------------------------------------------------------------------

class FakeKV:
    """内存版 plugindata。"""

    def __init__(self, initial=None):
        self.bag = dict(initial or {})
        self.writes = 0

    def get(self, key):
        return self.bag.get(key)

    def save(self, key, value):
        self.writes += 1
        self.bag[key] = value


def _store(initial=None):
    kv = FakeKV(initial)
    return WatchlistStore(kv.get, kv.save), kv


@case
def test_store_upsert_then_list():
    store, kv = _store()
    store.upsert(TrackedShow(tmdbid=11, title="剧一", source=SOURCE_MANUAL, added_at="2026-01-01"))
    shows = store.list_all()
    assert len(shows) == 1 and shows[0].tmdbid == 11
    assert json.loads(kv.bag["watchlist"])[0]["title"] == "剧一"  # 真落到了 KV 上


@case
def test_store_upsert_overwrites_and_keeps_added_at():
    store, _ = _store()
    store.upsert(TrackedShow(tmdbid=11, title="剧一", added_at="2026-01-01"))
    store.upsert(TrackedShow(tmdbid=11, title="剧一改", season=4))
    shows = store.list_all()
    assert len(shows) == 1, shows
    assert shows[0].title == "剧一改" and shows[0].season == 4
    assert shows[0].added_at == "2026-01-01", shows[0].added_at


@case
def test_store_remove_only_touches_watchlist():
    store, _ = _store()
    store.upsert(TrackedShow(tmdbid=11, title="剧一"))
    store.upsert(TrackedShow(tmdbid=22, title="剧二"))
    assert store.remove(11) is True
    assert [s.tmdbid for s in store.list_all()] == [22]
    assert store.remove(11) is False  # 幂等：再删一次返回 False


@case
def test_store_set_season():
    store, _ = _store()
    store.upsert(TrackedShow(tmdbid=11, title="剧一", season=1))
    assert store.set_season(11, 2) is True
    assert store.get(11).season == 2
    assert store.set_season(99, 2) is False


@case
def test_store_counts_sources():
    store, _ = _store()
    store.upsert(TrackedShow(tmdbid=1, title="a", source=SOURCE_MANUAL))
    store.upsert(TrackedShow(tmdbid=2, title="b", source=SOURCE_SUBSCRIBE))
    store.upsert(TrackedShow(tmdbid=3, title="c", source=SOURCE_LIBRARY))
    store.upsert(TrackedShow(tmdbid=4, title="d", source=SOURCE_SUBSCRIBE))
    assert store.sources() == {SOURCE_MANUAL: 1, SOURCE_SUBSCRIBE: 2, SOURCE_LIBRARY: 1}


@case
def test_store_survives_corrupt_payload():
    for junk in ("not json", "{}", "[1,2,3]", ""):
        store, _ = _store({"watchlist": junk})
        assert store.list_all() == [], junk
    store, _ = _store({"watchlist": None})
    assert store.list_all() == []
    # 坏数据之后还能正常写入
    store.upsert(TrackedShow(tmdbid=9, title="恢复"))
    assert [s.tmdbid for s in store.list_all()] == [9]


# --------------------------------------------------------------------------

def main() -> int:
    failed = []
    for fn in CASES:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
        except Exception:  # noqa: BLE001
            failed.append(fn.__name__)
            print(f"  FAIL  {fn.__name__}")
            traceback.print_exc(limit=2)
    total = len(CASES)
    print(f"\n{total - len(failed)}/{total} passed")
    if failed:
        print("failed: " + ", ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
