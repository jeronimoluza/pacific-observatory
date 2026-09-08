"""The survey period splits the comparison; a +/-1 month window pools the count.

Will put the survey period in the cell key. That is right for the COMPARISON --
a row must be judged against prices from its own month, never against a
different month's price level -- but on its own it slices support so finely
that most cells fall under `min_n` and lose trust for want of evidence rather
than for any defect: 1,003,316 rows, 67.7% of everything flagged.

So the two halves are separated. These tests pin that separation, because the
failure mode of getting it wrong is silent in both directions: pool the
comparison too and ordinary inflation reads as an outlier; pool nothing and
two thirds of the flags are cells that were never judged at all.
"""

from __future__ import annotations

import pandas as pd
import pytest

from prices.build import unit_value_audit as uva

pytestmark = pytest.mark.unit


def _cell(country: str, month: int, values: list[float]) -> list[dict]:
    return [
        {
            "coicop_code": "01.1.1.1",
            "country": country,
            "observation_date": f"2026-{month:02d}-15",
            "unit_value_local": v,
        }
        for v in values
    ]


def _run(rows: list[dict]) -> pd.DataFrame:
    return uva.flag_uv_outliers(pd.DataFrame(rows))


def test_price_movement_across_months_is_not_an_outlier():
    """The whole reason the period is in the key. A cell doubling over three
    months is inflation, not a defect."""
    out = _run(
        _cell("fiji", 1, [10.0] * 8)
        + _cell("fiji", 2, [14.0] * 8)
        + _cell("fiji", 3, [20.0] * 8)
    )
    assert out["uv_outlier"].sum() == 0


def test_each_month_is_judged_against_its_own_level():
    """Stronger than the above: two far-apart levels, neither flags the other.

    If pooling ever leaked into the comparison, the 10s and the 100s would each
    look like outliers against a merged distribution.
    """
    out = _run(_cell("kiribati", 1, [10.0] * 20) + _cell("kiribati", 2, [100.0] * 20))
    assert out["uv_outlier"].sum() == 0


def test_a_neighbouring_month_lends_support():
    """February alone has one row and cannot be judged; January and March make
    it judgeable without contributing to what it is judged against."""
    out = _run(
        _cell("tonga", 1, [10.0] * 8)
        + _cell("tonga", 2, [10.0])
        + _cell("tonga", 3, [10.0] * 8)
    )
    feb = out[out["observation_date"].str.startswith("2026-02")]
    assert feb["uv_cell_n"].iloc[0] == 17
    assert not feb["uv_thin"].iloc[0]


def test_a_gap_stays_a_gap():
    """Support is joined by month ARITHMETIC, not row position.

    January and June are adjacent ROWS in the grouped table with four empty
    months between them. A positional roll would pool them; this must not.
    """
    out = _run(_cell("samoa", 1, [10.0] * 8) + _cell("samoa", 6, [10.0]))
    jun = out[out["observation_date"].str.startswith("2026-06")]
    assert jun["uv_cell_n"].iloc[0] == 1
    assert jun["uv_thin"].iloc[0]


def test_a_real_defect_inside_a_month_is_still_caught():
    rows = _cell("vanuatu", 1, [10.0 + i * 0.05 for i in range(30)])
    rows[0]["unit_value_local"] = 1000.0
    out = _run(rows)
    assert out["uv_outlier"].iloc[0]
    assert abs(out["uv_robust_z"].iloc[0]) > 5


def test_the_window_is_the_three_month_one_that_was_chosen():
    assert uva.UV_SUPPORT_WINDOW == 1, "3 months total, not the projected 6"
