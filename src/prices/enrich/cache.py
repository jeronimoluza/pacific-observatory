from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from prices.enrich import config
from prices.enrich.versioning import SCHEMA_VERSION

# Provenance columns stamped onto every cached row. Identity = input_hash;
# the rest are audit / drift-detection metadata, never folded into the key.
PROVENANCE_COLUMNS = [
    "input_hash",
    "prompt_semver",
    "prompt_bytes_hash",
    "schema_version",
    "taxonomy_version",
    "model_version",
    "created_at",
    "match_method",
    "modality",
]


def _partition_path(schema_version: str = SCHEMA_VERSION) -> Path:
    return config.CACHE_DIR / f"enrichments_v{schema_version}.parquet"


def _read_parquet_or_empty(path: Path) -> pd.DataFrame:
    if path.exists():
        return pd.read_parquet(path)
    return pd.DataFrame()


def _all_partition_paths() -> list[Path]:
    if not config.CACHE_DIR.exists():
        return []
    return sorted(
        config.CACHE_DIR.glob("enrichments_v*.parquet"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )


def read_cache() -> pd.DataFrame:
    """Read cached enrichments. Walks newest-first across schema-version
    partitions, falling back to the unpartitioned legacy file when present.
    Returns one concatenated DataFrame; downstream callers may dedup by
    input_hash if multiple partitions claim the same identity."""
    frames: list[pd.DataFrame] = []
    for path in _all_partition_paths():
        frames.append(pd.read_parquet(path))
    legacy = _read_parquet_or_empty(config.ENRICHMENTS_PARQUET)
    if not legacy.empty:
        frames.append(legacy)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def read_failures() -> pd.DataFrame:
    return _read_parquet_or_empty(config.FAILED_PARQUET)


def _key_column(df: pd.DataFrame) -> str | None:
    """Identity lookup column. Prefer input_hash (post-decoupling), fall back
    to cache_key for unmigrated legacy rows."""
    if df.empty:
        return None
    if "input_hash" in df.columns:
        return "input_hash"
    if "cache_key" in df.columns:
        return "cache_key"
    return None


def existing_keys() -> set[str]:
    df = read_cache()
    col = _key_column(df)
    if col is None:
        return set()
    return set(df[col].dropna().tolist())


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
    """Append rows to the partition matching the current SCHEMA_VERSION.
    Caller is responsible for filling provenance columns; this function does
    not synthesize them."""
    _append(_partition_path(), rows)


def append_failures(rows: list[dict]) -> None:
    _append(config.FAILED_PARQUET, rows)


def enforce_collision_invariant() -> int:
    """Prune rows from _failed.parquet whose identity key also exists in
    enrichments. Returns the number of pruned rows."""
    enriched = read_cache()
    failed = read_failures()
    if enriched.empty or failed.empty:
        return 0
    enriched_col = _key_column(enriched)
    failed_col = _key_column(failed)
    if enriched_col is None or failed_col is None:
        return 0
    keep_mask = ~failed[failed_col].isin(enriched[enriched_col])
    pruned = int((~keep_mask).sum())
    failed[keep_mask].to_parquet(config.FAILED_PARQUET, index=False)
    return pruned


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
