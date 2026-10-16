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
from functools import lru_cache
from pathlib import Path

STAGING_ROOT = Path.home() / "text_staging"
REGIONS = ["menaap", "sar", "eap", "ssa", "lac", "eca"]
STATES = ["DONE", "TIMEOUT", "FAIL", "STUCK"]
RUN_ID = re.compile(r"^\d{8}T\d{4}Z$")
EVENT = re.compile(r"^\[(DONE|TIMEOUT|FAIL|STUCK)\s*\]\s+(\S+)")


def list_runs(staging_root: Path = STAGING_ROOT) -> list[str]:
    return sorted(p.name for p in staging_root.iterdir() if p.is_dir() and RUN_ID.match(p.name))


def run_regions(run_dir: Path) -> list[str]:
    found = {p.name[len("events_"):-len(".log")] for p in run_dir.glob("events_*.log")}
    found |= {p.name for p in run_dir.iterdir() if p.is_dir() and not p.name.startswith(".")}
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


@lru_cache(maxsize=None)
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
        rows.append({
            "run": run_dir.name, "region": region, "tag": tag,
            "key": str(d.relative_to(run_dir / region)),
            "state": last.get(tag, "no_event"),
            "has_news_csv": news.exists(),
            "news_rows": news_rows(news) if news.exists() else 0,
        })
    for tag in sorted(set(last) - seen):
        rows.append({
            "run": run_dir.name, "region": region, "tag": tag, "key": None,
            "state": last[tag], "has_news_csv": False, "news_rows": 0,
        })
    return rows


