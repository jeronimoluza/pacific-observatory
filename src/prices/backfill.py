"""Prices wayback backfill: per-source orchestrator + Click command.

Reads the union of `raw_items/*.jsonl` for a source to get the URL universe,
discovers daily Wayback snapshots for each URL, fetches raw HTML via the
`id_/` endpoint, and parses with the existing `SPIDER_SELECTORS` registry.
Writes rows into a sibling `wayback_items/{source}_{run_ts}.jsonl` and
tracks completion in `wayback_items/.ledger.json` for resumability.
"""

from __future__ import annotations

import hashlib
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import suppress
from datetime import date, datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from bs4 import BeautifulSoup

from core.http import make_session
from prices._shared.wayback import (
    bulk_discover,
    collapse_timestamps,
    discover_snapshots,
    fetch_snapshot,
    parse_timestamp_to_date,
)
from prices.price_scraping.selectors import extract_with_fallback, get_selectors

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
                if not url:
                    continue
                # Aggregator spiders disable DuplicationPipeline (one URL
                # emits ~50 rows), so url_hash isn't set on those rows.
                # Synthesize from URL — matches the md5(url) used elsewhere.
                url_hash = row.get("url_hash") or hashlib.md5(url.encode()).hexdigest()
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
        self._data: dict[str, set[str]] = {k: set(v) for k, v in (data or {}).items()}

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
    parse_html_fn=None,
    timestamps: list[str] | None = None,
    granularity: str = "week",
) -> list[dict[str, Any]]:
    """Discover, fetch, parse all wayback snapshots for one URL.

    Returns the list of row dicts to append. Rows are dropped (not returned)
    when the spider's price selector finds nothing — but the ledger is still
    updated for those timestamps so we don't retry dead snapshots.

    When `timestamps` is supplied (bulk-discovery path) it is used as-is —
    already intersected and collapsed. Otherwise a per-URL CDX query runs and
    its result is collapsed to `granularity` here.

    Dispatch:
    - When `parse_html_fn` is supplied (aggregator spiders that expose a
      `parse_html(html, url)` classmethod), each snapshot may yield MANY
      rows; the function is the single source of truth for parsing.
    - Otherwise (retailer spiders), the existing per-field SPIDER_SELECTORS
      path runs and emits one row per snapshot.
    """
    if timestamps is None:
        discovered = discover_snapshots(
            session, url, cutoff, collapse_digits=collapse_digits
        )
        timestamps = collapse_timestamps(discovered, granularity)
    pending = [ts for ts in timestamps if not ledger.is_done(url_hash, ts)]
    if max_snapshots is not None:
        pending = pending[:max_snapshots]

    rows: list[dict[str, Any]] = []
    for ts in pending:
        html = fetch_snapshot(session, ts, url)
        ledger.record(url_hash, ts)
        if html is None:
            continue
        snap_date = parse_timestamp_to_date(ts)
        snap_iso = (
            f"{snap_date.isoformat()}T00:00:00+00:00" if snap_date is not None else None
        )

        if parse_html_fn is not None:
            try:
                parsed = list(parse_html_fn(html, url))
            except Exception:
                logger.exception("[wayback] parse_html failed for %s @ %s", url, ts)
                continue
            if not parsed:
                logger.debug(
                    "[wayback] aggregator parse yielded 0 rows for %s @ %s",
                    url,
                    ts,
                )
                continue
            for rec in parsed:
                rec.setdefault("url", url)
                rec["url_hash"] = url_hash
                rec["source_kind"] = "wayback"
                rec["wayback_timestamp"] = ts
                rec["scraped_at_utc"] = snap_iso
                if currency and not rec.get("currency"):
                    rec["currency"] = currency
                rows.append(rec)
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
        row = {
            "url": url,
            "url_hash": url_hash,
            "currency": currency,
            "source_kind": "wayback",
            "wayback_timestamp": ts,
            "scraped_at_utc": snap_iso,
            **extracted,
        }
        rows.append(row)
    return rows


_RUN_TS_FMT = "%Y%m%d_%H%M%S"


def _resolve_currency(source_dir: Path) -> str | None:
    """Read currency from the first row of the most recent raw_items jsonl.

    Spiders hardcode currency as a class attr; the easiest source of truth
    at backfill time is the already-collected data.
    """
    raw_dir = source_dir / "raw_items"
    if not raw_dir.exists():
        return None
    files = sorted(raw_dir.glob("*.jsonl"), reverse=True)
    for f in files:
        for line in f.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            cur = row.get("currency")
            if cur:
                return cur
    return None


