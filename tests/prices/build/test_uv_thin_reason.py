"""The two `trust_uv == "flag"` verdicts must stay distinguishable.

`flag_uv_outliers` refuses a row for two unrelated reasons: its cell had fewer
than `min_n` baseline rows, so it was never scored at all, or it was scored and
came out beyond `k` MADs. `qa.py` reports those as `review_uv_thin` and
`review_uv_outlier` and its own comment insists a reader must not read one as
the other -- but the audit never emitted `uv_thin`, so `qa.py`'s
`df.get("uv_thin", ...)` default won and every thin row was filed as an
outlier. On the production corpus that mislabelled 348,545 rows and made
`review_uv_thin` dead code.
"""

from __future__ import annotations

import pandas as pd
import pytest

from prices.build import qa
from prices.build.unit_value_audit import NEW_COLS, flag_uv_outliers

pytestmark = pytest.mark.unit


def _cell(code: str, country: str, values: list[float]) -> list[dict]:
    return [
        {
            "coicop_code": code,
            "country": country,
            "observation_date": "2026-01-01",
            "unit_value_local": v,
        }
        for v in values
    ]


@pytest.fixture
def audited() -> pd.DataFrame:
    # One cell with enough baseline rows to judge (12 tight + 1 far), one with
    # too few to judge at all.
    rows = _cell("01.1.1.1", "fiji", [10.0 + i * 0.01 for i in range(12)] + [900.0])
    rows += _cell("01.1.9.9", "tonga", [7.0, 7.0])
    return flag_uv_outliers(pd.DataFrame(rows), min_n=5)


def test_the_audit_emits_every_column_it_advertises(audited):
    assert set(NEW_COLS) <= set(audited.columns)


def test_an_unjudgeable_cell_is_thin_not_an_outlier(audited):
    thin = audited[audited["country"] == "tonga"]
    assert thin["uv_thin"].all()
    assert not thin["uv_outlier"].any()
    # never scored, so there is no z to read
    assert thin["uv_robust_z"].isna().all()
    assert (thin["trust_uv"] == "flag").all()


def test_a_judged_failure_is_an_outlier_not_thin(audited):
    fat = audited[audited["country"] == "fiji"]
    assert not fat["uv_thin"].any(), "a well-supported cell is never thin"
    far = fat[fat["unit_value_local"] > 500]
    assert far["uv_outlier"].all()
    assert (fat[fat["unit_value_local"] < 500]["trust_uv"] == "high").all()


def test_qa_reports_the_two_refusals_under_different_names(audited):
    """End to end through compute_qa: the reason must survive the seam."""
    df = audited.assign(
        pricing_basis="mass",
        standard_unit="kg",
        quantity_amount=1.0,
        price_local=10.0,
        unit_value_usd=10.0,
        fx_rate=1.0,
    )
    out = qa.compute_qa(df)
    by_country = dict(zip(out["country"], out["qa_status"]))
    assert by_country["tonga"] == "review_uv_thin"
    statuses = set(out[out["country"] == "fiji"]["qa_status"])
    assert "review_uv_outlier" in statuses
    assert "review_uv_thin" not in statuses
