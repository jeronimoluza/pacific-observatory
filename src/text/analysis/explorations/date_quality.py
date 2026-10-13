"""Article-date quality per source, before trusting daily or weekly series.

Three symptoms of a date that is not the publication date:

- day-1 excess: month-only dates parse to the 1st, so the 1st carries far
  more than 1/30 of a source's articles.
- scrape stamping: a scrape run that saved many articles all dated on the
  scrape day (live scraping legitimately dates some articles that day; a
  backfill should not).
- spikes: a single day holding a large share of a source's articles.

Reads each source's news.csv (date and _scraped_at only, but the whole file
is parsed). Writes a CSV and prints the flagged sources.

Run: python src/text/analysis/explorations/date_quality.py --region ssa
"""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
DATA = ROOT / "data" / "text"
REPORT_DIR = ROOT / "outputs" / "text" / "reports" / "concepts-exploration-pdfs"

MIN_ARTICLES = 200
BATCH = 50  # articles in one scrape day to count as a batch
DAY1_FLAG = 0.15  # 1st of month share (uniform is about 0.033)
STAMP_FLAG = 0.5  # share of batch-scraped articles dated on the scrape day
SPIKE_FLAG = 0.05  # share of all articles on the single biggest day


def check(news_csv: Path) -> dict | None:
    cols = pd.read_csv(news_csv, nrows=0).columns
    use = [c for c in ("date", "_scraped_at") if c in cols]
    if "date" not in use:
        return None
    try:
        df = pd.read_csv(news_csv, usecols=use, on_bad_lines="skip")
    except (ValueError, pd.errors.ParserError):
        return None
    d = pd.to_datetime(
        df["date"], errors="coerce", format="mixed", utc=True
    ).dt.tz_localize(None)
    df = df.assign(day=d.dt.normalize()).dropna(subset=["day"])
    df = df[(df.day >= "2015-01-01") & (df.day <= pd.Timestamp.today())]
    n = len(df)
    if n < MIN_ARTICLES:
        return None
    per_day = df.day.value_counts()
    out = {
        "source": f"{news_csv.parent.parent.name}/{news_csv.parent.name}",
        "articles": n,
        "first": df.day.min().date(),
        "last": df.day.max().date(),
        "day1_share": float((df.day.dt.day == 1).mean()),
        "top_day": per_day.index[0].date(),
        "top_day_share": float(per_day.iloc[0] / n),
        "stamp_share": float("nan"),
    }
    if "_scraped_at" in df:
        s = pd.to_datetime(df["_scraped_at"], errors="coerce", format="mixed", utc=True)
        df = df.assign(scrape_day=s.dt.tz_localize(None).dt.normalize())
        size = df.groupby("scrape_day").day.transform("size")
        batch = df[size >= BATCH]
        if len(batch):
            out["stamp_share"] = float((batch.day == batch.scrape_day).mean())
    out["flag"] = ",".join(
        f
        for f, hit in (
            ("day1", out["day1_share"] > DAY1_FLAG),
            ("stamp", out["stamp_share"] > STAMP_FLAG),
            ("spike", out["top_day_share"] > SPIKE_FLAG),
        )
        if hit
    )
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--region", default="ssa")
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    files = sorted((DATA / args.region).glob("*/*/*/news.csv"))
    with ProcessPoolExecutor(args.workers) as pool:
        rows = [r for r in pool.map(check, files, chunksize=4) if r]
    df = pd.DataFrame(rows).sort_values("articles", ascending=False)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    out = REPORT_DIR / f"{date.today():%Y-%m-%d}-date-quality-{args.region}.csv"
    df.to_csv(out, index=False)
    flagged = df[df["flag"] != ""]
    print(f"{len(files)} files, {len(df)} sources with >= {MIN_ARTICLES} articles")
    print(
        f"flagged {len(flagged)} sources holding {flagged.articles.sum():,} of {df.articles.sum():,} articles"
    )
    for f in ("day1", "stamp", "spike"):
        hit = df[df["flag"].str.contains(f)]
        print(f"  {f}: {len(hit)} sources, {hit.articles.sum():,} articles")
    print(flagged.head(25).to_string(index=False))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
