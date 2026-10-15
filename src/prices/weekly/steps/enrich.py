"""Step `enrich` (W42 runbook step 8, was ~/scratch/w42_enrich/run.sh): concatenate, then prepare.

Each stage runs in its own process with logging on, so the step log carries the
stages' own progress lines. `--countries` becomes one `--only */*/<country>`
selector per country; concatenate and prepare both honour it.

After prepare, every prepared parquet in scope is listed against the step's start:
an old mtime is not a failure (prepare skips a country whose shards did not change)
but it is printed, which is how W42's stale `bahamas.parquet` would have shown.
"""

from __future__ import annotations

import sys
import time
from datetime import datetime, timezone

from prices.weekly.status import Status
from prices.weekly.steps import _common

MODULE = "prices.weekly.steps.enrich"
WORKERS = 4


def _only(countries: list[str] | None) -> list[str]:
    out = []
    for c in countries or []:
        out += ["--only", f"*/*/{c}"]
    return out


def _stage(stage: str, countries: list[str] | None) -> int:
    from prices.enrich.cli import process_command

    _common.setup_logging()
    args = ["--stage", stage, *_only(countries)]
    if stage == "prepare":
        args += ["--workers", str(WORKERS)]
    print(f"prices process {' '.join(args)}", flush=True)
    process_command.main(args=args, standalone_mode=False)
    return 0


def _report(countries: list[str] | None, start: float) -> None:
    from prices.enrich.prepare_shards import PREPARED_DIR

    files = _common.prepared_files(PREPARED_DIR, countries)
    stale = [p for p in files if p.stat().st_mtime < start]
    print(
        f"PREPARED {len(files)} files, {len(files) - len(stale)} written by this run",
        flush=True,
    )
    for p in stale:
        ts = datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).strftime(
            "%Y-%m-%dT%H:%MZ"
        )
        print(f"  not rewritten: {p.relative_to(PREPARED_DIR)} ({ts})", flush=True)
    if countries:
        have = {p.stem for p in files}
        missing = [c for c in countries if c not in have]
        if missing:
            print(f"  no prepared parquet: {', '.join(missing)}", flush=True)


def main() -> int:
    args = _common.parser("enrich").parse_args()
    countries = _common.countries(args.countries)
    if args.phase:
        return _stage(args.phase, countries)
    status = Status(args.week_dir, "enrich")
    start = time.time()
    scope = f"{len(countries)} countries" if countries else "all countries"
    for stage in ("concatenate", "prepare"):
        _common.say(status, f"{stage} start ({scope})")
        rc = _common.phase(MODULE, args, stage)
        if rc != 0:
            _common.say(status, f"{stage} FAILED rc={rc}")
            return rc
        _common.say(status, f"{stage} rc=0")
    _report(countries, start)
    return 0


if __name__ == "__main__":
    sys.exit(main())
