"""Hydrate a discovery slice with article text and cut it into agent shards.

Discovery keeps only what the gate needed -- title, url, date, score. The
extraction pass needs the article itself: a measure's name, its dates and its
status live in the body, not the headline. So the slice is joined back to the
corpus by url before it is handed out.

The join is per country and parallel, the same shape discovery used, because
the corpus is only readable in one direction: a country's news.csv files are
streamed once and the wanted urls are picked out on the way past.

Usage:
    po text policy-shard --region ssa --per-shard 110 --jobs 8
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from core.config import load_countries, load_regions
from text.policy import DATA, DEFAULT_OUT_DIR

# Enough for the lede and the paragraphs that carry the numbers; a wire story
# spends its tail on reaction quotes, which cost context and add nothing.
BODY_CHARS = 2500

KEEP = (
    "cand_id",
    "country",
    "date",
    "url",
    "title",
    "source",
    "language",
    "tracker_hint",
    "score",
)


def corpus_dirs(region: str, data_root: Path = DATA) -> dict[str, Path]:
    """Map each country's display name to its corpus directory."""
    topology = load_regions().get(region) or {}
    if not topology:
        raise SystemExit(f"unknown region: {region}")
    names = load_countries()
    found: dict[str, Path] = {}
    for sub_key, sub in (topology.get("subregions") or {}).items():
        for slug in sub.get("countries") or []:
            path = data_root / region / sub_key / slug
            if path.is_dir():
                found[(names.get(slug) or {}).get("name") or slug] = path
    return found


def hydrate_country(job: tuple[str, str, list[dict]]) -> list[dict]:
    """Attach body text to one country's candidates."""
    from text.analysis.policy_retrieval import iter_articles

    country, dir_str, rows = job
    wanted = {r["url"]: r for r in rows if r.get("url")}
    for article in iter_articles(Path(dir_str)):
        row = wanted.get(article.get("url", ""))
        if row is None or "body" in row:
            continue
        body = (article.get("body") or "").strip()
        row["body"] = " ".join(body.split())[:BODY_CHARS]
    return list(wanted.values())


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="po text policy-shard")
    ap.add_argument("--region", required=True)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    ap.add_argument(
        "--data-root",
        type=Path,
        default=DATA,
        help="corpus root the slice was discovered from (same as policy-discover)",
    )
    ap.add_argument("--per-shard", type=int, default=110)
    ap.add_argument("--jobs", type=int, default=8)
    args = ap.parse_args(argv)

    slice_rows = json.loads((args.out_dir / f"slice_{args.region}.json").read_text())
    dirs = corpus_dirs(args.region, args.data_root)

    by_country: dict[str, list[dict]] = defaultdict(list)
    for row in slice_rows:
        by_country[row["country"]].append({k: row.get(k) for k in KEEP})

    jobs = [
        (country, str(dirs[country]), rows)
        for country, rows in sorted(by_country.items())
        if country in dirs
    ]
    missing = sorted(set(by_country) - set(dirs))

    hydrated: list[dict] = []
    with ProcessPoolExecutor(max_workers=args.jobs) as pool:
        for rows in pool.map(hydrate_country, jobs):
            hydrated.extend(rows)

    # A candidate with no body is a url the corpus no longer carries. It cannot
    # be extracted from, so it is dropped here rather than sent to an agent.
    kept = [r for r in hydrated if r.get("body")]
    kept.sort(key=lambda r: r["cand_id"])

    shard_dir = args.out_dir / "shards" / args.region
    shard_dir.mkdir(parents=True, exist_ok=True)
    for old in shard_dir.glob("shard_*.json"):
        old.unlink()

    n_shards = 0
    for start in range(0, len(kept), args.per_shard):
        n_shards += 1
        out = shard_dir / f"shard_{n_shards:02d}.json"
        out.write_text(json.dumps(kept[start : start + args.per_shard], indent=1))

    print(f"{len(kept):,} of {len(slice_rows):,} candidates hydrated")
    print(f"  dropped (no body): {len(hydrated) - len(kept):,}")
    if missing:
        print(f"  countries with no corpus dir: {', '.join(missing)}")
    print(f"  shards: {n_shards} of <= {args.per_shard} in {shard_dir}")


if __name__ == "__main__":
    main()
