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

from datetime import date  # noqa: E402

from autorenew_core.calendarview import build_month_grid  # noqa: E402
from autorenew_core.library import diff_watchlist, library_candidates, parse_seasoninfo  # noqa: E402
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
    season_numbers,
    season_stats,
    should_notify,
)
from autorenew_core.rules import RULE_FIELDS, merge_rules, rule_payload  # noqa: E402
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
# library —— 宿主 mediaserveritem 的真实取值（实测：item_type 是中文，
# seasoninfo 是 JSON 字符串）—— 这两个坑踩过，测试钉死
# --------------------------------------------------------------------------

@case
def test_parse_seasoninfo_handles_json_string():
    assert parse_seasoninfo('{"1": [1, 2, 3], "2": [1, 2]}') == {1: 3, 2: 2}


@case
def test_parse_seasoninfo_tolerates_dict_and_junk():
    assert parse_seasoninfo({"3": [1, 2]}) == {3: 2}
    assert parse_seasoninfo(None) == {}
    assert parse_seasoninfo("") == {}
    assert parse_seasoninfo("not json") == {}
    assert parse_seasoninfo("{}") == {}
    assert parse_seasoninfo([1, 2]) == {}
    assert parse_seasoninfo('{"0": [1], "1": [1, 2]}') == {1: 2}  # S0 排除
    assert parse_seasoninfo('{"x": [1], "2": [1]}') == {2: 1}  # 非数字季号跳过
    assert parse_seasoninfo({"2": "not-a-list"}) == {2: 0}


@case
def test_library_candidates_filters_by_chinese_item_type():
    rows = [
        {"item_type": "电影", "title": "某电影", "media_id": "1", "seasoninfo": "{}"},
        {
            "item_type": "电视剧",
            "title": "赛博朋克：边缘行者",
            "media_id": "105248",
            "year": "2022",
            "seasoninfo": '{"1": [1, 2, 3]}',
        },
    ]
    got = library_candidates(rows)
    assert [c["tmdbid"] for c in got] == [105248], got
    assert got[0]["title"] == "赛博朋克：边缘行者"
    assert got[0]["season"] == 1


@case
def test_library_candidates_picks_highest_season():
    rows = [
        {
            "item_type": "电视剧",
            "title": "为了全人类",
            "media_id": "87917",
            "seasoninfo": '{"1": [1], "3": [1, 2, 3]}',
        }
    ]
    assert library_candidates(rows)[0]["season"] == 3


@case
def test_library_candidates_defaults_to_season_one_without_seasoninfo():
    rows = [{"item_type": "电视剧", "title": "X", "media_id": "9", "seasoninfo": "{}"}]
    assert library_candidates(rows)[0]["season"] == 1


@case
def test_library_candidates_skips_unusable_rows():
    rows = [
        {"item_type": "电视剧", "title": None, "media_id": "9", "seasoninfo": "{}"},
        {"item_type": "电视剧", "title": "X", "media_id": None, "seasoninfo": "{}"},
        {"item_type": "电视剧", "title": "X", "media_id": "abc", "seasoninfo": "{}"},
        {"item_type": "", "title": "X", "media_id": "9", "seasoninfo": "{}"},
    ]
    assert library_candidates(rows) == []


@case
def test_library_candidates_accepts_attribute_objects():
    """in-process ORM 给的是对象，不是 dict。"""

    class Row:
        def __init__(self, **kw):
            self.__dict__.update(kw)

    rows = [Row(item_type="电视剧", title="Y", media_id="7", seasoninfo='{"2": [1, 2]}')]
    got = library_candidates(rows)
    assert got[0]["tmdbid"] == 7 and got[0]["season"] == 2


# --------------------------------------------------------------------------
# library diff —— 「从媒体库导入」确认弹窗的比对 seam（纯函数）
#
# 语义（老板已确认）：
#   added   = 库里有、名单里没有          -> 建议新增
#   kept    = 库里也有、名单里也有        -> 不动
#   removed = 名单里 source=媒体库导入，但现在库里已经没有 -> 建议移除
#   名单里 source≠媒体库导入 且库里没有   -> 三条列表都不进（继续追踪，不动）
# --------------------------------------------------------------------------

