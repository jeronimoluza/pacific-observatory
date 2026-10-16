"""Read-only status of the ``text.delta`` node: one staged collect run per region and source.

A run is ``<staging_root>/<run_id>/`` as written by ``staged_collect_all.sh``:
``events_<region>.log`` (runner events), ``<region>/<sub>/<country>/<source>/news.csv``,
``STATUS.md``, ``.done``, and ``<region>/.merged`` once ``po text merge`` took it.
Counts follow ``staged_collect_all.sh`` exactly, so ``region_status`` reproduces STATUS.md.
"""

from __future__ import annotations

import argparse
import glob
import re
import sys
from pathlib import Path

STAGING_ROOT = Path.home() / "text_staging"
REGIONS = ["menaap", "sar", "eap", "ssa", "lac", "eca"]
STATES = ["DONE", "TIMEOUT", "FAIL", "STUCK"]
RUN_ID = re.compile(r"^\d{8}T\d{4}Z$")
EVENT = re.compile(r"^\[(DONE|TIMEOUT|FAIL|STUCK)\s*\]\s+(\S+)")


def list_runs(staging_root: Path = STAGING_ROOT) -> list[str]:
    return sorted(
        p.name for p in staging_root.iterdir() if p.is_dir() and RUN_ID.match(p.name)
    )


def run_regions(run_dir: Path) -> list[str]:
    found = {
        p.name[len("events_") : -len(".log")] for p in run_dir.glob("events_*.log")
    }
    found |= {
        p.name for p in run_dir.iterdir() if p.is_dir() and not p.name.startswith(".")
    }
    return [r for r in REGIONS if r in found] + sorted(found - set(REGIONS))


def read_events(log: Path) -> tuple[dict[str, int], dict[str, str]]:
    """Line counts per state (as ``grep -c '^\\[STATE'``) and the last state per runner tag."""
    counts = dict.fromkeys(STATES, 0)
    last: dict[str, str] = {}
    if not log.exists():
        return counts, last
    for line in log.read_text(errors="replace").splitlines():
        for s in STATES:
            if line.startswith("[" + s):
                counts[s] += 1
        m = EVENT.match(line)
        if m:
            last[m.group(2)] = m.group(1).lower()
    return counts, last


def news_rows(news_csv: Path) -> int:
    import pandas as pd

    return len(pd.read_csv(news_csv, usecols=["url"]))


def merged_marker(run_dir: Path, region: str) -> str | None:
    marker = run_dir / region / ".merged"
    return marker.read_text().strip() if marker.exists() else None


def delta_sources(run_dir: Path, region: str) -> list[dict]:
    """One row per source of ``region`` in the run: runner state and staged news rows.

    ``tag`` is the runner's ``<country>__<source>``; ``key`` is ``<sub>/<country>/<source>``
    (None for a source that ran but left no folder). ``state`` is done, timeout, fail,
    stuck, or no_event for a folder with no runner event.
    """
    _, last = read_events(run_dir / f"events_{region}.log")
    rows = []
    seen = set()
    for d in sorted(glob.glob(str(run_dir / region / "*" / "*" / "*"))):
        d = Path(d)
        if not d.is_dir():
            continue
        tag = f"{d.parent.name}__{d.name}"
        seen.add(tag)
        news = d / "news.csv"
        rows.append(
            {
                "run": run_dir.name,
                "region": region,
                "tag": tag,
                "key": str(d.relative_to(run_dir / region)),
                "state": last.get(tag, "no_event"),
                "has_news_csv": news.exists(),
                "news_rows": news_rows(news) if news.exists() else 0,
            }
        )
    for tag in sorted(set(last) - seen):
        rows.append(
            {
                "run": run_dir.name,
                "region": region,
                "tag": tag,
                "key": None,
                "state": last[tag],
                "has_news_csv": False,
                "news_rows": 0,
            }
        )
    return rows


def region_status(run_dir: Path, region: str) -> dict:
    """The STATUS.md row for ``region``, recomputed from the run's files, plus merge state."""
    log = run_dir / f"events_{region}.log"
    counts, _ = read_events(log)
    files = glob.glob(str(run_dir / region / "*" / "*" / "*" / "news.csv"))
    merged = merged_marker(run_dir, region)
    return {
        "run": run_dir.name,
        "region": region,
        "done": counts["DONE"],
        "timeout": counts["TIMEOUT"],
        "fail": counts["FAIL"],
        "stuck": counts["STUCK"],
        "sources_with_rows": len(files),
        "news_rows": sum(news_rows(Path(f)) for f in files),
        "events_log": log.exists(),
        "merged": merged is not None,
        "merged_note": merged,
    }


