"""Stale daily rows must roll up into their month, not vanish at the merge.

Incremental runs key `ym` by full date while a month is the current month and
never rewrite those rows once it passes. The continuous index carries only
month-start dates for past months, so merging against it used to drop them
silently — the articles were counted, then discarded before the index was built.
"""

import pandas as pd

from src.text.analysis.utils import collapse_to_index_grid

TAIL = "2026-08-01"


def _grid(dates):
    return pd.DataFrame({"date": pd.to_datetime(dates)})


def test_stale_daily_rows_survive_the_index_merge():
    """A July row keyed by full date must land on 2026-07-01, not disappear."""
    df = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-07-01", "2026-07-15", "2026-08-02"]),
            "ym": ["2026-07", "2026-07-15", "2026-08-02"],
            "a_A_total": [67, 742, 10],
        }
    )
    grid = _grid(["2026-07-01", "2026-08-02"])

    dropped = grid.merge(df, how="left", on="date").fillna(0)
    assert dropped["a_A_total"].sum() == 77  # 742 articles lost

    collapsed = collapse_to_index_grid(df, TAIL)
    merged = grid.merge(collapsed, how="left", on="date").fillna(0)
    assert merged["a_A_total"].sum() == 819
    july = merged.loc[merged["date"] == pd.Timestamp("2026-07-01"), "a_A_total"]
    assert july.iloc[0] == 809


def test_tail_rows_keep_daily_granularity():
    """Dates at or after the tail start stay on their own day."""
    df = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-08-02", "2026-08-03"]),
            "ym": ["2026-08-02", "2026-08-03"],
            "a_A_total": [5, 7],
        }
    )
    out = collapse_to_index_grid(df, TAIL)
    assert list(out["date"]) == list(df["date"])
    assert list(out["a_A_total"]) == [5, 7]


def test_ratios_are_recomputed_not_summed():
    """A ratio column must reflect the summed counts, not their sum."""
    df = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-07-01", "2026-07-15"]),
            "ym": ["2026-07", "2026-07-15"],
            "a_body_count": [100, 300],
            "a_epu_count": [10, 90],
            "a_ratio": [0.10, 0.30],
        }
    )
    out = collapse_to_index_grid(
        df, TAIL, ratio_cols={"a_ratio": ("a_epu_count", "a_body_count")}
    )
    assert len(out) == 1
    assert out["a_body_count"].iloc[0] == 400
    assert out["a_epu_count"].iloc[0] == 100
    assert out["a_ratio"].iloc[0] == 0.25  # not 0.40


def test_clean_monthly_frame_is_untouched():
    """A clean rebuild has no stale rows and must pass through unchanged."""
    df = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-06-01", "2026-07-01"]),
            "ym": ["2026-06", "2026-07"],
            "a_A_total": [3, 4],
        }
    )
    out = collapse_to_index_grid(df, TAIL)
    pd.testing.assert_frame_equal(out, df)


def test_no_tail_floors_every_row():
    """With no daily tail the index is purely monthly, so everything floors."""
    df = pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-07-01", "2026-07-15"]),
            "ym": ["2026-07", "2026-07-15"],
            "a_A_total": [1, 2],
        }
    )
    out = collapse_to_index_grid(df, None)
    assert len(out) == 1
    assert out["a_A_total"].iloc[0] == 3