def _lib(tmdbid, title, season=1):
    return {"tmdbid": tmdbid, "title": title, "year": None, "season": season, "seasons": {}}


@case
def test_diff_marks_library_only_shows_as_added():
    got = diff_watchlist([], [_lib(1, "新剧")])
    assert [c["tmdbid"] for c in got["added"]] == [1], got
    assert got["removed"] == [] and got["kept"] == []


@case
def test_diff_marks_intersection_as_kept():
    tracked = [TrackedShow(tmdbid=1, title="旧剧", source=SOURCE_LIBRARY)]
    got = diff_watchlist(tracked, [_lib(1, "旧剧")])
    assert got["added"] == [] and got["removed"] == [], got
    assert [s["tmdbid"] for s in got["kept"]] == [1], got


@case
def test_diff_removes_only_library_sourced_shows_missing_from_library():
    tracked = [
        TrackedShow(tmdbid=1, title="库导入了但库里没了", source=SOURCE_LIBRARY),
        TrackedShow(tmdbid=2, title="手动加的，库里没有也留着", source=SOURCE_MANUAL),
        TrackedShow(tmdbid=3, title="订阅同步的，库里没有也留着", source=SOURCE_SUBSCRIBE),
    ]
    got = diff_watchlist(tracked, [])
    assert [s["tmdbid"] for s in got["removed"]] == [1], got
    assert got["kept"] == [] and got["added"] == [], got
    # 手动/订阅来源的绝不许出现在任何一组里（否则会被误删）
    seen = {s["tmdbid"] for key in ("added", "removed", "kept") for s in got[key]}
    assert seen == {1}, seen


@case
def test_diff_matches_ids_across_str_and_int():
    tracked = [TrackedShow(tmdbid=105248, title="赛博朋克", source=SOURCE_LIBRARY)]
    got = diff_watchlist(tracked, [{"tmdbid": "105248", "title": "赛博朋克", "season": 1}])
    assert got["kept"] and not got["added"] and not got["removed"], got


@case
def test_diff_is_empty_for_empty_inputs():
    assert diff_watchlist([], []) == {"added": [], "removed": [], "kept": []}
    assert diff_watchlist(None, None) == {"added": [], "removed": [], "kept": []}


@case
def test_diff_added_payload_carries_title_and_season():
    got = diff_watchlist([], [_lib(7, "某剧", season=3)])
    assert got["added"][0]["title"] == "某剧" and got["added"][0]["season"] == 3


@case
def test_diff_handles_duplicate_candidates_without_double_counting():
    got = diff_watchlist([], [_lib(1, "重复"), _lib(1, "重复")])
    assert [c["tmdbid"] for c in got["added"]] == [1], got


# --------------------------------------------------------------------------
# 月历网格 —— 「播出日历」重做的纯函数 seam（纯函数，不碰宿主）
#
# 网格事实来自 `calendar.Calendar(firstweekday=0).monthdatescalendar`，不是脑算：
#   2026-10  31 天，10-01 周四 → 首格 2026-09-28，末格 2026-11-01，5 周
#   2026-06  30 天，06-01 周一 → 首格就是 06-01，无前导补位
#   2026-11  30 天，11-01 周日 → 10-26 起，**6 周**（末格 2026-12-06）
# --------------------------------------------------------------------------

def _ev(day, title="某剧", tmdbid=1, season=1, episode=None):
    return {
        "date": day,
        "title": title,
        "tmdbid": tmdbid,
        "season": season,
        "episode": episode,
        "poster_url": None,
        "status_label": "连载中",
    }


@case
def test_month_grid_october_2026_layout():
    got = build_month_grid(2026, 10, [])
    assert got["month_key"] == "2026-10" and got["days"] == 31, got
    assert len(got["weeks"]) == 5, len(got["weeks"])
    first = got["weeks"][0]
    assert [c["day"] for c in first] == [28, 29, 30, 1, 2, 3, 4], first
    assert first[0]["date"] == "2026-09-28" and first[0]["in_month"] is False
    assert first[3]["date"] == "2026-10-01" and first[3]["in_month"] is True
    assert got["weeks"][-1][-1]["date"] == "2026-11-01", got["weeks"][-1][-1]


