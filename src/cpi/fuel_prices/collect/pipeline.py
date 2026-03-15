"""Collection-stage pipeline helpers for fuel price sources."""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import cast

import pandas as pd

from ..constants import DATA_DIR, FETCH_STATE_JSON, STAGED_DATA_DIR
from ..fetchers import FETCHER_REGISTRY
from ..loader import (
    get_cutoff,
    load_fuel_csv,
    merge_new_rows,
    read_fetch_state,
    save_fuel_csv,
    write_fetch_state,
)
from ..storage import source_csv_path

logger = logging.getLogger(__name__)


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
) -> None:
    """Fetch new data from one or all configured fuel sources."""

    state = read_fetch_state(fetch_state_path)

    if source_key:
        if source_key not in FETCHER_REGISTRY:
            logger.error("Unknown source key: %s", source_key)
            logger.info("Available: %s", ", ".join(sorted(FETCHER_REGISTRY)))
            sys.exit(1)
        keys_to_run = [source_key]
    else:
        keys_to_run = list(FETCHER_REGISTRY)

    fn_to_keys: dict[Callable[[date], pd.DataFrame], list[str]] = {}
    for key in keys_to_run:
        fetch_fn = cast(Callable[[date], pd.DataFrame], FETCHER_REGISTRY[key][0])
        fn_to_keys.setdefault(fetch_fn, []).append(key)

    existing_cache: dict[str, pd.DataFrame] = {}

    for fetch_fn, source_keys in fn_to_keys.items():
        cutoffs: list[date] = []
        for key in source_keys:
            _fn, fallback, _full_refresh = FETCHER_REGISTRY[key]
            cutoffs.append(get_cutoff(state, key, fallback))
        cutoff = min(cutoffs) if cutoffs else date(1900, 1, 1)

        keys_label = ", ".join(source_keys)
        logger.info("--- %s (cutoff: %s) ---", keys_label, cutoff)
        try:
            new_df = fetch_fn(cutoff)
        except Exception:
            logger.exception("Fetcher %s failed", keys_label)
            continue

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

            full_refresh = bool(
                FETCHER_REGISTRY.get(grouped_source, (None, None, False))[2]
            )
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
                    state[str(key)] = date.fromisoformat(str(max_date_str))
                except (ValueError, TypeError):
                    continue

    write_fetch_state(state, fetch_state_path)
    logger.info("Done.")
