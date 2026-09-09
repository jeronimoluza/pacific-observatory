"""The replication gate.

RT-CAL was validated by William against a specific cell matrix, and the whole
port is only trustworthy insofar as it reproduces his published numbers on that
same input. These tests are the acceptance criteria for the port -- if they
fail, nothing downstream of them means anything.

They need the real `global_prices_unit_value_summary.parquet` and skip without
it, so they are a no-op on a fresh checkout and a hard gate on the box that has
the data.
"""

from __future__ import annotations

import pytest

pytest.importorskip("pyarrow")

from prices.rtcal import config, frames, prune  # noqa: E402

# From `benchmark_support/pruning_summary.json` in the handover package.
WILL_INPUT_ROWS = 358_710
WILL_FLAGGED = 872
WILL_PRUNED = 357_838
WILL_REASONS = {
    "region_extreme": 601,
    "global_extreme": 451,
    "month_extreme": 421,
    "region_month_extreme": 383,
    "series_spike": 377,
    "global_severe": 298,
}

pytestmark = pytest.mark.skipif(
    not config.UNIT_VALUE_SUMMARY_PARQUET.exists(),
    reason="needs the built unit-value summary parquet",
)


@pytest.fixture(scope="module")
def pruned():
    observed, unmatched = frames.prepare_observed()
    kept, flagged, summary = prune.prune(observed)
    return {"observed": observed, "kept": kept, "summary": summary, "unmatched": unmatched}


def test_country_context_matches_every_country(pruned):
    """A country with no frozen context silently loses its region and income
    features, which are inputs to the context ensemble."""
    assert pruned["unmatched"] == []


def test_observed_cell_count_matches_the_handover(pruned):
    assert pruned["summary"]["input_rows"] == WILL_INPUT_ROWS


def test_pruning_flags_the_same_cells(pruned):
    summary = pruned["summary"]
    assert summary["flagged_rows"] == WILL_FLAGGED
    assert summary["pruned_rows"] == WILL_PRUNED
    assert summary["flagged_share"] == pytest.approx(0.00243, abs=1e-5)


def test_pruning_reasons_match_the_handover(pruned):
    """Counted among flagged cells only -- the CSV's own `flagged_cells` header.
    Counting frame-wide inflates every reason and still totals 872."""
    assert pruned["summary"]["reason_counts"] == WILL_REASONS
