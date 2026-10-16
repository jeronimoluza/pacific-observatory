"""Step programs of `po text panel`, run as `python -m text.panel.steps <step> ...` inside the step's unit.

- ledger:  form the panel ledger (<state-dir>/<region>.sqlite) from the panel's corpus folders.
- collect: staged collect of the panel's enabled sources into <staging-root>/<run_id>/, with
           the refresh-text-region runner.sh (watchdog, per-source cap), STATUS.md and .done
           in the format of staged_collect_all.sh, so graph.observers.text_delta reads it.
- merge:   plan, not write: every unplanned run under <staging-root> becomes a sign-off plan
           under <pending-root>/<run_id>/ (text.panel.signoff); refuses if a staged source is
           outside the panel.
- signoff: apply that plan to <corpus-root> and the panel ledger, after the user signs.
- counts:  EPU build per panel country (source_counts cache + outputs) from the corpus, one
           run per region (one daily tail anchor), countries only.
- aggregate: subregion/region aggregates the panel holds whole (text.panel.publish).
- publish: internal dashboards under <publish-root>/<run_id>/ (text.panel.publish).
- check:   text.counts checks (T23/T26/watermark/hash) and silent zeros of this run.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

from prices.weekly.guards import free_gb
from prices.weekly.step import REPO_ROOT
from text.panel import publish

CONFIGS = REPO_ROOT / "src" / "text" / "configs"
SCRIPTS = REPO_ROOT / ".claude" / "skills" / "refresh-text-region" / "scripts"
DISABLED = re.compile(r"^enabled:\s*false\b", re.I | re.M)
STATES = ("DONE", "TIMEOUT", "FAIL", "STUCK")


def panel_sources(countries: list[str]) -> dict[tuple[str, str, str], list[str]]:
    """(region, sub, country) -> enabled source keys, filtered like launch_refresh.sh."""
    from core.config import get_country_path

    out = {}
    for c in countries:
        try:
            region, sub, _ = get_country_path(c)
        except ValueError:  # a config folder outside regions.yaml (`pacific`)
            (d,) = CONFIGS.glob(f"*/*/{c}")
            region, sub = d.parent.parent.name, d.parent.name
        d = CONFIGS / region / sub / c
        out[(region, sub, c)] = sorted(
            y.stem for y in d.glob("*.yaml") if not y.stem.startswith("_") and not DISABLED.search(y.read_text())
        )
    return out


def _regions(srcs: dict) -> dict[str, list[tuple[str, str, list[str]]]]:
    by = defaultdict(list)
    for (region, sub, c), s in srcs.items():
        by[region].append((sub, c, s))
    return dict(by)


def step_ledger(a) -> int:
    from text.ledger import Ledger, read_source_dir

    blocked = {}
    for region, entries in _regions(panel_sources(a.countries)).items():
        ledger = Ledger(region, a.state_dir)
        n = 0
        try:
            for sub, country, _ in entries:
                country_dir = a.corpus_root / region / sub / country
                if not country_dir.is_dir():
                    print(f"  {region}/{sub}/{country}: not in corpus, no ledger rows", flush=True)
                    continue
                for d in sorted(p for p in country_dir.iterdir() if p.is_dir() and not p.name.startswith((".", "_"))):
                    if not (d / "news.csv").exists() and not (d / "urls.csv").exists():
                        continue
                    key = f"{sub}/{country}/{d.name}"
                    try:
                        state = read_source_dir(d)
                    except Exception as e:  # same set bootstrap() blocks on, plus OS errors on the exFAT
                        blocked[f"{region}:{key}"] = f"{type(e).__name__}: {e}"
                        ledger.block(key, blocked[f"{region}:{key}"])
                        print(f"  BLOCKED {region}:{key}: {e}", flush=True)
                        continue
                    ledger.put(key, state)
                    ledger.conn.execute("DELETE FROM blocked WHERE key = ?", (key,))
                    ledger.conn.commit()
                    n += 1
                    print(f"  {region}:{key} news={len(state.news)} watermark={state.watermark}", flush=True)
        finally:
            ledger.close()
        print(f"== {region}: {n} sources -> {a.state_dir / (region + '.sqlite')}", flush=True)
    if blocked:
        print(f"{len(blocked)} blocked: {', '.join(blocked)}")
    return 1 if blocked else 0


def _staged_rows(region_dir: Path) -> tuple[int, int]:
    import pandas as pd

    fs = sorted(region_dir.glob("*/*/*/news.csv"))
    return len(fs), sum(len(pd.read_csv(f, usecols=["url"])) for f in fs)


def step_collect(a) -> int:
    srcs = panel_sources(a.countries)
    regions = _regions(srcs)
    missing = [r for r in regions if not (a.state_dir / f"{r}.sqlite").exists()]
    if missing:
        print(f"no ledger for {', '.join(missing)} under {a.state_dir}: run `po text panel step ledger` first")
        return 1
    run_dir = a.staging_root / a.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    sha = subprocess.run(["git", "-C", str(REPO_ROOT), "rev-parse", "--short", "HEAD"],
                         capture_output=True, text=True).stdout.strip()
    status = run_dir / "STATUS.md"
    status.write_text(
        f"# Staged collect {a.run_id}\n\nhost: panel  commit: {sha}  P={a.parallel} cap={a.cap}s  "
        f"countries: {len(srcs)}\nfree at start: {free_gb(a.staging_root)} GB under {a.staging_root}, "
        f"{free_gb(Path('/'))} GB under /\n\n"
        "| region | done | timeout | fail | stuck | sources with rows | news rows | note |\n"
        "|---|---|---|---|---|---|---|---|\n"
    )
    env = {"STAGING": str(run_dir), "MAX_SOURCE_SECONDS": str(a.cap), "KILL_SCRIPT": str(SCRIPTS / "kill_collect_python.sh")}
    for region, entries in regions.items():
        jobs = [f"{c}|{s}" for _, c, ss in entries for s in ss]
        events = run_dir / f"events_{region}.log"
        print(f"== {region}: {len(jobs)} sources, events {events}", flush=True)
        with open(events, "w") as ev:
            ev.write(f"[REFRESH-START] @ {int(time.time())}\n")
            ev.flush()
            subprocess.run(
                ["xargs", "-P", str(a.parallel), "-I", "JOB", "env", *[f"{k}={v}" for k, v in env.items()],
                 "bash", str(SCRIPTS / "runner.sh"), "JOB"],
                input="\n".join(jobs) + "\n", text=True, stdout=ev, stderr=subprocess.STDOUT, cwd=REPO_ROOT,
            )
            ev.write(f"[REFRESH-DONE] @ {int(time.time())}\n")
        lines = events.read_text(errors="replace").splitlines()
        n = {s: sum(line.startswith("[" + s) for line in lines) for s in STATES}
        n_src, n_rows = _staged_rows(run_dir / region)
        with open(status, "a") as f:
            f.write(f"| {region} | {n['DONE']} | {n['TIMEOUT']} | {n['FAIL']} | {n['STUCK']} | {n_src} | {n_rows} | |\n")
        print(f"== {region}: done={n['DONE']} timeout={n['TIMEOUT']} fail={n['FAIL']} stuck={n['STUCK']} "
              f"sources_with_rows={n_src} news_rows={n_rows}", flush=True)
    with open(status, "a") as f:
        f.write(f"\nfree: {free_gb(a.staging_root)} GB under {a.staging_root}, {free_gb(Path('/'))} GB under /\n")
    (run_dir / ".done").touch()  # po text merge takes only finished runs
    return 0


def step_merge(a) -> int:
    """Plan only: the corpus is written by `po text panel signoff <run_id>`."""
    from text.merge import pending_runs
    from text.panel import signoff

    srcs = panel_sources(a.countries)
    allowed = {(region, f"{sub}/{c}") for (region, sub, c) in srcs}
    if not a.staging_root.is_dir():
        print(f"no staging root {a.staging_root}")
        return 1
    # Runs of plans still awaiting sign-off are planned again, together with the new ones.
    plan_dir = a.pending_root / a.run_id
    if plan_dir.exists():
        print(f"{plan_dir} exists: a run id plans once")
        return 1
    folded = signoff.open_plans(a.pending_root)
    planned = {rd for rds in folded.values() for rd in rds}
    run_regions = sorted(planned)
    for region in _regions(srcs):
        runs = [r for r in pending_runs(a.staging_root, region) if r / region not in planned]
        outside = sorted(
            f"{run.name}/{region}/{d.relative_to(run / region)}"
            for run in runs for d in (run / region).glob("*/*/*")
            if d.is_dir() and (region, str(d.parent.relative_to(run / region))) not in allowed
        )
        if outside:
            print(f"{region}: staged sources outside --countries, refusing to merge: {', '.join(outside[:20])}")
            return 1
        print(f"== {region}: {len(runs)} unplanned run(s)", flush=True)
        run_regions += [run / region for run in runs]
    if not run_regions:
        print("nothing to plan")
        return 0
    rows = signoff.plan(sorted(run_regions, key=lambda p: (p.parent.name, p.name)), {c for (_, _, c) in srcs},
                        a.corpus_root, plan_dir)
    for old in folded:
        (old / signoff.SUPERSEDED).write_text(f"by {plan_dir.name}\n")
        print(f"{old.name}: superseded by {plan_dir.name}")
    print(f"plan {plan_dir}: {signoff.summary(rows)}")
    print(f"apply with: po text panel signoff {a.run_id}")
    return 0


def step_signoff(a) -> int:
    from text import ledger
    from text.panel import signoff

    if ledger.STATE_DIR != a.state_dir:
        print(f"TEXT_STATE_DIR is {ledger.STATE_DIR}, step was given {a.state_dir}")
        return 1
    return signoff.apply(a.pending_root / a.run_id, a.staging_root)


def _link_corpus(regions, corpus_root: Path) -> str | None:
    """data/text/<region> -> <corpus-root>/<region>: the build reads data/text under the repo."""
    base = REPO_ROOT / "data" / "text"
    base.mkdir(parents=True, exist_ok=True)
    for region in regions:
        link, target = base / region, corpus_root / region
        if link.is_symlink():
            if link.resolve() != target.resolve():
                return f"{link} -> {link.resolve()}, expected {target}"
        elif link.exists():
            return f"{link} is a real directory, expected a link to {target}"
        else:
            link.symlink_to(target)
            print(f"  linked {link} -> {target}", flush=True)
    return None


def _build_scopes(srcs: dict, corpus_root: Path) -> list[dict]:
    """run_analysis filters: the panel's countries of each region, countries only, so the
    region shares one daily tail anchor; the aggregates are the `aggregate` step's."""
    scopes = []
    for region, entries in _regions(srcs).items():
        have = [c for sub, c, _ in entries if (corpus_root / region / sub / c).is_dir()]
        for sub, c, _ in entries:
            if c not in have:
                print(f"== {region}/{sub}/{c}: not in corpus, skipped", flush=True)
        if have:
            scopes.append({"countries": have})
    return scopes


