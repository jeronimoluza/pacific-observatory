"""Collection and update commands for fuel_prices."""

from __future__ import annotations

import sys
from collections.abc import Callable
from datetime import date
from typing import cast

import pandas as pd

from ..backfill_fuelcheck import backfill_nsw_fuelcheck
from ..constants import PROJECT_ROOT
from ..csv_store import load_fuel_csv, save_fuel_csv
from ..fetchers import FETCHER_REGISTRY
from ..fetchers.korea import fetch_kr_fuel_news_evidence
from ..fetchers.thailand import fetch_thailand_news_evidence
from ..loader import get_cutoff, merge_new_rows, read_fetch_state, write_fetch_state
from ..storage import source_csv_path
from ..track_a_artifacts import write_news_evidence_artifact


def cmd_fetch(args) -> None:
    """Fetch new data from one or all configured fuel sources."""
    state = read_fetch_state()

    if args.source:
        if args.source not in FETCHER_REGISTRY:
            print(f"Unknown source key: {args.source}")
            print(f"Available: {', '.join(sorted(FETCHER_REGISTRY))}")
            sys.exit(1)
        keys_to_run = [args.source]
    else:
        keys_to_run = list(FETCHER_REGISTRY)

    fn_to_keys: dict[Callable[[date], pd.DataFrame], list[str]] = {}
    for source_key in keys_to_run:
        fetch_fn = cast(Callable[[date], pd.DataFrame], FETCHER_REGISTRY[source_key][0])
        fn_to_keys.setdefault(fetch_fn, []).append(source_key)

    existing_cache: dict[str, pd.DataFrame] = {}

    for fetch_fn, source_keys in fn_to_keys.items():
        cutoffs: list[date] = []
        for source_key in source_keys:
            _fn, fallback, _full_refresh = FETCHER_REGISTRY[source_key]
            cutoffs.append(get_cutoff(state, source_key, fallback))
        cutoff = min(cutoffs) if cutoffs else date(1900, 1, 1)

        keys_label = ", ".join(source_keys)
        print(f"\n--- {keys_label} (cutoff: {cutoff}) ---")
        try:
            new_df = fetch_fn(cutoff)
        except Exception as exc:
            print(f"  FAILED: {exc}")
            continue

        if new_df is None or new_df.empty:
            print("  No new rows")
            continue

        if "country" not in new_df.columns:
            new_df = new_df.copy()
            new_df["country"] = "Unknown"
        if "source_key" not in new_df.columns:
            new_df = new_df.copy()
            new_df["source_key"] = source_keys[0]

        for key, group in new_df.groupby(["country", "source_key"], dropna=False):
            country_raw, source_key_raw = cast(tuple[object, object], key)
            country = str(country_raw) if country_raw is not None else "Unknown"
            source_key = (
                str(source_key_raw) if source_key_raw is not None else source_keys[0]
            )
            out_path = source_csv_path(country, source_key)
            cache_key = str(out_path)

            if cache_key in existing_cache:
                existing = existing_cache[cache_key]
            else:
                existing = load_fuel_csv(out_path)
                existing_cache[cache_key] = existing

            full_refresh = False
            if source_key in FETCHER_REGISTRY:
                full_refresh = bool(FETCHER_REGISTRY[source_key][2])
            if full_refresh:
                existing = pd.DataFrame(columns=existing.columns)

            merged = merge_new_rows(existing, group)
            existing_cache[cache_key] = merged
            save_fuel_csv(merged, out_path)

        if "observation_date" in new_df.columns:
            for source_key, source_df in new_df.groupby("source_key"):
                max_date_str = source_df["observation_date"].dropna().max()
                missing = pd.isna(max_date_str)
                if max_date_str is None or (isinstance(missing, bool) and missing):
                    continue
                try:
                    state[str(source_key)] = date.fromisoformat(str(max_date_str))
                except (ValueError, TypeError):
                    continue

    write_fetch_state(state)
    print("\nDone.")


def _parse_period(value: str | None) -> tuple[int, int] | None:
    if not value:
        return None
    cleaned = str(value).strip()
    if not cleaned:
        return None
    parts = cleaned.split("-")
    if len(parts) != 2:
        raise ValueError("Expected YYYY-MM")
    return int(parts[0]), int(parts[1])


def cmd_backfill_fuelcheck(args) -> None:
    """Download and write all NSW FuelCheck price history."""
    out_path = backfill_nsw_fuelcheck(
        overwrite=bool(args.overwrite),
        from_period=_parse_period(getattr(args, "from_period", None)),
        to_period=_parse_period(getattr(args, "to_period", None)),
    )
    print(f"Done. Wrote FuelCheck history -> {out_path}")


def _write_news_artifact(
    *,
    records: list[dict],
    country_slug: str,
    artifact_name: str,
    producer: str,
) -> None:
    if not records:
        print("No news items fetched.")
        return

    result = write_news_evidence_artifact(
        records=records,
        project_root=PROJECT_ROOT,
        country_slug=country_slug,
        artifact_name=artifact_name,
        source_url=records[0].get("source_url") or "",
        producer=producer,
    )
    print(f"Saved {len(records)} records -> {result['artifact_path']}")


def cmd_th_news(args) -> None:
    """Collect Thailand EPPO oil price news evidence (Track A)."""
    print("Fetching Thailand news evidence RSS feed...")
    records = fetch_thailand_news_evidence(max_items=args.max_items)
    _write_news_artifact(
        records=records,
        country_slug="thailand",
        artifact_name="th_eppo_oil_price_status_news",
        producer="python -m src.cpi.fuel_prices tracka-news",
    )


def cmd_kr_news(args) -> None:
    """Collect Korea fuel price news evidence (Track A)."""
    print("Fetching Korea news evidence RSS feed...")
    records = fetch_kr_fuel_news_evidence(max_items=args.max_items)
    _write_news_artifact(
        records=records,
        country_slug="korea",
        artifact_name="kr_fuel_price_news",
        producer="python -m src.cpi.fuel_prices tracka-news-kr",
    )
