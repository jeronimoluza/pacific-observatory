"""Temporal coverage statistics over the archived-price backlog.

The backfill writes one file per (url, snapshot) into two trees with different
shapes -- Common Crawl's ``common_crawl_data/items/<hash>.json`` and Wayback's
``wayback_items/*.jsonl`` -- so "how deep is our history" is not answerable by
counting rows in either one alone. This walks both, normalises them to
``(country, source, url, snapshot_date)``, and reports how far back each source
reaches and how often it is re-observed.

Cadence is reported two ways because they answer different questions. The
per-source gap is the spacing of *any* observation, which says how often the
storefront appears in an archive at all. The per-url gap is the spacing of
repeat observations of the *same product*, which is what decides whether a
price series exists rather than a scatter of unrelated points -- a source can
have 25 snapshot dates and still yield no series if each crawl caught a
disjoint set of URLs.

Outputs are timestamped, never overwritten: the point is to re-run this as the
backfill progresses and compare.
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterator, List, Tuple

Row = Tuple[str, str, str, str, str, str, str]
_COLUMNS = ["region", "subregion", "country", "source", "archive", "url", "snapshot"]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _snapshot_date(stamp: str) -> str:
    """``20240712184207`` (or an ISO string) -> ``2024-07-12``."""
    digits = "".join(ch for ch in str(stamp) if ch.isdigit())
    if len(digits) >= 8:
        return f"{digits[0:4]}-{digits[4:6]}-{digits[6:8]}"
    return ""


def _iter_cc(root: Path) -> Iterator[Row]:
    for items in root.glob("*/*/*/*/common_crawl_data/items"):
        region, subregion, country, source = items.parts[-6:-2]
        for path in items.glob("*.json"):
            try:
                rec = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            day = _snapshot_date(rec.get("cc_timestamp", ""))
            if day:
                yield (
                    region,
                    subregion,
                    country,
                    source,
                    "common_crawl",
                    rec.get("url", ""),
                    day,
                )


def _iter_wayback(root: Path) -> Iterator[Row]:
    for items in root.glob("*/*/*/*/wayback_items"):
        region, subregion, country, source = items.parts[-5:-1]
        for path in items.glob("*.jsonl"):
            try:
                handle = path.open(encoding="utf-8")
            except OSError:
                continue
            with handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except ValueError:
                        continue
                    day = _snapshot_date(
                        rec.get("wayback_timestamp") or rec.get("scraped_at_utc") or ""
                    )
                    if day:
                        yield (
                            region,
                            subregion,
                            country,
                            source,
                            "wayback",
                            rec.get("url", ""),
                            day,
                        )


def _median_gap(days: List[str]) -> float:
    """Median spacing, in days, between consecutive distinct dates."""
    uniq = sorted(set(days))
    if len(uniq) < 2:
        return float("nan")
    stamps = [datetime.strptime(d, "%Y-%m-%d") for d in uniq]
    gaps = [(b - a).days for a, b in zip(stamps, stamps[1:])]
    return float(statistics.median(gaps))


def summarise(rows: Iterator[Row]) -> Tuple[List[dict], List[dict]]:
    """Collapse raw observations into per-source and per-source-month tables."""
    dates: Dict[tuple, List[str]] = defaultdict(list)
    per_url: Dict[tuple, Dict[str, List[str]]] = defaultdict(lambda: defaultdict(list))
    months: Dict[tuple, Dict[str, set]] = defaultdict(lambda: defaultdict(set))
    counts: Dict[tuple, int] = defaultdict(int)
    month_obs: Dict[tuple, int] = defaultdict(int)

    for region, subregion, country, source, archive, url, day in rows:
        key = (region, subregion, country, source, archive)
        counts[key] += 1
        dates[key].append(day)
        per_url[key][url].append(day)
        months[key][day[:7]].add(url)
        month_obs[(key, day[:7])] += 1

    source_rows: List[dict] = []
    month_rows: List[dict] = []
    for key, n_obs in sorted(counts.items()):
        region, subregion, country, source, archive = key
        day_list = dates[key]
        urls = per_url[key]
        repeat = [u for u, ds in urls.items() if len(set(ds)) > 1]
        url_gaps = [_median_gap(ds) for ds in urls.values() if len(set(ds)) > 1]
        first, last = min(day_list), max(day_list)
        span = (
            datetime.strptime(last, "%Y-%m-%d") - datetime.strptime(first, "%Y-%m-%d")
        ).days
        source_rows.append(
            {
                "region": region,
                "subregion": subregion,
                "country": country,
                "source": source,
                "archive": archive,
                "n_obs": n_obs,
                "n_urls": len(urls),
                "n_snapshot_dates": len(set(day_list)),
                "first_snapshot": first,
                "last_snapshot": last,
                "span_days": span,
                "median_source_gap_days": _median_gap(day_list),
                "n_urls_repeat_observed": len(repeat),
                "pct_urls_repeat_observed": round(100 * len(repeat) / len(urls), 1),
                "median_url_revisit_days": (
                    round(statistics.median(url_gaps), 1) if url_gaps else float("nan")
                ),
            }
        )
        for month, url_set in sorted(months[key].items()):
            month_rows.append(
                {
                    "region": region,
                    "country": country,
                    "source": source,
                    "archive": archive,
                    "month": month,
                    "n_obs": month_obs[(key, month)],
                    "n_urls": len(url_set),
                }
            )
    return source_rows, month_rows


def _write(rows: List[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        import pandas as pd

        pd.DataFrame(rows).to_parquet(path.with_suffix(".parquet"), index=False)
    except ImportError:
        pass
    with path.with_suffix(".jsonl").open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", type=Path, default=None)
    parser.add_argument("--out-dir", type=Path, default=None)
    parser.add_argument(
        "--archive",
        choices=["common_crawl", "wayback", "both"],
        default="both",
    )
    args = parser.parse_args()

    root = args.data_root or (_repo_root() / "data" / "prices")
    out_dir = args.out_dir or (root / "_build" / "archive_coverage")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    def _rows() -> Iterator[Row]:
        if args.archive in ("common_crawl", "both"):
            yield from _iter_cc(root)
        if args.archive in ("wayback", "both"):
            yield from _iter_wayback(root)

    source_rows, month_rows = summarise(_rows())
    _write(source_rows, out_dir / f"by_source_{stamp}")
    _write(month_rows, out_dir / f"by_source_month_{stamp}")

    print(f"{len(source_rows)} source/archive pairs -> {out_dir}\n")
    header = (
        f"{'source':26} {'country':16} {'arch':6} {'obs':>7} {'urls':>7} "
        f"{'snaps':>6} {'first':10} {'last':10} {'rpt%':>5} {'revisit_d':>9}"
    )
    print(header)
    for row in sorted(source_rows, key=lambda r: -r["n_obs"]):
        revisit = row["median_url_revisit_days"]
        print(
            f"{row['source'][:26]:26} {row['country'][:16]:16} "
            f"{row['archive'][:6]:6} {row['n_obs']:7} {row['n_urls']:7} "
            f"{row['n_snapshot_dates']:6} {row['first_snapshot']:10} "
            f"{row['last_snapshot']:10} {row['pct_urls_repeat_observed']:5} "
            f"{'-' if revisit != revisit else f'{revisit:9.0f}'}"
        )


if __name__ == "__main__":
    main()
