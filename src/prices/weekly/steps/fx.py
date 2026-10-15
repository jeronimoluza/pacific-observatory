"""Step `fx` (W42: by hand, plus ~/scratch/w42_enrich/fx_cache.pre_refresh_*.csv): refresh the FX cache.

1. A dated copy of `_fx/fx_cache.csv` next to it, verified by sha256 (an existing
   copy for the same day is kept, never overwritten).
2. `prices fx-refresh`.
3. Every line has exactly 4 fields (`awk -F, 'NF!=4'` must be empty).
4. `require_fresh_fx` for today: the gate Stage B applies.
5. Printed, not gated: share of currencies whose last date is today or yesterday
   (retired codes end early by design).

FX is one cache for every country: `--countries` does not apply here.
"""

from __future__ import annotations

import hashlib
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from prices.weekly.status import Status
from prices.weekly.steps import _common

FIELDS = 4


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _snapshot(cache: Path, today: str) -> Path:
    snap = cache.with_name(f"{cache.stem}.pre_refresh_{today}{cache.suffix}")
    if snap.exists():
        print(f"snapshot {snap} exists, kept as is", flush=True)
        return snap
    shutil.copy2(cache, snap)
    src, dst = _sha256(cache), _sha256(snap)
    if src != dst:
        raise SystemExit(f"snapshot sha differs: {cache} {src} vs {snap} {dst}")
    snap.with_name(snap.name + ".sha256").write_text(f"{dst}  {snap.name}\n")
    print(f"snapshot {snap} sha256 {dst}", flush=True)
    return snap


def _malformed(cache: Path) -> list[tuple[int, str]]:
    bad = []
    with open(cache) as f:
        for i, line in enumerate(f, 1):
            if line.rstrip("\r\n").count(",") != FIELDS - 1:
                bad.append((i, line.rstrip()[:120]))
    return bad


def _freshness(cache: Path, now: datetime) -> None:
    import pandas as pd

    last = (
        pd.read_csv(cache, usecols=["currency", "date"])
        .groupby("currency")["date"]
        .max()
    )
    since = (now.date() - timedelta(days=1)).isoformat()
    stale = last[last < since].sort_index()
    pct = 100 * (len(last) - len(stale)) / len(last) if len(last) else 0.0
    print(
        f"FX_FRESH {len(last) - len(stale)}/{len(last)} currencies end >= {since} ({pct:.1f}%)",
        flush=True,
    )
    for cur, d in stale.items():
        print(f"  {cur} ends {d}", flush=True)


def main() -> int:
    import pandas as pd

    from prices.fx.paths import PRICES_FX_CACHE
    from prices.fx.refresh import refresh
    from prices.stage_b_fx import require_fresh_fx

    args = _common.parser("fx").parse_args()
    _common.setup_logging()
    status = Status(args.week_dir, "fx")
    if args.countries:
        print(
            "note: --countries ignored, the FX cache is shared by every country",
            flush=True,
        )
    now = datetime.now(timezone.utc)
    cache = PRICES_FX_CACHE
    _common.say(status, f"snapshot {cache.name}")
    _snapshot(cache, now.strftime("%Y%m%d"))
    _common.say(status, "fx-refresh")
    fetched = refresh(cache_path=cache)
    print(f"Fetched {fetched:,} FX rows.", flush=True)
    bad = _malformed(cache)
    if bad:
        for i, line in bad[:5]:
            print(f"  line {i}: {line}", flush=True)
        _common.say(status, f"FAILED {len(bad)} lines without {FIELDS} fields")
        return 1
    print(f"lines with {FIELDS} fields: all", flush=True)
    try:
        require_fresh_fx(pd.Timestamp(now.date()), cache_path=cache)
    except RuntimeError as e:
        _common.say(status, f"FAILED {e}")
        return 1
    print("require_fresh_fx: pass", flush=True)
    _freshness(cache, now)
    return 0


if __name__ == "__main__":
    sys.exit(main())
