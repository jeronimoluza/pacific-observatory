"""Date-only backfill for sources whose existing news.csv has wrong/stuck dates.

Reads the matching YAML config to find the article date selector, refetches each
URL, and updates the date field in news.csv in place with atomic checkpointing.

By default only re-fetches rows whose existing date matches `--broken-dates`
(comma-separated YYYY-MM-DD). Use `--all` to re-fetch every row.

Usage:
  python scripts/backfill_dates.py data/text/eca/.../musavat/news.csv \
      --broken-dates 2026-04-23
"""
from __future__ import annotations

import argparse
import csv
import logging
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import httpx
import yaml
from bs4 import BeautifulSoup

logging.getLogger("src.text.scrapers.pipelines.cleaning.common").setLevel(logging.ERROR)

ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
CURRENT_YEAR = datetime.now().year

# qalampir.uz mashes the date together with view counter and read-time inside
# the same <p>, e.g. "13 Февральvisibility16706timer1 дақиқа". Strip the
# visibility/timer suffix before passing to handle_mixed_dates so strptime
# patterns can match.
_QALAMPIR_NOISE = re.compile(r"\s*visibility\s*\d+\s*timer\s*\d+\s*\S+(\s+\S+)?\s*$",
                              re.IGNORECASE)

# Add src/ to path for importing the cleaner
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from src.text.scrapers.pipelines.cleaning.common import handle_mixed_dates  # noqa: E402

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Allow per-source CSV field size (some bodies > default 128KB limit)
csv.field_size_limit(sys.maxsize)


def parse_selector(sel: str):
    """Return (base_selector, mode, attr_name)."""
    if sel.endswith("::text"):
        return sel[:-6].strip(), "text", None
    if "::attr(" in sel:
        prefix, suffix = sel.split("::attr(", 1)
        return prefix.strip(), "attr", suffix.rstrip(")")
    return sel.strip(), "elements", None


def yaml_for_csv(csv_path: Path) -> Path:
    # data/text/eca/<subregion>/<country>/<source>/news.csv
    #   -> src/text/configs/eca/<subregion>/<country>/<source>.yaml
    parts = list(csv_path.parts)
    try:
        i = parts.index("data")
        j = parts.index("eca", i)
    except ValueError:
        raise SystemExit(f"cannot derive YAML path from {csv_path}")
    rel = parts[j + 1:-1]  # [<subregion>, <country>, <source>]
    # Don't use with_suffix — sources like "qalampir.uz" have a dot in the name
    return REPO / "src" / "text" / "configs" / "eca" / Path(*rel[:-1]) / f"{rel[-1]}.yaml"


def load_date_selector(yaml_path: Path) -> str:
    with yaml_path.open() as f:
        cfg = yaml.safe_load(f)
    sel = cfg.get("selectors", {}).get("article", {}).get("date")
    if not sel:
        raise SystemExit(f"no article.date selector in {yaml_path}")
    return sel


def _try_clean(raw: str) -> str | None:
    """Return ISO date or None. Tries raw, then raw + current year for sites
    that omit the year on this-year articles (e.g. qalampir 'Февраль 13')."""
    if not raw:
        return None
    pre = _QALAMPIR_NOISE.sub("", raw).strip()
    cleaned = handle_mixed_dates(pre)
    if cleaned and ISO_DATE.match(cleaned):
        return cleaned
    cleaned2 = handle_mixed_dates(f"{pre} {CURRENT_YEAR}")
    if cleaned2 and ISO_DATE.match(cleaned2):
        return cleaned2
    return None


