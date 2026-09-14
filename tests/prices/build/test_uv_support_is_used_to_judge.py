"""Evidence admitted for the COUNT must also be admitted for the SPREAD.

`_pooled_support` lets neighbouring months lend a cell the rows it needs to
clear `min_n`, but the centre and spread are still estimated from the row's own
month alone (`bw.groupby(key)` where `key` carries `_period`). A cell can
therefore borrow its way past the thin gate and then find no spread at home:
`mad` is 0 or NaN, `has_spread` is False, `uv_robust_z` stays NaN, and
`outlier` -- a comparison against NaN -- is False. The row ships `trust_uv ==
"high"` without ever having been judged.

That is the opposite of the precision-first posture the module states. Either
the borrowed rows are good enough to judge with, or they were not good enough
to lend support in the first place. On the 2026-09-10 corpus 585,760 trusted
rows (3.85%) carry `uv_robust_z == NaN`; 101,993 of them sit at exactly
`uv_cell_n == 3`, the borrowed minimum.
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


def _feb(out: pd.DataFrame) -> pd.DataFrame:
    return out[out["observation_date"].str.startswith("2026-02")]


def test_a_lone_borrowed_row_is_actually_judged():
    """February borrows 16 rows of support, so it must be judged by them.

    Jan and Mar sit at 10. February's only row is 1000 -- a hundredfold break
    that every neighbouring month contradicts. It must not ship as trusted.
    """
    out = uva.flag_uv_outliers(
        pd.DataFrame(
            _cell("tonga", 1, [10.0 + i * 0.05 for i in range(8)])
            + _cell("tonga", 2, [1000.0])
            + _cell("tonga", 3, [10.0 + i * 0.05 for i in range(8)])
        )
    )
    feb = _feb(out)
    assert feb["uv_cell_n"].iloc[0] >= 3, "the row did borrow its support"
    assert not feb["uv_thin"].iloc[0], "so it is not withheld for thinness"
    assert feb["trust_uv"].iloc[0] == "flag", "and it must not ship as trusted"


def test_support_that_clears_the_gate_also_produces_a_verdict():
    """No row may be declared judgeable and then left unjudged."""
    out = uva.flag_uv_outliers(
        pd.DataFrame(
            _cell("tonga", 1, [10.0 + i * 0.05 for i in range(8)])
            + _cell("tonga", 2, [10.0])
            + _cell("tonga", 3, [10.0 + i * 0.05 for i in range(8)])
        )
    )
    feb = _feb(out)
    assert not feb["uv_thin"].iloc[0]
    assert feb["uv_robust_z"].notna().all(), (
        "a non-thin row with no robust_z was never scored"
    )


def test_pooling_the_spread_still_does_not_pool_the_comparison():
    """The guarantee the period-in-key buys must survive the change.

    A cell tripling over three months is inflation. Pooling the spread must not
    make January's 10 an outlier against March's 30.
    """
    out = uva.flag_uv_outliers(
        pd.DataFrame(
            _cell("fiji", 1, [10.0 + i * 0.05 for i in range(8)])
            + _cell("fiji", 2, [20.0 + i * 0.05 for i in range(8)])
            + _cell("fiji", 3, [30.0 + i * 0.05 for i in range(8)])
        )
    )
    assert out["uv_outlier"].sum() == 0
