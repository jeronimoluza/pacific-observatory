"""Build the traceable price time series from the GREEN artifact.

Each GREEN row is one deduped product keyed by ``input_hash``. This module joins
those keys back to ``raw_prices.csv`` — the ~20M-row DATED per-observation source
that ``prepare.py`` dedups into products_input — to recover every dated scrape of
each GREEN product, reapplies the product's stable tier-a unit-value transform to
each dated price, and attaches date-accurate FX -> USD. It emits a long parquet
(one row per ``input_hash`` x ``date``) with full provenance (product_url /
source / region), plus a small latest-snapshot CSV for dashboards.

``input_hash`` is recomputed row-wise on raw_prices.csv with the same
``prepare._row_input_dict`` + ``versioning.input_hash`` used to build
products_input, so the GREEN keys align — PROVIDED products_input.parquet is
current (rebuild via ``prices process --stage prepare`` if its hashes are stale).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from core.config import load_regions
from prices.build.fx import attach_fx_and_usd
from prices.enrich.config import RAW_PRICES_CSV, REPO_ROOT
from prices.enrich.stages.merge import compute_unit_value
from prices.enrich.stages.prepare import _clean_url, _row_input_dict, parse_price
from prices.enrich.versioning import input_hash as _input_hash

OUTPUTS_DIR = REPO_ROOT / "outputs" / "prices"
TIMESERIES_PARQUET = OUTPUTS_DIR / "eap_prices.parquet"
SNAPSHOT_CSV = OUTPUTS_DIR / "eap_prices_latest.csv"

# GREEN columns that describe the product (stable per input_hash) and travel onto
# every dated observation of it.
_GREEN_CARRY = [
    "input_hash",
    "amount_value",
    "count",
    "multiplier",
    "pricing_basis",
    "coicop_deep_leaf_code",
    "base_item",
    "form",
    "variety",
    "qa_value",
]
# raw_prices.csv columns read from disk (keep the read narrow — ~20M rows).
# raw carries product_name (not product_name_original) + a native region column.
_RAW_COLS = [
    "product_name",
    "product_url",
    "source",
    "country",
    "currency",
    "price",
    "date",
    "region",
]
# Identity columns for input_hash recompute (mirrors prepare._row_input_dict:
# url when present, else the (name, country, currency) fallback).
_IDENT_COLS = ["product_name_original", "product_url", "country", "currency"]
# Per-(input_hash, date) provenance kept from the first matching observation
# (product_url is inside the hash, so it is constant per input_hash).
_FIRST_COLS = [
    "product_name_original",
    "product_url",
    "source",
    "country",
    "region",
    "pricing_basis",
    "coicop_deep_leaf_code",
    "base_item",
    "form",
    "variety",
    "qa_value",
]
_OUT_COLS = [
    "input_hash",
    "date",
    "product_name_original",
    "country",
    "region",
    "source",
    "product_url",
    "currency",
    "price",
    "pricing_basis",
    "unit_value_local",
    "unit_value_usd",
    "coicop_deep_leaf_code",
    "base_item",
    "form",
    "variety",
    "qa_value",
]


def _country_region_map() -> dict[str, str]:
    m: dict[str, str] = {}
    for region, rdata in load_regions().items():
        for _sub, sub_data in (rdata or {}).get("subregions", {}).items():
            for c in (sub_data or {}).get("countries", []):
                m[c] = region
    return m


def build_timeseries(
    green: pd.DataFrame, raw: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (long_df, snapshot_df).

    green: GREEN artifact rows (needs input_hash + the tier-a denom columns +
      coicop/base_item/form/variety + product_name_original).
    raw: dated per-observation rows (raw_prices.csv grain), with at least
      product_name, product_url, currency, price, date, source, country
      (region optional — derived from country when absent).
    """
    if "qa_value" not in green.columns:
        green = green.assign(qa_value=2)
    carry = green[[c for c in _GREEN_CARRY if c in green.columns]].drop_duplicates(
        subset=["input_hash"], keep="first"
    )
    green_hashes = set(carry["input_hash"].dropna().astype(str))
    green_names = set(green["product_name_original"].dropna().astype(str))
    if not green_hashes:
        return pd.DataFrame(columns=_OUT_COLS), pd.DataFrame(columns=_OUT_COLS)

    pc = raw.copy()
    if "product_name_original" not in pc.columns:
        pc["product_name_original"] = pc["product_name"]
    if "product_url" not in pc.columns:
        pc["product_url"] = ""
    pc["product_url"] = pc["product_url"].map(_clean_url)
    # Prefilter by name (cheap) before recomputing hashes on the survivors.
    pc = pc[pc["product_name_original"].astype(str).isin(green_names)].copy()
    if pc.empty:
        return pd.DataFrame(columns=_OUT_COLS), pd.DataFrame(columns=_OUT_COLS)
    # Hash once per UNIQUE identity (~one per GREEN product), not per dated row —
    # the matched slice has many dates per product, so per-row hashing is the
    # bottleneck. Map the hash back onto every observation.
    ident = [c for c in _IDENT_COLS if c in pc.columns]
    uniq = pc[ident].drop_duplicates().copy()
    uniq["input_hash"] = [_input_hash(_row_input_dict(r)) for _i, r in uniq.iterrows()]
    pc = pc.merge(uniq, on=ident, how="left")
    pc = pc[pc["input_hash"].isin(green_hashes)]
    if pc.empty:
        return pd.DataFrame(columns=_OUT_COLS), pd.DataFrame(columns=_OUT_COLS)

    pc = pc.merge(carry, on="input_hash", how="left")
    # raw_prices.csv holds unparsed string prices (e.g. '$1.22'); parse them the
    # same way prepare does before reapplying the unit-value transform.
    pc["price"] = [parse_price(p, c) for p, c in zip(pc["price"], pc["currency"])]
    # raw dates come in mixed formats (ISO offset + RFC-2822); normalize to a
    # clean UTC calendar date so (input_hash, date) grouping is exact.
    # raw_prices.csv dates are HETEROGENEOUS per row (ISO-offset, RFC-2822, plain
    # date, wayback stamps). format="mixed" parses each value independently — the
    # default single-format inference from row 0 coerces ~80% of the corpus to NaT.
    pc["date"] = pd.to_datetime(
        pc["date"], errors="coerce", utc=True, format="mixed"
    ).dt.strftime("%Y-%m-%d")
    # A time series needs a date: drop observations whose raw date is unparseable
    # (strftime leaves them NaN). A product with only undated observations then
    # vanishes from the series — it cannot be placed on a timeline or FX-dated.
    pc = pc[pc["date"].notna()]
    if pc.empty:
        return pd.DataFrame(columns=_OUT_COLS), pd.DataFrame(columns=_OUT_COLS)
    derived = pc["country"].map(_country_region_map())
    if "region" in pc.columns:
        pc["region"] = pc["region"].where(pc["region"].astype(str).ne(""), derived)
        pc["region"] = pc["region"].fillna(derived)
    else:
        pc["region"] = derived
    pc["unit_value_local"] = [
        compute_unit_value(
            r.price, r.pricing_basis, r.amount_value, r.count, r.multiplier
        )
        for r in pc.itertuples()
    ]

    # Collapse to one row per (input_hash, date): median price/unit_value, first
    # provenance. product_url/source/region are constant per input_hash.
    grp = pc.groupby(["input_hash", "date"], dropna=False)
    agg = grp.agg(
        currency=("currency", "first"),
        price=("price", "median"),
        unit_value_local=("unit_value_local", "median"),
        **{c: (c, "first") for c in _FIRST_COLS},
    ).reset_index()

    fx_in = agg.rename(columns={"unit_value_local": "price_local", "date": "obs"})[
        ["price_local", "currency", "obs"]
    ].rename(columns={"obs": "observation_date"})
    fx_out = attach_fx_and_usd(fx_in)
    agg["unit_value_usd"] = fx_out["price_usd"].to_numpy()

    long_df = agg[_OUT_COLS].sort_values(["input_hash", "date"]).reset_index(drop=True)
    snapshot = _latest_snapshot(long_df)
    return long_df, snapshot


