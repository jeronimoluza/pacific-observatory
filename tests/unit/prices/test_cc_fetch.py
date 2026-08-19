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
