"""Pin the Layer-2 outlier rule to Will's spec, in Will's units.

Will's rule, stated 2026-08-31: within a cell, standardize to unit price, take
logs, take a robust centre and scale from the median and MAD with
`robust_sd = 1.4826 * MAD`, form `robust_z = (y - m) / robust_sd`, and refuse
rows where `|robust_z| > 5`.

The shipped audit divided by the RAW MAD and defaulted to k=3.0, which is
|robust_z| = 2.02 -- 2.5x tighter than the spec, while the code and its
docstring both claimed to implement the spec. Nothing in the suite pinned
either the constant or the scale, which is precisely why it drifted silently.
These tests fail if either moves again.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from prices.build import unit_value_audit as uva

pytestmark = pytest.mark.unit

SIGMA = 0.25


def _lognormal_cell(n: int = 4000, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    return pd.DataFrame(
        {
            "coicop_code": "01.1.1.1",
            "country": "fiji",
            "observation_date": "2026-01-01",
            "unit_value_local": np.exp(rng.normal(0.0, SIGMA, n)),
        }
    )


def test_the_threshold_is_the_one_will_specified():
    import inspect

    sig = inspect.signature(uva.flag_uv_outliers)
    assert sig.parameters["k"].default == 5.0, "Will's rule is |robust_z| > 5"
    assert uva.MAD_TO_SIGMA == pytest.approx(1.4826)


def test_z_is_scaled_so_the_threshold_means_standard_deviations():
    """The whole point of 1.4826: z must be readable as sigmas, not raw MADs.

    Recovering the generating sigma is the only check that catches a missing or
    doubled constant -- a threshold test alone passes with any scale, because
    the constant and the cutoff move together.
    """
    df = _lognormal_cell()
    out = uva.flag_uv_outliers(df)
    resid = np.log(df["unit_value_local"]) - np.median(np.log(df["unit_value_local"]))
    implied = (
        (resid / out["uv_robust_z"]).replace([np.inf, -np.inf], np.nan).abs().median()
    )
    assert implied == pytest.approx(SIGMA, rel=0.08)


def test_a_clean_population_is_not_flagged():
    """At |z|>5 a 4,000-row normal cell should yield no refusals at all.

    Under the old raw-MAD k=3.0 this cell flags heavily -- |z|>2.02 catches
    roughly 4% of a normal population -- which is the coverage the spec was
    losing."""
    out = uva.flag_uv_outliers(_lognormal_cell())
    assert out["uv_outlier"].sum() == 0
    old = uva.flag_uv_outliers(_lognormal_cell(), k=3.0 / uva.MAD_TO_SIGMA)
    assert old["uv_outlier"].sum() > 100, "the old gate really was this tight"


def test_a_real_defect_is_still_caught():
    """Loosening to the spec must not blind the audit to parse errors."""
    df = _lognormal_cell()
    df.loc[0, "unit_value_local"] = df.loc[0, "unit_value_local"] * 100
    out = uva.flag_uv_outliers(df)
    assert out.loc[0, "uv_outlier"]
    assert abs(out.loc[0, "uv_robust_z"]) > 5


def test_min_n_admits_a_three_row_cell():
    """min_n=3 is the least that yields a non-degenerate MAD."""
    import inspect

    assert inspect.signature(uva.flag_uv_outliers).parameters["min_n"].default == 3
    rows = [
        {
            "coicop_code": "01.1.1.1",
            "country": "tonga",
            "observation_date": "2026-01-01",
            "unit_value_local": v,
        }
        for v in (10.0, 10.5, 11.0)
    ]
    out = uva.flag_uv_outliers(pd.DataFrame(rows))
    assert not out["uv_thin"].any()
    assert (out["trust_uv"] == "high").all()
