"""Collapse a leaf's several pricing units into the one unit it is displayed in.

The dashboard was showing one row per (leaf, unit): "Bananas, fresh /kg" and
"Bananas, fresh /unit" as two lines, each populated for a different handful of
countries. Both rows are then mostly blank, and the blanks read as missing
coverage rather than as one quantity split across two labels.

The rule is William's, from 2026-09-04: pick a display unit per leaf, convert
into it wherever the conversion can be made with confidence, and drop what
cannot rather than showing a fifth mostly-empty row. Conversion is not the same
thing as pooling -- the standing rule that a per-kg and a per-count median must
never be averaged together still holds, and is exactly why the count rows are
converted onto the kg scale FIRST and only then pooled.

Two conversion routes, and nothing else:

  * MASS <-> VOLUME by density. One kilo of nearly every grocery liquid is
    within a few percent of one litre, so ``DEFAULT_DENSITY`` is water and the
    table below carries only the leaves where that is visibly wrong (oils at
    0.92, honey and syrups at 1.4). Applied symmetrically to every country, a
    density that is slightly off shifts a leaf's whole level and changes no
    comparison; only 39 leaves hold both units at all.

  * PIECE <-> MASS/VOLUME by the leaf's typical mass, read from
    ``leaf_typical_mass.csv`` and already gated there four ways -- support,
    stability, plausibility, and a price-ratio check that rejects the leaves
    whose piece rows turn out to be wholesale cases rather than single items.
    A leaf that table rejects gets no conversion here; its piece rows are
    dropped and booked in the audit with the table's own reason.

Rows that cannot be converted are returned as a second frame rather than
silently discarded, so the artifact doubles as the record of what the dashboard
is not showing and why.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Kilograms per litre. Absent from this table means water.
DEFAULT_DENSITY = 1.0
DENSITY_BY_LEAF = {
    "01.1.5.1.1": 0.92,  # butter and margarine oils
    "01.1.5.1.2": 0.92,  # olive oil
    "01.1.5.1.3": 0.92,  # other edible oils
    "01.1.5.1.6": 0.92,  # other edible oils n.e.c.
    "01.1.5.1.9": 0.92,  # oils n.e.c.
    "01.1.8.4.0": 1.42,  # honey, syrups
    "01.1.8.5.0": 1.42,  # jams, marmalades
}

MASS_UNIT = "kg"
VOLUME_UNIT = "lt"
# `each` is publish's folded label; `unit` and `item` are the pre-fold spellings.
PIECE_UNITS = frozenset({"each", "unit", "item"})
# Ties in the canonical vote break toward the unit an economist would quote.
UNIT_PREFERENCE = (MASS_UNIT, VOLUME_UNIT, "each", "unit", "item")


def _density(code: str) -> float:
    return DENSITY_BY_LEAF.get(str(code), DEFAULT_DENSITY)


def canonical_units(df: pd.DataFrame) -> dict[str, str]:
    """Per leaf, the unit it will be displayed in: the one carrying the most
    rows corpus-wide.

    Pooled across countries deliberately. How a commodity is sold is a property
    of the commodity, not of the country -- eggs are counted and rice is weighed
    everywhere -- so letting each country pick its own display unit would make
    the leaf's row incomparable across the columns of the very table it sits in.
    """
    counts = df.groupby(["coicop_code", "standard_unit"]).size()
    out: dict[str, str] = {}
    for code, grp in counts.groupby(level=0):
        by_unit = grp.droplevel(0)
        top = int(by_unit.max())
        tied = [u for u, n in by_unit.items() if int(n) == top]
        out[str(code)] = min(
            tied,
            key=lambda u: (
                UNIT_PREFERENCE.index(u) if u in UNIT_PREFERENCE else len(UNIT_PREFERENCE)
            ),
        )
    return out


def _piece_size(typical_mass: pd.DataFrame) -> dict[tuple[str, str], float]:
    """(leaf, unit) -> the size of one piece, for accepted leaves only.

    Both spellings are filled where either exists: a leaf whose typical piece
    was measured in litres still converts onto a kg display scale through its
    own density, and a leaf that stopped at a mass converts onto a litre scale
    the same way. Deriving the missing side here keeps the conversion table the
    only place that has to know it.
    """
    if typical_mass is None or typical_mass.empty:
        return {}
    acc = typical_mass[typical_mass["accepted"].astype(bool)]
    sizes: dict[tuple[str, str], float] = {}
    for row in acc.itertuples():
        code, unit, amt = str(row.coicop_code), str(row.unit), float(row.median_amount)
        if not np.isfinite(amt) or amt <= 0:
            continue
        d = _density(code)
        if unit == MASS_UNIT:
            sizes[(code, MASS_UNIT)] = amt
            sizes.setdefault((code, VOLUME_UNIT), amt / d)
        elif unit == VOLUME_UNIT:
            sizes[(code, VOLUME_UNIT)] = amt
            sizes.setdefault((code, MASS_UNIT), amt * d)
    return sizes


def _factor(code: str, src: str, dst: str, sizes: dict) -> float | None:
    """Multiplier taking a unit value quoted per `src` to one quoted per `dst`.

    None means no defensible route exists, which is the signal to drop the row
    rather than to guess at one.
    """
    if src == dst:
        return 1.0
    d = _density(code)
    src_piece, dst_piece = src in PIECE_UNITS, dst in PIECE_UNITS
    if not src_piece and not dst_piece:
        # price/kg -> price/lt multiplies by the kilos in a litre, and back.
        return d if (src == MASS_UNIT and dst == VOLUME_UNIT) else 1.0 / d
    if src_piece and dst_piece:
        return 1.0
    if src_piece:
        # price/piece -> price/kg divides by the kilos in a piece.
        size = sizes.get((code, dst))
        return None if not size else 1.0 / size
    size = sizes.get((code, src))
    return None if not size else size


def collapse(
    df: pd.DataFrame,
    typical_mass: pd.DataFrame,
    value_cols: tuple[str, ...] = ("unit_value_usd", "unit_value_local"),
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Rewrite every row onto its leaf's display unit.

    Returns (converted, dropped). `converted` carries the same columns as the
    input with `standard_unit` rewritten and the value columns rescaled, plus
    `display_unit_source` recording whether the row was already in the display
    unit, converted by density, or converted through a typical mass. Grouping
    the result by (leaf, country) now yields one row per category, because
    `standard_unit` is constant within a leaf.
    """
    if df.empty:
        return df, df.iloc[:0].assign(drop_reason=pd.Series(dtype=object))

    canonical = canonical_units(df)
    sizes = _piece_size(typical_mass)
    reasons = _rejection_reasons(typical_mass)

    codes = df["coicop_code"].astype(str)
    units = df["standard_unit"].astype(str)
    target = codes.map(canonical)

    # Solved on the distinct (leaf, from, to) triples and joined back. There are
    # a few hundred of those against millions of rows, so a row-wise lookup here
    # is the difference between a second and several minutes.
    keys = pd.DataFrame({"_c": codes, "_s": units, "_t": target})
    distinct = keys.drop_duplicates().copy()
    distinct["_f"] = [
        _factor(c, s, t, sizes) for c, s, t in distinct.itertuples(index=False)
    ]
    factors = keys.merge(distinct, on=["_c", "_s", "_t"], how="left")["_f"]
    factors.index = df.index

    keep = factors.notna()
    dropped = df.loc[~keep].copy()
    if not dropped.empty:
        dropped["drop_reason"] = codes.loc[~keep].map(
            lambda c: reasons.get(c, "no typical mass for leaf")
        )
        dropped["display_unit"] = target.loc[~keep]

    out = df.loc[keep].copy()
    f = factors.loc[keep]
    for col in value_cols:
        if col in out.columns:
            out[col] = out[col].astype("float64") * f
    out["display_unit_source"] = np.where(
        f.eq(1.0) & units.loc[keep].eq(target.loc[keep]),
        "native",
        np.where(units.loc[keep].isin(PIECE_UNITS) | target.loc[keep].isin(PIECE_UNITS), "typical_mass", "density"),
    )
    out["standard_unit"] = target.loc[keep]

    logger.info(
        "unit collapse: %d rows -> %d display units over %d leaves; "
        "converted %d (density %d, typical mass %d), dropped %d",
        len(df),
        out["standard_unit"].nunique(),
        len(canonical),
        int((out["display_unit_source"] != "native").sum()),
        int((out["display_unit_source"] == "density").sum()),
        int((out["display_unit_source"] == "typical_mass").sum()),
        len(dropped),
    )
    return out, dropped


def _rejection_reasons(typical_mass: pd.DataFrame) -> dict[str, str]:
    """The typical-mass table's own verdict, so a dropped row says why."""
    if typical_mass is None or typical_mass.empty:
        return {}
    rej = typical_mass[~typical_mass["accepted"].astype(bool)]
    return {
        str(r.coicop_code): str(r.rejected_reason)
        for r in rej.itertuples()
        if isinstance(r.rejected_reason, str)
    }
