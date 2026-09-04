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
  - ``qa_uv_category`` a parsed mass/volume/length denominator is MEANINGFUL for
                      this leaf (``enrich.uv_gate``). Distinct from
                      ``qa_quantity``: a "1mg*84" pharma row has a perfectly
                      real parsed quantity, it just is not a net pack weight, so
                      dividing price by it yields $880k/kg. Non-measured bases
                      (count/item) are not gated here.
  - ``qa_uv_inlier``  Layer-2 unit-value audit passed (trust_uv == "high"): the
                      row sits inside its (leaf, country, unit) distribution.
  - ``qa_uv_plausible`` the unit value sits inside an ABSOLUTE per-unit band
                      (``PLAUSIBLE_USD``), judged on its own and not against its
                      cell. ``qa_uv_inlier`` is a RELATIVE (MAD) test and is
                      therefore structurally blind to a defect that shifts a
                      whole country at once, because the bad rows become their
                      own cell's norm. In the 2026-09-03 Slovak 100x incident
                      every breaching row passed ``qa_uv_inlier``.
  - ``qa_fx``         a USD unit value could be computed (fx_rate present).

qa_status precedence (a row wears the first gate it fails):
  review_zero_price   -> price_local is zero, negative, or missing
  review_basis        -> Layer-1 rejected the (leaf, basis) pair
  review_missing_qty  -> `item` basis with no per-item prior: unknown quantity,
                         RETAINED and triageable, never shipped
  review_uv_category  -> measured denominator on a leaf where mass/volume is not
                         a sale quantity (pharma dosage, device capacity)
  review_uv_thin      -> Layer-2 withheld trust for lack of support: the cell
                         held too few rows to judge the price at all. NOT a
                         claim that anything is wrong with the row.
  review_uv_outlier   -> Layer-2 judged the row and it sat outside its cell
  review_uv_implausible -> the unit value is outside the absolute band for its
                         standard_unit, whatever its cell says
  review_fx           -> local unit value fine, but no FX -> no USD
  trusted             -> all gates pass; ships in the consumable deliverable
"""

from __future__ import annotations

import pandas as pd

from prices.build.sold_by_item import is_sold_by_item
from prices.enrich import uv_gate

GATE_COLS = [
    "qa_price_positive",
    "qa_basis_ok",
    "qa_quantity",
    "qa_uv_category",
    "qa_uv_inlier",
    "qa_uv_plausible",
    "qa_fx",
]
_MARKER_BASES = frozenset({"mass", "volume", "length", "count"})

# Absolute (low, high) USD bounds per standard_unit. A unit absent from this map
# is not scoped by the gate: `item` means "no quantity was parsed", so there is
# no quantity for a per-unit band to be about.
#
# kg's floor is 0.20, not 0.05: a 2026-09-04 audit of the delivered dashboard's
# fat tail found 37,015 Argentina rows (vea_ar/disco_ar/jumbo_ar/carrefour_ar --
# cheese, yogurt, fresh pork, sausages) sitting between $0.05 and $0.30/kg, a
# price-parsing defect upstream (report, not fixed here), plus a cluster of
# CJK multipack-count-noun rows (a whole fruit box's stated total weight
# multiplied again by its piece count) landing in the same band. Global staple
# grains (rice/wheat/potatoes) sit at $0.53/kg at their own 1st percentile, so
# 0.20 does not reach genuine staple pricing; wholesale China veg (xinfadi,
# which legitimately prices under $0.20/kg) loses 37 of 31,212 rows. `lt` stays
# at 0.05 -- its own low tail is bottled water and soda, genuinely that cheap.
PLAUSIBLE_USD = {"kg": (0.20, 200.0), "lt": (0.05, 200.0), "unit": (0.005, 500.0)}


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
    if not row["qa_uv_category"]:
        return "review_uv_category"
    if not row["qa_uv_inlier"]:
        # two different verdicts, and a reader must not read one as the other
        return "review_uv_thin" if row["qa_uv_thin"] else "review_uv_outlier"
    if not row["qa_uv_plausible"]:
        return "review_uv_implausible"
    if not row["qa_fx"]:
        return "review_fx"
    return "trusted"


def compute_qa(df: pd.DataFrame) -> pd.DataFrame:
    """Attach the five gate booleans + the categorical ``qa_status`` column.

    Non-destructive: adds columns, drops nothing. Expects the Layer-1
    (``trust_level``) and Layer-2 (``trust_uv``) columns plus ``fx_rate`` to be
    present, i.e. call this after flag_uv_outliers + attach_fx_and_usd.
    """
    df = df.copy()
    if df.empty:
        for col in GATE_COLS + ["qa_uv_thin"]:
            df[col] = pd.Series(dtype=bool)
        df["qa_status"] = pd.Series(dtype=object)
        return df

    trust_level = df.get("trust_level", pd.Series("high", index=df.index)).fillna(
        "high"
    )
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
    # Vectorised equivalent of `uv_gate.gate(code, basis)[0]`: the allow-list
    # depends only on the code, so map over DISTINCT codes (hundreds) rather
    # than calling per row (millions). test_qa_uv_category asserts the two agree.
    codes = df.get("coicop_code", pd.Series(pd.NA, index=df.index)).astype("string")
    is_gated = (
        df.get("pricing_basis", pd.Series(pd.NA, index=df.index))
        .isin(uv_gate.GATED_BASES)
        .to_numpy()
    )
    allow_by_code = {c: uv_gate.is_allowed_leaf(c) for c in codes.dropna().unique()}
    # .eq(True) rather than .fillna(False): an unmapped code is NaN here, and
    # fillna on an object column is deprecated.
    allowed = codes.map(allow_by_code).eq(True).to_numpy()
    df["qa_uv_category"] = ~is_gated | allowed

    df["qa_uv_inlier"] = trust_uv.eq("high").to_numpy()
    # not a gate (it never decides shippability), only the reason a failed
    # qa_uv_inlier wears -- so it stays out of GATE_COLS.
    df["qa_uv_thin"] = (
        df.get("uv_thin", pd.Series(False, index=df.index)).fillna(False).to_numpy()
    )
    # Same constant the explorer applies to cell MEDIANS, applied here per ROW.
    # A systematic defect corrupts most of a cell at once, so both catch the same
    # incident -- but the row test also names the individual offending row.
    units = df.get("standard_unit", pd.Series(pd.NA, index=df.index))
    uv_usd = pd.to_numeric(
        df.get("unit_value_usd", pd.Series(pd.NA, index=df.index)), errors="coerce"
    )
    lo = units.map(lambda u: PLAUSIBLE_USD.get(u, (None, None))[0])
    hi = units.map(lambda u: PLAUSIBLE_USD.get(u, (None, None))[1])
    scoped = pd.to_numeric(lo, errors="coerce").notna()
    # A missing unit value is not an implausible one -- qa_fx and the upstream
    # denominator gates own that case, and this gate must not double-report it.
    df["qa_uv_plausible"] = (
        ~scoped | uv_usd.isna() | uv_usd.between(pd.to_numeric(lo), pd.to_numeric(hi))
    ).to_numpy()

    df["qa_fx"] = df.get("fx_rate", pd.Series(pd.NA, index=df.index)).notna().to_numpy()

    df["qa_status"] = df.apply(_status, axis=1).to_numpy()
    return df
