"""Title-only backfill for huge sources where full rebuild is impractical.
Fetches og:title / <title> from each article URL and updates news.csv in place.
Skips rows where title is already non-URL (already correct).
"""
import argparse
import csv
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def fetch_title(url: str, client: httpx.Client, retries: int = 3) -> str | None:
    """Fetch og:title with retries on timeouts/connection errors. Returns None
    only if all retries fail or the response has no usable title."""
    for attempt in range(retries):
        try:
            r = client.get(url, timeout=30, follow_redirects=True)
            if r.status_code != 200:
                if r.status_code in (429, 503) and attempt < retries - 1:
                    import time as _t; _t.sleep(2 ** attempt)
                    continue
                return None
            soup = BeautifulSoup(r.text, "html.parser")
            og = soup.find("meta", attrs={"property": "og:title"})
            if og and og.get("content"):
                return og["content"].strip()
            h1 = soup.find("h1")
            if h1:
                t = h1.get_text(strip=True)
                if t:
                    return t
            t = soup.find("title")
            if t:
                return t.get_text(strip=True)
            return None
        except (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError, httpx.RemoteProtocolError):
            if attempt < retries - 1:
                import time as _t; _t.sleep(1 + attempt)
                continue
            return None
        except Exception:
            return None
    return None


def is_url_title(t) -> bool:
    if t is None:
        return True
    s = str(t).strip()
    return s.startswith(("http://", "https://")) or s == "" or s == "nan"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv_path", help="Path to news.csv to backfill")
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--limit", type=int, default=None, help="Debug: only backfill N rows")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    p = Path(args.csv_path)
    if not p.exists():
        sys.exit(f"not found: {p}")

    # Load rows with csv module to preserve everything exactly
    with p.open() as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames
    if "title" not in fieldnames or "url" not in fieldnames:
        sys.exit(f"csv missing required columns: have {fieldnames}")

    total = len(rows)
    targets = [i for i, r in enumerate(rows) if is_url_title(r.get("title"))]
    print(f"[{p}] total={total:,}  to_backfill={len(targets):,}  ({100*len(targets)/max(1,total):.1f}%)", flush=True)
    if args.limit:
        targets = targets[: args.limit]
        print(f"  limited to first {len(targets):,}", flush=True)

    if not targets:
        print("nothing to do"); return
    if args.dry_run:
        print("dry-run; exiting")
        return

    updated = 0
    failed = 0
    start = time.time()
    last_save = start
    last_progress = start

    with httpx.Client(headers=HEADERS, follow_redirects=True) as client:
        with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            futures = {pool.submit(fetch_title, rows[i]["url"], client): i for i in targets}
            done = 0
            for fut in as_completed(futures):
                i = futures[fut]
                done += 1
                title = fut.result()
                if title:
                    rows[i]["title"] = title
                    updated += 1
                else:
                    failed += 1
                now = time.time()
                # Progress every 30s
                if now - last_progress > 30:
                    rate = done / (now - start)
                    eta = (len(targets) - done) / max(0.01, rate)
                    print(f"  {done:,}/{len(targets):,} ({100*done/len(targets):.1f}%)  "
                          f"updated={updated:,}  failed={failed:,}  "
                          f"rate={rate:.1f}/s  eta={eta/60:.0f}m", flush=True)
                    last_progress = now
                # Checkpoint save every 5 min
                if now - last_save > 300:
                    tmp = p.with_suffix(".csv.tmp")
                    with tmp.open("w", newline="") as f:
                        w = csv.DictWriter(f, fieldnames=fieldnames)
                        w.writeheader()
                        w.writerows(rows)
                    tmp.replace(p)
                    print(f"  checkpointed at {done:,}/{len(targets):,}", flush=True)
                    last_save = now

    # Final save
    tmp = p.with_suffix(".csv.tmp")
    with tmp.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    tmp.replace(p)
    dur = time.time() - start
    print(f"[{p}] DONE  updated={updated:,}  failed={failed:,}  "
          f"duration={dur/60:.1f}m", flush=True)


if __name__ == "__main__":
    main()