def step_counts(a) -> int:
    from text.analysis import main as build
    from text.process import _validate_baseline_window

    srcs = panel_sources(a.countries)
    err = _link_corpus(_regions(srcs), a.corpus_root)
    if err:
        print(err)
        return 1
    start, end = _validate_baseline_window("2024-01-01", "2024-12-31")
    region_of = {c: r for (r, _, c) in srcs}
    for scope in _build_scopes(srcs, a.corpus_root):
        label = region_of[scope["countries"][0]]
        units = build.preview_build_units(**scope)
        t = time.time()
        print(f"== {label}: build, {len(units)} units", flush=True)
        build.run_analysis(**scope, cutoff_start_date=start, cutoff_end_date=end,
                           max_parallel_sources=a.parallel_sources)
        # run_analysis logs a failed unit and goes on; a reused cache keeps its old mtime.
        bad = []
        for u in units:
            epu = u["output_dir"] / "epu" / "epu.csv"
            params = u["cache_dir"] / "source_counts.params.json"
            if not epu.exists() or epu.stat().st_mtime < t - 1 or (u["level"] == "country" and not params.exists()):
                bad.append(u["name"])
        if bad:
            print(f"== {label}: build failed for {', '.join(bad)} (no params or no fresh epu.csv)")
            return 1
        print(f"== {label}: ok {len(units)} units {time.time() - t:.0f}s", flush=True)
    return 0


