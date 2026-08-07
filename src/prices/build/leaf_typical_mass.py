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
pooled: it is an economic quantity and stays country-local. This module reads
only ``amount_value``; no price column is touched anywhere in it.

A leaf earns a typical mass only if the measured rows agree. The three gates:

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

Rejected leaves are written to the artifact WITH their reason rather than
dropped, so the table doubles as the audit of what could not be converted and
why.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

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

TABLE_COLS = [
    "coicop_code", "unit", "n", "median_amount", "mad", "robust_cv",
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

    table = pd.DataFrame(rows, columns=TABLE_COLS)
    if not table.empty:
        n_ok = int(table["accepted"].sum())
        logger.info(
            "typical mass: %d leaves with measured support, %d accepted, %d rejected",
            len(table), n_ok, len(table) - n_ok,
        )
    return table


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
