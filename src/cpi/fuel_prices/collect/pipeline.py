"""Collection-stage pipeline helpers for fuel price sources."""

from __future__ import annotations

import logging
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import cast

import pandas as pd

from ..constants import DATA_DIR, FETCH_STATE_JSON, STAGED_DATA_DIR
from ..fetchers import FETCHER_REGISTRY, Cadence
from ..loader import (
    get_cutoff,
    get_last_run_ts,
    load_fuel_csv,
    merge_new_rows,
    read_fetch_state,
    save_fuel_csv,
    set_last_data_date,
    set_last_run_ts,
    write_fetch_state,
)
from ..storage import source_csv_path

logger = logging.getLogger(__name__)

# ── Cadence skip intervals ────────────────────────────────────────────────────

_CADENCE_MIN_INTERVAL: dict[str, timedelta] = {
    "daily": timedelta(hours=20),
    "weekly": timedelta(days=5),
    "monthly": timedelta(days=25),
    "quarterly": timedelta(days=80),
    # "irregular": no minimum — always run
    # "manual": handled separately — never auto-run
}


def _should_skip(
    source_key: str,
    cadence: Cadence,
    state: dict,
    force: bool,
) -> bool:
    """Return True if this source should be skipped based on cadence.

    - manual: always skip unless force=True
    - irregular: never skip
    - others: skip if last_run_ts is within the cadence interval
    """
    if force:
        if cadence == "manual":
            logger.warning("Running manual source %s (--force override)", source_key)
        return False

    if cadence == "manual":
        logger.info("Skipping %s (cadence=manual; use --force to run)", source_key)
        return True

    if cadence == "irregular":
        return False

    min_interval = _CADENCE_MIN_INTERVAL.get(cadence)
    if min_interval is None:
        return False

    last_run = get_last_run_ts(state, source_key)
    if last_run is None:
        return False  # never run → always execute

    now = datetime.now(tz=timezone.utc)
    if last_run.tzinfo is None:
        last_run = last_run.replace(tzinfo=timezone.utc)
    elapsed = now - last_run

    if elapsed < min_interval:
        logger.info(
            "Skipping %s (cadence=%s; last run %s ago, interval %s)",
            source_key,
            cadence,
            str(elapsed).split(".")[0],
            min_interval,
        )
        return True

    return False


def staged_collect_dir() -> Path:
    """Return the staged collect output directory."""
    return STAGED_DATA_DIR / "collect"


def staged_fetch_state_path() -> Path:
    """Return the staged collect fetch-state path."""
    return staged_collect_dir() / ".fetch_state.json"