@case
def test_month_grid_has_no_leading_pad_when_month_starts_on_monday():
    got = build_month_grid(2026, 6, [])
    assert got["weeks"][0][0]["date"] == "2026-06-01", got["weeks"][0][0]
    assert got["weeks"][0][0]["in_month"] is True
    assert got["weeks"][0][0]["day"] == 1


@case
def test_month_grid_uses_six_weeks_when_month_spans_six():
    got = build_month_grid(2026, 11, [])
    assert len(got["weeks"]) == 6, len(got["weeks"])
    assert got["weeks"][-1][-1]["date"] == "2026-12-06", got["weeks"][-1][-1]


@case
def test_month_grid_attaches_events_to_the_right_day():
    got = build_month_grid(2026, 10, [_ev("2026-10-20", "赛博朋克", 105248)])
    cells = [c for w in got["weeks"] for c in w if c["date"] == "2026-10-20"]
    assert len(cells) == 1, cells
    assert [e["title"] for e in cells[0]["events"]] == ["赛博朋克"], cells[0]
    rest = [c for w in got["weeks"] for c in w if c["date"] != "2026-10-20"]
    assert all(c["events"] == [] for c in rest)
    assert got["events_total"] == 1


@case
def test_month_grid_keeps_padding_day_events():
    # 2026-09-28 在网格里但属于上月 —— 事件必须照挂，否则跨月那一格会丢内容
    got = build_month_grid(2026, 10, [_ev("2026-09-28", "上月最后一天")])
    cell = got["weeks"][0][0]
    assert cell["in_month"] is False, cell
    assert [e["title"] for e in cell["events"]] == ["上月最后一天"], cell


@case
def test_month_grid_drops_events_outside_the_grid():
    got = build_month_grid(2026, 10, [_ev("2026-12-31"), _ev("2026-01-01")])
    assert got["events_total"] == 0, got["events_total"]
    assert all(c["events"] == [] for w in got["weeks"] for c in w)


@case
def test_month_grid_marks_today_exactly_once():
    got = build_month_grid(2026, 10, [], today=date(2026, 10, 6))
    marked = [c["date"] for w in got["weeks"] for c in w if c["is_today"]]
    assert marked == ["2026-10-06"], marked


@case
def test_month_grid_prev_next_wrap_across_year_boundary():
    jan = build_month_grid(2026, 1, [])
    assert jan["prev"] == "2025-12" and jan["next"] == "2026-02", jan
    dec = build_month_grid(2026, 12, [])
    assert dec["prev"] == "2026-11" and dec["next"] == "2027-01", dec


@case
def test_month_grid_sorts_events_within_a_day():
    got = build_month_grid(2026, 10, [_ev("2026-10-20", "B", 2), _ev("2026-10-20", "A", 1)])
    cell = [c for w in got["weeks"] for c in w if c["date"] == "2026-10-20"][0]
    assert [e["title"] for e in cell["events"]] == ["A", "B"], cell


# --------------------------------------------------------------------------
# 季数统计：已完结区「x/y季」
# --------------------------------------------------------------------------


@case
def test_season_stats_excludes_specials_from_total():
    """特别季 S0 一律不计入总季数。"""
    got = season_stats(_seasons((0, 5), (1, 8), (2, 10)), library={1})
    assert got["total"] == 2, got
    assert got["library"] == 1, got


@case
def test_season_stats_total_is_season_count_not_max_number():
    """y 是「季的个数」而不是最大季号 —— 缺号时两者不等（1/2/5 应为 3 而不是 5）。"""
    got = season_stats(_seasons((1, 8), (2, 10), (5, 6)), library={1, 2})
    assert got["total"] == 3, got
    assert got["library"] == 2, got


@case
def test_season_stats_library_ignores_seasons_tmdb_does_not_know():
    """库里多出来的季（S0、幽灵季）不算进 x，也不能让 x 超过 y。"""
    got = season_stats(_seasons((1, 8), (2, 10)), library={0, 1, 9})
    assert got["library"] == 1, got
    assert got["total"] == 2, got


