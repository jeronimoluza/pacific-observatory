"""Stage B trust: allowed bases, William's band, size imputation, trust levels.

Spec: vault `specs/prices-refactor/stage-b-trust.md`. Divisions 01 + 02.1 only.

The band is William's rule (email 2026-08-31) as `unit_value_audit` already
implements it: per (leaf, country, standard_unit) cell and month, with a +/-1
month support window, |robust_z| > 5 is out. What changes here is what may
DEFINE a cell. Only rows whose size was extracted and whose basis is one the
leaf is sold in (`basis_map.csv`) enter the baseline, and the band is built
twice so a first-pass outlier cannot hold the median it was judged against.

A sizeless row gets a size from its own country's extracted rows of the same
leaf, never from a cross-country typical mass. Imputed rows are scored against
the final band and never feed it: an `imputed_fit` size is chosen to fit the
band, so letting it in would grade its own guess. Because a non-baseline row
cannot move any statistic in `flag_uv_outliers`, every candidate size of every
leaf is scored in one call.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from prices.build.unit_value_audit import UV_SUPPORT_WINDOW, flag_uv_outliers

_DIR = Path(__file__).resolve().parent
BASIS_MAP_CSV = _DIR / "basis_map.csv"
NONFOOD_BASIS_MAP_CSV = _DIR / "basis_map_nonfood.csv"
BASIS_OVERRIDES_CSV = _DIR / "basis_overrides.csv"
OFFICIAL_SOURCES_CSV = _DIR / "official_sources.csv"
COICOP_OVERRIDES_CSV = _DIR / "coicop_overrides.csv"

CELL = ["coicop_code", "country", "standard_unit"]
K = 5.0
MIN_IMPUTE_ROWS = 30
MIN_IMPUTE_SOURCES = 2
MODE_SHARE = 0.6
# Candidate sizes tried per leaf by `imputed_fit`, most frequent first. The
# spec says "each candidate"; the long tail of one-off sizes is cut for cost.
MAX_FIT_CANDIDATES = 25

_MEASURED = frozenset({"mass", "volume", "length"})
_UNIT_BASIS = {"kg": "mass", "lt": "volume", "m": "length", "unit": "count"}


def allowed_bases(country: str) -> dict[str, frozenset[str]]:
    """`{leaf: allowed bases}`, the global map with this country's overrides."""
    def parse(frame):
        return {r.code: frozenset(str(r.allowed).split("|")) for r in frame.itertuples()}

    out = parse(pd.read_csv(BASIS_MAP_CSV, dtype=str))
    out.update(parse(pd.read_csv(NONFOOD_BASIS_MAP_CSV, dtype=str)))
    over = pd.read_csv(BASIS_OVERRIDES_CSV, dtype=str)
    out.update(parse(over[over["country"] == country]))
    return out


def nonfood_leaves() -> frozenset[str]:
    """Non-food goods leaves Stage B prices (services are not in the map)."""
    return frozenset(pd.read_csv(NONFOOD_BASIS_MAP_CSV, dtype=str)["code"])


def piece_leaves(country: str) -> frozenset[str]:
    """Non-food leaves read with the piece grammar: allowed bases only item/count."""
    allowed = allowed_bases(country)
    return frozenset(c for c in nonfood_leaves() if allowed[c] <= {"item", "count"})


def official_sources() -> frozenset[str]:
    """Sources judged against their own series instead of the online band."""
    return frozenset(pd.read_csv(OFFICIAL_SOURCES_CSV, dtype=str)["source"])


def coicop_overrides() -> dict[tuple[str, str], str]:
    """`{(source, product name): leaf}`, applied after classification."""
    over = pd.read_csv(COICOP_OVERRIDES_CSV, dtype=str)
    return {(r.source, r.product_name): r.coicop_code for r in over.itertuples()}


