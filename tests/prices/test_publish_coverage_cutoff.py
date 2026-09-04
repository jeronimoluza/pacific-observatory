"""The bottom-quartile coverage cut that drives the dashboard's hide toggle."""

from __future__ import annotations

import pandas as pd

from prices import publish

RESIDUAL = frozenset({"01.9.9.9.9"})


def _frame(coverage: dict[str, int], residual_extra: dict[str, int] | None = None):
    """One row per (country, leaf); leaf codes are synthetic but well-formed."""
    rows = []
    for country, n in coverage.items():
        for i in range(n):
            rows.append(
                {
                    "country": country,
                    "coicop_code": f"01.1.1.{i // 10}.{i % 10}",
                    "standard_unit": "kg",
                    "median_usd": 1.0,
                    "n_obs": 5,
                }
            )
    for country, n in (residual_extra or {}).items():
        for _ in range(n):
            rows.append(
                {
                    "country": country,
                    "coicop_code": "01.9.9.9.9",
                    "standard_unit": "kg",
                    "median_usd": 1.0,
                    "n_obs": 5,
                }
            )
    return pd.DataFrame(rows)


def test_drops_the_bottom_quartile():
    coverage = {f"c{i:02d}": i + 1 for i in range(20)}  # counts 1..20
    threshold, low, stats = publish._coverage_cutoff(_frame(coverage), RESIDUAL)
    assert threshold == 5
    assert low == {"c00", "c01", "c02", "c03"}
    assert stats["n_dropped"] == 4
    assert stats["n_countries"] == 20
    assert stats["median"] == 10


def test_the_cut_is_strict_so_ties_on_the_boundary_survive():
    # Nine countries sit exactly on the 25th percentile. Applying the cut with
    # <= would carry every one of them over and drop 60% of the set, not 25%.
    coverage = {"a": 1, "b": 2}
    coverage.update({f"t{i}": 3 for i in range(9)})
    coverage.update({f"h{i}": 40 for i in range(9)})
    threshold, low, _ = publish._coverage_cutoff(_frame(coverage), RESIDUAL)
    assert threshold == 3
    assert low == {"a", "b"}


def test_residual_leaves_do_not_count_toward_coverage():
    # Reaching a catch-all leaf is the classifier giving up, not the country
    # having a price for a real category, so it must not buy a country breadth.
    coverage = {f"c{i:02d}": i + 1 for i in range(20)}
    padded = _frame(coverage, residual_extra={"c00": 1, "c01": 1})
    threshold, low, _ = publish._coverage_cutoff(padded, RESIDUAL)
    assert low == {"c00", "c01", "c02", "c03"}
    assert threshold == 5


def test_empty_frame_drops_nobody():
    empty = pd.DataFrame(columns=["country", "coicop_code"])
    threshold, low, stats = publish._coverage_cutoff(empty, RESIDUAL)
    assert threshold == 0
    assert low == set()
    assert stats["n_countries"] == 0
