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
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import suppress
from datetime import date, datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from bs4 import BeautifulSoup

import click

from core.http import make_session
from prices._shared.wayback import (
    discover_snapshots,
    fetch_snapshot,
    parse_timestamp_to_date,
)
from prices.config import PriceSourceConfig, discover_prices_configs
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


def run_source_backfill(
    *,
    source_dir: Path,
    spider: str,
    cutoff_override: date | None = None,
    collapse_digits: int = 8,
    max_snapshots_per_url: int | None = None,
    max_urls: int | None = None,
    workers: int = 4,
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
    selectors = get_selectors(spider)
    currency = _resolve_currency(source_dir)

    run_ts = datetime.now(timezone.utc).strftime(_RUN_TS_FMT)
    out_path = wayback_dir / f"{source_dir.name}_{run_ts}.jsonl"
    write_lock = Lock()
    out_fh = open(out_path, "w", encoding="utf-8")

    def _process(entry: dict[str, Any]) -> int:
        url = entry["url"]
        url_hash = entry["url_hash"]
        earliest = entry.get("earliest_scraped_at")
        cutoff = cutoff_override or (
            earliest.date() if earliest is not None else date(2015, 1, 1)
        )
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


_PRICES_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _PRICES_DIR.parent.parent


def _load_manifests(
    region: str | None,
    subregion: str | None,
    country: str | None,
    source: str | None,
) -> list[PriceSourceConfig]:
    paths = discover_prices_configs(region=region, subregion=subregion, country=country)
    if source is not None:
        paths = [p for p in paths if p.stem == source]
    return [PriceSourceConfig.load(p) for p in paths]


def _source_dir_for(manifest: PriceSourceConfig) -> Path:
    return (
        _PROJECT_ROOT
        / "data"
        / "prices"
        / manifest.region
        / manifest.subregion
        / manifest.country
        / manifest.source
    )


def _parse_iso_date(value: str | None) -> date | None:
    if value is None:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


@click.command()
@click.option("--region", "-r", default=None, help="Region slug (e.g. eap)")
@click.option("--subregion", "-S", default=None, help="Subregion slug")
@click.option("--country", "-c", default=None, help="Country slug")
@click.option("--source", "-s", default=None, help="Run a single source slug")
@click.option(
    "--from",
    "from_date",
    default=None,
    help="CDX cutoff (YYYY-MM-DD). Default: earliest live row for the source.",
)
@click.option(
    "--collapse",
    type=click.Choice(["day", "month", "year"]),
    default="day",
    show_default=True,
    help="CDX collapse granularity",
)
@click.option(
    "--max-snapshots-per-url",
    type=int,
    default=None,
    help="Cap snapshots fetched per URL (testing/cost control).",
)
@click.option(
    "--max-urls", type=int, default=None, help="Cap URLs processed per source."
)
@click.option(
    "--workers",
    type=int,
    default=4,
    show_default=True,
    help="Thread pool size per source.",
)
@click.option("--dry-run", is_flag=True, help="List sources + URL counts; don't fetch.")
def backfill_command(
    region,
    subregion,
    country,
    source,
    from_date,
    collapse,
    max_snapshots_per_url,
    max_urls,
    workers,
    dry_run,
):
    """Recover historical prices from the Wayback Machine."""
    manifests = _load_manifests(region, subregion, country, source)
    if not manifests:
        raise click.ClickException(
            "No matching sources. Check --region/--subregion/--country/--source."
        )

    active = [m for m in manifests if m.active]
    if not active:
        raise click.ClickException("No active sources to back-fill.")

    collapse_digits = {"day": 8, "month": 6, "year": 4}[collapse]
    cutoff = _parse_iso_date(from_date)

    plan = []
    for m in active:
        sd = _source_dir_for(m)
        n_urls = len(load_url_universe(sd))
        plan.append((m, sd, n_urls))

    for m, sd, n in plan:
        click.echo(
            f"  {m.region}/{m.subregion}/{m.country}/{m.source}  "
            f"(spider={m.spider}, urls={n})"
        )
    click.echo(f"\n{len(plan)} sources, {sum(n for _, _, n in plan)} unique URLs")

    if dry_run:
        return

    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

    for m, sd, n in plan:
        if n == 0:
            click.echo(
                f"Skipping {m.source}: no raw_items found at {sd}/raw_items/"
            )
            continue
        click.echo(f"\n=== {m.source} ({n} URLs) ===")
        run_source_backfill(
            source_dir=sd,
            spider=m.spider,
            cutoff_override=cutoff,
            collapse_digits=collapse_digits,
            max_snapshots_per_url=max_snapshots_per_url,
            max_urls=max_urls,
            workers=workers,
        )