@case
def test_season_stats_accepts_string_season_numbers():
    """库内季号来自 `seasoninfo` 的 JSON 键，可能是字符串。"""
    got = season_stats(_seasons((1, 8), (2, 10)), library={"1", "2"})
    assert got["library"] == 2, got


@case
def test_season_stats_handles_empty_and_junk():
    assert season_stats([], library={1}) == {"library": 0, "total": 0}
    assert season_stats(None, library=None) == {"library": 0, "total": 0}
    assert season_stats(None, library={"x", None}) == {"library": 0, "total": 0}
    junk = [{"season_number": None}, {"season_number": "2", "episode_count": 3}]
    assert season_stats(junk, library={2}) == {"library": 1, "total": 1}


# --------------------------------------------------------------------------
# 通知去重：同一部剧的同一季只提醒一次
# --------------------------------------------------------------------------


@case
def test_should_notify_first_time_for_a_season():
    assert should_notify(2, None) is True
    assert should_notify(2, 0) is True


@case
def test_should_notify_skips_already_notified_season():
    """仅提醒模式下 `show.season` 永不推进，不去重就会每 6h 重复轰炸。"""
    assert should_notify(2, 2) is False
    assert should_notify(2, 3) is False


@case
def test_should_notify_when_a_higher_season_appears():
    assert should_notify(3, 2) is True


@case
def test_should_notify_without_season_is_false():
    assert should_notify(None, None) is False
    assert should_notify(0, None) is False


# --------------------------------------------------------------------------
# 硬门槛：已完结 / 已砍 的剧永不自动续订
# --------------------------------------------------------------------------


@case
def test_decide_renewal_never_renews_ended_show_with_new_season():
    """已完结的剧即便 TMDB 上有更新的季，也不许自动续订。

    真事：名单里「绝望写手」在已完结区（TMDB=Ended），但 TMDB 有 5 季、磁盘只有
    第 1 季 —— 旧逻辑判成「有新季」连续建了 S2、S3 两条订阅并真的下载了。
    """
    show = TrackedShow(tmdbid=1, title="绝望写手", season=1, tmdb_status="Ended")
    got = decide_renewal(show, _seasons((1, 10), (2, 8), (3, 9), (4, 8), (5, 6)))
    assert got.should_renew is False, got
    assert got.season is None, got
    assert "已完结" in got.reason, got.reason


@case
def test_decide_renewal_never_renews_canceled_show_with_new_season():
    show = TrackedShow(tmdbid=2, title="被砍的剧", season=1, tmdb_status="Canceled")
    got = decide_renewal(show, _seasons((1, 10), (2, 8)))
    assert got.should_renew is False, got
    assert "已砍" in got.reason or "已完结" in got.reason, got.reason


@case
def test_decide_renewal_still_renews_returning_series():
    """门槛只针对已终止状态，连载中的剧照旧续订。"""
    show = TrackedShow(tmdbid=3, title="连载中", season=1, tmdb_status="Returning Series")
    got = decide_renewal(show, _seasons((1, 10), (2, 8)))
    assert got.should_renew is True, got
    assert got.season == 2, got


@case
def test_decide_renewal_terminal_gate_beats_per_show_switch():
    """硬门槛优先于单剧开关：已完结就是不发，开关是开还是关都一样。"""
    for flag in (True, False):
        show = TrackedShow(tmdbid=4, title="已完结", season=1, auto_renew=flag,
                           tmdb_status="Ended")
        assert decide_renewal(show, _seasons((1, 10), (2, 8))).should_renew is False


@case
def test_decide_renewal_unknown_status_still_renews():
    """status 未知（TMDB 新取值 / 拉取失败）不做拦截，避免误杀。"""
    show = TrackedShow(tmdbid=5, title="状态未知", season=1, tmdb_status=None)
    assert decide_renewal(show, _seasons((1, 10), (2, 8))).should_renew is True


# --------------------------------------------------------------------------
# 续订规则的三级回退
# --------------------------------------------------------------------------