def size_of(basis, amount, count, multiplier) -> tuple[str | None, float]:
    """(standard_unit, quantity) a row's unit value divides by.

    Mirrors `compute_unit_value`: a measured basis divides by amount x
    multiplier (count is inert), a count basis by count x multiplier, and a
    double-encoded multipack (count == multiplier > 1) collapses to one.
    """
    c = 1.0 if pd.isna(count) else float(count)
    m = 1.0 if pd.isna(multiplier) else float(multiplier)
    if c == m and c > 1:
        m = 1.0
    if basis in _MEASURED:
        return None, (np.nan if pd.isna(amount) else float(amount) * m)
    if basis == "count":
        return "unit", c * m
    return None, np.nan


def band(rows: pd.DataFrame, baseline: pd.Series) -> pd.Series:
    """The final baseline after William's rule is applied once and rebuilt.

    Pass 1 scores every row against a band built from `baseline`; pass-1
    outliers leave the baseline. Thin rows stay: they were never judged.
    """
    first = flag_uv_outliers(
        rows, group_cols=tuple(CELL), baseline_mask=baseline, k=K
    )
    return baseline & ~first["uv_outlier"].astype(bool)


# Human-owned: a shop's sizeless price within this factor of its own per-kg
# price is read as a per-kg price (the "/kg" left off), not as a pack.
PER_KG_BOUNDS = (0.7, 1.4)


def per_kg_rows(extracted: pd.DataFrame, sizeless: pd.DataFrame) -> pd.DataFrame:
    """Sizeless rows whose shop sells the same leaf per kg at about that price.

    Per (country, leaf, source) with >= 3 rows on each side: when the median
    sizeless price is within PER_KG_BOUNDS of the same source's median per-kg
    unit value, the rows are per-kg prices and get 1 kg (`size_source`
    `per_kg`). Imputing a pack size instead would scale their unit value by
    the pack, e.g. a per-kg chicken at the country's 0.5 kg mode doubles.

    A false match is bounded by construction: a pack of true size s costs
    about s x the per-kg price, so a ratio inside PER_KG_BOUNDS means s is
    too, and 1 kg is off by at most that factor (a 0.8 kg formula tin reads
    25% cheap). No guard on "sells loose" separates the cases on Vietnam.
    """
    key = ["country", "coicop_code", "source"]
    kg = extracted[extracted["pricing_basis"].eq("mass")]
    own = kg.groupby(key)["unit_value_local"].agg(["size", "median"])
    free = sizeless.groupby(key)["price_local"].agg(["size", "median"])
    both = free.join(own, lsuffix="_free", rsuffix="_kg", how="inner")
    both = both[(both["size_free"] >= 3) & (both["size_kg"] >= 3)]
    ratio = both["median_free"] / both["median_kg"]
    hit = set(both.index[ratio.between(*PER_KG_BOUNDS)])
    rows = sizeless[[k in hit for k in zip(*(sizeless[c] for c in key))]]
    return rows.assign(
        pricing_basis="mass", standard_unit="kg", amount_value=1.0, count=1.0,
        multiplier=1.0, size_qty=1.0, size_source="per_kg",
        unit_value_local=rows["price_local"].astype(float),
    )


