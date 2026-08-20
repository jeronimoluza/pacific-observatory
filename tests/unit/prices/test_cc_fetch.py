import json
import threading
from pathlib import Path

import pytest

from prices.cc_fetch import run_from_manifest
from prices.cc_warc_fetcher import CommonCrawlScraper

pytestmark = pytest.mark.unit


def _scraper(tmp_path):
    s = object.__new__(CommonCrawlScraper)
    s.spider_name = "test_spider"
    s.output_dir = tmp_path
    s.indexes = []
    s.url_prefix = "example.com/p/"
    s.path_re = None
    s.parse_html_fn = None
    s.selectors = {}
    s.declared_currency = ""
    s.scraped_at = "2026-01-01T00:00:00"
    s._file_lock = threading.Lock()
    s._samples = None
    return s


def _manifest(tmp_path, rows):
    path = tmp_path / "m.jsonl"
    with open(path, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    return path


def _row(i, index):
    return {
        "url": f"http://example.com/p/{i}",
        "timestamp": f"2020010100000{i}",
        "filename": "crawl/x.warc.gz",
        "offset": i,
        "length": 10,
        "cc_index": index,
    }


def test_fetching_from_a_manifest_never_touches_cluster_idx(tmp_path, monkeypatch):
    # The whole point of the split: this half runs where the 13 GB cache does
    # not exist, so any cluster.idx read here is a bug.
    def explode(*a, **k):
        raise AssertionError("cluster.idx must not be read on the fetch side")

    monkeypatch.setattr("prices.cc_index.load_cluster", explode)
    monkeypatch.setattr("prices.cc_index.query_prefix", explode)

    s = _scraper(tmp_path)
    rows = [_row(i, "CC-MAIN-2020-01") for i in range(3)]
    monkeypatch.setattr(s, "_fetch_warc_record", lambda rec: b"raw")
    monkeypatch.setattr(s, "_extract_html_from_record", lambda raw: "<html></html>")

    stats = run_from_manifest(
        s, ("eap", "sub", "country"), _manifest(tmp_path, rows), num_workers=1
    )
    assert stats["queried"] == 3
    assert stats["no_extract"] == 3


def test_records_already_saved_are_skipped(tmp_path, monkeypatch):
    s = _scraper(tmp_path)
    rows = [_row(i, "CC-MAIN-2020-01") for i in range(3)]

    items = Path(s._items_dir(("eap", "sub", "country")))
    items.mkdir(parents=True, exist_ok=True)
    (items / f"{s._record_hash(rows[0]['url'], rows[0]['timestamp'])}.json").write_text(
        "{}", encoding="utf-8"
    )

    monkeypatch.setattr(s, "_fetch_warc_record", lambda rec: b"raw")
    monkeypatch.setattr(s, "_extract_html_from_record", lambda raw: "<html></html>")
    stats = run_from_manifest(
        s, ("eap", "sub", "country"), _manifest(tmp_path, rows), num_workers=1
    )
    assert stats["skipped"] == 1
    assert stats["no_extract"] == 2


def test_per_crawl_yield_survives_the_manifest_path(tmp_path, monkeypatch):
    # Grouping by crawl is what makes a redesign visible as a cliff; a flat
    # run over the manifest would average it away.
    s = _scraper(tmp_path)
    rows = [_row(0, "CC-MAIN-2019-04"), _row(1, "CC-MAIN-2024-10")]
    monkeypatch.setattr(s, "_fetch_warc_record", lambda rec: b"raw")
    monkeypatch.setattr(s, "_extract_html_from_record", lambda raw: "<html></html>")
    run_from_manifest(
        s, ("eap", "sub", "country"), _manifest(tmp_path, rows), num_workers=1
    )
    written = json.loads(
        (
            Path(s._items_dir(("eap", "sub", "country"))).parent / "index_yield.json"
        ).read_text(encoding="utf-8")
    )
    assert set(written) == {"CC-MAIN-2019-04", "CC-MAIN-2024-10"}


def _always_parses(s, monkeypatch, rows_per_page=1):
    monkeypatch.setattr(s, "_fetch_warc_record", lambda rec: b"raw")
    monkeypatch.setattr(s, "_extract_html_from_record", lambda raw: "<html></html>")
    monkeypatch.setattr(
        s, "_parse_rows", lambda html, url: [{"price": "1"}] * rows_per_page
    )


def _blank_for(s, monkeypatch, ids):
    """Make _parse_rows yield nothing for the given /p/<id> URLs."""
    wanted = set(ids)

    def rows(html, url):
        return [] if int(url.rsplit("/", 1)[1]) in wanted else [{"p": 1}]

    monkeypatch.setattr(s, "_parse_rows", rows)


def test_crawls_are_walked_newest_first(tmp_path, monkeypatch):
    # The recent end is where a parser written against the live site matches,
    # so a source cut short keeps the readable years. Walking oldest-first is
    # what burned an hour on chemist_warehouse's 2015 templates for zero rows.
    s = _scraper(tmp_path)
    rows = [
        _row(0, "CC-MAIN-2018-05"),
        _row(1, "CC-MAIN-2024-30"),
        _row(2, "CC-MAIN-2021-10"),
    ]
    _always_parses(s, monkeypatch)
    seen = []
    real = s._process_one
    monkeypatch.setattr(
        s,
        "_process_one",
        lambda rec, loc, idx: (seen.append(idx), real(rec, loc, idx))[1],
    )
    run_from_manifest(
        s, ("eap", "sub", "country"), _manifest(tmp_path, rows), num_workers=1
    )
    assert seen == ["CC-MAIN-2024-30", "CC-MAIN-2021-10", "CC-MAIN-2018-05"]


def test_a_parser_that_never_matches_stops_instead_of_walking_every_crawl(
    tmp_path, monkeypatch
):
    s = _scraper(tmp_path)
    rows = [
        _row(i, f"CC-MAIN-20{yr:02d}-01") for yr in range(10, 25) for i in range(30)
    ]
    monkeypatch.setattr(s, "_fetch_warc_record", lambda rec: b"raw")
    monkeypatch.setattr(s, "_extract_html_from_record", lambda raw: "<html></html>")
    stats = run_from_manifest(
        s,
        ("eap", "sub", "country"),
        _manifest(tmp_path, rows),
        num_workers=1,
        dead_after=60,
    )
    assert stats["stop_reason"] == "dead_parser"
    assert stats["indexes_walked"] < len(
        {r["cc_index"] for r in rows}
    ), "a dead parser must not pay for every crawl in the manifest"


def test_one_barren_crawl_is_not_enough_to_stop(tmp_path, monkeypatch):
    # Archive coverage is genuinely lumpy -- 2023 was near-absent for several
    # sources -- so a single empty crawl must not end a decade of history.
    s = _scraper(tmp_path)
    rows = [_row(i, "CC-MAIN-2024-01") for i in range(30)]
    rows += [_row(100 + i, "CC-MAIN-2023-01") for i in range(30)]
    rows += [_row(200 + i, "CC-MAIN-2022-01") for i in range(30)]
    _always_parses(s, monkeypatch)
    _blank_for(s, monkeypatch, range(100, 200))
    stats = run_from_manifest(
        s,
        ("eap", "sub", "country"),
        _manifest(tmp_path, rows),
        num_workers=1,
        min_evidence=10,
        stop_after_empty=2,
    )
    assert stats["stop_reason"] == ""
    assert stats["indexes_walked"] == 3


def test_two_consecutive_barren_crawls_do_stop_the_source(tmp_path, monkeypatch):
    # A parser that matched the recent template and lost it at a redesign: the
    # summed counters still call the source healthy, so the streak is the only
    # thing that catches it.
    s = _scraper(tmp_path)
    rows = [_row(i, "CC-MAIN-2024-01") for i in range(30)]
    rows += [_row(100 + i, "CC-MAIN-2023-01") for i in range(30)]
    rows += [_row(200 + i, "CC-MAIN-2022-01") for i in range(30)]
    rows += [_row(300 + i, "CC-MAIN-2021-01") for i in range(30)]
    _always_parses(s, monkeypatch)
    _blank_for(s, monkeypatch, range(100, 300))
    stats = run_from_manifest(
        s,
        ("eap", "sub", "country"),
        _manifest(tmp_path, rows),
        num_workers=1,
        min_evidence=10,
        stop_after_empty=2,
    )
    assert stats["stop_reason"] == "empty_crawls"
    assert stats["stopped_at"] == "CC-MAIN-2022-01"
    assert stats["indexes_walked"] == 3, "the 2021 crawl must never be paid for"


def test_a_crawl_whose_records_are_all_held_is_not_evidence_of_emptiness(
    tmp_path, monkeypatch
):
    # On a resume, an already-finished crawl produces zero new rows. Counting
    # that as an empty crawl would make every second run stop at the point the
    # first run reached, which is the worst possible failure: silent, and it
    # looks exactly like success.
    s = _scraper(tmp_path)
    loc = ("eap", "sub", "country")
    rows = [_row(i, "CC-MAIN-2024-01") for i in range(30)]
    rows += [_row(100 + i, "CC-MAIN-2023-01") for i in range(30)]
    rows += [_row(200 + i, "CC-MAIN-2022-01") for i in range(30)]

    items = Path(s._items_dir(loc))
    items.mkdir(parents=True, exist_ok=True)
    for r in rows[:60]:
        (items / f"{s._record_hash(r['url'], r['timestamp'])}.json").write_text(
            "{}", encoding="utf-8"
        )

    _always_parses(s, monkeypatch)
    stats = run_from_manifest(
        s, loc, _manifest(tmp_path, rows), num_workers=1, min_evidence=10
    )
    assert stats["stop_reason"] == ""
    assert stats["skipped"] == 60
    assert stats["indexes_walked"] == 3


def test_a_403_ban_stops_the_source_instead_of_grinding_out_zeros(
    tmp_path, monkeypatch
):
    s = _scraper(tmp_path)
    s.http_403 = 0
    rows = [_row(i, f"CC-MAIN-202{y}-01") for y in range(4) for i in range(30)]

    def banned(rec):
        s.http_403 += 1
        return None

    monkeypatch.setattr(s, "_fetch_warc_record", banned)
    stats = run_from_manifest(
        s,
        ("eap", "sub", "country"),
        _manifest(tmp_path, rows),
        num_workers=1,
        max_403=10,
        dead_after=10_000,
    )
    assert stats["stop_reason"] == "cc_403_ban"
    assert stats["indexes_walked"] == 1


def test_why_a_source_stopped_is_written_next_to_its_items(tmp_path, monkeypatch):
    # The sweep driver reads this back to tell "finished the manifest" from
    # "waiting on a parser fix"; scraping it off stdout would break silently.
    s = _scraper(tmp_path)
    rows = [_row(i, "CC-MAIN-2024-01") for i in range(30)]
    _always_parses(s, monkeypatch)
    run_from_manifest(
        s, ("eap", "sub", "country"), _manifest(tmp_path, rows), num_workers=1
    )
    state = json.loads(
        (
            Path(s._items_dir(("eap", "sub", "country"))).parent / "fetch_state.json"
        ).read_text(encoding="utf-8")
    )
    assert state["stop_reason"] == ""
    assert state["covered_through"] == "CC-MAIN-2024-01"
    assert state["indexes_walked"] == 1


def test_a_page_becomes_lines_in_its_crawls_jsonl_not_files(tmp_path, monkeypatch):
    # One inode and one 4 KB block per ~600-byte record is what filled the
    # fetch machine after ~8 of 123 crawls while df still showed free bytes.
    s = _scraper(tmp_path)
    rows = [_row(0, "CC-MAIN-2024-01"), _row(1, "CC-MAIN-2019-04")]
    _always_parses(s, monkeypatch, rows_per_page=3)
    run_from_manifest(
        s, ("eap", "sub", "country"), _manifest(tmp_path, rows), num_workers=1
    )
    items = Path(s._items_dir(("eap", "sub", "country")))
    assert not list(items.glob("*.json")), "no per-record files"
    assert sorted(p.name for p in items.glob("*.jsonl")) == [
        "CC-MAIN-2019-04.jsonl",
        "CC-MAIN-2024-01.jsonl",
    ]
    # Three rows per page, and each row carries the crawl it came from.
    lines = (items / "CC-MAIN-2024-01.jsonl").read_text().strip().split("\n")
    assert len(lines) == 3
    assert json.loads(lines[0])["cc_index"] == "CC-MAIN-2024-01"


def test_rows_written_in_one_run_are_skipped_by_the_next(tmp_path, monkeypatch):
    # The skip set is the whole resume mechanism; JSONL has to preserve it.
    s = _scraper(tmp_path)
    loc = ("eap", "sub", "country")
    rows = [_row(i, "CC-MAIN-2024-01") for i in range(5)]
    _always_parses(s, monkeypatch)
    first = run_from_manifest(s, loc, _manifest(tmp_path, rows), num_workers=1)
    second = run_from_manifest(s, loc, _manifest(tmp_path, rows), num_workers=1)
    assert first["parsed"] == 5
    assert second["parsed"] == 0
    assert second["skipped"] == 5


def test_a_ban_aborts_the_crawl_in_progress_not_just_the_next_one(
    tmp_path, monkeypatch
):
    # Checking only at crawl boundaries makes the guard blind for the length of
    # a crawl, and crawls are not small: one source burned 29 minutes and 20.3k
    # refusals inside a single crawl before the boundary check ran once.
    s = _scraper(tmp_path)
    s.http_403 = 0
    attempts = []
    rows = [_row(i, "CC-MAIN-2026-01") for i in range(500)]

    def banned(rec):
        attempts.append(rec["url"])
        s.http_403 += 1
        return None

    monkeypatch.setattr(s, "_fetch_warc_record", banned)
    stats = run_from_manifest(
        s,
        ("eap", "sub", "country"),
        _manifest(tmp_path, rows),
        num_workers=1,
        max_403=10,
        dead_after=10_000,
    )
    assert stats["stop_reason"] == "cc_403_ban"
    assert len(attempts) < 50, f"kept fetching through a ban: {len(attempts)} of 500"
