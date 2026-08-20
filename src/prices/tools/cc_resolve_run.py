"""Resolve every archive-scoped source against every crawl, once, on this machine.

Runs the index half of the backfill where the ~13 GB ``cluster.idx`` cache
already lives, and writes manifests the fetch half can consume anywhere. See
:mod:`prices.cc_resolve` for why the two halves are separated and why this is
index-major.

Resume is per crawl: a crawl's manifest is written atomically, so an interrupt
leaves either the whole crawl or none of it, and a rerun skips what is done.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import List, Optional


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def main(argv: Optional[List[str]] = None) -> int:
    from prices.cc_config import all_cc_configs, interleave_indexes
    from prices.tools.cc_backfill_run import _resolve_indexes_once
    from prices.cc_resolve import (
        consolidate,
        resolve_index,
        resolved_indexes,
        write_horizon,
    )
    from prices.tools.cc_worklist import build_worklist

    root = _repo_root()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--out", type=Path, default=root / "data" / "prices" / "_cc_manifests"
    )
    ap.add_argument("--since", type=int, default=2013)
    ap.add_argument("--only", default="", help="comma-separated spider names")
    ap.add_argument("--limit-indexes", type=int, default=0, help="stop after N crawls")
    ap.add_argument(
        "--consolidate-every",
        type=int,
        default=3,
        help=(
            "refresh the per-source manifests every N crawls so the fetch "
            "machine can start before the whole resolve finishes (0 = only "
            "at the end)"
        ),
    )
    ap.add_argument(
        "--consolidate-only",
        action="store_true",
        help="regroup existing per-crawl files into per-source manifests and exit",
    )
    args = ap.parse_args(argv)

    out = args.out
    out.mkdir(parents=True, exist_ok=True)

    sources = build_worklist()
    if args.only:
        wanted = {s.strip() for s in args.only.split(",") if s.strip()}
        sources = [s for s in sources if s.spider in wanted]
    configs = all_cc_configs()

    if args.consolidate_only:
        counts = consolidate(out)
        h = write_horizon(out)
        print(
            f"consolidated {sum(counts.values())} records for {len(counts)} "
            f"sources, horizon {h['newest']}..{h['oldest']} ({h['count']} crawls)"
        )
        return 0

    # Pinned on first success, then reused. ``collinfo.json`` lives on
    # index.commoncrawl.org, which returns 504s and empty replies for hours at
    # a time -- it was down again the day this was written, while
    # data.commoncrawl.org served 206 from the same address. Without the pin a
    # transient outage of the flaky host stops the half of the backfill that
    # does not otherwise depend on it at all. Resolution stays strict, so the
    # 8-crawl fallback can never quietly become the horizon.
    indexes = _resolve_indexes_once(out, args.since)
    done = set(resolved_indexes(out))
    # Bisected rather than newest-first. A source's presence in Common Crawl
    # arrives in bursts, and which crawl holds the burst is unguessable: one
    # source keeps 64,856 URLs across 91 crawls spanning 2015-2025 and *none*
    # in 2026, so a newest-first resolve reported it as absent from the
    # archive entirely. Walking ends-then-midpoints means whatever prefix of
    # the run actually completes spans the whole period.
    pending = interleave_indexes([i for i in indexes if i not in done])
    if args.limit_indexes:
        pending = pending[: args.limit_indexes]

    print(
        f"{len(sources)} sources, {len(indexes)} crawls since {args.since}, "
        f"{len(done)} already resolved, {len(pending)} to go",
        flush=True,
    )

    for n, index in enumerate(pending, 1):
        start = time.time()
        written = resolve_index(index, sources, configs, out)
        print(
            f"[{n}/{len(pending)}] {index}: {written} records "
            f"in {time.time() - start:.0f}s",
            flush=True,
        )
        # Republishing mid-run is what lets the fetch machine work in parallel
        # instead of idling until all ~123 crawls are in. What it picks up is a
        # manifest with holes, because crawls resolve bisected rather than
        # newest-first: the fetch side must therefore decide "owed another
        # pass" from how many crawls the horizon covers, never from how far
        # back its oldest one reaches.
        if args.consolidate_every and n % args.consolidate_every == 0:
            counts = consolidate(out)
            h = write_horizon(out)
            print(
                f"    published {sum(counts.values())} records / "
                f"{len(counts)} sources, horizon through {h['oldest']}",
                flush=True,
            )

    counts = consolidate(out)
    h = write_horizon(out)
    print(
        f"consolidated {sum(counts.values())} records for {len(counts)} sources "
        f"into {out / 'by_source'} (horizon {h['newest']}..{h['oldest']}, "
        f"{h['count']} crawls)",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
