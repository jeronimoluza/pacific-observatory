"""Fetch-state cache, CSV helpers, and publish-time fuel data loader."""

import json
import logging
from datetime import date, datetime, timezone
from pathlib import Path
from typing import TypedDict

import pandas as pd

from .constants import COLUMNS, DATA_DIR, FETCH_STATE_JSON, STAGED_DATA_DIR
from .utils import make_hash

logger = logging.getLogger(__name__)


# ── CSV helpers (absorbed from csv_store) ─────────────────────────────────────


def load_fuel_csv(path: Path) -> pd.DataFrame:
    """Load a fuel CSV, returning an empty schema-aligned frame if missing."""
    if path.exists():
        return pd.read_csv(path, low_memory=False)
    return pd.DataFrame(columns=pd.Index(COLUMNS))


def save_fuel_csv(df: pd.DataFrame, path: Path) -> None:
    """Persist a fuel CSV using the canonical column order."""
    path.parent.mkdir(parents=True, exist_ok=True)
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = None
    df[COLUMNS].to_csv(path, index=False)
    logger.info("Saved %d rows -> %s", len(df), path)


# ── Fetch state v2 ────────────────────────────────────────────────────────────
#
# v1 format (legacy): { "source_key": "2026-01-01" }
# v2 format:          { "source_key": { "last_data_date": "2026-01-01",
#                                        "last_run_ts": "2026-03-16T10:23:00" } }
#
# last_data_date: max observation_date of data stored for this source.
#                 Used as cutoff passed to fetch_fn on the next run.
# last_run_ts:    ISO-8601 UTC datetime of when the fetcher last executed
#                 (success, empty return, or exception).
#                 Used for cadence skip decisions — NOT for cutoff calculation.


class SourceState(TypedDict):
    last_data_date: str | None  # ISO date string or None
    last_run_ts: str | None  # ISO datetime string or None


def _normalize_entry(value: object) -> SourceState:
    """Normalize a v1 bare string or v2 object to SourceState."""
    if isinstance(value, str):
        return {"last_data_date": value, "last_run_ts": None}
    if isinstance(value, dict):
        return {
            "last_data_date": value.get("last_data_date"),
            "last_run_ts": value.get("last_run_ts"),
        }
    return {"last_data_date": None, "last_run_ts": None}


def read_fetch_state(path: Path = FETCH_STATE_JSON) -> dict[str, SourceState]:
    """Load .fetch_state.json; return dict of source_key → SourceState (v2).

    Transparently migrates v1 bare-string entries to v2 objects.
    """
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return {k: _normalize_entry(v) for k, v in raw.items()}
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Could not read fetch state from %s: %s", path, exc)
        return {}


def write_fetch_state(
    state: dict[str, SourceState], path: Path = FETCH_STATE_JSON
) -> None:
    """Persist fetch state to .fetch_state.json in v2 format."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def get_cutoff(state: dict[str, SourceState], source_key: str, fallback: date) -> date:
    """Return the last_data_date for source_key, or fallback if not present."""
    entry = state.get(source_key)
    if entry is None:
        return fallback
    raw = entry.get("last_data_date")
    if not raw:
        return fallback
    try:
        return date.fromisoformat(str(raw))
    except (ValueError, TypeError):
        return fallback


def get_last_run_ts(state: dict[str, SourceState], source_key: str) -> datetime | None:
    """Return the last_run_ts for source_key as a UTC-aware datetime, or None."""
    entry = state.get(source_key)
    if entry is None:
        return None
    raw = entry.get("last_run_ts")
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(str(raw))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def set_last_run_ts(
    state: dict[str, SourceState],
    source_key: str,
    ts: datetime | None = None,
) -> None:
    """Update last_run_ts for source_key in-place. Defaults to now (UTC)."""
    if ts is None:
        ts = datetime.now(tz=timezone.utc)
    entry = state.get(source_key, {"last_data_date": None, "last_run_ts": None})
    state[source_key] = {
        "last_data_date": entry.get("last_data_date"),
        "last_run_ts": ts.isoformat(),
    }


def set_last_data_date(
    state: dict[str, SourceState],
    source_key: str,
    d: date,
) -> None:
    """Update last_data_date for source_key in-place (preserves last_run_ts)."""
    entry = state.get(source_key, {"last_data_date": None, "last_run_ts": None})
    state[source_key] = {
        "last_data_date": d.isoformat(),
        "last_run_ts": entry.get("last_run_ts"),
    }


# ── Row merging / deduplication ───────────────────────────────────────────────


def merge_new_rows(df_existing: pd.DataFrame, df_new: pd.DataFrame) -> pd.DataFrame:
    """Append new rows, deduplicating by observation_hash."""
    if df_new is None or df_new.empty:
        return df_existing

    if "observation_hash" not in df_new.columns:
        df_new = df_new.copy()
        df_new["observation_hash"] = df_new.apply(make_hash, axis=1)

    existing_hashes = set(df_existing["observation_hash"].dropna())
    df_unique = df_new[~df_new["observation_hash"].isin(existing_hashes)].copy()
    dupes = len(df_new) - len(df_unique)

    if df_unique.empty:
        logger.info("All %d fetched rows are duplicates — no changes", len(df_new))
        return df_existing

    logger.info("Appending %d new rows (%d duplicates dropped)", len(df_unique), dupes)

    for col in df_existing.columns:
        if col not in df_unique.columns:
            df_unique[col] = None
    df_unique = df_unique[df_existing.columns]

    combined = pd.concat([df_existing, df_unique], ignore_index=True)
    return combined.sort_values(
        ["country", "source_key", "observation_date"]
    ).reset_index(drop=True)


# ── Publish-time loader ───────────────────────────────────────────────────────


def load_fuel_data(
    *,
    enriched_csv: Path | None = None,
) -> dict:
    """Load fuel series for publishing.

    Reads from staged enriched CSV if available; otherwise builds from scratch
    using process.build_enriched_frame.
    """
    from .process import build_enriched_frame, frame_to_country_series

    if enriched_csv is None:
        enriched_csv = STAGED_DATA_DIR / "enrich" / "retail_series_enriched.csv"

    if enriched_csv.exists():
        df = pd.read_csv(enriched_csv, low_memory=False)
        if "observation_date" in df.columns:
            df["observation_date"] = pd.to_datetime(
                df["observation_date"], errors="coerce"
            )
        logger.info("Loading enriched fuel series from %s", enriched_csv)
        return frame_to_country_series(df)

    logger.info("Enriched CSV not found — building from scratch")
    df = build_enriched_frame(collect_dir=DATA_DIR)
    return frame_to_country_series(df)