def fetch_date(url: str, client: httpx.Client, base_sel: str, mode: str,
               attr_name: str | None, retries: int = 2,
               request_timeout: float = 10.0,
               delay: float = 0.0) -> str | None:
    if delay > 0:
        time.sleep(delay)
    for attempt in range(retries):
        try:
            r = client.get(url, timeout=request_timeout, follow_redirects=True)
            if r.status_code != 200:
                if r.status_code in (429, 503) and attempt < retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                return None
            soup = BeautifulSoup(r.text, "html.parser")
            elem = soup.select_one(base_sel)
            if not elem:
                return None
            if mode == "text":
                raw = elem.get_text(strip=True)
            elif mode == "attr":
                raw = elem.get(attr_name) or ""
            else:
                raw = elem.get_text(strip=True)
            return _try_clean(raw)
        except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError,
                httpx.RemoteProtocolError):
            if attempt < retries - 1:
                time.sleep(0.5)
                continue
            return None
        except Exception:
            return None
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv_path")
    ap.add_argument("--broken-dates", default="",
                    help="comma-separated YYYY-MM-DD values to consider broken")
    ap.add_argument("--all", action="store_true",
                    help="re-fetch every row regardless of current date")
    ap.add_argument("--concurrency", type=int, default=3,
                    help="match the source's YAML concurrency (default 3)")
    ap.add_argument("--delay", type=float, default=0.0,
                    help="per-request sleep in seconds to throttle (default 0)")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    csv_path = Path(args.csv_path).resolve()
    if not csv_path.exists():
        sys.exit(f"not found: {csv_path}")

    yaml_path = yaml_for_csv(csv_path)
    if not yaml_path.exists():
        sys.exit(f"yaml not found: {yaml_path}")
    sel = load_date_selector(yaml_path)
    base_sel, mode, attr_name = parse_selector(sel)
    print(f"[{csv_path.name}] yaml={yaml_path.name}  selector={sel!r}  "
          f"mode={mode}  base={base_sel!r}  attr={attr_name}", flush=True)

    broken = {d.strip() for d in args.broken_dates.split(",") if d.strip()}
    if not args.all and not broken:
        sys.exit("specify --broken-dates or --all")

    with csv_path.open() as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames
    if "date" not in fieldnames or "url" not in fieldnames:
        sys.exit(f"csv missing required cols: have {fieldnames}")

    total = len(rows)
    if args.all:
        targets = list(range(total))
    else:
        targets = [i for i, r in enumerate(rows) if (r.get("date") or "").strip() in broken]
    print(f"[{csv_path.name}] total={total:,}  to_backfill={len(targets):,}  "
          f"({100*len(targets)/max(1,total):.1f}%)", flush=True)
    if args.limit:
        targets = targets[: args.limit]
        print(f"  limited to first {len(targets):,}", flush=True)
    if not targets:
        print("nothing to do"); return
    if args.dry_run:
        print("dry-run; exiting"); return

    updated = unchanged = failed = 0
    start = last_save = last_progress = time.time()

    with httpx.Client(headers=HEADERS, follow_redirects=True) as client:
        with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            futures = {
                pool.submit(fetch_date, rows[i]["url"], client, base_sel, mode,
                            attr_name, delay=args.delay): i
                for i in targets
            }
            done = 0
            for fut in as_completed(futures):
                i = futures[fut]
                done += 1
                new_date = fut.result()
                if new_date:
                    if new_date != (rows[i].get("date") or "").strip():
                        rows[i]["date"] = new_date
                        updated += 1
                    else:
                        unchanged += 1
                else:
                    failed += 1
                now = time.time()
                if now - last_progress > 30:
                    rate = done / (now - start)
                    eta_m = (len(targets) - done) / max(0.01, rate) / 60
                    print(f"  {done:,}/{len(targets):,} ({100*done/len(targets):.1f}%)  "
                          f"updated={updated:,}  unchanged={unchanged:,}  failed={failed:,}  "
                          f"rate={rate:.1f}/s  eta={eta_m:.0f}m", flush=True)
                    last_progress = now
                if now - last_save > 300:
                    tmp = csv_path.with_suffix(".csv.tmp")
                    with tmp.open("w", newline="") as f:
                        w = csv.DictWriter(f, fieldnames=fieldnames)
                        w.writeheader()
                        w.writerows(rows)
                    tmp.replace(csv_path)
                    print(f"  checkpointed at {done:,}/{len(targets):,}", flush=True)
                    last_save = now

    tmp = csv_path.with_suffix(".csv.tmp")
    with tmp.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    tmp.replace(csv_path)
    dur = time.time() - start
    print(f"[{csv_path.name}] DONE  updated={updated:,}  unchanged={unchanged:,}  "
          f"failed={failed:,}  duration={dur/60:.1f}m", flush=True)


if __name__ == "__main__":
    main()
