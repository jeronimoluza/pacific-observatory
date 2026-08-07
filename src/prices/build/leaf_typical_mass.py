"""Per-leaf typical mass/volume, derived from the measured rows of a build frame.

The third bucket of the ``item``-basis problem. `sold_by_item` splits `item`
rows into GENUINE per-piece sales (trusted as-is) and MISSING-QUANTITY parse
failures (quarantined). A third class fits neither: the good IS sold as a
piece, but the analytically useful figure is per-kg or per-lt, and the piece
has a stable typical mass. Bread is the canonical case -- a loaf is a piece,
but a loaf is also reliably ~0.4 kg, so its price per piece can be converted
into a price per kilo without fabricating anything.

The mass comes from rows the pipeline already measured: every `mass`/`volume`
row whose amount was extracted from the product name. Those are pooled ACROSS
COUNTRIES per leaf, deliberately -- a typical loaf weighs the same in Fiji and
Vietnam, because mass is a physical property of the product. Price is never
pooled: it is an economic quantity and stays country-local.

DERIVING the mass reads only ``amount_value``. VALIDATING it has to look at
price, because the failure that matters is invisible in the amounts: a leaf
whose measured rows agree beautifully can still have `item` rows drawn from a
completely different population -- catering crates, cases, bulk sacks -- and
dividing a crate price by a single-portion mass yields a per-kilo figure that is
wrong by orders of magnitude. The amounts cannot see this; only the prices can.

A leaf earns a typical mass only if the measured rows agree. The four gates:

  * ``insufficient_support`` -- fewer than MIN_SUPPORT measured rows. Too few
    to call the central value typical.
  * ``unstable_mass`` -- robust CV (MAD / median) above MAX_REL_SPREAD. The
    leaf's products come in many sizes, so there is no typical one. This is
    what correctly rejects catch-all leaves (rice, pasta, "other sauces"),
    where a median would be an artifact of the pack-size mix, not a constant.
  * ``implausible_*`` -- median outside the physical bounds. A defensive rail
    against extraction artifacts, deliberately wide: single tea sachets are
    real at a few grams and rice sacks are real at several kilos, so this gate
    should almost never fire on a healthy corpus.
  * ``implausible_price_ratio`` -- the empirical check. Within a country,
    compare the unit values the conversion WOULD produce against the ones
    measured rows actually produce; the ratio is dimensionless, so per-country
    ratios pool across countries with no FX and no price-level contamination.
    A leaf whose pooled ratio sits outside RATIO_BOUNDS is not converting, it is
    fabricating. This is the gate that catches apples (10.1x) and tomatoes
    (70x), where the `item` rows are wholesale cases rather than single fruit.

Rejected leaves are written to the artifact WITH their reason rather than
dropped, so the table doubles as the audit of what could not be converted and
why. A leaf with no country carrying RATIO_MIN_SIDE rows on both sides gets no
ratio and is left alone here -- unverifiable is not the same as wrong, and the
Layer-2 baseline rule is what withholds trust from those rows downstream.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from prices.enrich.stages.merge import compute_unit_value
from prices.enrich.stages.prepare import parse_price

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[3]
BUILD_DIR = REPO_ROOT / "data" / "prices" / "build"
TYPICAL_MASS_CSV = BUILD_DIR / "leaf_typical_mass.csv"

# Bases whose rows carry a real measured quantity, and so can donate a mass.
MEASURED_BASES = frozenset({"mass", "volume"})

# A leaf needs at least this many measured rows before its median is called
# typical. Mirrors the spirit of the Layer-2 min_n: thin evidence is reported,
# never trusted.
MIN_SUPPORT = 30

# Maximum robust CV (MAD / median) for a leaf's mass to count as a constant.
# 0.5 admits bread (0.27) and eggs (0.29) while rejecting rice (0.80) and
# ice cream (0.81), whose spread reflects a pack-size mix rather than a product.
MAX_REL_SPREAD = 0.5

# Physical plausibility rails, in kg and lt respectively. Wide on purpose --
# these catch extraction artifacts, not unusual-but-real products.
MASS_BOUNDS = (0.001, 10.0)
VOLUME_BOUNDS = (0.001, 10.0)

# standard_unit -> the pricing_basis a converted row should carry.
UNIT_TO_BASIS = {"kg": "mass", "lt": "volume"}

# Acceptable range for median(derived unit value) / median(measured unit value),
# pooled over countries. "Within a factor of two" -- generous, because a real
# typical mass will not be off by that much, and anything worse is a different
# product population rather than an imprecise average.
RATIO_BOUNDS = (0.5, 2.0)

# Rows required on EACH side of a country's ratio before it counts. Below this
# the country contributes nothing rather than a noisy vote.
RATIO_MIN_SIDE = 5

TABLE_COLS = [
    "coicop_code", "unit", "n", "median_amount", "mad", "robust_cv",
    "price_ratio", "ratio_countries",
    "accepted", "rejected_reason", "generated_at",
]


def _gate(unit: str, n: int, median_amount: float, robust_cv: float) -> tuple[bool, str]:
    """Accept/reject one leaf's derived mass. Returns (accepted, reason)."""
    if n < MIN_SUPPORT:
        return False, f"insufficient_support (n={n}<{MIN_SUPPORT})"
    if pd.isna(robust_cv) or robust_cv > MAX_REL_SPREAD:
        cv = "nan" if pd.isna(robust_cv) else f"{robust_cv:.3f}"
        return False, f"unstable_mass (robust_cv={cv}>{MAX_REL_SPREAD})"
    bounds = MASS_BOUNDS if unit == "kg" else VOLUME_BOUNDS
    if not (bounds[0] <= median_amount <= bounds[1]):
        return False, (
            f"implausible_{unit} (median={median_amount:.4f} outside {bounds})"
        )
    return True, ""


