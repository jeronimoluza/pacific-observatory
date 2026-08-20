import json

import pytest

from prices.cc_resolve import read_horizon, write_horizon
from prices.tools.cc_backfill_state import _last_records, _should_run

pytestmark = pytest.mark.unit


def _rec(**kw):
    base = {
        "spider": "s",
        "status": "completed",
        "stop_reason": "",
        "covered_through": "CC-MAIN-2013-20",
    }
    base.update(kw)
    return base


def test_a_source_never_run_is_owed_a_pass():
    assert _should_run(None, "CC-MAIN-2013-20", False) is True


def test_a_source_that_walked_the_whole_manifest_is_left_alone():
    assert _should_run(_rec(), "CC-MAIN-2013-20", False) is False


def test_a_source_is_requeued_when_the_manifest_reaches_further_back():
    # Resolution is index-major, so every manifest grows one crawl at a time.
    # A source that finished the three-crawl prefix it was handed has not
    # finished its history, and filing it as complete is how a decade of
    # archive silently becomes a few months.
    rec = _rec(covered_through="CC-MAIN-2024-10")
    assert _should_run(rec, "CC-MAIN-2019-04", False) is True
    assert _should_run(rec, "CC-MAIN-2024-10", False) is False


def test_a_parked_source_waits_for_a_human_then_reruns_on_demand():
    for reason in ("dead_parser", "empty_crawls"):
        rec = _rec(stop_reason=reason, covered_through="CC-MAIN-2019-04")
        assert _should_run(rec, "CC-MAIN-2013-20", False) is False
        assert _should_run(rec, "CC-MAIN-2013-20", True) is True


def test_a_ban_is_transient_and_retries_without_being_asked():
    rec = _rec(stop_reason="cc_403_ban", covered_through="CC-MAIN-2024-10")
    assert _should_run(rec, "CC-MAIN-2013-20", False) is True


def test_a_source_that_did_not_complete_is_always_retried():
    assert _should_run(_rec(status="timeout"), "CC-MAIN-2013-20", False) is True
    assert _should_run(_rec(status="error"), "CC-MAIN-2013-20", False) is True


def test_the_latest_record_for_a_spider_wins(tmp_path):
    # The results file is append-only on purpose, so a spider appears once per
    # pass and only the last line describes where it actually got to.
    path = tmp_path / "results.jsonl"
    path.write_text(
        json.dumps({"spider": "a", "status": "timeout"})
        + "\n"
        + json.dumps({"spider": "a", "status": "completed", "covered_through": "x"})
        + "\n",
        encoding="utf-8",
    )
    got = _last_records(path)
    assert got["a"]["status"] == "completed"
    assert got["a"]["covered_through"] == "x"


def test_the_horizon_records_how_far_back_the_manifests_reach(tmp_path):
    by_index = tmp_path / "by_index"
    by_index.mkdir()
    for name in ("CC-MAIN-2026-30", "CC-MAIN-2019-04", "CC-MAIN-2024-10"):
        (by_index / f"{name}.jsonl").write_text("", encoding="utf-8")

    payload = write_horizon(tmp_path)
    assert payload["newest"] == "CC-MAIN-2026-30"
    assert payload["oldest"] == "CC-MAIN-2019-04"
    assert payload["count"] == 3
    assert read_horizon(tmp_path / "by_source") == payload


def test_a_missing_horizon_reads_as_empty_rather_than_raising(tmp_path):
    # The fetch machine may be handed manifests before the file exists; an
    # exception there would stop the sweep on a cosmetic problem.
    assert read_horizon(tmp_path / "nope")["count"] == 0


def test_the_sweep_watches_inodes_not_only_bytes(tmp_path):
    # One item is one small JSON file, so a fleet-wide crawl costs ~half a
    # million inodes and only a couple of gigabytes. The byte guard stays happy
    # while saves start failing one by one -- free bytes are not evidence that
    # a file can be created.
    from prices.tools.cc_backfill_state import _free_gb, _free_inodes

    assert _free_gb(tmp_path) > 0
    inodes = _free_inodes(tmp_path)
    assert inodes == -1 or inodes > 0
