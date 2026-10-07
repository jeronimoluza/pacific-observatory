"""Choose which discovery candidates the extraction pass reads.

Extraction is the expensive stage, so the slice is where the budget is spent.
Two rules shape it:

*Per country, not globally.* Ranking 43k candidates by score alone hands 40% of
the budget to Nigeria and Ghana and leaves Eswatini with nothing. The trackers
are read per country, so coverage has to be per country too.

*Pre-2025 first.* The workbooks are a verification stamp -- 3 of 187 SSA fuel
rows cite any pre-2025 year -- so a 2026 candidate mostly re-finds a row the
tracker already holds and link_workbook then drops it. The history is the part
that does not exist anywhere else. A smaller recent quota still runs, because a
measure the analysts missed outright is worth finding whatever its year.

Usage:
    python scripts/policy_slice.py --region ssa --old 80 --recent 20
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = REPO_ROOT / "data" / "text" / "policy_tracker_extended"

CUTOFF = 2025


def year_of(row: dict) -> int | None:
    date = (row.get("date") or "")[:4]
    return int(date) if date.isdigit() else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", required=True)
    ap.add_argument("--old", type=int, default=80, help="per country, pre-2025")
    ap.add_argument("--recent", type=int, default=20, help="per country, 2025+")
    args = ap.parse_args()

    src = OUT_DIR / f"candidates_{args.region}.json"
    data = json.loads(src.read_text())

    picked: list[dict] = []
    for country, block in sorted(data["countries"].items()):
        rows = sorted(block["candidates"], key=lambda r: -r.get("score", 0))
        old = [r for r in rows if (year_of(r) or 9999) < CUTOFF][: args.old]
        recent = [r for r in rows if (year_of(r) or 0) >= CUTOFF][: args.recent]
        for row in old + recent:
            row["cand_id"] = f"{args.region}-{len(picked):05d}"
            picked.append(row)

    years = Counter(year_of(r) for r in picked)
    trackers = Counter(r.get("tracker_hint") for r in picked)
    out = OUT_DIR / f"slice_{args.region}.json"
    out.write_text(json.dumps(picked, indent=1))

    total = sum(c["n_candidates"] for c in data["countries"].values())
    print(f"{len(picked):,} of {total:,} candidates selected")
    print(f"  countries:  {len({r['country'] for r in picked})}")
    print(f"  pre-{CUTOFF}:   {sum(n for y, n in years.items() if y and y < CUTOFF):,}")
    print(
        f"  {CUTOFF}+:      {sum(n for y, n in years.items() if y and y >= CUTOFF):,}"
    )
    print(f"  tracker:    {dict(trackers)}")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
