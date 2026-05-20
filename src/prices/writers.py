"""Writers for fetcher-emitted PriceObservation / IndexObservation rows.

Fetchers return DataFrames with ``observation_hash`` already populated; the
writer's job is just load-existing → drop dup hashes → append → save.
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

import pandas as pd

from core.storage import load_csv, save_csv

logger = logging.getLogger(__name__)

PRICE_COLUMNS = [
    "observation_date",
    "period_kind",
    "country",
    "source_key",
    "coicop_code",
    "item_name",
    "price_local",
    "currency",
    "unit",
    "source_url",
    "notes",
    "scrape_ts",
    "observation_hash",
]

INDEX_COLUMNS = [
    "observation_date",
    "period_kind",
    "country",
    "source_key",
    "coicop_code",
    "index_value",
    "index_base_period",
    "source_url",
    "notes",
    "scrape_ts",
    "observation_hash",
]


def is_index_source(analytical_role: str | None) -> bool:
    return analytical_role == "cpi_benchmark"


def output_path_for(
    *,
    data_root: Path,
    region: str,
    subregion: str,
    country: str,
    source: str,
    analytical_role: str | None,
) -> Path:
    filename = (
        "index_observations.csv"
        if is_index_source(analytical_role)
        else "price_observations.csv"
    )
    return data_root / "prices" / region / subregion / country / source / filename


def columns_for(analytical_role: str | None) -> list[str]:
    return INDEX_COLUMNS if is_index_source(analytical_role) else PRICE_COLUMNS


def cutoff_from_csv(out_path: Path, fallback: date) -> date:
    if not out_path.exists():
        return fallback
    df = load_csv(out_path)
    if df.empty or "observation_date" not in df.columns:
        return fallback
    max_val = df["observation_date"].dropna().max()
    if max_val is None or (isinstance(max_val, float) and pd.isna(max_val)):
        return fallback
    try:
        return date.fromisoformat(str(max_val))
    except (ValueError, TypeError):
        return fallback


def append_observations(
    df_new: pd.DataFrame,
    out_path: Path,
    columns: list[str],
) -> int:
    """Merge df_new into out_path on observation_hash. Returns rows appended."""
    if df_new is None or df_new.empty:
        return 0
    if "observation_hash" not in df_new.columns:
        raise ValueError(f"df_new missing observation_hash column (path={out_path})")

    existing = load_csv(out_path, columns=columns)
    existing_hashes = (
        set(existing["observation_hash"].dropna()) if not existing.empty else set()
    )
    df_unique = df_new[~df_new["observation_hash"].isin(existing_hashes)].copy()
    dupes = len(df_new) - len(df_unique)
    if df_unique.empty:
        logger.info(
            "All %d fetched rows are duplicates (%s)", len(df_new), out_path.name
        )
        return 0
    logger.info(
        "Appending %d new rows (%d duplicates dropped) → %s",
        len(df_unique),
        dupes,
        out_path,
    )
    frames = [df for df in (existing, df_unique) if not df.empty]
    combined = pd.concat(frames, ignore_index=True)
    sort_cols = (
        ["country", "source_key", "coicop_code", "observation_date"]
        if "index_value" in combined.columns
        else ["country", "source_key", "observation_date", "item_name"]
    )
    sort_cols = [c for c in sort_cols if c in combined.columns]
    if sort_cols:
        combined = combined.sort_values(sort_cols).reset_index(drop=True)
    save_csv(combined, out_path, columns=columns)
    return len(df_unique)
