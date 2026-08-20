import json

import pytest

from prices.cc_storage import count_rows, existing_hashes, iter_jsonl, record_hash
from prices.tools.cc_compact_items import compact_dir

pytestmark = pytest.mark.unit


def _legacy(items, url, ts, index="CC-MAIN-2024-10", **extra):
    items.mkdir(parents=True, exist_ok=True)
    payload = {"url": url, "cc_timestamp": ts, "cc_index": index, **extra}
    (items / f"{record_hash(url, ts)}.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )


def test_a_partial_final_line_costs_one_row_not_the_whole_file(tmp_path):
    # A run killed mid-append leaves a truncated line. Refusing to read the
    # file it sits at the end of would throw away the whole crawl.
    p = tmp_path / "CC-MAIN-2024-10.jsonl"
    p.write_text(
        json.dumps({"url": "a", "cc_timestamp": "1"})
        + "\n"
        + json.dumps({"url": "b", "cc_timestamp": "2"})
        + "\n"
        + '{"url": "c", "cc_time',
        encoding="utf-8",
    )
    assert [r["url"] for r in iter_jsonl(p)] == ["a", "b"]


def test_the_skip_set_reads_both_layouts(tmp_path):
    # A corpus captured before compaction must not be re-fetched.
    items = tmp_path / "items"
    _legacy(items, "http://x/1", "20240101000000")
    (items / "CC-MAIN-2023-05.jsonl").write_text(
        json.dumps({"url": "http://x/2", "cc_timestamp": "20230101000000"}) + "\n",
        encoding="utf-8",
    )
    got = existing_hashes(items)
    assert record_hash("http://x/1", "20240101000000") in got
    assert record_hash("http://x/2", "20230101000000") in got


def test_rows_are_counted_across_both_layouts(tmp_path):
    items = tmp_path / "items"
    _legacy(items, "http://x/1", "20240101000000")
    (items / "CC-MAIN-2023-05.jsonl").write_text(
        json.dumps({"url": "http://x/2", "cc_timestamp": "2"})
        + "\n"
        + json.dumps({"url": "http://x/3", "cc_timestamp": "3"})
        + "\n",
        encoding="utf-8",
    )
    assert count_rows(items) == 3


def test_compaction_groups_by_crawl_and_removes_only_what_it_verified(tmp_path):
    items = tmp_path / "items"
    for i in range(3):
        _legacy(items, f"http://x/{i}", f"2024010100000{i}", index="CC-MAIN-2024-10")
    for i in range(2):
        _legacy(items, f"http://y/{i}", f"2019010100000{i}", index="CC-MAIN-2019-04")

    before = existing_hashes(items)
    got = compact_dir(items, delete_originals=True)

    assert got == {"legacy": 5, "appended": 5, "removed": 5, "verified": 5}
    assert sorted(p.name for p in items.glob("*.jsonl")) == [
        "CC-MAIN-2019-04.jsonl",
        "CC-MAIN-2024-10.jsonl",
    ]
    assert not list(items.glob("*.json"))
    # The whole point: the skip set is identical afterwards, so nothing is
    # re-fetched because of the migration.
    assert existing_hashes(items) == before


def test_compacting_twice_does_not_duplicate_rows(tmp_path):
    items = tmp_path / "items"
    for i in range(3):
        _legacy(items, f"http://x/{i}", f"2024010100000{i}")
    compact_dir(items, delete_originals=False)
    compact_dir(items, delete_originals=False)
    assert count_rows(items) == 6, "3 legacy files plus 3 compacted rows, not 9"
    assert sum(1 for _ in iter_jsonl(items / "CC-MAIN-2024-10.jsonl")) == 3


def test_an_unreadable_legacy_file_is_kept_rather_than_deleted(tmp_path):
    items = tmp_path / "items"
    items.mkdir(parents=True)
    _legacy(items, "http://x/1", "20240101000000")
    (items / "broken.json").write_text("{not json", encoding="utf-8")
    got = compact_dir(items, delete_originals=True)
    assert got["removed"] == 1
    assert (items / "broken.json").exists(), "never delete what could not be read"