def derive_typical_mass(df: pd.DataFrame) -> pd.DataFrame:
    """Derive and gate a per-leaf typical mass from a build frame's measured rows.

    Reads only measured (mass/volume) rows, pooled across all countries. Returns
    one row per leaf that had any measured support, accepted or not.
    """
    if df.empty:
        return pd.DataFrame(columns=TABLE_COLS)

    measured = df[df["pricing_basis"].isin(MEASURED_BASES)]
    measured = measured[
        measured["amount_value"].notna() & (measured["amount_value"] > 0)
    ]
    if measured.empty:
        return pd.DataFrame(columns=TABLE_COLS)

    generated_at = datetime.now(timezone.utc).isoformat()
    rows = []
    for code, group in measured.groupby("coicop_code"):
        amounts = group["amount_value"]
        median_amount = float(amounts.median())
        mad = float((amounts - median_amount).abs().median())
        robust_cv = (mad / median_amount) if median_amount else np.nan
        units = group["standard_unit"].mode()
        if units.empty:
            continue
        unit = units.iloc[0]
        accepted, reason = _gate(unit, len(group), median_amount, robust_cv)
        rows.append({
            "coicop_code": str(code),
            "unit": unit,
            "n": len(group),
            "median_amount": median_amount,
            "mad": mad,
            "robust_cv": robust_cv,
            "accepted": accepted,
            "rejected_reason": reason,
            "generated_at": generated_at,
        })

    table = apply_ratio_gate(pd.DataFrame(rows, columns=TABLE_COLS), df)
    if not table.empty:
        n_ok = int(table["accepted"].sum())
        logger.info(
            "typical mass: %d leaves with measured support, %d accepted, %d rejected",
            len(table), n_ok, len(table) - n_ok,
        )
    return table


def _local_price(df: pd.DataFrame) -> pd.Series:
    """Local-currency price, whether or not ``price_local`` exists yet.

    The gate runs before the build parses prices, but the same function is
    useful against an already-finalized frame, so accept either shape.
    """
    if "price_local" in df.columns:
        parsed = pd.to_numeric(df["price_local"], errors="coerce")
        if parsed.notna().any():
            return parsed
    return pd.to_numeric(
        df.apply(lambda r: parse_price(r.get("price"), r.get("currency")), axis=1),
        errors="coerce",
    )


