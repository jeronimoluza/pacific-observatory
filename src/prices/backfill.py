"""Prices wayback backfill: per-source orchestrator + Click command.

Reads the union of `raw_items/*.jsonl` for a source to get the URL universe,
discovers daily Wayback snapshots for each URL, fetches raw HTML via the
`id_/` endpoint, and parses with the existing `SPIDER_SELECTORS` registry.
Writes rows into a sibling `wayback_items/{source}_{run_ts}.jsonl` and
tracks completion in `wayback_items/.ledger.json` for resumability.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from prices._shared.wayback import (
    discover_snapshots,
    fetch_snapshot,
    parse_timestamp_to_date,
)
from prices.price_scraping.selectors import extract_with_fallback

logger = logging.getLogger(__name__)


def load_url_universe(source_dir: Path) -> list[dict[str, Any]]:
    """Return one entry per unique url_hash across all raw_items jsonl files.

    Each entry: {"url", "url_hash", "earliest_scraped_at" (timezone-aware UTC)}.
    Rows missing url or url_hash are skipped silently.
    """
    raw_dir = source_dir / "raw_items"
    if not raw_dir.exists():
        return []

    by_hash: dict[str, dict[str, Any]] = {}
    for jsonl in sorted(raw_dir.glob("*.jsonl")):
        try:
            for line in jsonl.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                url = row.get("url")
                url_hash = row.get("url_hash")
                if not url or not url_hash:
                    continue
                scraped_at = _parse_iso_utc(row.get("scraped_at_utc"))
                prior = by_hash.get(url_hash)
                if prior is None:
                    by_hash[url_hash] = {
                        "url": url,
                        "url_hash": url_hash,
                        "earliest_scraped_at": scraped_at,
                    }
                elif scraped_at is not None and (
                    prior["earliest_scraped_at"] is None
                    or scraped_at < prior["earliest_scraped_at"]
                ):
                    prior["earliest_scraped_at"] = scraped_at
        except OSError as exc:
            logger.warning("Failed to read %s: %s", jsonl, exc)

    return sorted(by_hash.values(), key=lambda r: r["url_hash"])


def _parse_iso_utc(value: str | None) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class Ledger:
    """Per-source ledger of (url_hash, wayback_timestamp) pairs already fetched.

    Stored as `{url_hash: sorted_unique_list_of_timestamps}` JSON.
    """

    def __init__(self, path: Path, data: dict[str, list[str]] | None = None):
        self.path = path
        self._data: dict[str, set[str]] = {
            k: set(v) for k, v in (data or {}).items()
        }

    @classmethod
    def load(cls, path: Path) -> "Ledger":
        if not path.exists():
            return cls(path)
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                logger.warning("Ledger %s is not a dict; starting fresh", path)
                return cls(path)
            return cls(
                path,
                {k: list(v) for k, v in raw.items() if isinstance(v, list)},
            )
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to read ledger %s: %s — starting fresh", path, exc)
            return cls(path)

    def is_done(self, url_hash: str, timestamp: str) -> bool:
        return timestamp in self._data.get(url_hash, set())

    def record(self, url_hash: str, timestamp: str) -> None:
        self._data.setdefault(url_hash, set()).add(timestamp)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        out = {k: sorted(v) for k, v in self._data.items() if v}
        self.path.write_text(
            json.dumps(out, indent=2, sort_keys=True), encoding="utf-8"
        )


def backfill_one_url(
    *,
    session,
    url: str,
    url_hash: str,
    cutoff: date,
    selectors: dict[str, list[str]],
    ledger: Ledger,
    currency: str | None,
    collapse_digits: int = 8,
    max_snapshots: int | None = None,
) -> list[dict[str, Any]]:
    """Discover, fetch, parse all wayback snapshots for one URL.

    Returns the list of row dicts to append. Rows are dropped (not returned)
    when the spider's price selector finds nothing — but the ledger is still
    updated for those timestamps so we don't retry dead snapshots.
    """
    timestamps = discover_snapshots(
        session, url, cutoff, collapse_digits=collapse_digits
    )
    pending = [ts for ts in timestamps if not ledger.is_done(url_hash, ts)]
    if max_snapshots is not None:
        pending = pending[:max_snapshots]

    rows: list[dict[str, Any]] = []
    for ts in pending:
        html = fetch_snapshot(session, ts, url)
        ledger.record(url_hash, ts)
        if html is None:
            continue
        soup = BeautifulSoup(html, "html.parser")
        extracted: dict[str, Any] = {}
        for field, selector_list in selectors.items():
            value = extract_with_fallback(soup, selector_list)
            if value:
                extracted[field] = value
        if not extracted.get("price"):
            logger.debug("[wayback] dropping %s @ %s: no price extracted", url, ts)
            continue
        snap_date = parse_timestamp_to_date(ts)
        row = {
            "url": url,
            "url_hash": url_hash,
            "currency": currency,
            "source_kind": "wayback",
            "wayback_timestamp": ts,
            "scraped_at_utc": (
                f"{snap_date.isoformat()}T00:00:00+00:00"
                if snap_date is not None
                else None
            ),
            **extracted,
        }
        rows.append(row)
    return rows
