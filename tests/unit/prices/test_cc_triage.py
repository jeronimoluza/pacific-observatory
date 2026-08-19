import pytest

from prices.tools import cc_triage

pytestmark = pytest.mark.unit


# The block the CLI prints. ``indexes_failed`` is the regression case: it is
# exactly as wide as the old padding, so a two-or-more-space split dropped it.
STATS_BLOCK = """
2026-08-19 12:37:57,779  INFO  CC-MAIN-2017-34: nothing new to fetch

Run stats for demo_spider (eca/balkans/greece):
  indexes          103
  indexes_failed   7
  queried          718
  skipped          105
  parsed           101
  fetch_failed     0
  parse_failed     0
  no_extract       512
  save_failed      0
  capped           0
"""


def test_indexes_failed_survives_the_stats_parser():
    stats = cc_triage.parse_stats(STATS_BLOCK)
    assert stats["indexes_failed"] == 7
    assert stats["queried"] == 718
    assert stats["no_extract"] == 512


def test_single_space_between_key_and_value_still_parses():
    # The old CLI padding left exactly one space for a 14-char key.
    stats = cc_triage.parse_stats("  indexes_failed 7\n  parsed         3\n")
    assert stats == {"indexes_failed": 7, "parsed": 3}


def test_log_lines_are_not_mistaken_for_stats():
    stats = cc_triage.parse_stats(
        "2026-08-19 12:37:57,779  INFO  CC-MAIN-2017-34: 0 product records\n"
    )
    assert stats == {}


def test_parser_dead_when_every_fetched_page_extracts_nothing():
    primary, flags = cc_triage.classify(
        "completed", {"queried": 500, "parsed": 0, "no_extract": 480}
    )
    assert primary == "PARSER_DEAD"


def test_no_archive_is_not_reported_as_a_dead_parser():
    # Nothing under the prefix in any crawl: an archive_prefix problem, and no
    # parser change can fix it.
    primary, flags = cc_triage.classify(
        "completed", {"queried": 0, "parsed": 0, "no_extract": 0}
    )
    assert primary == "NO_ARCHIVE"
    assert "PARSER_DEAD" not in flags


def test_all_records_already_held_is_not_a_failure():
    primary, _ = cc_triage.classify(
        "completed", {"queried": 400, "skipped": 400, "parsed": 0, "no_extract": 0}
    )
    assert primary == "NOTHING_NEW"


def test_weak_yield_needs_enough_attempts_to_be_called():
    thin = {"queried": 50, "parsed": 2, "no_extract": 48}
    primary, flags = cc_triage.classify("completed", thin)
    assert "PARSER_WEAK" not in flags

    fat = {"queried": 1000, "parsed": 20, "no_extract": 980}
    _, flags = cc_triage.classify("completed", fat)
    assert "PARSER_WEAK" in flags


def test_budget_bound_source_is_not_flagged_as_a_parser_problem():
    primary, flags = cc_triage.classify(
        "completed",
        {"queried": 62571, "parsed": 6880, "no_extract": 6772, "capped": 47205},
    )
    assert primary == "BUDGET_BOUND"
    assert "PARSER_DEAD" not in flags


def test_lost_indexes_are_flagged_even_when_rows_look_fine():
    _, flags = cc_triage.classify(
        "completed",
        {"queried": 900, "parsed": 700, "no_extract": 100, "indexes_failed": 9},
    )
    assert "DEPTH_LOST" in flags


def test_crash_outranks_every_other_flag():
    primary, flags = cc_triage.classify(
        "timeout", {"queried": 100, "parsed": 0, "no_extract": 90}
    )
    assert primary == "CRASHED"
    assert "PARSER_DEAD" in flags


def test_healthy_source_is_ok():
    primary, flags = cc_triage.classify(
        "completed", {"queried": 900, "parsed": 700, "no_extract": 150}
    )
    assert primary == "OK"
    assert flags == ["OK"]


def _crawl(year, parsed, no_extract, week="04"):
    return {f"CC-MAIN-{year}-{week}": {"parsed": parsed, "no_extract": no_extract}}


def test_redesign_year_is_detected_as_a_cliff():
    per_index = {}
    for year in ("2023", "2024", "2025"):
        per_index.update(_crawl(year, 180, 20))
    for year in ("2018", "2019"):
        per_index.update(_crawl(year, 2, 198))
    cliff = cc_triage.date_cliff(per_index)
    assert cliff["broken_years"] == ["2018", "2019"]
    assert cliff["worst_yield"] < cliff["best_yield"]


def test_flat_parse_rate_reports_no_cliff():
    per_index = {}
    for year in ("2019", "2022", "2025"):
        per_index.update(_crawl(year, 150, 50))
    assert cc_triage.date_cliff(per_index) == {}


def test_thin_year_cannot_trigger_a_cliff():
    # Two attempts in 2016 that both failed is not evidence of a redesign.
    per_index = {}
    per_index.update(_crawl("2025", 180, 20))
    per_index.update(_crawl("2016", 0, 2))
    assert cc_triage.date_cliff(per_index) == {}


def test_cliff_needs_two_comparable_years():
    assert cc_triage.date_cliff(_crawl("2025", 180, 20)) == {}


def test_totally_dead_parser_is_not_reported_as_a_cliff():
    # Every year at zero has no good year to fall from; PARSER_DEAD covers it.
    per_index = {}
    for year in ("2019", "2025"):
        per_index.update(_crawl(year, 0, 200))
    assert cc_triage.date_cliff(per_index) == {}