def leaf_price_ratios(df: pd.DataFrame, table: pd.DataFrame) -> pd.DataFrame:
    """Per-leaf median of the per-country derived/measured unit-value ratios.

    Only leaves the amount-based gates already accepted are checked, and only
    the `item` rows that would ACTUALLY convert -- a leaf in the sold_by_item
    prior keeps its per-piece rows, so including them here would gate a mass on
    rows it will never touch.
    """
    from prices.build.sold_by_item import is_sold_by_item

    empty = pd.DataFrame(columns=["coicop_code", "price_ratio", "ratio_countries"])
    if df.empty or table.empty or not table["accepted"].any():
        return empty

    cand = table[table["accepted"]]
    mass = {str(r.coicop_code): float(r.median_amount) for r in cand.itertuples()}
    unit = {str(r.coicop_code): str(r.unit) for r in cand.itertuples()}

    code = df["coicop_code"].astype(str)
    in_cand = code.isin(mass)
    convertible = (
        in_cand
        & (df["pricing_basis"] == "item")
        & ~df["coicop_code"].apply(is_sold_by_item)
    )
    measured = in_cand & df["pricing_basis"].isin(MEASURED_BASES)
    sel = convertible | measured
    if not sel.any():
        return empty

    sub = df.loc[sel].copy()
    sub["_code"] = code[sel]
    sub["_derived"] = convertible[sel].to_numpy()
    # A convertible row is priced as if it already carried the leaf's typical
    # amount -- exactly what convert_item_rows would give it.
    amount = sub["amount_value"].where(~sub["_derived"], sub["_code"].map(mass))
    basis = sub["pricing_basis"].where(
        ~sub["_derived"], sub["_code"].map(unit).map(UNIT_TO_BASIS)
    )
    sub["_uv"] = pd.to_numeric(pd.Series(
        [
            compute_unit_value(p, b, a, c, m)
            for p, b, a, c, m in zip(
                _local_price(sub), basis, amount,
                sub.get("count", pd.Series(index=sub.index, dtype=float)),
                sub.get("multiplier", pd.Series(index=sub.index, dtype=float)),
            )
        ],
        index=sub.index,
    ), errors="coerce")
    sub = sub[sub["_uv"].notna() & (sub["_uv"] > 0)]
    if sub.empty:
        return empty

    keys = ["_code", "country"]
    d = sub[sub["_derived"]].groupby(keys)["_uv"].agg(md="median", nd="size")
    m = sub[~sub["_derived"]].groupby(keys)["_uv"].agg(mm="median", nm="size")
    j = d.join(m, how="inner")
    j = j[(j["nd"] >= RATIO_MIN_SIDE) & (j["nm"] >= RATIO_MIN_SIDE) & (j["mm"] > 0)]
    if j.empty:
        return empty

    j["ratio"] = j["md"] / j["mm"]
    out = j.groupby(level="_code").agg(
        price_ratio=("ratio", "median"), ratio_countries=("ratio", "size")
    )
    return out.reset_index().rename(columns={"_code": "coicop_code"})


def apply_ratio_gate(table: pd.DataFrame, df: pd.DataFrame) -> pd.DataFrame:
    """Demote accepted leaves whose conversion does not reproduce measured prices."""
    if table.empty:
        return table
    table = table.drop(columns=["price_ratio", "ratio_countries"], errors="ignore")
    table = table.merge(leaf_price_ratios(df, table), on="coicop_code", how="left")

    lo, hi = RATIO_BOUNDS
    bad = (
        table["accepted"]
        & table["price_ratio"].notna()
        & ((table["price_ratio"] < lo) | (table["price_ratio"] > hi))
    )
    if bad.any():
        table.loc[bad, "rejected_reason"] = [
            f"implausible_price_ratio (derived/measured={r.price_ratio:.2f} outside "
            f"{RATIO_BOUNDS} over {int(r.ratio_countries)} countries)"
            for r in table.loc[bad].itertuples()
        ]
        table.loc[bad, "accepted"] = False
        logger.info(
            "typical mass: %d leaves demoted by the price-ratio gate", int(bad.sum())
        )
    return table[TABLE_COLS]


def write_typical_mass(table: pd.DataFrame) -> None:
    """Persist the table (accepted and rejected alike) for inspection."""
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    table.to_csv(TYPICAL_MASS_CSV, index=False)
    logger.info("wrote %s (%d leaves)", TYPICAL_MASS_CSV, len(table))


def accepted_lookup(table: pd.DataFrame) -> dict[str, tuple[float, str]]:
    """coicop_code -> (median_amount, unit) for accepted leaves only."""
    if table.empty:
        return {}
    ok = table[table["accepted"]]
    return {
        str(r.coicop_code): (float(r.median_amount), str(r.unit))
        for r in ok.itertuples()
    }
