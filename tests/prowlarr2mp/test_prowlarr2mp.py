import stubs
from stubs import RequestUtils, Resp, MediaType

PLUGIN = stubs.load_plugin()

PUB_CAT = {"movie": [{"id": 2000, "cat": "Movies", "desc": "Movies"}],
           "tv": [{"id": 5000, "cat": "TV", "desc": "TV"}]}


def new_inst():
    inst = PLUGIN.Prowlarr2MP()
    inst._enabled = True
    inst._host = "http://prowlarr:9696"
    inst._api_key = "KEY"
    inst._indexers = []
    return inst


# ---- fix 1: public sites are no longer filtered ----
def test_public_indexer_is_kept():
    RequestUtils.RESPONDER = None
    inst = new_inst()
    inst._get_indexers_from_prowlarr = lambda: [{"id": 1, "name": "PublicSite", "privacy": "public", "enable": True}]
    inst._build_indexer_dict = lambda idx: ({"id": "Prowlarr2MP-PublicSite", "name": "Prowlarr2MP-PublicSite",
                                             "domain": "prowlarr2mp.1", "public": True, "category": PUB_CAT}, False)
    assert inst._fetch_and_build_indexers() is True
    assert len(inst._indexers) == 1
    assert inst._indexers[0]["public"] is True
    assert inst._indexers[0]["domain"] == "prowlarr2mp.1"


# ---- fix 2: category-probe failure must NOT drop the indexer ----
def test_category_probe_failure_falls_back_not_dropped():
    RequestUtils.RESPONDER = lambda url, timeout=None: None  # probe fails
    inst = new_inst()
    inst._get_indexers_from_prowlarr = lambda: [{"id": 9, "name": "PubNoCat", "privacy": "public"}]
    assert inst._fetch_and_build_indexers() is True
    assert len(inst._indexers) == 1
    cat = inst._indexers[0]["category"]
    assert cat["movie"][0]["id"] == 2000 and cat["tv"][0]["id"] == 5000
    assert inst._indexers[0]["domain"] == "prowlarr2mp.9"


def test_get_indexer_categories_failure_returns_default():
    RequestUtils.RESPONDER = lambda url, timeout=None: None
    inst = new_inst()
    cat, xxx = inst._get_indexer_categories(5)
    assert xxx is False
    assert cat["movie"][0]["id"] == 2000 and cat["tv"][0]["id"] == 5000


def test_xxx_only_still_filtered():
    RequestUtils.RESPONDER = lambda url, timeout=None: Resp(200, {"capabilities": {"categories": [{"id": 6000, "name": "XXX"}]}})
    inst = new_inst()
    inst._get_indexers_from_prowlarr = lambda: [{"id": 3, "name": "AdultOnly", "privacy": "public"}]
    assert inst._fetch_and_build_indexers() is True
    assert inst._indexers == []


def test_xxx_only_flag_from_categories():
    RequestUtils.RESPONDER = lambda url, timeout=None: Resp(200, {"capabilities": {"categories": [{"id": 6000, "name": "XXX"}]}})
    inst = new_inst()
    cat, xxx = inst._get_indexer_categories(3)
    assert xxx is True and cat is None


def test_movie_tv_categories_mapped():
    RequestUtils.RESPONDER = lambda url, timeout=None: Resp(200, {"capabilities": {"categories": [
        {"id": 2000, "name": "Movies"}, {"id": 5000, "name": "TV"}, {"id": 6000, "name": "XXX"}]}})
    inst = new_inst()
    cat, xxx = inst._get_indexer_categories(4)
    assert xxx is False
    assert [c["id"] for c in cat["movie"]] == [2000]
    assert [c["id"] for c in cat["tv"]] == [5000]


# ---- helpers ----
def test_is_imdb_id():
    inst = new_inst()
    assert inst._is_imdb_id("tt0133093") is True
    assert inst._is_imdb_id("The Matrix") is False
    assert inst._is_imdb_id("tt123456") is False  # 6 digits


def test_is_english_keyword():
    inst = new_inst()
    assert inst._is_english_keyword("The Matrix") is True
    assert inst._is_english_keyword("\u9ed1\u5ba2\u5e1d\u56fd") is False