def _latest_snapshot(long_df: pd.DataFrame) -> pd.DataFrame:
    dated = long_df[long_df["date"].notna()] if not long_df.empty else long_df
    if dated.empty:
        return long_df.iloc[0:0].copy()
    idx = dated.groupby("input_hash")["date"].idxmax()
    return dated.loc[idx].sort_values("input_hash").reset_index(drop=True)


def _dedup_owner(green: pd.DataFrame) -> pd.DataFrame:
    """Backstop arbiter: one physical product (input_hash) must not be double
    counted into two base_items' GREEN sets. Part A routes the non-owner run to
    OTHER_FORM, so cross-item duplicates are rare; where one slips through (contam
    vs earn divergence), keep the head-owner via 'rightmost alias END wins, ties
    broken by longer alias'. The head noun sits rightmost in English ("Chicken
    RICE" -> rice), while a specific compound and its constituent end at the same
    position ("olive oil" and "oil" both end at ...oil) so the longer compound
    wins ("olive oil" beats "oil"). Deterministic: no parse, stable on ties
    (keeps the first-seen row)."""
    from . import store

    if "input_hash" not in green.columns or green["input_hash"].isna().all():
        return green
    dup_hashes = green["input_hash"].value_counts()
    dup_hashes = set(dup_hashes[dup_hashes > 1].index)
    if not dup_hashes:
        return green
    owner_idx = store.head_alias_index()

    def _score(row) -> tuple[int, int]:
        aliases = [a for a, b in owner_idx.items() if b == str(row["base_item"])]
        name = str(row["product_name_original"]).lower()
        best = (-1, -1)  # (rightmost match end, alias length)
        for a in aliases:
            i = name.rfind(a)
            if i >= 0:
                best = max(best, (i + len(a), len(a)))
        return best

    keep_idx = set(green.index[~green["input_hash"].isin(dup_hashes)])
    for h, grp in green[green["input_hash"].isin(dup_hashes)].groupby("input_hash"):
        if grp["base_item"].nunique() <= 1:
            keep_idx.update(grp.index)
            continue
        scores = grp.apply(_score, axis=1)
        keep_idx.add(max(scores.index, key=lambda ix: scores.loc[ix]))
    return green.loc[sorted(keep_idx)].reset_index(drop=True)


