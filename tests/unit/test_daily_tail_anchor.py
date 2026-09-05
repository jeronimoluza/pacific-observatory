"""The daily tail has to follow the corpus, not the calendar.

``process_unit_v2`` anchored the tail to the first of the current calendar
month. The daily index is ``date_range(tail_start, max_date)``, so the moment
the newest article predated that anchor the range came out empty: the series
went pure monthly, and the dashboard's weekly points -- which it buckets from
the daily rows -- vanished with them. That is what happened once the EAP corpus
stopped at 2026-08-28 while the clock read September.

Future-dated articles are parse errors (one source carried 36 rows dated into
December). They must not drag the anchor forward, or they re-create the empty
tail this is meant to prevent.
"""

import pandas as pd
import pytest

from src.text.analysis.orchestrator import (
    _daily_backfill_cutoff,
    frontier_date,
    resolve_tail_start,
)

TODAY = pd.Timestamp("2026-09-04")


def test_lagging_corpus_anchors_to_the_last_month_with_data():
    """The regression: August data, September clock."""
    assert resolve_tail_start(pd.Timestamp("2026-08-28"), TODAY) == "2026-08-01"


def test_current_corpus_keeps_the_calendar_month():
    """A corpus collected up to today must behave exactly as it used to."""
    assert resolve_tail_start(pd.Timestamp("2026-09-03"), TODAY) == "2026-09-01"


def test_anchor_never_runs_past_the_current_month():
    """Belt and braces: even an unclamped future max stays capped."""
    assert resolve_tail_start(pd.Timestamp("2026-12-06"), TODAY) == "2026-09-01"


def test_empty_corpus_falls_back_to_the_calendar_month():
    assert resolve_tail_start(None, TODAY) == "2026-09-01"


@pytest.mark.parametrize(
    "newest,expected",
    [
        ("2026-08-01", "2026-08-01"),
        ("2026-08-31", "2026-08-01"),
        ("2026-01-15", "2026-01-01"),
        ("2025-11-30", "2025-11-01"),
    ],
)
def test_anchor_is_the_first_of_the_newest_articles_month(newest, expected):
    assert resolve_tail_start(pd.Timestamp(newest), TODAY) == expected


# ── Backfill trigger ──────────────────────────────────────────────────
#
# Moving the anchor is not enough on its own. No source has rows past its
# cached tail, so the extension check finds nothing and the cache is reused
# verbatim -- the month stays monthly and the daily rows never appear. The
# backfill cutoff is what forces that month to be re-annotated at daily grain.

AUG = pd.Timestamp("2026-08-01")


def _cache(*ym):
    return pd.DataFrame({"ym": list(ym), "source_key": ["s"] * len(ym)})


def test_monthly_tail_month_triggers_backfill():
    """The regression: August cached as a single monthly row."""
    assert _daily_backfill_cutoff(_cache("2026-07", "2026-08"), AUG) == pd.Timestamp(
        "2026-07-31"
    )


def test_already_daily_does_not_retrigger():
    """Idempotence: a second run must not redo the work."""
    cache = _cache("2026-07", "2026-08-01", "2026-08-02")
    assert _daily_backfill_cutoff(cache, AUG) is None


def test_no_rows_at_or_after_tail_is_left_alone():
    """Nothing to convert means no wasted re-annotation."""
    assert _daily_backfill_cutoff(_cache("2026-06", "2026-07"), AUG) is None


def test_empty_or_missing_cache_is_safe():
    assert _daily_backfill_cutoff(None, AUG) is None
    assert _daily_backfill_cutoff(pd.DataFrame(), AUG) is None
    assert _daily_backfill_cutoff(_cache("2026-08"), None) is None


def test_unpadded_monthly_form_still_triggers():
    """The cache carries both "2026-8" and "2026-08" from older builds."""
    assert _daily_backfill_cutoff(_cache("2026-8"), AUG) == pd.Timestamp("2026-07-31")


# ── Frontier, not maximum ─────────────────────────────────────────────
#
# Anchoring to the corpus maximum made the tail hostage to whichever single
# source was freshest. Probing two Taiwanese papers wrote 8 rows dated into
# September; against August's 57,759 articles that was enough to move the
# anchor a month and collapse the whole daily tail into one monthly row.


def _dates(*s):
    return [pd.Timestamp(x) for x in s]


def test_a_few_fresh_outliers_cannot_move_the_frontier():
    """The regression, in miniature: 2 fresh sources against 298 settled ones."""
    fleet = _dates(*(["2026-08-27"] * 298)) + _dates("2026-09-04", "2026-09-03")
    assert frontier_date(fleet) == pd.Timestamp("2026-08-27")
    assert max(fleet) == pd.Timestamp("2026-09-04")  # what we used to use


def test_frontier_follows_a_genuine_fleet_wide_move():
    """When most of the fleet really does advance, the frontier advances."""
    fleet = _dates(*(["2026-09-03"] * 200)) + _dates(*(["2026-08-27"] * 100))
    assert frontier_date(fleet) == pd.Timestamp("2026-09-03")


def test_frontier_ignores_the_long_tail_of_dead_sources():
    """Roughly half the EAP fleet stopped collecting months or years ago."""
    fleet = _dates(*(["2026-08-27"] * 150)) + _dates(*(["2024-01-01"] * 150))
    assert frontier_date(fleet) == pd.Timestamp("2026-08-27")


def test_frontier_of_nothing_is_none():
    assert frontier_date([]) is None
    assert frontier_date([None, None]) is None


def test_frontier_end_to_end_lands_on_august():
    """Frontier feeding the anchor reproduces the intended 2026-08-01."""
    fleet = _dates(*(["2026-08-27"] * 298)) + _dates("2026-09-04", "2026-09-03")
    got = resolve_tail_start(frontier_date(fleet), pd.Timestamp("2026-09-04"))
    assert got == "2026-08-01"