def test_build_search_params_imdb_and_keyword():
    inst = new_inst()
    p = inst._build_search_params("tt0133093", 12, MediaType.MOVIE, 0)
    d = dict(p)
    assert d.get("indexerIds") == 12
    assert d.get("imdbId") == "0133093"
    assert "query" not in d
    p2 = inst._build_search_params("The Matrix", 12, MediaType.TV, 0)
    d2 = dict(p2)
    assert d2.get("query") == "The Matrix"
    assert ("categories", 5000) in p2


def test_torrent_category_map():
    inst = new_inst()
    assert inst._torrent_category([{"id": 2000}]) == "movie"
    assert inst._torrent_category([{"id": 5000}]) == "tv"
    assert inst._torrent_category([{"id": 6000}]) is None


def test_format_imdb_id():
    inst = new_inst()
    assert inst._format_imdb_id(133093) == "tt133093"
    assert inst._format_imdb_id("tt99") == "tt99"


# ---- the domain<->id coupling we flagged ----
def test_search_torrents_extracts_id_from_domain():
    RequestUtils.RESPONDER = None
    inst = new_inst()
    inst._indexers = [{"id": "Prowlarr2MP-MyIndexer", "name": "Prowlarr2MP-MyIndexer",
                       "domain": "prowlarr2mp.12", "category": PUB_CAT}]
    captured = {}

    def fake_search(params, indexer_id=None):
        captured["params"] = params
        return []

    inst._search_prowlarr_api = fake_search
    site = {"name": "Prowlarr2MP-MyIndexer", "domain": "http://prowlarr2mp.12/"}
    res = inst.search_torrents(site, "The Matrix", MediaType.MOVIE, 0)
    assert res == []
    d = dict(captured["params"])
    assert d.get("indexerIds") == 12


# ---- regression: global plugin-resource-source call must aggregate ALL indexers ----
def test_global_search_aggregates_all_indexers_even_when_indexer_sites_set():
    import stubs as _s
    _s.SystemConfigOper.RETURN = [1, 4, 5]  # host site int ids; none equal our string ids
    RequestUtils.RESPONDER = None
    inst = new_inst()
    inst._indexers = [
        {"id": "Prowlarr2MP-A", "name": "Prowlarr2MP-A", "domain": "prowlarr2mp.1", "category": PUB_CAT},
        {"id": "Prowlarr2MP-B", "name": "Prowlarr2MP-B", "domain": "prowlarr2mp.2", "category": PUB_CAT},
    ]
    item = {"title": "The Matrix 1999", "downloadUrl": "http://dl/1", "size": 100,
            "seeders": 5, "leechers": 1, "categories": [{"id": 2000}],
            "publishDate": "2020-01-02T03:04:05Z", "imdbId": 133093}
    inst._search_prowlarr_api = lambda params, indexer_id=None: [item]
    res = inst.search_torrents({}, "The Matrix", MediaType.MOVIE, 0)
    assert len(res) == 2, f"expected 2 (one per indexer), got {len(res)}"
    assert {r.site_name for r in res} == {"Prowlarr2MP-A", "Prowlarr2MP-B"}
    _s.SystemConfigOper.RETURN = None


# ---- regression: parse must use the real TorrentInfo signature (no imdbid kwarg) ----
def test_parse_torrent_info_matches_real_signature():
    RequestUtils.RESPONDER = None
    inst = new_inst()
    inst._indexers = []
    item = {"title": "Dune 2021 2160p", "downloadUrl": "http://dl/x", "size": 123,
            "seeders": 3, "leechers": 1, "categories": [{"id": 2000}],
            "publishDate": "2021-10-22T00:00:00Z", "imdbId": 1160419,
            "infoUrl": "http://prowlarr/details/1", "sortTitle": "Dune"}
    t = inst._parse_torrent_info(item, "Prowlarr2MP-A")
    assert t is not None, "parse returned None -> TorrentInfo rejected a kwarg"
    assert t.title == "Dune 2021 2160p"
    assert t.site_name == "Prowlarr2MP-A"
    assert getattr(t, "imdbid", None) is None
