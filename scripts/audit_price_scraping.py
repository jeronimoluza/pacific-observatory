"""Audit data/cpi/price_scraping/ — count retailers, items, date ranges per country & retailer.

Walks data/cpi/price_scraping/<country>/<retailer>/raw_items/*.jsonl and reports:
  - per retailer: lifetime unique URLs, latest-run item count, first/last scrape date, n files
  - per country: retailer count, summed totals, country-wide date range
Writes two CSVs and prints summary tables to stdout.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DATA_DIR = Path("data/cpi/price_scraping")
DEFAULT_OUTPUT_DIR = Path("outputs/cpi/price_scraping")
FILENAME_TS_RE = re.compile(r"_(\d{8})_(\d{6})\.jsonl$")
DEFAULT_STALE_DAYS = 3
OVERRIDES_FILENAME = "retailer_status_overrides.csv"


@dataclass
class RetailerStats:
    country: str
    retailer: str
    n_unique_urls_lifetime: int = 0
    n_items_latest_run: int = 0
    observations_count: int = 0
    first_scrape_date: str = ""
    last_scrape_date: str = ""
    n_files: int = 0
    n_bad_lines: int = 0
    status: str = ""


def parse_filename_timestamp(path: Path) -> datetime | None:
    m = FILENAME_TS_RE.search(path.name)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        return None


def parse_iso_utc(s: str) -> datetime | None:
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def audit_retailer(
    country: str, retailer: str, retailer_dir: Path
) -> RetailerStats | None:
    raw_dir = retailer_dir / "raw_items"
    if not raw_dir.is_dir():
        return None
    files = sorted(raw_dir.glob("*.jsonl"))
    if not files:
        return RetailerStats(country=country, retailer=retailer)

    files_with_ts = [
        (parse_filename_timestamp(f) or datetime.min.replace(tzinfo=timezone.utc), f)
        for f in files
    ]
    files_with_ts.sort()
    latest_file = files_with_ts[-1][1]

    seen_url_hashes: set[str] = set()
    min_dt: datetime | None = None
    max_dt: datetime | None = None
    n_bad = 0
    n_latest = 0
    n_observations = 0

    for _, f in files_with_ts:
        file_fallback_dt = parse_filename_timestamp(f)
        is_latest = f == latest_file
        with f.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    n_bad += 1
                    continue
                n_observations += 1
                if is_latest:
                    n_latest += 1
                h = rec.get("url_hash")
                if h:
                    seen_url_hashes.add(h)
                dt = parse_iso_utc(rec.get("scraped_at_utc", "")) or file_fallback_dt
                if dt is not None:
                    if min_dt is None or dt < min_dt:
                        min_dt = dt
                    if max_dt is None or dt > max_dt:
                        max_dt = dt

    return RetailerStats(
        country=country,
        retailer=retailer,
        n_unique_urls_lifetime=len(seen_url_hashes),
        n_items_latest_run=n_latest,
        observations_count=n_observations,
        first_scrape_date=min_dt.date().isoformat() if min_dt else "",
        last_scrape_date=max_dt.date().isoformat() if max_dt else "",
        n_files=len(files),
        n_bad_lines=n_bad,
    )


def walk_data_dir(data_dir: Path) -> list[RetailerStats]:
    rows: list[RetailerStats] = []
    if not data_dir.is_dir():
        sys.exit(f"error: data directory not found: {data_dir}")
    for country_dir in sorted(p for p in data_dir.iterdir() if p.is_dir()):
        for retailer_dir in sorted(p for p in country_dir.iterdir() if p.is_dir()):
            stats = audit_retailer(country_dir.name, retailer_dir.name, retailer_dir)
            if stats is None:
                print(
                    f"warn: no raw_items/ in {country_dir.name}/{retailer_dir.name}",
                    file=sys.stderr,
                )
                continue
            rows.append(stats)
    return rows


def load_status_overrides(path: Path) -> dict[tuple[str, str], str]:
    if not path.is_file():
        return {}
    out: dict[tuple[str, str], str] = {}
    with path.open("r", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            country = (row.get("country") or "").strip()
            retailer = (row.get("retailer") or "").strip()
            status = (row.get("status") or "").strip()
            if country and retailer and status:
                out[(country, retailer)] = status
    return out


def assign_status(
    rows: list[RetailerStats],
    stale_days: int,
    overrides: dict[tuple[str, str], str],
    today: datetime,
) -> None:
    cutoff = today.date()
    for r in rows:
        last = parse_iso_utc(r.last_scrape_date)
        is_stale = last is None or (cutoff - last.date()).days > stale_days
        if not is_stale:
            r.status = "active"
        else:
            r.status = overrides.get((r.country, r.retailer), "stale_unchecked")


def country_rollup(rows: list[RetailerStats]) -> list[dict]:
    by_country: dict[str, list[RetailerStats]] = {}
    for r in rows:
        by_country.setdefault(r.country, []).append(r)
    out = []
    for country, items in sorted(by_country.items()):
        dates = [
            d for r in items for d in (r.first_scrape_date, r.last_scrape_date) if d
        ]
        out.append(
            {
                "country": country,
                "n_retailers": len(items),
                "total_unique_urls": sum(r.n_unique_urls_lifetime for r in items),
                "total_items_latest_run": sum(r.n_items_latest_run for r in items),
                "observations_count": sum(r.observations_count for r in items),
                "first_scrape_date": min(dates) if dates else "",
                "last_scrape_date": max(dates) if dates else "",
            }
        )
    return out


def write_retailer_csv(rows: list[RetailerStats], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(
            [
                "country",
                "retailer",
                "n_unique_urls_lifetime",
                "n_items_latest_run",
                "observations_count",
                "first_scrape_date",
                "last_scrape_date",
                "n_files",
                "status",
            ]
        )
        for r in rows:
            w.writerow(
                [
                    r.country,
                    r.retailer,
                    r.n_unique_urls_lifetime,
                    r.n_items_latest_run,
                    r.observations_count,
                    r.first_scrape_date,
                    r.last_scrape_date,
                    r.n_files,
                    r.status,
                ]
            )


def write_country_csv(country_rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(
            fh,
            fieldnames=[
                "country",
                "n_retailers",
                "total_unique_urls",
                "total_items_latest_run",
                "observations_count",
                "first_scrape_date",
                "last_scrape_date",
            ],
        )
        w.writeheader()
        w.writerows(country_rows)


def print_tables(retailer_rows: list[RetailerStats], country_rows: list[dict]) -> None:
    try:
        from rich.console import Console
        from rich.table import Table
    except ImportError:
        _print_plain(retailer_rows, country_rows)
        return

    console = Console()

    country_cols = [
        "country",
        "n_retailers",
        "total_unique_urls",
        "total_items_latest_run",
        "observations_count",
        "first_scrape_date",
        "last_scrape_date",
    ]
    t1 = Table(title="Country summary", show_lines=False)
    for col in country_cols:
        t1.add_column(
            col, justify="right" if col.startswith(("n_", "total_")) else "left"
        )
    for r in country_rows:
        t1.add_row(*[str(r[c]) for c in country_cols])
    console.print(t1)

    t2 = Table(title="Retailer summary", show_lines=False)
    for col in [
        "country",
        "retailer",
        "n_unique_urls_lifetime",
        "n_items_latest_run",
        "observations_count",
        "first_scrape_date",
        "last_scrape_date",
        "n_files",
        "status",
    ]:
        t2.add_column(
            col,
            justify="right" if col.startswith(("n_", "total_", "observ")) else "left",
        )
    for r in retailer_rows:
        t2.add_row(
            r.country,
            r.retailer,
            str(r.n_unique_urls_lifetime),
            str(r.n_items_latest_run),
            str(r.observations_count),
            r.first_scrape_date,
            r.last_scrape_date,
            str(r.n_files),
            r.status,
        )
    console.print(t2)


def _print_plain(retailer_rows: list[RetailerStats], country_rows: list[dict]) -> None:
    print("\n=== Country summary ===")
    cols = [
        "country",
        "n_retailers",
        "total_unique_urls",
        "total_items_latest_run",
        "observations_count",
        "first_scrape_date",
        "last_scrape_date",
    ]
    print("\t".join(cols))
    for r in country_rows:
        print("\t".join(str(r[c]) for c in cols))
    print("\n=== Retailer summary ===")
    rcols = [
        "country",
        "retailer",
        "n_unique_urls_lifetime",
        "n_items_latest_run",
        "observations_count",
        "first_scrape_date",
        "last_scrape_date",
        "n_files",
        "status",
    ]
    print("\t".join(rcols))
    for r in retailer_rows:
        print(
            "\t".join(
                [
                    r.country,
                    r.retailer,
                    str(r.n_unique_urls_lifetime),
                    str(r.n_items_latest_run),
                    str(r.observations_count),
                    r.first_scrape_date,
                    r.last_scrape_date,
                    str(r.n_files),
                    r.status,
                ]
            )
        )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    ap.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    ap.add_argument("--no-write", action="store_true", help="skip writing CSVs")
    ap.add_argument("--quiet", action="store_true", help="skip stdout tables")
    ap.add_argument(
        "--stale-days",
        type=int,
        default=DEFAULT_STALE_DAYS,
        help=f"days since last_scrape after which a retailer is stale (default: {DEFAULT_STALE_DAYS})",
    )
    args = ap.parse_args()

    all_rows = walk_data_dir(args.data_dir)
    skipped = [r for r in all_rows if not (r.first_scrape_date and r.last_scrape_date)]
    retailer_rows = [r for r in all_rows if r.first_scrape_date and r.last_scrape_date]

    overrides = load_status_overrides(args.output_dir / OVERRIDES_FILENAME)
    assign_status(retailer_rows, args.stale_days, overrides, datetime.now(timezone.utc))

    country_rows = country_rollup(retailer_rows)
    if skipped:
        names = ", ".join(f"{r.country}/{r.retailer}" for r in skipped)
        print(
            f"info: excluded {len(skipped)} retailers with no scrape dates: {names}",
            file=sys.stderr,
        )

    bad_total = sum(r.n_bad_lines for r in all_rows)
    if bad_total:
        print(f"warn: skipped {bad_total} malformed JSONL lines", file=sys.stderr)

    if not args.no_write:
        write_retailer_csv(retailer_rows, args.output_dir / "retailer_summary.csv")
        write_country_csv(country_rows, args.output_dir / "country_summary.csv")
        print(f"wrote {args.output_dir/'retailer_summary.csv'}", file=sys.stderr)
        print(f"wrote {args.output_dir/'country_summary.csv'}", file=sys.stderr)

    if not args.quiet:
        print_tables(retailer_rows, country_rows)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
