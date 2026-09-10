"""The coverage floor that drives the dashboard's hide toggle.

It used to be the 25th percentile of named-leaf breadth, which is a filter
that can never be satisfied: it labels a quarter of the countries
"low coverage" however good they all become, so a country could be pushed
under it by its neighbours improving. On the September 2026 corpus that put
Belgium, Kuwait, Norway, Iceland and Tanzania in the same bucket as
Gibraltar's single leaf, 50 of 202 countries globally and 10 of 38 in EAP.
It is now an absolute claim about the country, `COVERAGE_MIN_NAMED_LEAVES`,
which flags 8 and 1 respectively and retires itself as the corpus fills.
"""

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


def test_the_floor_is_absolute_and_not_a_quantile():
    # 1..20 named leaves. Under the old quartile the cut landed at 5 and took
    # four countries; under the floor it takes exactly those below the floor,
    # and it would take the same four whatever the other sixteen did.
    coverage = {f"c{i:02d}": i + 1 for i in range(20)}
    threshold, low, stats = publish._coverage_cutoff(_frame(coverage), RESIDUAL)
    assert threshold == publish.COVERAGE_MIN_NAMED_LEAVES
    assert low == {f"c{i:02d}" for i in range(20) if i + 1 < threshold}
    assert stats["n_dropped"] == len(low)
    assert stats["n_countries"] == 20
    assert stats["mode"] == "floor"


def test_a_country_is_never_flagged_by_its_neighbours_improving():
    # THE WHOLE POINT. Two identical countries, one in a thin world and one in a
    # rich one. A quartile flags the second and not the first; a floor cannot
    # tell the two worlds apart, because the question is about the country.
    n = publish.COVERAGE_MIN_NAMED_LEAVES + 5
    thin = {"subject": n, **{f"p{i}": 2 for i in range(9)}}
    rich = {"subject": n, **{f"p{i}": 200 for i in range(9)}}
    _, low_thin, _ = publish._coverage_cutoff(_frame(thin), RESIDUAL)
    _, low_rich, _ = publish._coverage_cutoff(_frame(rich), RESIDUAL)
    assert "subject" not in low_thin
    assert "subject" not in low_rich


def test_the_cut_is_strict_so_a_country_exactly_on_the_floor_survives():
    floor = publish.COVERAGE_MIN_NAMED_LEAVES
    coverage = {"under": floor - 1, "on": floor, "over": floor + 1}
    _, low, _ = publish._coverage_cutoff(_frame(coverage), RESIDUAL)
    assert low == {"under"}


def test_the_named_leaf_count_travels_with_the_verdict():
    # A hidden column has to be able to say how thin it is, and a future slider
    # has to be able to move the floor without a rebuild, so the per-country
    # count is in the payload beside the set.
    coverage = {"a": 3, "b": 40}
    _, _, stats = publish._coverage_cutoff(_frame(coverage), RESIDUAL)
    assert stats["counts"] == {"a": 3, "b": 40}


def test_residual_leaves_do_not_count_toward_coverage():
    # Reaching a catch-all leaf is the classifier giving up, not the country
    # having a price for a real category, so it must not buy a country breadth.
    floor = publish.COVERAGE_MIN_NAMED_LEAVES
    coverage = {"thin": floor - 2, "fat": floor + 2}
    padded = _frame(coverage, residual_extra={"thin": 5})
    _, low, stats = publish._coverage_cutoff(padded, RESIDUAL)
    assert low == {"thin"}
    assert stats["counts"]["thin"] == floor - 2


def test_empty_frame_drops_nobody():
    empty = pd.DataFrame(columns=["country", "coicop_code"])
    threshold, low, stats = publish._coverage_cutoff(empty, RESIDUAL)
    assert threshold == 0
    assert low == set()
    assert stats["n_countries"] == 0