@case
def test_merge_rules_first_non_empty_level_wins():
    """三级回退：每个字段独立取「第一个非空」的那一级。"""
    got = merge_rules(
        [
            {"quality": "BluRay"},              # L1 该剧已有订阅
            {"quality": "WEB-DL", "resolution": "1080P"},  # L2 插件设置
            {"resolution": "4K"},               # L3 交给宿主全局
        ]
    )
    assert got == {"quality": "BluRay", "resolution": "1080P"}, got


@case
def test_merge_rules_skips_empty_strings_none_and_blank_lists():
    """空值不算「有值」——空字符串 / None / 空列表都要继续往下回退。"""
    got = merge_rules(
        [
            {"quality": "", "resolution": None, "sites": []},
            {"quality": "WEB-DL", "sites": [1, 4]},
        ]
    )
    assert got == {"quality": "WEB-DL", "sites": [1, 4]}, got


@case
def test_merge_rules_keeps_unset_fields_out_of_the_result():
    """三级都没配的字段**不出现在结果里** —— 这样宿主才会用自己的全局默认。"""
    got = merge_rules([{}, {"quality": "BluRay"}, {}])
    assert got == {"quality": "BluRay"}, got
    assert "resolution" not in got, got


@case
def test_merge_rules_ignores_the_string_null_sentinel():
    """宿主空值会落成字符串 "null"（实测 subscribe.sites 就是这样），不能当有值。"""
    got = merge_rules([{"sites": "null", "filter_groups": "null"}, {"sites": [1]}])
    assert got == {"sites": [1]}, got


@case
def test_merge_rules_handles_empty_and_junk_levels():
    assert merge_rules([]) == {}
    assert merge_rules([None, {}, {"quality": "x"}]) == {"quality": "x"}


@case
def test_merge_rules_ignores_fields_not_in_the_allow_list():
    """只认订阅表真实存在的列，界面上的无关字段不许漏进订阅行。"""
    got = merge_rules([{"quality": "BluRay", "随便什么键": 1, "enabled": True}])
    assert got == {"quality": "BluRay"}, got


@case
def test_rule_payload_normalizes_sites_to_ints_and_trims_strings():
    got = rule_payload(
        {
            "rules_sites": ["1", 4, None, "x"],
            "rules_filter_groups": [" 电视剧 ", "", None],
            "rules_quality": "  BluRay  ",
            "rules_resolution": "   ",
            "rules_downloader": "qbittorrent",
            "rules_include": "H265",
            "enabled": True,
        }
    )
    assert got == {
        "sites": [1, 4],
        "filter_groups": ["电视剧"],
        "quality": "BluRay",
        "downloader": "qbittorrent",
        "include": "H265",
    }, got


@case
def test_rule_payload_drops_everything_when_nothing_configured():
    """一个都没配 → 空 dict → 上游不传任何字段 → 宿主用全局默认。"""
    assert rule_payload({}) == {}
    assert rule_payload(None) == {}
    assert rule_payload({"rules_sites": [], "rules_quality": ""}) == {}


@case
def test_rule_payload_output_is_a_valid_fallback_level():
    """`rule_payload` 的输出必须能直接当作三级回退里的第二级使用。"""
    level = rule_payload({"rules_quality": "WEB-DL"})
    got = merge_rules([{}, level, {"quality": "4K"}])
    assert got == {"quality": "WEB-DL"}, got


@case
def test_season_numbers_drops_specials_and_sorts():
    """持久化用的季号列表：去掉特别季 S0、按升序，脏值丢弃。"""
    got = season_numbers(
        [
            {"season_number": 0, "episode_count": 5},
            {"season_number": 2, "episode_count": 8},
            {"season_number": 1, "episode_count": 10},
            {"season_number": "x"},
            {},
        ]
    )
    assert got == [1, 2], got
    assert season_numbers(None) == []


@case
def test_season_numbers_roundtrip_reproduces_season_stats():
    """页面现场重算拿到的结果，必须和联网刷新时算的一模一样。"""
    seasons = [{"season_number": 1}, {"season_number": 2}, {"season_number": 3}]
    direct = season_stats(seasons, [1, 3])
    rebuilt = season_stats([{"season_number": n} for n in season_numbers(seasons)], [1, 3])
    assert direct == rebuilt == {"library": 2, "total": 3}, (direct, rebuilt)


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
