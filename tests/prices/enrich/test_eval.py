"""Thin CI wrapper over the first-class gold-eval harness.

Scores the deterministic cascade (tier-c off) against the 313-row de-contaminated
working gold and gates against regression floors. Floors sit a few points below
the measured baseline (2026-06-18); they are honest-but-low because the gold is
de-contaminated (the 187 cache-verbatim rows were split out to the held-out cert
set), so coicop drops from the inflated ~50% to the honest ~23%. Raise the floors
as the cascade improves. Tier-c accuracy is exercised manually via
`python run.py prices eval --tier-c`, not in CI.
"""

from __future__ import annotations

import pytest

from prices.enrich.eval import gold as gold_mod
from prices.enrich.eval import runner
from prices.enrich.eval.gold import CATEGORICAL_FIELDS

# Regression floors (measured 313-row de-contaminated baseline in parens).
FLOORS = {
    "coicop_code": 0.20,  # 23.32% — honest/low, de-contaminated; capped by 197 residual_llm (no tier-c)
    "pricing_basis": 0.88,  # 91.69%
    "standard_unit": 0.88,  # 91.69%
    "unit_value": 0.85,  # 89.78%
}
SUB_LABEL_FLOOR = 0.01  # 2.88% — dominated by partial_sub_label_pending state


@pytest.fixture(scope="module")
def result() -> dict:
    if not gold_mod.GOLD_PATH.exists():
        pytest.skip(f"gold set absent at {gold_mod.GOLD_PATH}")
    return runner.run(run_tier_c=False, write=False)


@pytest.mark.integration
@pytest.mark.slow
def test_all_rows_scored(result):
    assert result["n_total"] == 313, f"expected 313 gold rows, got {result['n_total']}"
    overall = result["overall"]
    assert overall["n"] == 313
    for f in CATEGORICAL_FIELDS:
        assert overall["fields"][f][1] == 313
    assert overall["unit_value"][1] == 313
    # Causal buckets partition the rows exactly once.
    assert sum(overall["buckets"].values()) == 313


@pytest.mark.integration
@pytest.mark.slow
def test_accuracy_floors(result):
    overall = result["overall"]
    for field, floor in FLOORS.items():
        c, t = (
            overall["fields"][field] if field in CATEGORICAL_FIELDS else overall[field]
        )
        acc = c / t
        assert acc >= floor, f"{field} {acc:.3%} regressed below floor {floor:.0%}"
    c, t = overall["fields"]["sub_label_id"]
    assert (
        c / t >= SUB_LABEL_FLOOR
    ), f"sub_label_id {c / t:.3%} below {SUB_LABEL_FLOOR:.0%}"