def impute_candidates(extracted: pd.DataFrame, sizeless: pd.DataFrame) -> pd.DataFrame:
    """Sizeless rows copied once per candidate size, with a unit value each.

    Per (country, leaf) with >= 30 extracted rows from >= 2 sources. One size
    at >= 60% of the rows in its unit is `imputed_mode` and the only candidate; otherwise
    every frequent size is an `imputed_fit` candidate and `choose_fit` picks.
    A row with `_pieces` > 1 (a piece count, no size) gets the size per piece,
    times its pieces.
    """
    if extracted.empty or sizeless.empty:
        return sizeless.iloc[0:0]
    ex = extracted.dropna(subset=["size_qty"])
    ex = ex[ex["size_qty"] > 0]
    ex = ex.assign(size_qty=ex["size_qty"].round(6))
    out = []
    for (country, leaf), grp in sizeless.groupby(["country", "coicop_code"], sort=False):
        pool = ex[(ex["country"] == country) & (ex["coicop_code"] == leaf)]
        if len(pool) < MIN_IMPUTE_ROWS or pool["source"].nunique() < MIN_IMPUTE_SOURCES:
            continue
        sizes = pool.groupby(["standard_unit", "size_qty"]).size().sort_values(ascending=False)
        # The mode's share among rows in its own unit: per-piece rows of a leaf
        # sold both ways say nothing about which kg size is typical.
        share = sizes.iloc[0] / pool["standard_unit"].eq(sizes.index[0][0]).sum()
        kind = "imputed_mode" if share >= MODE_SHARE else "imputed_fit"
        chosen = sizes.head(1 if kind == "imputed_mode" else MAX_FIT_CANDIDATES)
        pieces = grp["_pieces"].fillna(1.0) if "_pieces" in grp else 1.0
        for rank, ((unit, qty), n) in enumerate(chosen.items()):
            basis = _UNIT_BASIS[unit]
            cand = grp.assign(
                pricing_basis=basis,
                standard_unit=unit,
                amount_value=np.nan if basis == "count" else qty,
                count=qty * pieces if basis == "count" else 1.0,
                multiplier=1.0 if basis == "count" else pieces,
                size_qty=qty * pieces,
                size_source=kind,
                _cand=rank,
                _cand_share=n / len(pool),
            )
            out.append(cand)
    if not out:
        return sizeless.iloc[0:0]
    cand = pd.concat(out, ignore_index=True)
    cand["unit_value_local"] = cand["price_local"] / cand["size_qty"]
    return cand


def choose_fit(scored: pd.DataFrame) -> pd.DataFrame:
    """Keep one candidate size per product: the one putting most of its months
    in band. A size is a property of the product, so every month of it takes
    the same one.

    Ties go to the more frequent size (lower `_cand`). `imputed_mode` rows have
    a single candidate and pass through unchanged.
    """
    if scored.empty:
        return scored
    inside = scored["uv_robust_z"].abs().le(K)
    wins = (
        scored.assign(_in=inside)
        .groupby(["input_hash", "_cand"], sort=False)["_in"].sum()
        .reset_index()
        .sort_values(["input_hash", "_in", "_cand"], ascending=[True, False, True])
        .drop_duplicates(["input_hash"])
    )
    keep = scored.merge(wins[["input_hash", "_cand"]], on=["input_hash", "_cand"])
    return keep.drop(columns=["_cand"])


def cell_sources(rows: pd.DataFrame, baseline: pd.Series, window: int = UV_SUPPORT_WINDOW) -> pd.Series:
    """Distinct baseline sources in each row's cell, over the same month window
    that lends the band its support."""
    period = pd.to_datetime(rows["observation_date"], errors="coerce").dt.to_period("M")
    ords = pd.Series(pd.PeriodIndex(period).asi8, index=rows.index).where(period.notna())
    base = rows.loc[baseline, CELL + ["source"]].assign(_ord=ords[baseline])
    lent = pd.concat([base.assign(_ord=base["_ord"] + d) for d in range(-window, window + 1)])
    n = lent.groupby(CELL + ["_ord"], dropna=False)["source"].nunique().rename("_srcs")
    keyed = rows[CELL].assign(_ord=ords)
    return keyed.join(n, on=CELL + ["_ord"])["_srcs"].fillna(0).astype(int)


def qa_level(z: pd.Series, sources: pd.Series) -> pd.Series:
    """A: |z| <= 1.5 and >= 2 sources; B: <= 3; C: <= 5; out: > 5.

    `unscored` when the band could not judge the row (thin cell or zero spread):
    William's rule says nothing about it, so it is not a level.
    """
    a = z.abs()
    return pd.Series(
        np.select(
            [a.isna(), (a <= 1.5) & (sources >= 2), a <= 3.0, a <= K],
            ["unscored", "A", "B", "C"],
            default="out",
        ),
        index=z.index,
    )
