"""Composable QA gates + a categorical ``qa_status`` rollup for the consumable.

Not an opaque numeric score: each trust dimension is its own named boolean gate,
and ``qa_status`` is the first-failing-gate rollup so a reviewer reads *why* a
row is or is not shippable, not just a number.

Gates (all True == shippable):
  - ``qa_price_positive``  ``price_local`` is a real positive number (not zero,
                      negative, or NaN) -- catches out-of-stock $0 rows.
  - ``qa_basis_ok``   Layer-1 basis audit passed (trust_level == "high"). The
                      (leaf, pricing_basis) pair is physically possible.
  - ``qa_quantity``   the denominator of unit_value is real: an explicit
                      mass/volume/length/count marker was parsed, OR the leaf is
                      a genuine per-item sale (sold_by_item prior). This is the
                      gate that separates a legit per-piece pineapple from a
                      loose-flour row that merely lost its "500 g" token.
  - ``qa_uv_inlier``  Layer-2 unit-value audit passed (trust_uv == "high"): the
                      row sits inside its (leaf, country, unit) distribution.
  - ``qa_fx``         a USD unit value could be computed (fx_rate present).

qa_status precedence (a row wears the first gate it fails):
  review_zero_price   -> price_local is zero, negative, or missing
  review_basis        -> Layer-1 rejected the (leaf, basis) pair
  review_missing_qty  -> `item` basis with no per-item prior: unknown quantity,
                         RETAINED and triageable, never shipped
  review_uv_outlier   -> Layer-2 flagged (outlier or thin cell)
  review_fx           -> local unit value fine, but no FX -> no USD
  modelled_estimate   -> every gate passed, but the row is a cost-of-living
                         city average rather than a shelf price. Its own tier
                         because for ~90% of these no retail row exists in the
                         cell to score against, so "passed every gate" would
                         really mean "was never tested". Ships labelled.
  trusted             -> all gates pass on an observed retail price; ships in
                         the consumable deliverable
"""
from __future__ import annotations

import pandas as pd

from prices.build.sold_by_item import is_sold_by_item

GATE_COLS = ["qa_price_positive", "qa_basis_ok", "qa_quantity", "qa_uv_inlier", "qa_fx"]
_MARKER_BASES = frozenset({"mass", "volume", "length", "count"})


def _row_has_quantity(basis, coicop_code) -> bool:
    """True when the unit-value denominator is real for this row.

    Marker bases (mass/volume/length/count) always carry a parsed quantity.
    The `item` fallback is real only when the leaf is a genuine per-piece sale.
    """
    if isinstance(basis, str) and basis in _MARKER_BASES:
        return True
    if basis == "item":
        return is_sold_by_item(coicop_code)
    return False


def _status(row) -> str:
    if not row["qa_price_positive"]:
        return "review_zero_price"
    if not row["qa_basis_ok"]:
        return "review_basis"
    if not row["qa_quantity"]:
        # item-basis with no per-item prior: unknown quantity, quarantined.
        return "review_missing_qty"
    modelled = row.get("evidence") == "modelled"
    # A modelled row whose cell holds no retail row is flagged by Layer-2 for
    # having no baseline at all, not for failing a comparison -- `uv_outlier`
    # stays False. Reporting that as `review_uv_outlier` would claim a test that
    # never ran. Retail rows are untouched by this branch and keep the existing
    # behaviour exactly.
    untested = modelled and not row.get("uv_outlier", False)
    if not row["qa_uv_inlier"] and not untested:
        return "review_uv_outlier"
    if not row["qa_fx"]:
        return "review_fx"
    if modelled:
        return "modelled_estimate"
    return "trusted"


def compute_qa(df: pd.DataFrame) -> pd.DataFrame:
    """Attach the five gate booleans + the categorical ``qa_status`` column.

    Non-destructive: adds columns, drops nothing. Expects the Layer-1
    (``trust_level``) and Layer-2 (``trust_uv``) columns plus ``fx_rate`` to be
    present, i.e. call this after flag_uv_outliers + attach_fx_and_usd.
    """
    df = df.copy()
    if df.empty:
        for col in GATE_COLS:
            df[col] = pd.Series(dtype=bool)
        df["qa_status"] = pd.Series(dtype=object)
        return df

    trust_level = df.get("trust_level", pd.Series("high", index=df.index)).fillna("high")
    trust_uv = df.get("trust_uv", pd.Series("high", index=df.index)).fillna("high")

    price_local = df.get("price_local", pd.Series(1.0, index=df.index))
    df["qa_price_positive"] = (
        pd.to_numeric(price_local, errors="coerce").gt(0).to_numpy()
    )
    df["qa_basis_ok"] = trust_level.eq("high").to_numpy()
    df["qa_quantity"] = df.apply(
        lambda r: _row_has_quantity(r.get("pricing_basis"), r.get("coicop_code")),
        axis=1,
    ).to_numpy()
    df["qa_uv_inlier"] = trust_uv.eq("high").to_numpy()
    df["qa_fx"] = df.get("fx_rate", pd.Series(pd.NA, index=df.index)).notna().to_numpy()

    df["qa_status"] = df.apply(_status, axis=1).to_numpy()
    return df
