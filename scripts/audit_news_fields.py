"""Audit field quality of all per-source news.csv files under data/text/eca/.

Flags per source: missing/short body, missing/short title, empty/invalid URL,
empty/unparseable/future/ancient dates, duplicate URLs, and date diversity
(all-same-date = scraper bug).

Run: python scripts/audit_news_fields.py
"""
from __future__ import annotations

import argparse
import re
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import date
from pathlib import Path

import pandas as pd

DATA_ROOT = Path("/Users/avraa/iDrive/GitHub/ECA/text/pacific-observatory/data/text/eca")
URL_RE = re.compile(r"^https?://[^/\s]+/.+")
TODAY = date.today()
MIN_BODY = 50
MIN_TITLE = 10
CHUNK = 200_000


def audit_one(csv_path: Path) -> dict:
    parts = csv_path.parts
    # .../data/text/eca/<subregion>/<country>/<source>/news.csv
    src = parts[-2]
    country = parts[-3]
    subregion = parts[-4]
    stats = {
        "subregion": subregion, "country": country, "source": src,
        "path": str(csv_path),
        "rows": 0,
        "empty_url": 0, "bad_url": 0, "dup_url": 0,
        "empty_title": 0, "short_title": 0,
        "empty_body": 0, "short_body": 0,
        "empty_date": 0, "bad_date": 0, "future_date": 0, "ancient_date": 0,
        "min_date": None, "max_date": None, "unique_dates": 0,
        "error": "",
    }
    try:
        url_seen: set[str] = set()
        unique_dates: set = set()
        min_d, max_d = None, None
        for chunk in pd.read_csv(
            csv_path,
            usecols=["url", "title", "date", "body"],
            dtype=str,
            chunksize=CHUNK,
            on_bad_lines="skip",
            engine="c",
            low_memory=True,
        ):
            chunk = chunk.fillna("")
            stats["rows"] += len(chunk)

            url_len = chunk["url"].str.len()
            empty_url = (url_len == 0)
            stats["empty_url"] += int(empty_url.sum())
            bad_url = (~chunk["url"].str.match(URL_RE, na=False)) & (~empty_url)
            stats["bad_url"] += int(bad_url.sum())

            t_len = chunk["title"].str.len()
            stats["empty_title"] += int((t_len == 0).sum())
            stats["short_title"] += int(((t_len > 0) & (t_len < MIN_TITLE)).sum())

            b_len = chunk["body"].str.len()
            stats["empty_body"] += int((b_len == 0).sum())
            stats["short_body"] += int(((b_len > 0) & (b_len < MIN_BODY)).sum())

            d_len = chunk["date"].str.len()
            empty_date = (d_len == 0)
            stats["empty_date"] += int(empty_date.sum())
            d = pd.to_datetime(chunk["date"], errors="coerce", utc=False)
            bad_date = d.isna() & (~empty_date)
            stats["bad_date"] += int(bad_date.sum())
            valid_d = d.dropna()
            if len(valid_d):
                d_dates = valid_d.dt.date
                stats["future_date"] += int((d_dates > TODAY).sum())
                stats["ancient_date"] += int((valid_d.dt.year < 2000).sum())
                cur_min = d_dates.min()
                cur_max = d_dates.max()
                min_d = cur_min if min_d is None else min(min_d, cur_min)
                max_d = cur_max if max_d is None else max(max_d, cur_max)
                unique_dates.update(d_dates.unique())

            # per-source dedup
            urls = chunk["url"][~empty_url]
            for u in urls:
                if u in url_seen:
                    stats["dup_url"] += 1
                else:
                    url_seen.add(u)

        stats["min_date"] = min_d.isoformat() if min_d else None
        stats["max_date"] = max_d.isoformat() if max_d else None
        stats["unique_dates"] = len(unique_dates)
    except Exception as e:
        stats["error"] = f"{type(e).__name__}: {e}"[:200]
    return stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(DATA_ROOT))
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--out", default="outputs/text/field_audit.csv")
    args = ap.parse_args()

    root = Path(args.root)
    csvs = sorted(root.glob("*/*/*/news.csv"))
    print(f"Auditing {len(csvs)} news.csv files...", flush=True)

    results = []
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(audit_one, p): p for p in csvs}
        done = 0
        for fut in as_completed(futures):
            r = fut.result()
            results.append(r)
            done += 1
            if done % 20 == 0 or done == len(csvs):
                print(f"  {done}/{len(csvs)}  last: {r['country']}/{r['source']} rows={r['rows']:,}", flush=True)

    df = pd.DataFrame(results)
    # Derived: percentages relative to row count
    for col in ["empty_url","bad_url","dup_url","empty_title","short_title",
                "empty_body","short_body","empty_date","bad_date",
                "future_date","ancient_date"]:
        df[f"{col}_pct"] = (df[col] / df["rows"].clip(lower=1) * 100).round(2)
    df["date_diversity_pct"] = (df["unique_dates"] / df["rows"].clip(lower=1) * 100).round(2)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.sort_values(["subregion","country","source"]).to_csv(out_path, index=False)
    print(f"\nWrote {out_path}")

    # ---- Summary report ----
    total_rows = df["rows"].sum()
    print(f"\n=== TOTALS across {len(df)} sources / {total_rows:,} rows ===")
    for col in ["empty_url","bad_url","dup_url","empty_title","short_title",
                "empty_body","short_body","empty_date","bad_date",
                "future_date","ancient_date"]:
        n = int(df[col].sum())
        pct = n / max(total_rows, 1) * 100
        print(f"  {col:14s}: {n:>12,}  ({pct:5.2f}%)")

    # Worst offenders
    print("\n=== TOP 15 by empty_body_pct (>= 5% body coverage gap) ===")
    bad = df[df["empty_body_pct"] >= 5].sort_values("empty_body_pct", ascending=False).head(15)
    for _, r in bad.iterrows():
        print(f"  {r['country']:>18s}/{r['source']:<30s}  rows={r['rows']:>9,}  empty_body={r['empty_body']:>8,} ({r['empty_body_pct']}%)")

    print("\n=== TOP 15 by bad_date_pct (>= 1%) ===")
    bd = df[df["bad_date_pct"] >= 1].sort_values("bad_date_pct", ascending=False).head(15)
    for _, r in bd.iterrows():
        print(f"  {r['country']:>18s}/{r['source']:<30s}  rows={r['rows']:>9,}  bad_date={r['bad_date']:>8,} ({r['bad_date_pct']}%)")

    print("\n=== TOP 15 by future_date count ===")
    fd = df[df["future_date"] > 0].sort_values("future_date", ascending=False).head(15)
    for _, r in fd.iterrows():
        print(f"  {r['country']:>18s}/{r['source']:<30s}  future={r['future_date']:>6,}  max_date={r['max_date']}")

    print("\n=== TOP 15 by dup_url count ===")
    du = df[df["dup_url"] > 0].sort_values("dup_url", ascending=False).head(15)
    for _, r in du.iterrows():
        print(f"  {r['country']:>18s}/{r['source']:<30s}  dup={r['dup_url']:>8,}  ({r['dup_url_pct']}%)")

    print("\n=== SOURCES with date_diversity_pct < 0.01 (all rows same/few dates) ===")
    nd = df[(df["rows"] > 100) & (df["date_diversity_pct"] < 0.01)].sort_values("rows", ascending=False).head(15)
    for _, r in nd.iterrows():
        print(f"  {r['country']:>18s}/{r['source']:<30s}  rows={r['rows']:>8,}  unique_dates={r['unique_dates']}  range={r['min_date']}..{r['max_date']}")

    err = df[df["error"] != ""]
    if len(err):
        print(f"\n=== ERRORS ({len(err)}) ===")
        for _, r in err.iterrows():
            print(f"  {r['country']}/{r['source']}: {r['error']}")


if __name__ == "__main__":
    main()