def run_status(run_dir: Path) -> dict:
    return {
        "run": run_dir.name,
        "done": (run_dir / ".done").exists(),
        "status_md": (run_dir / "STATUS.md").exists(),
        "regions": [region_status(run_dir, r) for r in run_regions(run_dir)],
    }


def parse_status_md(run_dir: Path) -> list[dict]:
    """The region rows of the run's STATUS.md, as written by the collect driver."""
    out = []
    for line in (run_dir / "STATUS.md").read_text().splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 8 or cells[0] in ("region", "---"):
            continue
        keys = [
            "region",
            "done",
            "timeout",
            "fail",
            "stuck",
            "sources_with_rows",
            "news_rows",
            "note",
        ]
        row = dict(zip(keys, cells))
        for k in keys[1:7]:
            row[k] = int(row[k]) if row[k] else None
        out.append(row)
    return out


def compare_status_md(status: dict, run_dir: Path) -> list[str]:
    cols = ["done", "timeout", "fail", "stuck", "sources_with_rows", "news_rows"]
    ours = {r["region"]: r for r in status["regions"]}
    diffs = []
    for row in parse_status_md(run_dir):
        mine = ours.get(row["region"])
        for c in cols:
            if mine is None or mine[c] != row[c]:
                diffs.append(
                    f"{row['region']}.{c}: STATUS.md={row[c]} observed={mine and mine[c]}"
                )
    return diffs


def observe(node) -> list[dict]:
    """Graph contract (`text.corpus`): one row per region of the newest run; done = the
    run was merged into the corpus (``.merged``). A run with ``.done`` and an unmerged
    region is drift."""
    from datetime import datetime, timezone

    from graph.observe import row

    if not STAGING_ROOT.is_dir() or not list_runs(STAGING_ROOT):
        return []
    run_dir = STAGING_ROOT / list_runs(STAGING_ROOT)[-1]
    st = run_status(run_dir)
    ts = (
        datetime.strptime(st["run"], "%Y%m%dT%H%MZ")
        .replace(tzinfo=timezone.utc)
        .timestamp()
    )
    out = []
    for r in st["regions"]:
        drift = ["done_not_merged"] if st["done"] and not r["merged"] else []
        out.append(
            row(
                node,
                r["region"],
                r["merged"],
                r["news_rows"],
                ts,
                drift=drift,
                extra={
                    k: r[k]
                    for k in (
                        "run",
                        "done",
                        "timeout",
                        "fail",
                        "stuck",
                        "sources_with_rows",
                        "merged_note",
                    )
                },
            )
        )
    return out


def main(argv: list[str] | None = None) -> int:
    import pandas as pd

    ap = argparse.ArgumentParser(prog="python -m graph.observers.text_delta")
    ap.add_argument("--run", help="run id (default: newest)")
    ap.add_argument("--staging-root", type=Path, default=STAGING_ROOT)
    ap.add_argument("--sources", action="store_true", help="print one row per source")
    ap.add_argument(
        "--check", action="store_true", help="exit 1 unless equal to STATUS.md"
    )
    a = ap.parse_args(argv)
    run_dir = a.staging_root / (a.run or list_runs(a.staging_root)[-1])
    st = run_status(run_dir)
    print(f"run {st['run']}  .done={st['done']}  STATUS.md={st['status_md']}")
    cols = [
        "region",
        "done",
        "timeout",
        "fail",
        "stuck",
        "sources_with_rows",
        "news_rows",
        "merged",
    ]
    print(pd.DataFrame(st["regions"], columns=cols).to_string(index=False))
    if a.sources:
        rows = [s for r in run_regions(run_dir) for s in delta_sources(run_dir, r)]
        with pd.option_context("display.max_rows", None, "display.width", 200):
            print(pd.DataFrame(rows).drop(columns="run").to_string(index=False))
    if a.check:
        diffs = compare_status_md(st, run_dir)
        print(
            "STATUS.md: identical"
            if not diffs
            else "STATUS.md differs:\n  " + "\n  ".join(diffs)
        )
        return 1 if diffs else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
