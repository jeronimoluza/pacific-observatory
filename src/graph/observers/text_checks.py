"""Silent-zero check on ``text.delta``: a source that used to bring rows and now brings 0.

Per source, the target run's staged news rows are compared with the median over the
previous ``n`` runs where the source finished (state done) or staged rows before it timed
out, failed or got stuck. A done source with 0 rows
after a positive baseline is yellow; 0 in two consecutive done runs is red. A source that
timed out, failed or got stuck is reported with that state, never as a zero.
"""

from __future__ import annotations

import argparse
import statistics
import sys
from pathlib import Path

from graph.observers.text_delta import STAGING_ROOT, delta_sources, list_runs, run_regions


def _level(history: list[dict], n: int) -> dict:
    cur = history[-1]
    out = {"state": cur["state"], "news_rows": cur["news_rows"], "baseline": None, "zero_streak": 0}
    if cur["state"] != "done":
        out["level"] = cur["state"]
        return out
    if cur["news_rows"] > 0:
        out["level"] = "ok"
        return out
    i = len(history) - 1
    while i >= 0 and history[i]["state"] == "done" and history[i]["news_rows"] == 0:
        i -= 1
    out["zero_streak"] = len(history) - 1 - i
    before = [h["news_rows"] for h in history[: i + 1] if h["state"] == "done" or h["news_rows"]][-n:]
    out["baseline"] = statistics.median(before) if before else None
    if not out["baseline"]:
        out["level"] = "zero_no_baseline"
    else:
        out["level"] = "red" if out["zero_streak"] >= 2 else "yellow"
    return out


def silent_zeros(staging_root: Path = STAGING_ROOT, run: str | None = None, n: int = 4) -> list[dict]:
    """One row per source of ``run`` (default newest) with level ok, yellow, red,
    zero_no_baseline, timeout, fail, stuck or no_event, judged on up to ``n`` earlier runs.
    """
    runs = list_runs(staging_root)
    run = run or runs[-1]
    window = runs[: runs.index(run) + 1][-(n + 1):]
    hist: dict[tuple[str, str], list[dict]] = {}
    for r in window:
        run_dir = staging_root / r
        for region in run_regions(run_dir):
            for s in delta_sources(run_dir, region):
                hist.setdefault((region, s["tag"]), []).append(s)
    rows = []
    for (region, tag), h in sorted(hist.items()):
        if h[-1]["run"] != run:
            continue
        rows.append({"run": run, "region": region, "tag": tag, "key": h[-1]["key"],
                     "runs_seen": len(h), **_level(h, n)})
    return rows


def observe(node) -> list[dict]:
    """Graph contract (`text.delta`): per owner (manifest ``owners``), one row per source of
    that owner's newest run, with its silent-zero level from ``silent_zeros``. A source
    staged by the owner that does not own its country is drift ``owner_conflict`` (the
    panel is the only writer of what prod excludes)."""
    from datetime import datetime, timezone

    from graph.observe import row
    from graph.observers.text_owners import country_of_key, owner_of, root

    owners = node.owners or {"prod": {"staging": str(STAGING_ROOT)}}
    out = []
    for owner, spec in owners.items():
        staging = root(spec, "staging")
        if not staging or not staging.is_dir() or not list_runs(staging):
            continue
        for s in silent_zeros(staging):
            ts = datetime.strptime(s["run"], "%Y%m%dT%H%MZ").replace(tzinfo=timezone.utc).timestamp()
            country = country_of_key(s["key"], s["tag"])
            drift = [] if owner_of(owners, s["region"], country) == owner else ["owner_conflict"]
            out.append(row(node, f"{owner}/{s['region']}/{s['key'] or s['tag']}", s["state"] == "done",
                           s["news_rows"], ts, drift=drift,
                           extra={"owner": owner, **{k: s[k] for k in ("run", "state", "level", "baseline",
                                                                        "zero_streak")}}))
    return out


def main(argv: list[str] | None = None) -> int:
    import pandas as pd

    ap = argparse.ArgumentParser(prog="python -m graph.observers.text_checks")
    ap.add_argument("--run", help="run id to judge (default: newest)")
    ap.add_argument("--staging-root", type=Path, default=STAGING_ROOT)
    ap.add_argument("-n", type=int, default=4, help="earlier runs in the baseline")
    ap.add_argument("--all", action="store_true", help="also print sources at level ok")
    a = ap.parse_args(argv)
    df = pd.DataFrame(silent_zeros(a.staging_root, a.run, a.n))
    print(df.groupby(["region", "level"]).size().unstack(fill_value=0).to_string())
    shown = df if a.all else df[df["level"] != "ok"]
    with pd.option_context("display.max_rows", None, "display.width", 200):
        print(shown.drop(columns="run").to_string(index=False))
    return 1 if (df["level"] == "red").any() else 0


if __name__ == "__main__":
    sys.exit(main())
