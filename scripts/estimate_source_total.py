#!/usr/bin/env python3
"""
Estimate the total number of articles a scraper config should discover.

Usage:
    poetry run python scripts/estimate_source_total.py <config.yaml> [...]

Strategy handlers:
    api (WordPress): HEAD request → X-WP-Total header
    api (Ghost):     GET /posts?limit=1 → meta.pagination.total
    api (generic):   prints total field from json_paths if present
    sitemap:         fetches sitemap_index, then every matched sub-sitemap,
                     counts <loc> entries matching url_regex
    archive / paginated_archive:
                     samples one day mid-range and multiplies by day count
    pagination:      not estimable cheaply — prints a warning
"""

from __future__ import annotations

import gzip
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import httpx
import yaml
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
}


def fetch(url: str) -> bytes:
    r = httpx.get(url, headers=HEADERS, timeout=30, follow_redirects=True)
    content = r.content
    if content[:2] == b"\x1f\x8b":
        content = gzip.decompress(content)
    return content


def estimate_api(cfg: dict) -> str:
    url = cfg["listing"]["url_template"]
    sample_url = url.format(page=1, offset=0, size=1)

    if "/wp-json/" in sample_url:
        r = httpx.head(sample_url.replace("per_page=100", "per_page=1"), headers=HEADERS, timeout=15)
        total = r.headers.get("x-wp-total")
        return f"WordPress API total = {total}"

    if "/ghost/api/" in sample_url:
        r = httpx.get(sample_url.replace("limit=100", "limit=1"), headers=HEADERS, timeout=15)
        total = json.loads(r.text)["meta"]["pagination"]["total"]
        return f"Ghost API total = {total}"

    return "Custom API — fetch page 1 and inspect response manually"


def estimate_sitemap(cfg: dict) -> str:
    listing = cfg["listing"]
    sm_rx = re.compile(listing["sitemap_regex"]) if listing.get("sitemap_regex") else None
    url_rx = re.compile(listing["url_regex"]) if listing.get("url_regex") else None

    idx = fetch(listing["sitemap_index_url"]).decode("utf-8", errors="replace")
    subs = [l.get_text(strip=True) for l in BeautifulSoup(idx, "html.parser").select("sitemap loc")]
    if sm_rx:
        subs = [u for u in subs if sm_rx.search(u)]

    print(f"  scanning {len(subs)} sub-sitemaps...", file=sys.stderr)
    total = 0
    for i, u in enumerate(subs, 1):
        try:
            body = fetch(u).decode("utf-8", errors="replace")
            locs = BeautifulSoup(body, "html.parser").select("url loc")
            if url_rx:
                locs = [l for l in locs if url_rx.search(l.get_text(strip=True))]
            total += len(locs)
            if i % 10 == 0 or i == len(subs):
                print(f"    [{i}/{len(subs)}] running total={total:,}", file=sys.stderr)
        except Exception as e:
            print(f"    {u}: ERROR {e}", file=sys.stderr)
    return f"{len(subs)} sub-sitemaps → {total:,} URLs (after url_regex filter)"


def estimate_archive(cfg: dict) -> str:
    listing = cfg["listing"]
    start = datetime.strptime(listing["start_date"], "%Y-%m-%d")
    end_str = listing.get("end_date")
    end = datetime.strptime(end_str, "%Y-%m-%d") if end_str else datetime.now()

    fmt = listing.get("date_format", "daily")
    if fmt == "daily":
        units = (end - start).days
    elif fmt == "monthly":
        units = (end.year - start.year) * 12 + (end.month - start.month)
    else:
        return "range mode — estimate manually"

    # Sample mid-range day/month
    mid = start + (end - start) / 2
    sample_url = listing["url_template"].format(
        year=mid.year, month=f"{mid.month:02d}", day=f"{mid.day:02d}"
    )
    try:
        body = fetch(sample_url).decode("utf-8", errors="replace")
        container = cfg["selectors"]["thumbnail"]["container"]
        cards = len(BeautifulSoup(body, "html.parser").select(container))
    except Exception as e:
        return f"Could not sample mid-date: {e}"
    return (
        f"{units} {'days' if fmt=='daily' else 'months'} in range, "
        f"~{cards} articles on sampled {fmt[:-2]} ({mid.date()}) → "
        f"≈ {units * cards:,} total (rough)"
    )


def estimate(path: Path) -> None:
    cfg = yaml.safe_load(open(path))
    t = cfg.get("listing", {}).get("type")
    name = cfg.get("name", path.stem)
    print(f"\n{name} [{t}]")
    try:
        if t == "api":
            print(f"  {estimate_api(cfg)}")
        elif t == "sitemap":
            print(f"  {estimate_sitemap(cfg)}")
        elif t in ("archive", "paginated_archive"):
            print(f"  {estimate_archive(cfg)}")
        else:
            print(f"  {t}: no cheap estimator (would need to crawl pagination)")
    except Exception as e:
        print(f"  ERROR: {e}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: estimate_source_total.py <config.yaml> [...]")
        sys.exit(1)
    for arg in sys.argv[1:]:
        estimate(Path(arg))
