"""`_compute_unit_values` feeds the scalar helpers by column, not by row.

`apply(axis=1)` handed each helper a Series, so the old code could reach an
optional column with `r.get(...)` and get None when it was absent. Zipping
arrays has no such tolerance, so it is restated in `_column` -- and restated
behaviour needs a test, or the next frame that omits a column fails with a
KeyError deep inside a list comprehension.

The helpers return None, but pandas infers a float column from a list of floats
and Nones, so the absent values read back as NaN. That was already true of the
`apply` version; these assertions compare NaN-aware for that reason.
"""

from __future__ import annotations

import pandas as pd
import pytest

from prices.build import aggregate

pytestmark = pytest.mark.unit


def _frame(**overrides) -> pd.DataFrame:
    base = {
        "price": ["10.0", "20.0", "bad"],
        "currency": ["FJD", "FJD", "FJD"],
        "pricing_basis": ["mass", "count", "mass"],
        "amount_value": [2.0, None, 4.0],
        "count": [1, 4, 1],
        "multiplier": [1, 1, 1],
    }
    base.update(overrides)
    return pd.DataFrame(base)


def _values(series) -> list:
    """The column as plain floats with every flavour of missing spelled None."""
    return [None if pd.isna(v) else float(v) for v in series]


def test_unit_values_are_computed_per_column():
    out = aggregate._compute_unit_values(_frame())
    assert _values(out["price_local"]) == [10.0, 20.0, None]
    # mass: price / (amount * multiplier); count: price / (count * multiplier);
    # an unparseable price has no unit value at all.
    assert _values(out["unit_value_local"]) == [5.0, 5.0, None]
    assert "price" not in out.columns


@pytest.mark.parametrize("missing", ["amount_value", "count", "multiplier"])
def test_an_absent_optional_column_is_tolerated(missing):
    """These three reached the helper through `r.get(...)` before. A frame
    without one must still compute, not raise."""
    out = aggregate._compute_unit_values(_frame().drop(columns=[missing]))
    assert len(out) == 3
    assert _values(out["price_local"]) == [10.0, 20.0, None]


def test_a_missing_column_matches_what_the_row_wise_version_returned():
    """`r.get(name)` yielded None, and `compute_unit_value` treats None as 1 for
    count/multiplier and as "no amount" for mass. Pin that, so the fallback is a
    decision rather than an accident."""
    out = aggregate._compute_unit_values(_frame().drop(columns=["amount_value"]))
    # mass rows lose their denominator entirely; the count row is unaffected.
    assert _values(out["unit_value_local"]) == [None, 5.0, None]
