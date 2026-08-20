"""Cut a keyword slice out of resolved Common Crawl manifests.

The resolve half answers "which URLs does this storefront have", by prefix.
That is the only question a sorted index can answer cheaply, and it is not the
question a price series asks -- which is "where is this product, across every
storefront, across every year".

Nothing remote is needed to bridge the two. A resolved manifest already holds
the URL next to its WARC pointer, so the product question is a scan over ~1.5
GB of local JSONL rather than over Common Crawl's ~100 TB. Terms are matched
against the URL *path* only: a host like ``coca-cola-shop.example`` would
otherwise pull its entire catalogue into every slice.

Output is per source and schema-identical to the input, so a slice is fed
straight to :func:`prices.cc_fetch.run_from_manifest` with that source's own
parser. Slicing changes which records are fetched, never how.

The catch is worth stating where it will be read: this matches URL text, so it
finds only storefronts that put product names in their slugs. A retailer using
numeric SKUs (``/p/8901234``) contributes nothing regardless of what it sells.
A slice is a sample, never a census.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import List, Optional


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _url_path(url: str) -> str:
    return url.split("//", 1)[-1].partition("/")[2]


def main(argv: Optional[List[str]] = None) -> int:
    from prices.cc_terms import load_keyword_regex

    root = _repo_root()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--manifests",
        type=Path,
        default=root / "data" / "prices" / "_cc_manifests" / "by_source",
    )
    ap.add_argument(
        "--terms", type=Path, default=root / "src" / "prices" / "cc_product_terms.txt"
    )
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument(
        "--max-terms", type=int, default=0, help="use only the first N terms"
    )
    ap.add_argument(
        "--max-per-source",
        type=int,
        default=0,
        help=(
            "keep at most N records per source, spread evenly across that "
            "source's crawls so a bounded slice stays a time series"
        ),
    )
    ap.add_argument("--only", default="", help="comma-separated spider names")
    args = ap.parse_args(argv)

    rx = re.compile(
        load_keyword_regex(args.terms, args.max_terms or None), re.IGNORECASE
    )
    args.out.mkdir(parents=True, exist_ok=True)
    wanted = {s.strip() for s in args.only.split(",") if s.strip()}

    kept_total = 0
    scanned_total = 0
    per_source: Counter = Counter()
    for path in sorted(args.manifests.glob("*.jsonl")):
        if wanted and path.stem not in wanted:
            continue
        by_crawl: dict = {}
        scanned = 0
        with path.open(encoding="utf-8") as fh:
            for line in fh:
                scanned += 1
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if not rx.search(_url_path(rec.get("url", ""))):
                    continue
                by_crawl.setdefault(rec.get("cc_index", "unknown"), []).append(line)
        scanned_total += scanned
        if not by_crawl:
            continue
        kept = _cap(by_crawl, args.max_per_source)
        if not kept:
            continue
        (args.out / path.name).write_text("".join(kept), encoding="utf-8")
        per_source[path.stem] = len(kept)
        kept_total += len(kept)

    print(f"scanned {scanned_total:,} records in {args.manifests}")
    print(f"kept    {kept_total:,} across {len(per_source)} sources -> {args.out}")
    for name, n in per_source.most_common(10):
        print(f"  {n:>8,}  {name}")
    return 0


def _cap(by_crawl: dict, cap: int) -> List[str]:
    """Flatten per-crawl groups, taking evenly from each when capped.

    A flat head-N would spend the whole budget on whichever crawl sorts first,
    and the point of the slice is that it spans years. Round-robin across
    crawls keeps every year represented at any budget.
    """
    flat = [ln for lines in by_crawl.values() for ln in lines]
    if not cap or len(flat) <= cap:
        return flat
    out: List[str] = []
    groups = [list(v) for v in by_crawl.values()]
    i = 0
    while len(out) < cap and any(groups):
        g = groups[i % len(groups)]
        if g:
            out.append(g.pop())
        i += 1
        if i % len(groups) == 0:
            groups = [g for g in groups if g]
            i = 0
            if not groups:
                break
    return out


if __name__ == "__main__":
    raise SystemExit(main())