def region_status(run_dir: Path, region: str) -> dict:
    """The STATUS.md row for ``region``, recomputed from the run's files, plus merge state."""
    log = run_dir / f"events_{region}.log"
    counts, _ = read_events(log)
    files = glob.glob(str(run_dir / region / "*" / "*" / "*" / "news.csv"))
    merged = merged_marker(run_dir, region)
    return {
        "run": run_dir.name, "region": region,
        "done": counts["DONE"], "timeout": counts["TIMEOUT"],
        "fail": counts["FAIL"], "stuck": counts["STUCK"],
        "sources_with_rows": len(files),
        "news_rows": sum(news_rows(Path(f)) for f in files),
        "events_log": log.exists(), "merged": merged is not None, "merged_note": merged,
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
        keys = ["region", "done", "timeout", "fail", "stuck", "sources_with_rows", "news_rows", "note"]
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
                diffs.append(f"{row['region']}.{c}: STATUS.md={row[c]} observed={mine and mine[c]}")
    return diffs


def plans(pending_root: Path | None) -> list[dict]:
    """Sign-off plans under ``pending_root``: the ``<run>/<region>`` dirs each covers, its new
    rows per region (PLAN.tsv, news.csv lines), and whether it was applied or superseded."""
    import csv

    out = []
    if not pending_root or not pending_root.is_dir():
        return out
    for d in sorted(p for p in pending_root.iterdir() if p.is_dir()):
        runs = (d / "RUNS").read_text().split() if (d / "RUNS").exists() else []
        new_rows: dict[str, int] = {}
        if (d / "PLAN.tsv").exists():
            with open(d / "PLAN.tsv", newline="") as f:
                for r in csv.DictReader(f, delimiter="\t"):
                    if r.get("file") == "news.csv":
                        new_rows[r["region"]] = new_rows.get(r["region"], 0) + int(r["new_rows"] or 0)
        out.append({"plan": d.name, "dir": d, "runs": runs, "has_plan": (d / "PLAN.tsv").exists(),
                    "new_rows": new_rows, "applied": (d / "APPLIED").exists(),
                    "superseded": (d / "SUPERSEDED").exists()})
    return out


def _stamp(marker: Path) -> str | None:
    head = marker.read_text().split(maxsplit=1)
    return head[0] if head and re.match(r"\d{4}-\d{2}-\d{2}T", head[0]) else None


def merge_state(run_dir: Path, region: str, mac_staging: Path | None,
                all_plans: list[dict]) -> tuple[str | None, list[str], str | None]:
    """How ``<run>/<region>`` reached the corpus (None = not yet) and the drift on the way.

    Evidence, first hit wins: ``.merged`` in the staging run on this machine; ``.merged`` in
    the Mac's copy of the run (prod merged there until S6); an applied plan covering it; a
    plan covering it whose PLAN.tsv brings 0 new news rows for the region (already in the
    corpus). An open plan with new rows is awaiting sign-off; a pending dir named after the
    run without PLAN.tsv means merge refused before planning. The third value is the
    merge time a marker records."""
    if merged_marker(run_dir, region) is not None:
        return "marker", [], _stamp(run_dir / region / ".merged")
    if mac_staging and (mac_staging / run_dir.name / region / ".merged").exists():
        return "marker_mac", [], _stamp(mac_staging / run_dir.name / region / ".merged")
    drift = []
    me = str(run_dir / region)
    for p in all_plans:
        if me not in p["runs"]:
            continue
        if p["applied"]:
            return f"plan {p['plan']} applied", [], None
        if p["has_plan"] and not p["superseded"] and p["new_rows"].get(region, 0) == 0:
            return f"plan {p['plan']}: 0 new rows", [], None
        if p["has_plan"] and not p["superseded"]:
            drift.append(f"awaiting_signoff {p['plan']} ({p['new_rows'].get(region, 0)} new rows)")
    for p in all_plans:
        if p["plan"] == run_dir.name and not p["has_plan"]:
            drift.append(f"pending/{p['plan']} sin PLAN.tsv (merge rehusó)")
    return None, drift, None


def _run_sha(logs_root: Path | None, run: str) -> str | None:
    """The collect commit the run's step log recorded (``... @<sha>``), if the owner keeps one."""
    events = logs_root / run / "events.log" if logs_root else None
    if not events or not events.exists():
        return None
    for line in events.read_text(errors="replace").splitlines():
        m = re.search(r" collect: RUNNING .*@([0-9a-f]{7,40})", line)
        if m:
            return m.group(1)
    return None


def observe(node) -> list[dict]:
    """Graph contract (`text.corpus`): per owner (manifest ``owners``), one row per run and
    region of that owner's staging; done = the region reached the corpus (``merge_state``).
    STATUS.md is never read: counts come from the events logs and the staged files."""
    from datetime import datetime, timezone

    from graph.observe import row
    from graph.observers.text_owners import root

    owners = node.owners or {"prod": {"staging": str(STAGING_ROOT)}}
    all_plans = [p for spec in owners.values() for p in plans(root(spec, "pending"))]
    out = []
    for owner, spec in owners.items():
        staging = root(spec, "staging")
        if not staging or not staging.is_dir():
            continue
        for run in list_runs(staging):
            run_dir = staging / run
            st = run_status(run_dir)
            ts = datetime.strptime(run, "%Y%m%dT%H%MZ").replace(tzinfo=timezone.utc).timestamp()
            sha = _run_sha(root(spec, "logs"), run)
            for r in st["regions"]:
                how, drift, at = merge_state(run_dir, r["region"], root(spec, "merged_mac"), all_plans)
                if st["done"] and how is None:
                    drift = ["done_not_merged"] + drift
                out.append(row(node, f"{owner}/{run}/{r['region']}", how is not None, r["news_rows"], ts,
                               sha=sha, drift=drift,
                               extra={"owner": owner, "run": run, "run_done": st["done"], "merged_by": how,
                                      "merged_at": at,
                                      **{k: r[k] for k in ("done", "timeout", "fail", "stuck",
                                                           "sources_with_rows", "events_log")}}))
    return out


def main(argv: list[str] | None = None) -> int:
    import pandas as pd

    ap = argparse.ArgumentParser(prog="python -m graph.observers.text_delta")
    ap.add_argument("--run", help="run id (default: newest)")
    ap.add_argument("--staging-root", type=Path, default=STAGING_ROOT)
    ap.add_argument("--sources", action="store_true", help="print one row per source")
    ap.add_argument("--check", action="store_true", help="exit 1 unless equal to STATUS.md")
    a = ap.parse_args(argv)
    run_dir = a.staging_root / (a.run or list_runs(a.staging_root)[-1])
    st = run_status(run_dir)
    print(f"run {st['run']}  .done={st['done']}  STATUS.md={st['status_md']}")
    cols = ["region", "done", "timeout", "fail", "stuck", "sources_with_rows", "news_rows", "merged"]
    print(pd.DataFrame(st["regions"], columns=cols).to_string(index=False))
    if a.sources:
        rows = [s for r in run_regions(run_dir) for s in delta_sources(run_dir, r)]
        with pd.option_context("display.max_rows", None, "display.width", 200):
            print(pd.DataFrame(rows).drop(columns="run").to_string(index=False))
    if a.check:
        diffs = compare_status_md(st, run_dir)
        print("STATUS.md: identical" if not diffs else "STATUS.md differs:\n  " + "\n  ".join(diffs))
        return 1 if diffs else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
