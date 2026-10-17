"""One text-count partition per process: a country's counts state, or an aggregate.

Global text never holds more than one country in a process. `country` builds or
updates one country's state (data/text/cache/<r>/<sub>/<country>/source_counts.*)
from its corpus folders and writes its outputs; `aggregate` reads the country
states of a subregion or region (no corpus read) and writes the aggregate's
outputs. `partition_driver` runs each one in its own MemoryMax scope.

Run from the repo root with PYTHONPATH=src:
    python -m text.analysis.partition country --name ukraine --tail-start 2026-10-01 --end 2026-10-12
    python -m text.analysis.partition aggregate --region eca --subregion eastern_europe --tail-start 2026-10-01
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone

import pandas as pd

from src.text.analysis import main as build
from src.text.analysis import source_counts
from src.text.analysis.cache_gate import _dedup_source_counts
from src.text.analysis.orchestrator import process_unit_v2, write_unit_outputs

BASELINE = ("2024-01-01", "2024-12-31")
SUBSET_START = "2015-01-01"
SIDECAR = "partition.json"


def _sha() -> str:
    return subprocess.run(
        ["git", "-C", str(build.PROJECT_ROOT), "rev-parse", "--short", "HEAD"],
        capture_output=True,
        text=True,
    ).stdout.strip()


def country_units(names: set[str] | None = None) -> list[dict]:
    """Country units of the corpus (main._discover_units, no aggregates), all or ``names``."""
    dirs = [d for d in build._get_country_dirs() if names is None or d.name in names]
    return build._discover_units(dirs, include_aggregates=False)


def aggregate_units(region: str, subregion: str | None) -> tuple[dict, list[dict]]:
    dirs = [
        d
        for d in build._get_country_dirs()
        if d.parent.parent.name == region
        and (subregion is None or d.parent.name == subregion)
    ]
    units = build._discover_units(dirs, include_aggregates=True)
    level = "subregion" if subregion else "region"
    (agg,) = [
        u
        for u in units
        if u["level"] == level
        and (level == "region" or u["output_dir"].parent.name == subregion)
    ]
    return agg, [u for u in units if u["level"] == "country"]


def _sidecar(cache_dir, info: dict) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / SIDECAR).write_text(json.dumps(info, indent=2, default=str))


def run_country(name: str, tail_start: str, end: str, parallel_sources: int) -> int:
    units = country_units({name})
    if len(units) != 1:
        print(f"{name}: {len(units)} country units in {build.DATA_ROOT}")
        return 1
    (u,) = units
    t = time.time()
    read_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    diag = process_unit_v2(
        name=u["name"],
        level="country",
        news_dirs=u["news_dirs"],
        output_dir=u["output_dir"],
        cache_dir=u["cache_dir"],
        cutoff_start_date=BASELINE[0],
        cutoff_end_date=BASELINE[1],
        subset_condition=f"date >= '{SUBSET_START}' and date <= '{end}'",
        source_languages=u["source_languages"],
        max_parallel_sources=parallel_sources,
        data_root=build.DATA_ROOT,
        cache_root=build.CACHE_DIR,
        daily_tail_start=tail_start,
    )
    info = {
        "partition": f"country/{name}",
        "mode": diag.get("mode"),
        "status": diag.get("status"),
        "staleness_reason": diag.get("staleness_reason"),
        "n_sources": len(u["news_dirs"]),
        "articles": int(diag.get("total_articles", 0) or 0),
        "tail_start": tail_start,
        "end": end,
        # every plan applied to the corpus before this moment is inside the state
        "corpus_read_at": read_at,
        "wall_s": round(time.time() - t, 1),
        "sha": _sha(),
        "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    _sidecar(u["cache_dir"], info)
    print(json.dumps(info), flush=True)
    return 0 if diag.get("status") == "ok" else 1


def run_delta(name: str, plan, tail_start: str, end: str, parallel_sources: int) -> int:
    """Stream a signed-off plan's rows for ``name`` into its state (text.analysis.delta)."""
    from pathlib import Path

    from src.text.analysis import delta

    (u,) = country_units({name})
    applied = Path(plan) / "APPLIED"
    if not applied.exists():
        print(f"{plan}: not signed off and applied, nothing to stream")
        return 1
    side = u["cache_dir"] / SIDECAR
    read_at = (
        json.loads(side.read_text()).get("corpus_read_at") if side.exists() else None
    )
    applied_at = datetime.fromtimestamp(applied.stat().st_mtime, timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    if read_at and applied_at < read_at:
        print(
            f"{name}: {Path(plan).name} applied {applied_at}, before the state read the corpus ({read_at})"
        )
        return 0
    items = []
    for region, delta_csv, target in delta.plan_sources(Path(plan)).get(name, []):
        corpus_csv = build.DATA_ROOT / region / target.relative_to(target.parents[3])
        items.append((delta_csv, corpus_csv, build._source_language(corpus_csv)))
    t = time.time()
    try:
        info = delta.apply_delta(
            u["cache_dir"], items, tail_start, end, Path(plan).name
        )
    except delta.NeedsFull as e:
        print(f"{name}: {e}, full partition run instead", flush=True)
        return run_country(name, tail_start, end, parallel_sources)
    df, _ = source_counts.read_source_counts(u["cache_dir"])
    write_unit_outputs(df, name, u["output_dir"], BASELINE[0], BASELINE[1], tail_start)
    info = {
        "partition": f"country/{name}",
        "mode": "delta",
        "plan": Path(plan).name,
        **info,
        "corpus_read_at": read_at,
        "wall_s": round(time.time() - t, 1),
        "sha": _sha(),
        "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    _sidecar(u["cache_dir"], info)
    print(json.dumps(info), flush=True)
    return 0


def run_aggregate(region: str, subregion: str | None, tail_start: str) -> int:
    agg, countries = aggregate_units(region, subregion)
    frames, missing = [], []
    for u in countries:
        df, _ = source_counts.read_source_counts(u["cache_dir"])
        if df is None:
            missing.append(u["name"])
            continue
        frames.append(_dedup_source_counts(df, pd.Timestamp(tail_start)))
    if missing:
        print(f"{agg['name']}: no country state for {', '.join(missing)}")
        return 1
    t = time.time()
    write_unit_outputs(
        pd.concat(frames, ignore_index=True),
        agg["name"],
        agg["output_dir"],
        BASELINE[0],
        BASELINE[1],
        tail_start,
    )
    print(
        json.dumps(
            {
                "partition": agg["name"],
                "countries": len(frames),
                "wall_s": round(time.time() - t, 1),
            }
        )
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="text.analysis.partition")
    ap.add_argument("kind", choices=["country", "delta", "aggregate"])
    ap.add_argument("--plan", help="delta: a signed-off plan dir (<pending>/<plan_id>)")
    ap.add_argument("--name")
    ap.add_argument("--region")
    ap.add_argument("--subregion")
    ap.add_argument(
        "--tail-start",
        required=True,
        help="daily tail anchor, shared by every partition of a run",
    )
    ap.add_argument(
        "--end",
        default=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        help="last article date counted",
    )
    ap.add_argument("--parallel-sources", type=int, default=1)
    a = ap.parse_args(argv)
    if a.kind == "country":
        return run_country(a.name, a.tail_start, a.end, a.parallel_sources)
    if a.kind == "delta":
        return run_delta(a.name, a.plan, a.tail_start, a.end, a.parallel_sources)
    return run_aggregate(a.region, a.subregion, a.tail_start)


if __name__ == "__main__":
    sys.exit(main())
