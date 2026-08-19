"""Unit tests for the Common Crawl WARC fetcher's per-index run loop."""

from __future__ import annotations

import threading
from pathlib import Path
from unittest.mock import patch

import pytest

from prices.cc_warc_fetcher import CommonCrawlScraper


def _make_scraper(tmp_path: Path) -> CommonCrawlScraper:
    scraper = object.__new__(CommonCrawlScraper)
    scraper.spider_name = "test_spider"
    scraper.output_dir = tmp_path
    scraper.indexes = ["CC-MAIN-2020-01", "CC-MAIN-2020-05", "CC-MAIN-2020-10"]
    scraper.url_prefix = "example.com/product/"
    scraper.path_re = None
    scraper.parse_html_fn = None
    scraper.selectors = {}
    scraper.scraped_at = "2026-01-01T00:00:00"
    scraper._file_lock = threading.Lock()
    return scraper


@pytest.mark.unit
def test_run_scrape_cc_skips_a_failing_index_and_continues(tmp_path: Path):
    scraper = _make_scraper(tmp_path)

    def fake_query_index(index: str):
        if index == "CC-MAIN-2020-05":
            raise RuntimeError("cdx block fetch failed after 6 attempts: 503")
        return []

    with patch.object(scraper, "_query_index", side_effect=fake_query_index):
        stats = scraper.run_scrape_cc(("eap", "sub", "country"), num_workers=1)

    # All 3 indexes were scheduled; only the bad one is marked failed, and the
    # loop did not abort after hitting it — the summary must show 1 of 3
    # failed rather than looking identical to a clean run.
    assert stats["indexes"] == 3
    assert stats["indexes_failed"] == 1


@pytest.mark.unit
def test_run_scrape_cc_reports_zero_failures_when_all_indexes_succeed(
    tmp_path: Path,
):
    scraper = _make_scraper(tmp_path)

    with patch.object(scraper, "_query_index", return_value=[]):
        stats = scraper.run_scrape_cc(("eap", "sub", "country"), num_workers=1)

    assert stats["indexes"] == 3
    assert stats["indexes_failed"] == 0


@pytest.mark.unit
def test_unparseable_pages_are_sampled_and_yield_is_recorded_per_crawl(
    tmp_path: Path,
):
    scraper = _make_scraper(tmp_path)
    scraper.declared_currency = ""

    def fake_query_index(index: str):
        year = index.split("-")[2]
        return [
            {
                "url": f"http://example.com/product/{year}-{i}",
                "timestamp": f"{year}0101000000",
            }
            for i in range(2)
        ]

    html = "<html><body>no product markup here</body></html>"
    with (
        patch.object(scraper, "_query_index", side_effect=fake_query_index),
        patch.object(scraper, "_fetch_warc_record", return_value=b"raw"),
        patch.object(scraper, "_extract_html_from_record", return_value=html),
    ):
        stats = scraper.run_scrape_cc(("eap", "sub", "country"), num_workers=1)

    assert stats["no_extract"] == 6
    assert stats["parsed"] == 0

    base = tmp_path / "eap" / "sub" / "country" / "test_spider" / "common_crawl_data"

    # The page a parser could not read is the one worth keeping.
    kept = list((base / "samples").glob("*/*.html"))
    assert kept, "a no_extract page should have been retained for repair"

    # Per-crawl yield must be recorded, not just the sum, so a redesign that
    # breaks one year is distinguishable from a uniformly weak parser.
    import json

    per_index = json.loads((base / "index_yield.json").read_text(encoding="utf-8"))
    assert set(per_index) == set(scraper.indexes)
    assert per_index["CC-MAIN-2020-01"]["no_extract"] == 2