def step_check(a) -> int:
    from graph.checks import text_counts
    from graph.observers.text_checks import silent_zeros
    from graph.observers.text_delta import list_runs

    rows = text_counts.read(REPO_ROOT / "data" / "text" / "cache", a.corpus_root, a.state_dir, a.countries)
    findings = text_counts.evaluate(rows)
    for f in findings:
        print(f"{f['color']:<8} {f['node']}  {f['partition']:<36} {f['msg']}")
    red = sum(f["color"] == "rojo" for f in findings)
    print(f"text.counts: {len(rows)} countries, rojo {red}, amarillo {len(findings) - red}")
    if a.staging_root.is_dir() and a.run_id in list_runs(a.staging_root):
        zs = silent_zeros(a.staging_root, a.run_id)
        for z in zs:
            if z["level"] in ("red", "yellow"):
                print(f"{z['level']:<8} text.delta  {z['region']}/{z['tag']} 0 rows, streak {z['zero_streak']}, "
                      f"baseline {z['baseline']}")
        zred = sum(z["level"] == "red" for z in zs)
        print(f"text.delta {a.run_id}: {len(zs)} sources, red {zred}, "
              f"yellow {sum(z['level'] == 'yellow' for z in zs)}")
        red += zred
    return 1 if red else 0


def step_aggregate(a) -> int:
    srcs = panel_sources(a.countries)
    err = _link_corpus(_regions(srcs), a.corpus_root)
    if err:
        print(err)
        return 1
    return publish.step_aggregate(a, srcs, _regions(srcs))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="text.panel.steps")
    ap.add_argument("step", choices=["ledger", "collect", "merge", "signoff", "counts", "check", "aggregate", "publish"])
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--countries", required=True)
    ap.add_argument("--corpus-root", type=Path, required=True)
    ap.add_argument("--state-dir", type=Path, required=True)
    ap.add_argument("--staging-root", type=Path, required=True)
    ap.add_argument("--pending-root", type=Path, required=True)
    ap.add_argument("--parallel", type=int, default=12)
    ap.add_argument("--cap", type=int, default=300)
    ap.add_argument("--parallel-sources", type=int, default=2, help="counts: --max-parallel-sources of the build")
    ap.add_argument("--publish-root", type=Path)
    ap.add_argument("--addons-dir", type=Path, default=publish.ADDONS_DIR)
    ap.add_argument("--trackers", default="fuel,food", help="publish: comma list of fuel, food")
    a = ap.parse_args(argv)
    a.countries = [c for c in a.countries.split(",") if c]
    return {"ledger": step_ledger, "collect": step_collect, "merge": step_merge,
            "signoff": step_signoff, "counts": step_counts, "check": step_check,
            "aggregate": step_aggregate, "publish": publish.step_publish}[a.step](a)


if __name__ == "__main__":
    sys.exit(main())
