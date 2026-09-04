"""Aggregate enriched price observations into the EAP F&B basket parquets.

Two outputs, two sources:

  1. SNAPSHOT (current-state tab):
     - read data/prices/enrich/products_input.parquet (dedup'd, one row per
       input_hash), which already carries `input_hash`
     - inner-join the classifier output (classified.parquet) on `input_hash`
     - no date; FX dated to today
     → data/prices/build/eap_fnb_snapshot.parquet

  2. OBSERVATIONS (historical tab):
     - stream outputs/prices/raw/raw_prices.csv
     - recompute `input_hash` per raw row (same _row_input_dict basis prepare
       used) and inner-join classified.parquet on it
     - has `date` (rename to observation_date) → monthly history
     → data/prices/build/eap_fnb_observations.parquet

Both paths:
  - filter classified.parquet → COICOP 01/02 × live states × trust_level==high
  - compute_unit_value via merge.compute_unit_value (multipack C-fix wired)
  - require a leaf + standard_unit; keep every pricing basis (no modal collapse)
  - flag Layer-2 unit-value outliers per (coicop_code, country, standard_unit)
  - attach FX (USD-base) → price_usd, unit_value_usd
  - compute composable QA gates + categorical qa_status

Design notes (why it is wired this way):
  - The join key is `input_hash`, NOT the (name, country, currency) triple used
    before. The embedding→head classifier writes classified.parquet keyed on the
    exact input_hash it inherited from products_input.parquet (no recompute in
    between), so the two frames' hashes are identical by construction and the
    join is exact. The old triple-key workaround existed only because the retired
    LLM cascade recomputed the hash on a divergent basis; that no longer applies.
  - The unit-value CELL (for the Layer-2 audit and the consumable grain) is
    (coicop_code, country, standard_unit) at the deepest leaf the classifier
    assigns. The retired cascade emitted a finer `sub_label_id`, but the
    embedding→head classifier has no sub-leaf output and leaves that column
    null. coicop_code is the finest granularity the live pipeline populates;
    using the leaf (never rolling up) keeps distinct products (e.g. apples vs
    oranges) in separate cells wherever the taxonomy separates them. Adding
    standard_unit to the cell keeps each pricing basis as its own homogeneous
    series instead of collapsing a leaf to one modal unit — a country priced
    per-count survives alongside a per-kg country. This is a coarsening vs
    sub_label_id: Layer-2 under-covers (withholds trust on more rows) but never
    mis-rejects — consistent with precision-first.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterator, Sequence

import pandas as pd

from prices import partition
from prices.build.analytical import write_analytical
from prices.build.basket import EAP_COUNTRIES, FNB_COICOP_PREFIXES
from prices.build.fx import attach_fx_and_usd
from prices.build.leaf_typical_mass import TYPICAL_MASS_CSV, read_typical_mass
from prices.build.qa import compute_qa
from prices.build.sold_by_item import convert_item_rows
from prices.build.unit_value_audit import flag_uv_outliers
from prices.build.unit_value_summary import (
    build_unit_value_summary,
    trusted_observations,
)
from prices.enrich import config as enrich_config
from prices.enrich import shards as shard_io
from prices.enrich.stages import decisions_store
from prices.enrich.stages.merge import compute_unit_value
from prices.enrich.stages.prepare import _row_input_dict, parse_price
from prices.enrich.versioning import input_hash

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[3]
BUILD_DIR = REPO_ROOT / "data" / "prices" / "build"
OBSERVATIONS_PARQUET = BUILD_DIR / "eap_fnb_observations.parquet"
SNAPSHOT_PARQUET = BUILD_DIR / "eap_fnb_snapshot.parquet"
TRUSTED_OBS_PARQUET = BUILD_DIR / "eap_fnb_trusted_observations.parquet"
UNIT_VALUE_SUMMARY_PARQUET = BUILD_DIR / "eap_fnb_unit_value_summary.parquet"
PRODUCTS_INPUT_PARQUET = (
    REPO_ROOT / "data" / "prices" / "enrich" / "products_input.parquet"
)
CSV_CHUNK_SIZE = 50_000
FX_HISTORY_FLOOR = pd.Timestamp("2024-03-06")

JOIN_KEYS = ["input_hash"]

CACHE_KEEP_COLS = [
    "input_hash",
    "pricing_basis",
    "amount_value",
    "standard_unit",
    "count",
    "multiplier",
    "coicop_code",
    "is_promotion",
    "is_bundle",
    "is_multipack",
    "confidence",
    "trust_level",
]


def load_filtered_cache() -> pd.DataFrame:
    """Live classifier rows matching F&B × classified state × trust_level==high.

    Reads the CLASSIFY STAGE'S OWN OUTPUT, one row per input_hash — which is
    `classified.parquet` for the head backend and `classified_hierlex.parquet`
    for hierlex. `BUILD_CLASSIFIED_PARQUET` is the config that resolves that,
    and reading `CLASSIFIED_PARQUET` directly instead meant a hierlex run built
    from the head's file: absent by default, so the empty frame reached the
    "No cache rows match the basket filter" raise at the end of a full pipeline.

    Country is filtered later at the join sites (from products_input / the raw
    CSV), since the file carries no country. No taxonomy_version filter: it is
    regenerated wholesale each `prices process` run, so there is no
    stale-version drift to guard against.
    """
    # `decisions_store.read` because the table is a directory of per-country
    # parts now, not one file. It accepts either form and prefers the parts, so
    # a checkout that has not been ported still reads its single file.
    path = enrich_config.BUILD_CLASSIFIED_PARQUET
    cache = decisions_store.read(path)
    if cache.empty:
        return pd.DataFrame(columns=CACHE_KEEP_COLS)
    cache = cache[cache["coicop_code"].astype(str).str.startswith(FNB_COICOP_PREFIXES)]
    # Live classify states: narrow_source / classified carry trust_level==high;
    # rejected / flagged_basis are demoted by the basis audit. Keep the two
    # trustworthy-and-classified states, then re-assert trust_level defensively.
    cache = cache[cache["state"].isin(["narrow_source", "classified"])].copy()
    if "trust_level" not in cache.columns:
        cache["trust_level"] = "high"
    else:
        cache["trust_level"] = cache["trust_level"].fillna("high")
    cache = cache[cache["trust_level"] == "high"]
    return cache[CACHE_KEEP_COLS]


# The raw columns observations needs. input_hash is read when present so the
# per-row rehash in _join_chunk is skipped; the monolith predates it, and
# usecols is a callable so a file without the column is not an error.
RAW_OBSERVATION_COLS = (
    "product_name",
    "product_url",
    "price",
    "currency",
    "country",
    "source",
    "date",
    "input_hash",
)


def _iter_raw_chunks(csv_path: Path) -> Iterator[pd.DataFrame]:
    return pd.read_csv(
        csv_path,
        usecols=lambda c: c in RAW_OBSERVATION_COLS,
        chunksize=CSV_CHUNK_SIZE,
        low_memory=False,
    )


def _iter_shard_chunks(
    selectors: Sequence[str] | None = None, root: Path | None = None
) -> Iterator[pd.DataFrame]:
    """Raw rows straight from the parquet shards, one frame per source.

    A shard is already the natural chunk, it carries real dtypes, and only the
    eight columns observations needs are read off disk — where the monolith is
    re-parsed from 33 GB of text in 50k-row slices to get the same rows."""
    for shard in partition.select(selectors, root):
        yield shard_io.read_shard(shard.path, columns=list(RAW_OBSERVATION_COLS))


def _observation_chunks(
    csv_path: Path | None,
    selectors: Sequence[str] | None,
    shard_root: Path | None,
) -> Iterator[pd.DataFrame]:
    """Shards when there are any, the monolith otherwise. A selector forces the
    shards, since the monolith cannot be scoped."""
    root = shard_root or partition.PER_SOURCE_DIR
    has_shards = root.is_dir() and any(partition.iter_shards(root))
    if selectors or has_shards:
        return _iter_shard_chunks(selectors, root)
    return _iter_raw_chunks(csv_path or enrich_config.RAW_PRICES_CSV)


# One cache per worker process, loaded in the initializer. It is ~the same for
# every task, and passing it as an argument would pickle it once per shard.
_WORKER_CACHE: pd.DataFrame | None = None


def _init_worker() -> None:
    global _WORKER_CACHE
    _WORKER_CACHE = load_filtered_cache()


def _join_one_shard(path: str) -> pd.DataFrame:
    chunk = shard_io.read_shard(Path(path), columns=list(RAW_OBSERVATION_COLS))
    return _join_chunk(chunk, _WORKER_CACHE)


def _parallel_join(shards, workers: int, budget_bytes: int) -> list[pd.DataFrame]:
    """Join shards in parallel, admitting work by bytes in flight.

    The scheduler lives in `partition` because prepare needs exactly the same
    rule and learned it the same way. Two copies of a memory-admission rule
    disagree silently: one stage keeps running while the other is OOM-killed,
    and the difference reads as a flaky box rather than as a policy that drifted.
    """
    jobs = [(s.size, str(s.path)) for s in shards]
    got = partition.run_budgeted(
        jobs, _join_one_shard, workers, budget_bytes, initializer=_init_worker
    )
    return [g for g in got if not g.empty]


def _join_chunk(chunk: pd.DataFrame, cache: pd.DataFrame) -> pd.DataFrame:
    """Inner-join a raw-CSV chunk to classified.parquet on input_hash.

    Recompute input_hash per raw row via the SAME _row_input_dict basis prepare
    used (name+url when a URL exists, else name+country+currency). product_url is
    read into the chunk so the URL branch matches prepare exactly — otherwise
    every row would fall to the URL-less fallback and mismatch the snapshot hashes.
    """
    chunk = chunk[chunk["country"].isin(EAP_COUNTRIES)].copy()
    if chunk.empty:
        return chunk
    # Parquet shards carry input_hash, computed once when the shard was written.
    # The CSV monolith does not, so the recompute stays as the fallback.
    if "input_hash" not in chunk.columns or chunk["input_hash"].isna().any():
        chunk["input_hash"] = chunk.apply(
            lambda r: input_hash(_row_input_dict(r)), axis=1
        )
    merged = chunk.merge(cache, on="input_hash", how="inner", suffixes=("_raw", ""))
    return merged.drop(columns=["input_hash"])


def _require_unit(df: pd.DataFrame) -> pd.DataFrame:
    """Drop only rows with no coicop_code or standard_unit; keep every basis.

    The unit-value CELL is (coicop_code, country, standard_unit), so each cell
    is unit-homogeneous by construction and no modal-unit collapse is needed:
    eggs-by-dozen and eggs-by-kg live in two distinct cells and both survive as
    separate trusted series. Rows lacking a leaf or a unit can't be placed in a
    cell (no comparable distribution), so they are dropped here. This replaces
    the earlier global per-coicop modal-unit filter, which deleted a country's
    rows whenever its pricing basis differed from the cross-country mode.
    """
    if df.empty:
        return df
    df = df.copy()
    kept = df.dropna(subset=["coicop_code", "standard_unit"])
    dropped = len(df) - len(kept)
    if dropped:
        logger.info(
            "Unit filter dropped %d / %d rows (null coicop_code/standard_unit)",
            dropped,
            len(df),
        )
    return kept


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


def _finalize(
    df: pd.DataFrame, typical_mass: pd.DataFrame | None = None
) -> pd.DataFrame:
    """Shared tail: require unit, convert item rows, unit_value, Layer-2, FX, QA.

    The typical-mass conversion runs before unit values are computed, so a
    converted row is indistinguishable from a measured one to every stage that
    follows. That is what keeps the change local to this one line.

    `typical_mass` pins that conversion to a previously derived table. It is
    None for a full build, which derives and rewrites it; a scoped build must
    supply it, or a leaf's typical mass would come from the slice.
    """
    df = _require_unit(df)
    df = convert_item_rows(df, table=typical_mass)
    df = _compute_unit_values(df)
    # Only rows that measured their own quantity may define what "normal" is in
    # a cell; a typical-mass conversion is scored against them, never with them.
    df = flag_uv_outliers(
        df,
        group_cols=("coicop_code", "country", "standard_unit"),
        baseline_mask=df.get("mass_source", pd.Series(index=df.index, dtype=object)).ne(
            "derived_typical"
        ),
    )
    df = df[df["price_local"].notna()].copy()
    df = attach_fx_and_usd(df)
    df["unit_value_usd"] = df.apply(
        lambda r: (
            (r["unit_value_local"] / r["fx_rate"])
            if pd.notna(r["unit_value_local"]) and pd.notna(r["fx_rate"])
            else None
        ),
        axis=1,
    )
    df = compute_qa(df)
    return df


def build_snapshot(typical_mass: pd.DataFrame | None = None) -> pd.DataFrame:
    """Build the current-state snapshot from products_input.parquet.

    products_input is a dedup'd (name, country, currency) → median-price table
    derived from prepare — no observation date. We tag every row with today
    so FX resolution lands at the most recent rate.
    """
    cache = load_filtered_cache()
    logger.info("[snapshot] cache rows: %d", len(cache))
    if cache.empty:
        raise RuntimeError("No cache rows match the basket filter.")

    # Filter in the reader, not after it. products_input is the GLOBAL corpus --
    # 37.4M rows over 17 columns, ~27 GB once pandas has it -- and the snapshot
    # wants only EAP. Reading it whole and subsetting a line later is what the
    # kernel killed this stage for, at 27.1 GB anon-rss on a 26 GB box. Predicate
    # pushdown reads the same rows the mask would have kept, so the result is
    # unchanged; only the rows that never mattered stop being materialised.
    pi = pd.read_parquet(
        PRODUCTS_INPUT_PARQUET,
        filters=[("country", "in", sorted(EAP_COUNTRIES))],
    )
    merged = pi.merge(cache, on=JOIN_KEYS, how="inner")
    logger.info(
        "[snapshot] joined rows: %d across %d countries",
        len(merged),
        merged["country"].nunique(),
    )

    today = pd.Timestamp.now(tz="UTC").tz_localize(None).normalize()
    merged["observation_date"] = today
    merged["source"] = "products_input"

    df = _finalize(merged, typical_mass=typical_mass)
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(SNAPSHOT_PARQUET, index=False)
    logger.info(
        "wrote %s (%d rows, %d countries)",
        SNAPSHOT_PARQUET,
        len(df),
        df["country"].nunique(),
    )
    return df


def overlay_observations(fresh: pd.DataFrame, existing_path: Path) -> pd.DataFrame:
    """Put a scoped build's rows back into the full observations frame.

    A slice-only dashboard has no cross-country context, so an outlier stops
    being visible — which is the whole reason for rebuilding. The recomputed
    countries replace their old rows and every other country is carried through
    untouched, so the consumables downstream still see the whole corpus.

    Country is the overlay key because it is the grain the slice was computed
    at: a selector names sources, and every source sits under exactly one
    country, so a recomputed country is recomputed in full."""
    if not existing_path.exists() or fresh.empty:
        return fresh
    existing = pd.read_parquet(existing_path)
    if "country" not in existing.columns:
        return fresh
    recomputed = set(fresh["country"].unique())
    kept = existing[~existing["country"].isin(recomputed)]
    logger.info(
        "[observations] overlay: %d fresh rows over %d countries, "
        "%d rows carried through from %d other countries",
        len(fresh),
        len(recomputed),
        len(kept),
        kept["country"].nunique(),
    )
    return pd.concat([kept, fresh], ignore_index=True)


def build_observations(
    csv_path: Path | None = None,
    typical_mass: pd.DataFrame | None = None,
    selectors: Sequence[str] | None = None,
    shard_root: Path | None = None,
    overlay: bool = False,
    workers: int = 1,
) -> pd.DataFrame:
    """Build the historical time-series observations from the raw rows."""
    cache = load_filtered_cache()
    logger.info("[observations] cache rows: %d", len(cache))
    if cache.empty:
        raise RuntimeError("No cache rows match the basket filter.")

    root = shard_root or partition.PER_SOURCE_DIR
    shards = (
        list(partition.select(selectors, root))
        if root.is_dir() and any(partition.iter_shards(root))
        else []
    )
    if workers > 1 and shards:
        pieces = _parallel_join(shards, workers, partition.memory_budget_bytes())
    else:
        # The monolith has no shard boundaries to fan out over, and one worker
        # has nothing to gain from the pool's pickling.
        pieces = []
        for i, chunk in enumerate(_observation_chunks(csv_path, selectors, shard_root)):
            joined = _join_chunk(chunk, cache)
            if not joined.empty:
                pieces.append(joined)
            if (i + 1) % 20 == 0:
                logger.info(
                    "[observations] scanned %d chunks; joined rows: %d",
                    i + 1,
                    sum(len(p) for p in pieces),
                )
    if not pieces:
        scope = f" for {list(selectors)}" if selectors else ""
        raise RuntimeError(f"raw rows produced nothing joinable for the basket{scope}.")
    df = pd.concat(pieces, ignore_index=True)
    logger.info(
        "[observations] joined: %d rows × %d countries × %d coicop leaves",
        len(df),
        df["country"].nunique(),
        df["coicop_code"].nunique(),
    )

    df = df.rename(columns={"date": "observation_date"})
    # format="mixed" (not "ISO8601"): sources write dates in heterogeneous forms
    # — RFC 2822 HTTP headers ("Sat, 24 Jan 2026 02:31:06 GMT"), compact numeric
    # ("20250623125358"), and ISO. ISO8601 coerced the non-ISO forms to NaT, and
    # NaT >= FX_HISTORY_FLOOR is False, so ~5.7M valid EAP rows (whole leaves:
    # baby cereals, mandarins, flour of rice) were silently dropped by the floor.
    df["observation_date"] = pd.to_datetime(
        df["observation_date"], errors="coerce", utc=True, format="mixed"
    ).dt.tz_localize(None)
    before = len(df)
    df = df[df["observation_date"] >= FX_HISTORY_FLOOR]
    logger.info(
        "[observations] date floor (%s) kept %d of %d rows",
        FX_HISTORY_FLOOR.date(),
        len(df),
        before,
    )
    df = _finalize(df, typical_mass=typical_mass)
    if overlay:
        df = overlay_observations(df, OBSERVATIONS_PARQUET)
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OBSERVATIONS_PARQUET, index=False)
    logger.info("wrote %s (%d rows)", OBSERVATIONS_PARQUET, len(df))
    return df


def _write_consumables(df: pd.DataFrame) -> None:
    """Derive the two curated deliverables from the finalized observations frame.

    Built from observations (real dated history) rather than the snapshot, whose
    date is a synthetic "today". trusted_observations is the row-level ship set;
    unit_value_summary is the monthly (period, leaf, country, unit) rollup.
    """
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    obs = trusted_observations(df)
    obs.to_parquet(TRUSTED_OBS_PARQUET, index=False)
    logger.info("wrote %s (%d trusted rows)", TRUSTED_OBS_PARQUET, len(obs))
    summary = build_unit_value_summary(df)
    summary.to_parquet(UNIT_VALUE_SUMMARY_PARQUET, index=False)
    logger.info("wrote %s (%d cells)", UNIT_VALUE_SUMMARY_PARQUET, len(summary))
    write_analytical(df)


def _pinned_typical_mass(scoped: bool, recompute: bool | None) -> pd.DataFrame | None:
    """Resolve the typical-mass table for this build.

    The default is structural rather than a flag the caller has to remember: a
    full build derives the table, a scoped build pins it. Passing `recompute`
    overrides that in either direction.

    A scoped build with no table on disk raises. Falling back to deriving it
    would be the silent version of exactly the bug the pin exists to prevent."""
    if recompute is None:
        recompute = not scoped
    if recompute:
        return None
    table = read_typical_mass()
    if table is None:
        raise RuntimeError(
            f"scoped build needs a pinned typical-mass table at "
            f"{TYPICAL_MASS_CSV}, and there is not one. Run a full build first, "
            f"or pass recompute_leaf_tables=True to derive it from this slice — "
            f"knowing the slice's leaves will not match the full build's."
        )
    logger.info("[build] pinned typical-mass table: %d leaves", len(table))
    return table


def build(
    csv_path: Path | None = None,
    selectors: Sequence[str] | None = None,
    shard_root: Path | None = None,
    recompute_leaf_tables: bool | None = None,
    workers: int = 1,
) -> None:
    """Build the basket parquets, optionally recomputing only part of the corpus.

    A scoped run recomputes its countries' observations and overlays them onto
    the existing full frame, so the consumables downstream are still derived
    from the whole corpus. That is what makes the loop useful: the dashboard
    that comes out has cross-country context, with the fix applied."""
    scoped = bool(selectors)
    typical_mass = _pinned_typical_mass(scoped, recompute_leaf_tables)
    build_snapshot(typical_mass=typical_mass)
    obs = build_observations(
        csv_path=csv_path,
        typical_mass=typical_mass,
        selectors=selectors,
        shard_root=shard_root,
        overlay=scoped,
        workers=workers,
    )
    _write_consumables(obs)


def run(
    selectors: Sequence[str] | None = None,
    recompute_leaf_tables: bool | None = None,
    workers: int = 1,
) -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    build(
        selectors=selectors,
        recompute_leaf_tables=recompute_leaf_tables,
        workers=workers,
    )
