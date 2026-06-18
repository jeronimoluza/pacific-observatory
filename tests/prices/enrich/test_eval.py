"""Thin CI wrapper over the first-class gold-eval harness.

Scores the deterministic cascade (tier-c off) against all 500 gold rows and
gates against regression floors. Floors sit a few points below the measured
baseline (2026-06-17); raise them as the cascade improves. Tier-c accuracy is
exercised manually via `python run.py prices eval --tier-c`, not in CI.
"""

from __future__ import annotations

import pytest

from prices.enrich.eval import gold as gold_mod
from prices.enrich.eval import runner
from prices.enrich.eval.gold import CATEGORICAL_FIELDS

# Regression floors (measured deterministic baseline in parens).
FLOORS = {
    "coicop_code": 0.48,  # 50.6% — capped by 41% residual_llm (no tier-c)
    "pricing_basis": 0.90,  # 92.4%
    "standard_unit": 0.90,  # 92.4%
    "unit_value": 0.85,  # 87.8%
}
SUB_LABEL_FLOOR = 0.15  # 20.0% — dominated by partial_sub_label_pending state


@pytest.fixture(scope="module")
def result() -> dict:
    if not gold_mod.GOLD_PATH.exists():
        pytest.skip(f"gold set absent at {gold_mod.GOLD_PATH}")
    return runner.run(run_tier_c=False, write=False)


@pytest.mark.integration
@pytest.mark.slow
def test_all_rows_scored(result):
    assert result["n_total"] == 500, f"expected 500 gold rows, got {result['n_total']}"
    overall = result["overall"]
    assert overall["n"] == 500
    for f in CATEGORICAL_FIELDS:
        assert overall["fields"][f][1] == 500
    assert overall["unit_value"][1] == 500
    # Causal buckets partition the rows exactly once.
    assert sum(overall["buckets"].values()) == 500


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
