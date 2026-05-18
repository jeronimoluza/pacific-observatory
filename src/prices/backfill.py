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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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