def run_collection(
    *,
    source_key: str | None = None,
    observations_base_dir: Path = DATA_DIR,
    fetch_state_path: Path = FETCH_STATE_JSON,
    cadence_filter: Cadence | None = None,
    force: bool = False,
    rebuild: bool = False,
) -> None:
    """Fetch new data from one or all configured fuel sources.

    Args:
        source_key: Run a single source key only. Required when rebuild=True.
        observations_base_dir: Base directory for per-source observations.csv files.
        fetch_state_path: Path to .fetch_state.json.
        cadence_filter: If set, only run sources whose cadence matches.
        force: Ignore cadence skip logic (including manual sources).
        rebuild: Delete existing observations.csv and re-fetch from fallback_date.
                 Requires source_key to be set.
    """
    if rebuild and not source_key:
        logger.error("--rebuild requires --source KEY")
        sys.exit(1)

    state = read_fetch_state(fetch_state_path)

    if source_key:
        if source_key not in FETCHER_REGISTRY:
            logger.error("Unknown source key: %s", source_key)
            logger.info("Available: %s", ", ".join(sorted(FETCHER_REGISTRY)))
            sys.exit(1)
        keys_to_run = [source_key]
    else:
        keys_to_run = list(FETCHER_REGISTRY)

    # Apply cadence filter
    if cadence_filter:
        keys_to_run = [
            k for k in keys_to_run if FETCHER_REGISTRY[k].cadence == cadence_filter
        ]
        if not keys_to_run:
            logger.info("No sources match cadence=%s", cadence_filter)
            return

    # Handle rebuild: wipe observations.csv and reset state
    if rebuild and source_key:
        cfg = FETCHER_REGISTRY[source_key]
        out_path = source_csv_path(
            cfg.country, source_key, base_dir=observations_base_dir
        )
        if out_path.exists():
            out_path.unlink()
            logger.info("Deleted %s for rebuild", out_path)
        state[source_key] = {
            "last_data_date": cfg.fallback_date.isoformat(),
            "last_run_ts": None,
        }
        force = True  # rebuild always runs regardless of cadence

    # Group keys by fetch function (some functions serve multiple source keys)
    fn_to_keys: dict = {}
    for key in keys_to_run:
        fn = FETCHER_REGISTRY[key].fn
        fn_to_keys.setdefault(fn, []).append(key)

    existing_cache: dict[str, pd.DataFrame] = {}

    for fetch_fn, source_keys in fn_to_keys.items():
        # Cadence skip: check the first key in the group (shared fn → same cadence)
        primary_key = source_keys[0]
        primary_cfg = FETCHER_REGISTRY[primary_key]

        if _should_skip(primary_key, primary_cfg.cadence, state, force):
            # Mark run timestamp even for skipped sources? No — skip means no attempt.
            continue

        cutoffs: list[date] = []
        for key in source_keys:
            cfg = FETCHER_REGISTRY[key]
            cutoffs.append(get_cutoff(state, key, cfg.fallback_date))
        cutoff = min(cutoffs) if cutoffs else date(1900, 1, 1)

        keys_label = ", ".join(source_keys)
        logger.info("--- %s (cutoff: %s) ---", keys_label, cutoff)

        run_ts = datetime.now(tz=timezone.utc)
        try:
            new_df = fetch_fn(cutoff)
        except Exception:
            logger.exception("Fetcher %s failed", keys_label)
            # Update last_run_ts even on failure (the attempt was made)
            for key in source_keys:
                set_last_run_ts(state, key, run_ts)
            continue

        # Update last_run_ts after successful attempt (including empty returns)
        for key in source_keys:
            set_last_run_ts(state, key, run_ts)

        if new_df is None or new_df.empty:
            logger.info("No new rows")
            continue

        if "country" not in new_df.columns:
            new_df = new_df.copy()
            new_df["country"] = "Unknown"
        if "source_key" not in new_df.columns:
            new_df = new_df.copy()
            new_df["source_key"] = source_keys[0]

        for grouped_key, group in new_df.groupby(
            ["country", "source_key"], dropna=False
        ):
            country_raw, grouped_source_key = cast(tuple[object, object], grouped_key)
            country = str(country_raw) if country_raw is not None else "Unknown"
            grouped_source = (
                str(grouped_source_key)
                if grouped_source_key is not None
                else source_keys[0]
            )
            out_path = source_csv_path(
                country,
                grouped_source,
                base_dir=observations_base_dir,
            )
            cache_key = str(out_path)

            if cache_key in existing_cache:
                existing = existing_cache[cache_key]
            else:
                existing = load_fuel_csv(out_path)
                existing_cache[cache_key] = existing

            cfg = FETCHER_REGISTRY.get(grouped_source)
            full_refresh = cfg.full_refresh if cfg is not None else False
            if full_refresh:
                existing = pd.DataFrame(columns=existing.columns)

            merged = merge_new_rows(existing, group)
            existing_cache[cache_key] = merged
            save_fuel_csv(merged, out_path)

        if "observation_date" in new_df.columns:
            for key, source_df in new_df.groupby("source_key"):
                max_date_str = source_df["observation_date"].dropna().max()
                missing = pd.isna(max_date_str)
                if max_date_str is None or (isinstance(missing, bool) and missing):
                    continue
                try:
                    set_last_data_date(
                        state, str(key), date.fromisoformat(str(max_date_str))
                    )
                except (ValueError, TypeError):
                    continue

    write_fetch_state(state, fetch_state_path)
    logger.info("Done.")