def _load_item_green(item_dir: Path, min_qa: int) -> pd.DataFrame | None:
    latest = item_dir / "latest"
    if min_qa >= 2:
        g = latest / "green.csv"
        if not g.exists():
            return None
        df = pd.read_csv(g)
        if "qa_value" not in df.columns:
            df["qa_value"] = 2
        return df
    # min_qa < 2: pool ALL candidate rows (qa1 is assigned globally afterwards, so
    # the qa0 rows must stay in the pool to be eligible for rescue — do NOT filter
    # per item here). green.csv is a strict subset of candidates.csv.
    c = latest / "candidates.csv"
    if not c.exists():
        return None
    df = pd.read_csv(c)
    if "qa_value" not in df.columns:
        # legacy run predating the ladder: derive per-item qa2 from GREEN, rest qa0
        # (qa0 may be lifted to qa1 by the cross-item leaf pass).
        if "promotion_status" in df.columns:
            df["qa_value"] = (df["promotion_status"] == "green").astype(int) * 2
        else:
            df["qa_value"] = 0
    return df


def load_accumulated_green(min_qa: int = 2) -> pd.DataFrame:
    """Concatenate the accumulated classified rows across all base_items at or above
    the requested quality tier. min_qa=2 (default) = green.csv only (today's series);
    min_qa=1 also admits leaf-grain-rescued rows from candidates.csv."""
    from .validate import VALIDATION_RUNS_DIR

    frames = []
    if VALIDATION_RUNS_DIR.exists():
        for item_dir in sorted(VALIDATION_RUNS_DIR.iterdir()):
            df = _load_item_green(item_dir, min_qa)
            if df is not None and not df.empty:
                frames.append(df)
    if not frames:
        return pd.DataFrame(columns=["input_hash", "product_name_original"])
    pooled = pd.concat(frames, ignore_index=True)
    if min_qa < 2:
        # qa1 is a cross-item leaf-grain decision — assign it on the global pool,
        # then keep rows at or above the requested tier.
        from .promote import assign_leaf_qa

        pooled = assign_leaf_qa(pooled)
        pooled = pooled[pooled["qa_value"] >= min_qa]
    return _dedup_owner(pooled)


def run(
    green_path: Path | str | None = None,
    raw_path: Path = RAW_PRICES_CSV,
    min_qa: int = 2,
) -> dict:
    """IO wrapper: read the accumulated GREEN (all {item}/latest greens at or above
    min_qa, or a single green.csv when green_path is given) + raw_prices.csv, build
    the time series, and write the long parquet + latest-snapshot CSV."""
    from .audit import write_audit

    green = pd.read_csv(green_path) if green_path else load_accumulated_green(min_qa)
    raw = pd.read_csv(raw_path, usecols=_RAW_COLS, low_memory=False)
    long_df, snapshot = build_timeseries(green, raw)
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    long_df.to_parquet(TIMESERIES_PARQUET, index=False)
    snapshot.to_csv(SNAPSHOT_CSV, index=False)
    audit = write_audit()
    return {
        "green_products": int(green["input_hash"].nunique())
        if "input_hash" in green.columns
        else 0,
        "matched_products": int(long_df["input_hash"].nunique()),
        "observations": int(len(long_df)),
        "parquet": str(TIMESERIES_PARQUET),
        "snapshot": str(SNAPSHOT_CSV),
        **audit,
    }
