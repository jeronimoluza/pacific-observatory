"""Aggregate enriched price observations into the EAP F&B basket parquets.

Two outputs, two sources:

  1. SNAPSHOT (current-state tab):
     - read data/prices/_enrich/products_input.parquet (270k dedup'd rows)
     - inner-join cache on (product_name_original, country, currency)
     - 100% coverage of the 2,246 cache rows across 16 EAP countries
     - no date; FX dated to today
     → data/prices/_build/eap_fnb_snapshot.parquet

  2. OBSERVATIONS (historical tab):
     - stream outputs/prices/raw/raw_prices.csv
     - inner-join cache on (product_name_original, country, currency)
       where the CSV's `product_name` → cache's `product_name_original`
     - has `date` (rename to observation_date) → monthly history
     → data/prices/_build/eap_fnb_observations.parquet

Both paths:
  - filter cache → current taxonomy × EAP × COICOP 01/02 × resolved
  - compute_unit_value via merge.compute_unit_value (multipack C-fix wired)
  - canonicalize standard_unit per sub_label (modal; drop minority)
  - attach FX (USD-base) → price_usd, unit_value_usd

The join key is the (name, country, currency) triple rather than input_hash.
We measured 102/2246 (4.5%) hit rate via input_hash but 2246/2246 (100%) via
direct triple-key join — the input_hash basis stored in products_input.parquet
diverges in ways we couldn't fully reproduce, and the direct join is simpler.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterator

import pandas as pd

from prices.build.basket import EAP_COUNTRIES, FNB_COICOP_PREFIXES
from prices.build.fx import attach_fx_and_usd
from prices.enrich.tier_b import cache as enrich_cache
from prices.enrich import config as enrich_config
from prices.enrich.stages.merge import compute_unit_value
from prices.enrich.stages.prepare import parse_price
from prices.enrich.versioning import TAXONOMY_VERSION

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[3]
BUILD_DIR = REPO_ROOT / "data" / "prices" / "_build"
OBSERVATIONS_PARQUET = BUILD_DIR / "eap_fnb_observations.parquet"
SNAPSHOT_PARQUET = BUILD_DIR / "eap_fnb_snapshot.parquet"
PRODUCTS_INPUT_PARQUET = REPO_ROOT / "data" / "prices" / "_enrich" / "products_input.parquet"
CSV_CHUNK_SIZE = 50_000
FX_HISTORY_FLOOR = pd.Timestamp("2024-03-06")

JOIN_KEYS = ["product_name_original", "country", "currency"]

CACHE_KEEP_COLS = [
    "product_name_original", "country", "currency",
    "pricing_basis", "amount_value", "standard_unit",
    "count", "multiplier", "coicop_code", "sub_label_id",
    "is_promotion", "is_bundle", "is_multipack", "confidence",
    "trust_level",
]


def load_filtered_cache() -> pd.DataFrame:
    """Cache rows matching current taxonomy × EAP × F&B × resolved."""
    cache = enrich_cache.read_cache()
    if cache.empty:
        return cache
    cache = cache[cache["taxonomy_version"] == TAXONOMY_VERSION]
    cache = cache[cache["country"].isin(EAP_COUNTRIES)]
    cache = cache[cache["coicop_code"].astype(str).str.startswith(FNB_COICOP_PREFIXES)]
    cache = cache[cache["state"] == "resolved"].copy()
    cache = cache.sort_values("created_at").drop_duplicates(
        subset=JOIN_KEYS, keep="last"
    )
    if "trust_level" not in cache.columns:
        cache["trust_level"] = "high"
    else:
        cache["trust_level"] = cache["trust_level"].fillna("high")
    return cache[CACHE_KEEP_COLS]


def _iter_raw_chunks(csv_path: Path) -> Iterator[pd.DataFrame]:
    return pd.read_csv(
        csv_path,
        usecols=[
            "product_name", "price", "currency",
            "country", "source", "date",
        ],
        chunksize=CSV_CHUNK_SIZE,
        low_memory=False,
    )


def _join_chunk(chunk: pd.DataFrame, cache: pd.DataFrame) -> pd.DataFrame:
    """Inner-join a raw-CSV chunk to cache on (name, country, currency)."""
    chunk = chunk[chunk["country"].isin(EAP_COUNTRIES)].copy()
    if chunk.empty:
        return chunk
    # The cache's product_name_original column holds the value that prepare
    # put under that key — which itself came from raw row["product_name"].
    # So join the raw CSV's `product_name` to cache's `product_name_original`.
    chunk["product_name_original_join"] = chunk["product_name"].astype(str)
    merged = chunk.merge(
        cache,
        left_on=["product_name_original_join", "country", "currency"],
        right_on=JOIN_KEYS,
        how="inner",
        suffixes=("_raw", ""),
    )
    return merged.drop(columns=["product_name_original_join"])


def _canonicalize_units(df: pd.DataFrame) -> pd.DataFrame:
    """Per sub_label_id, drop rows whose standard_unit is not the modal unit.

    Cross-country medians are meaningless when half a sub_label is in lt
    and the other half in kg, so we collapse to the dominant unit. The
    minority rows are flagged for follow-up enrichment, not silently kept.
    """
    if df.empty:
        return df
    canonical = (
        df.dropna(subset=["sub_label_id", "standard_unit"])
        .groupby("sub_label_id")["standard_unit"]
        .agg(lambda s: s.value_counts().idxmax())
        .to_dict()
    )
    df = df.copy()
    df["canonical_unit"] = df["sub_label_id"].map(canonical)
    kept = df[df["standard_unit"] == df["canonical_unit"]]
    dropped = len(df) - len(kept)
    if dropped:
        logger.info(
            "Canonical-unit filter dropped %d / %d rows (off-modal standard_unit)",
            dropped, len(df),
        )
    return kept.drop(columns=["canonical_unit"])


def _compute_unit_values(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["price_local"] = df.apply(
        lambda r: parse_price(r["price"], r["currency"]), axis=1
    )
    df = df.drop(columns=["price"])
    df["unit_value_local"] = df.apply(
        lambda r: compute_unit_value(
            r["price_local"],
            r["pricing_basis"],
            r.get("amount_value"),
            r.get("count"),
            r.get("multiplier"),
        ),
        axis=1,
    )
    return df


def _finalize(df: pd.DataFrame) -> pd.DataFrame:
    """Shared tail: canonicalize unit, compute unit_value, attach FX → USD."""
    df = _canonicalize_units(df)
    df = _compute_unit_values(df)
    df = df[df["price_local"].notna()].copy()
    df = attach_fx_and_usd(df)
    df["unit_value_usd"] = df.apply(
        lambda r: (r["unit_value_local"] / r["fx_rate"])
        if pd.notna(r["unit_value_local"]) and pd.notna(r["fx_rate"])
        else None,
        axis=1,
    )
    return df


def build_snapshot() -> pd.DataFrame:
    """Build the current-state snapshot from products_input.parquet.

    products_input is a dedup'd (name, country, currency) → median-price table
    derived from prepare — no observation date. We tag every row with today
    so FX resolution lands at the most recent rate.
    """
    cache = load_filtered_cache()
    logger.info("[snapshot] cache rows: %d", len(cache))
    if cache.empty:
        raise RuntimeError("No cache rows match the basket filter.")

    pi = pd.read_parquet(PRODUCTS_INPUT_PARQUET)
    pi = pi[pi["country"].isin(EAP_COUNTRIES)]
    merged = pi.merge(cache, on=JOIN_KEYS, how="inner")
    logger.info(
        "[snapshot] joined rows: %d across %d countries",
        len(merged), merged["country"].nunique(),
    )

    today = pd.Timestamp.now(tz="UTC").tz_localize(None).normalize()
    merged["observation_date"] = today
    merged["source"] = "products_input"

    df = _finalize(merged)
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(SNAPSHOT_PARQUET, index=False)
    logger.info("wrote %s (%d rows, %d countries)",
                SNAPSHOT_PARQUET, len(df), df["country"].nunique())
    return df


def build_observations(csv_path: Path | None = None) -> pd.DataFrame:
    """Build the historical time-series observations from the raw CSV."""
    csv_path = csv_path or enrich_config.RAW_PRICES_CSV
    cache = load_filtered_cache()
    logger.info("[observations] cache rows: %d", len(cache))
    if cache.empty:
        raise RuntimeError("No cache rows match the basket filter.")

    pieces: list[pd.DataFrame] = []
    for i, chunk in enumerate(_iter_raw_chunks(csv_path)):
        joined = _join_chunk(chunk, cache)
        if not joined.empty:
            pieces.append(joined)
        if (i + 1) % 20 == 0:
            logger.info(
                "[observations] scanned %d chunks; joined rows: %d",
                i + 1, sum(len(p) for p in pieces),
            )
    if not pieces:
        raise RuntimeError("Raw CSV produced no joinable rows for the basket.")
    df = pd.concat(pieces, ignore_index=True)
    logger.info(
        "[observations] joined: %d rows × %d countries × %d sub_labels",
        len(df), df["country"].nunique(), df["sub_label_id"].nunique(),
    )

    df = df.rename(columns={"date": "observation_date"})
    df["observation_date"] = pd.to_datetime(
        df["observation_date"], errors="coerce", utc=True, format="ISO8601"
    ).dt.tz_localize(None)
    before = len(df)
    df = df[df["observation_date"] >= FX_HISTORY_FLOOR]
    logger.info(
        "[observations] date floor (%s) kept %d of %d rows",
        FX_HISTORY_FLOOR.date(), len(df), before,
    )
    df = _finalize(df)
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OBSERVATIONS_PARQUET, index=False)
    logger.info("wrote %s (%d rows)", OBSERVATIONS_PARQUET, len(df))
    return df


def build(csv_path: Path | None = None) -> None:
    build_snapshot()
    build_observations(csv_path=csv_path)


def run() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    build()
