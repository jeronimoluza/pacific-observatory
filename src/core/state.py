"""Source state tracking: what data we have, when we last checked."""

import json
import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import TypedDict

import pandas as pd

logger = logging.getLogger(__name__)


class SourceState(TypedDict):
    last_data_date: str | None  # newest observation date in stored data (ISO)
    last_checked_ts: str | None  # when collect last ran for this source (ISO UTC)
    note: str | None  # optional: error message, known issues


def read_state(path: Path) -> dict[str, SourceState]:
    """Load a .state.json file. Returns empty dict if missing."""
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return {k: _normalize(v) for k, v in raw.items()}
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Could not read state from %s: %s", path, exc)
        return {}


def write_state(state: dict[str, SourceState], path: Path) -> None:
    """Persist state to JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def get_last_data_date(state: dict[str, SourceState], key: str, fallback: date) -> date:
    """Return last_data_date for a source, or fallback if unknown.

    Passed as cutoff hint to fetchers: 'don't re-fetch before this date'.
    """
    entry = state.get(key)
    if entry is None:
        return fallback
    raw = entry.get("last_data_date")
    if not raw:
        return fallback
    try:
        return date.fromisoformat(str(raw))
    except (ValueError, TypeError):
        return fallback


def set_last_data_date(state: dict[str, SourceState], key: str, d: date) -> None:
    """Update last_data_date for a source (preserves other fields)."""
    entry = state.get(key, _empty())
    state[key] = {**entry, "last_data_date": d.isoformat()}


def set_checked(
    state: dict[str, SourceState], key: str, ts: datetime | None = None
) -> None:
    """Mark that we attempted to collect from this source."""
    if ts is None:
        ts = datetime.now(tz=timezone.utc)
    entry = state.get(key, _empty())
    state[key] = {**entry, "last_checked_ts": ts.isoformat()}


def set_note(state: dict[str, SourceState], key: str, note: str | None) -> None:
    """Attach or clear a note (e.g. error message) on a source."""
    entry = state.get(key, _empty())
    state[key] = {**entry, "note": note}


def staleness(state: dict[str, SourceState], key: str) -> timedelta | None:
    """How long since last_data_date. None if never collected."""
    entry = state.get(key)
    if entry is None:
        return None
    raw = entry.get("last_data_date")
    if not raw:
        return None
    try:
        d = date.fromisoformat(str(raw))
        return timedelta(days=(date.today() - d).days)
    except (ValueError, TypeError):
        return None


def expected_update_interval(observations: pd.Series) -> timedelta | None:
    """Median gap between data points. observations is a Series of date strings or datetimes.

    Returns None if fewer than 2 observations.
    """
    if observations is None or len(observations) < 2:
        return None
    dates = pd.to_datetime(observations).dropna().sort_values()
    if len(dates) < 2:
        return None
    gaps = dates.diff().dropna()
    median_gap = gaps.median()
    return median_gap


def assess_source(
    last_data_date: date | None,
    observations: pd.Series | None = None,
    note: str | None = None,
) -> str:
    """Human-readable staleness assessment for CLI status display."""
    if note:
        return f"✗ {note}"
    if last_data_date is None:
        return "? never collected"

    gap = timedelta(days=(date.today() - last_data_date).days)
    interval = expected_update_interval(observations)

    if interval is None:
        if gap.days <= 7:
            return f"✓ {gap.days}d ago"
        return f"⚠ {gap.days}d ago (insufficient history to assess)"

    if gap <= interval:
        return f"✓ up to date ({gap.days}d ago)"
    if gap <= interval * 2:
        return f"⚠ likely has new data ({gap.days}d, expected every ~{interval.days}d)"
    return f"✗ needs check ({gap.days}d, expected every ~{interval.days}d)"


# ── internal ─────────────────────────────────────────────────────────────


def _empty() -> SourceState:
    return {"last_data_date": None, "last_checked_ts": None, "note": None}


def _normalize(value: object) -> SourceState:
    """Handle legacy formats (bare date strings)."""
    if isinstance(value, str):
        return {"last_data_date": value, "last_checked_ts": None, "note": None}
    if isinstance(value, dict):
        return {
            "last_data_date": value.get("last_data_date"),
            "last_checked_ts": value.get("last_checked_ts", value.get("last_run_ts")),
            "note": value.get("note"),
        }
    return _empty()
