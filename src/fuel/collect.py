"""Fuel collect stage: run fetchers, deduplicate, append new observations."""

from __future__ import annotations

import logging
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

from core.hashing import observation_hash
from core.state import read_state, set_checked, set_last_data_date, write_state
from core.storage import load_csv, save_csv

from .fx import build_fx_table
from .paths import canonical_observations_path_for_entry

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DATA_DIR = _PROJECT_ROOT / "data" / "fuel"

COLUMNS = [
    "observation_date",
    "country",
    "fuel_product",
    "price_local",
    "currency",
    "unit",
    "source_key",
    "subnational_area",
    "city",
    "address",
    "scrape_ts",
    "observation_hash",
]

_HASH_FIELDS = [
    "country",
    "source_key",
    "observation_date",
    "fuel_product",
    "subnational_area",
    "city",
    "address",
    "price_local",
]


def _source_csv_path(entry: dict, base_dir: Path = _DATA_DIR) -> Path:
    return canonical_observations_path_for_entry(entry, base_dir=base_dir)


def _cutoff_from_df(df: pd.DataFrame, fallback: date) -> date:
    """Derive cutoff from max observation_date in a loaded DataFrame."""
    if df.empty or "observation_date" not in df.columns:
        return fallback
    max_val = df["observation_date"].dropna().max()
    if max_val is None or (isinstance(max_val, float) and pd.isna(max_val)):
        return fallback
    try:
        return date.fromisoformat(str(max_val))
    except (ValueError, TypeError):
        return fallback


def _merge_new_rows(df_existing: pd.DataFrame, df_new: pd.DataFrame) -> pd.DataFrame:
    if df_new is None or df_new.empty:
        return df_existing
    if "observation_hash" not in df_new.columns:
        df_new = df_new.copy()
        df_new["observation_hash"] = df_new.apply(
            lambda row: observation_hash(row, _HASH_FIELDS), axis=1
        )
    existing_hashes = set(df_existing["observation_hash"].dropna())
    df_unique = df_new[~df_new["observation_hash"].isin(existing_hashes)].copy()
    dupes = len(df_new) - len(df_unique)
    if df_unique.empty:
        logger.info("All %d fetched rows are duplicates", len(df_new))
        return df_existing
    logger.info("Appending %d new rows (%d duplicates dropped)", len(df_unique), dupes)
    for col in df_existing.columns:
        if col not in df_unique.columns:
            df_unique[col] = None
    df_unique = df_unique[df_existing.columns]
    frames = [df for df in (df_existing, df_unique) if not df.empty]
    combined = pd.concat(frames, ignore_index=True)
    return combined.sort_values(
        ["country", "source_key", "observation_date"]
    ).reset_index(drop=True)


# ── Main collection ──────────────────────────────────────────────────────────


def run_collection(
    *,
    registry: dict[str, dict],
    source_key: str | None = None,
    base_dir: Path = _DATA_DIR,
    force: bool = False,
    rebuild: bool = False,
    dry_run: bool = False,
    refresh_fx: bool = False,
) -> None:
    """Fetch new data from one or all configured fuel sources.

    Args:
        registry: source_key → {fn, fallback_date, enabled, country_slug, ...}
        source_key: Run a single source key only.
        base_dir: Base directory for observations.csv files.
        force: Run even if source has enabled=false.
        rebuild: Delete existing observations and re-fetch from fallback_date.
        dry_run: Print plan without writing data.
        refresh_fx: Also refresh FX cache for currencies in the registry.
    """
    if rebuild and not source_key:
        logger.error("--rebuild requires --source KEY")
        sys.exit(1)

    state_path = base_dir / ".state.json"
    state = read_state(state_path)

    keys_to_run = [source_key] if source_key else list(registry)

    if rebuild and source_key:
        entry = registry[source_key]
        out_path = _source_csv_path(entry, base_dir=base_dir)
        if out_path.exists():
            out_path.unlink()
            logger.info("Deleted %s for rebuild", out_path)

    for key in keys_to_run:
        entry = registry[key]
        country_slug = entry["country_slug"]

        if not entry.get("enabled", True) and not force:
            logger.info("Skipping %s (disabled; use --force to run)", key)
            continue

        out_path = _source_csv_path(entry, base_dir=base_dir)
        existing = load_csv(out_path, columns=COLUMNS)
        cutoff = _cutoff_from_df(existing, entry["fallback_date"])

        if dry_run:
            logger.info(
                "[DRY RUN] Would fetch %s (%s) from cutoff %s",
                key,
                entry.get("country_name", country_slug),
                cutoff,
            )
            continue

        logger.info("--- %s (cutoff: %s) ---", key, cutoff)
        run_ts = datetime.now(tz=timezone.utc)

        try:
            new_df = entry["fn"](cutoff)
        except Exception:
            logger.exception("Fetcher %s failed", key)
            set_checked(state, key, run_ts)
            continue

        set_checked(state, key, run_ts)

        if new_df is None or new_df.empty:
            logger.info("No new rows for %s", key)
            continue

        new_df = new_df.copy()
        new_df["scrape_ts"] = run_ts.isoformat()
        new_df["observation_hash"] = new_df.apply(
            lambda row: observation_hash(row, _HASH_FIELDS), axis=1
        )

        if entry.get("full_refresh"):
            existing = pd.DataFrame(columns=existing.columns)

        merged = _merge_new_rows(existing, new_df)
        save_csv(merged, out_path, columns=COLUMNS)

        if "observation_date" in new_df.columns:
            max_date_str = new_df["observation_date"].dropna().max()
            if max_date_str and not pd.isna(max_date_str):
                try:
                    new_max = date.fromisoformat(str(max_date_str))
                    prev = _cutoff_from_df(existing, date(1900, 1, 1))
                    set_last_data_date(state, key, max(new_max, prev))
                except (ValueError, TypeError):
                    pass

    if not dry_run:
        write_state(state, state_path)

    # Refresh FX cache for non-USD currencies in the registry
    if not dry_run and refresh_fx:
        currencies = sorted(
            {
                entry.get("currency", "")
                for entry in registry.values()
                if entry.get("currency") and entry["currency"] != "USD"
            }
        )
        if currencies:
            logger.info("Refreshing FX cache for %d currencies ...", len(currencies))
            try:
                today = pd.Timestamp.now().normalize()
                window_start = today - pd.Timedelta(days=60)
                span = pd.date_range(window_start, today, freq="D")
                dummy = pd.DataFrame(
                    [
                        {"observation_date": d.strftime("%Y-%m-%d"), "currency": c}
                        for c in currencies
                        for d in (span[0], span[-1])
                    ]
                )
                build_fx_table(dummy, cache_path=base_dir / "fx_cache.csv")
                logger.info("FX cache updated.")
            except Exception:
                logger.exception("FX refresh failed (non-fatal)")

    logger.info("Done.")