def _load_spider_parse_html(spider_name: str):
    """Return the spider's `parse_html(html, url)` classmethod if it exists.

    Aggregator spiders (livingcost, mylifeelsewhere, expatistan) expose this
    so live scrape and Wayback share one parser. Retailer spiders don't, and
    the backfiller falls back to the SPIDER_SELECTORS path.
    """
    import importlib

    try:
        mod = importlib.import_module(f"prices.price_scraping.spiders.{spider_name}")
    except ImportError:
        logger.debug(
            "[wayback] no spider module prices.price_scraping.spiders.%s",
            spider_name,
        )
        return None
    for attr_name in dir(mod):
        obj = getattr(mod, attr_name)
        if not isinstance(obj, type):
            continue
        if getattr(obj, "name", None) != spider_name:
            continue
        parse_html = getattr(obj, "parse_html", None)
        if callable(parse_html):
            logger.info(
                "[wayback] using parse_html hook from %s.%s",
                mod.__name__,
                obj.__name__,
            )
            return parse_html
    return None


def run_source_backfill(
    *,
    source_dir: Path,
    spider: str,
    cutoff_override: date | None = None,
    collapse_digits: int = 8,
    max_snapshots_per_url: int | None = None,
    max_urls: int | None = None,
    workers: int = 4,
    discovery: str = "bulk",
    granularity: str = "week",
) -> dict[str, int]:
    """Backfill one source. Returns stats dict.

    Writes:
      {source_dir}/wayback_items/{source}_{run_ts}.jsonl
      {source_dir}/wayback_items/.ledger.json
    """
    universe = load_url_universe(source_dir)
    if max_urls is not None:
        universe = universe[:max_urls]

    stats = {
        "urls_total": len(universe),
        "urls_processed": 0,
        "rows_written": 0,
    }
    if not universe:
        logger.info("[%s] no URLs to backfill", source_dir.name)
        return stats

    wayback_dir = source_dir / "wayback_items"
    wayback_dir.mkdir(parents=True, exist_ok=True)
    ledger = Ledger.load(wayback_dir / ".ledger.json")
    parse_html_fn = _load_spider_parse_html(spider)
    selectors = get_selectors(spider) if parse_html_fn is None else {}
    currency = _resolve_currency(source_dir)

    # CDX `from=` is the EARLIEST snapshot date to include. For backfill we
    # want every archived snapshot (older than what live collection already
    # covers), so default to a very early year. Narrow with --from.
    cutoff = cutoff_override or date(2010, 1, 1)

    # Bulk discovery: one paged CDX query per host instead of one per URL.
    bulk_ts: dict[str, list[str]] | None = None
    if discovery == "bulk":
        disc_session = make_session()
        try:
            bulk_ts = bulk_discover(
                disc_session, universe, cutoff, granularity=granularity
            )
        finally:
            disc_session.close()
        logger.info(
            "[%s] bulk discovery: %d/%d urls have snapshots, %d total after %s collapse",
            source_dir.name,
            len(bulk_ts),
            len(universe),
            sum(len(v) for v in bulk_ts.values()),
            granularity,
        )

    run_ts = datetime.now(timezone.utc).strftime(_RUN_TS_FMT)
    out_path = wayback_dir / f"{source_dir.name}_{run_ts}.jsonl"
    write_lock = Lock()
    out_fh = open(out_path, "w", encoding="utf-8")

    def _process(entry: dict[str, Any]) -> int:
        url = entry["url"]
        url_hash = entry["url_hash"]
        ts_list = None
        if bulk_ts is not None:
            ts_list = bulk_ts.get(url_hash, [])
            if not ts_list:
                return 0
        session = make_session()
        try:
            rows = backfill_one_url(
                session=session,
                url=url,
                url_hash=url_hash,
                cutoff=cutoff,
                selectors=selectors,
                ledger=ledger,
                currency=currency,
                collapse_digits=collapse_digits,
                max_snapshots=max_snapshots_per_url,
                parse_html_fn=parse_html_fn,
                timestamps=ts_list,
                granularity=granularity,
            )
        finally:
            session.close()
        if rows:
            with write_lock:
                for r in rows:
                    out_fh.write(json.dumps(r, ensure_ascii=False) + "\n")
                out_fh.flush()
        return len(rows)

    try:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_process, e): e for e in universe}
            for fut in as_completed(futures):
                entry = futures[fut]
                try:
                    n = fut.result()
                except Exception:
                    logger.exception(
                        "[%s] backfill failed for %s",
                        source_dir.name,
                        entry["url"],
                    )
                    n = 0
                stats["rows_written"] += n
                stats["urls_processed"] += 1
                if stats["urls_processed"] % 25 == 0:
                    logger.info(
                        "[%s] %d/%d urls, %d rows so far",
                        source_dir.name,
                        stats["urls_processed"],
                        stats["urls_total"],
                        stats["rows_written"],
                    )
                    with suppress(OSError):
                        ledger.save()
    finally:
        out_fh.close()
        with suppress(OSError):
            ledger.save()

    if stats["rows_written"] == 0:
        with suppress(OSError):
            out_path.unlink()

    logger.info(
        "[%s] backfill complete — %d urls, %d rows written",
        source_dir.name,
        stats["urls_processed"],
        stats["rows_written"],
    )
    return stats
