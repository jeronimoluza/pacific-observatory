"""Helpers for bounded standardization windows and cache matching."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


def normalize_bound(value: str | None) -> str | None:
    """Normalize empty string inputs to None."""
    if value is None:
        return None
    value = value.strip()
    return value or None


def format_baseline_window(
    cutoff_start_date: str | None,
    cutoff_end_date: str | None,
) -> str:
    """Return a human-readable baseline window label."""
    start = cutoff_start_date or "open start"
    end = cutoff_end_date or "today"
    return f"{start} -> {end}"


def baseline_mask(
    dates: pd.Series | pd.Index | np.ndarray,
    cutoff_start_date: str | None,
    cutoff_end_date: str | None,
):
    """Build an inclusive boolean mask for the requested baseline window."""
    if isinstance(dates, pd.Series):
        date_series = pd.to_datetime(dates, errors="coerce")
    else:
        date_series = pd.Series(pd.to_datetime(dates, errors="coerce"))
    mask = pd.Series(True, index=date_series.index)
    if cutoff_start_date is not None:
        mask &= date_series >= pd.Timestamp(cutoff_start_date)
    if cutoff_end_date is not None:
        mask &= date_series <= pd.Timestamp(cutoff_end_date)
    return mask


def source_key_for_news_path(news_csv: Path) -> str:
    """Build the canonical source key used in params.json."""
    country = news_csv.parent.parent.name
    newspaper = news_csv.parent.name.replace(country, "").strip("_")
    return f"{country}_{newspaper}"


def cached_baseline_window(params: dict) -> tuple[str | None, str | None]:
    """Read baseline start/end dates from params.json."""
    return (
        normalize_bound(params.get("cutoff_start_date")),
        normalize_bound(params.get("cutoff_end_date")),
    )


def has_modern_baseline_window(params: dict) -> bool:
    """Return whether params.json uses the new start/end baseline schema."""
    return "cutoff_start_date" in params or "cutoff_end_date" in params


def cache_matches_baseline(
    params: dict,
    current_sources: set[str],
    cutoff_start_date: str | None,
    cutoff_end_date: str | None,
) -> bool:
    """Return whether cached params can be reused for the requested build."""
    if not has_modern_baseline_window(params):
        return False
    cached_sources = set(params.get("sources", []))
    cached_start, cached_end = cached_baseline_window(params)
    return (
        cached_sources == current_sources
        and cached_start == normalize_bound(cutoff_start_date)
        and cached_end == normalize_bound(cutoff_end_date)
    )
