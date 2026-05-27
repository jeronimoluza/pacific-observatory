from pathlib import Path

import pandas as pd

from prices.enrich import config


def _read_parquet_or_empty(path: Path) -> pd.DataFrame:
    if path.exists():
        return pd.read_parquet(path)
    return pd.DataFrame()


def read_cache() -> pd.DataFrame:
    return _read_parquet_or_empty(config.ENRICHMENTS_PARQUET)


def read_failures() -> pd.DataFrame:
    return _read_parquet_or_empty(config.FAILED_PARQUET)


def existing_keys() -> set[str]:
    df = read_cache()
    if df.empty or "cache_key" not in df.columns:
        return set()
    return set(df["cache_key"].tolist())


def _append(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    new = pd.DataFrame(rows)
    if path.exists():
        existing = pd.read_parquet(path)
        out = pd.concat([existing, new], ignore_index=True)
    else:
        out = new
    out.to_parquet(path, index=False)


def append_enrichments(rows: list[dict]) -> None:
    _append(config.ENRICHMENTS_PARQUET, rows)


def append_failures(rows: list[dict]) -> None:
    _append(config.FAILED_PARQUET, rows)


def enforce_collision_invariant() -> int:
    """Prune rows from _failed.parquet whose cache_key also exists in enrichments.parquet.

    Returns the number of pruned rows.
    """
    enriched = read_cache()
    failed = read_failures()
    if enriched.empty or failed.empty:
        return 0
    keep_mask = ~failed["cache_key"].isin(enriched["cache_key"])
    pruned = int((~keep_mask).sum())
    failed[keep_mask].to_parquet(config.FAILED_PARQUET, index=False)
    return pruned
