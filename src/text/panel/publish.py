"""Panel steps after counts: `aggregate` (subregion and region EPU aggregates) and `publish`
(the internal dashboards of TX-32, written on the 5TB, never published outside).

aggregate: per region, the subregion and region aggregates of `po text build --region`,
  through the same `process_unit_v2`, over the country caches that `counts` left. Only a
  subregion or region the panel holds WHOLE gets one: whole means every country the prod
  build would put in it (a corpus folder with active news.csv) is in the panel. A partial
  one (eca/central_asia: 2 of 5) gets no `_aggregate`: an aggregate of part of a subregion
  under its name would read as prod's number and is not. Its countries are still built
  and published, and the dashboard shows the subregion node without a series of its own.
  The daily tail anchor is the one `counts` used: p90 over the panel's files in the region.

publish: `po text publish` (every region in outputs/text, one call per tracker) with
  outputs/text/{dashboards,dashboard_data,database_status} and small_dashboard_integrated.html
  linked into <publish-root>/<run_id>/ (a8's disk), and src/text/plotting/addons linked to --addons-dir.
  The database-status rescan (TX-36, ~17 min over the whole corpus) is skipped, so the
  per-region xlsx has no `sources` sheet.
"""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path

import pandas as pd

from prices.weekly.step import REPO_ROOT

PUBLISH_LINKS = ("dashboards", "dashboard_data", "database_status", "small_dashboard_integrated.html")
# Addon HTMLs of `po text build-policy-addons`, copied from the prod checkout (untracked there).
ADDONS_DIR = Path.home() / "text_panel" / "addons"
TRACKERS = {"fuel": "fuel", "food": "food_security"}
# Publish runs kept under <publish-root>; older ones are removed only after a successful publish.
PUBLISH_KEEP = 5
BACKUP_MOUNT = Path("/mnt/backup5tb")


def _anchor(files: list[Path]) -> str:
    """run_analysis's daily tail start over these files."""
    from text.analysis.orchestrator import frontier_date, resolve_tail_start

    today = pd.Timestamp.today().normalize()
    per_source_max = []
    for fp in files:
        try:
            dates = pd.read_csv(fp, usecols=["date"], encoding="utf-8")["date"]
            dates = pd.to_datetime(dates, format="mixed", errors="coerce").dropna()
            dates = dates[dates <= today]
            if len(dates):
                per_source_max.append(dates.max())
        except Exception:
            continue
    return resolve_tail_start(frontier_date(per_source_max), today)


def whole_aggregates(region: str, panel: set[str]) -> tuple[list[dict], list[dict], list[str]]:
    """(country units, whole aggregate units, notes on partial ones) of `region` for the panel."""
    from text.analysis import main as build

    prod = build.preview_build_units(region=region)
    prod_countries = [u for u in prod if u["level"] == "country"]
    dirs = [d for d in build._get_country_dirs() if d.parent.parent.name == region and d.name in panel]
    units = build._discover_units(dirs, include_aggregates=True)
    countries = [u for u in units if u["level"] == "country"]
    keep, notes = [], []
    for u in units:
        if u["level"] == "country":
            continue
        if u["level"] == "subregion":
            sub = u["output_dir"].parent.name
            members = {c["name"] for c in prod_countries if c["output_dir"].parent.name == sub}
        else:
            members = {c["name"] for c in prod_countries}
        missing = sorted(members - panel)
        if missing:
            notes.append(f"{u['name']}: partial, {len(members) - len(missing)}/{len(members)} countries "
                         f"in the panel, no aggregate (missing {', '.join(missing)})")
        else:
            keep.append(u)
    return countries, keep, notes


def step_aggregate(a, srcs: dict, regions: dict) -> int:
    from text.analysis import main as build
    from text.analysis.orchestrator import process_unit_v2
    from text.process import _validate_baseline_window

    start, end = _validate_baseline_window("2024-01-01", "2024-12-31")
    subset = f"date >= '2015-01-01' and date <= '{pd.Timestamp.today().strftime('%Y-%m-%d')}'"
    panel = {c for (_, _, c) in srcs}
    for region in regions:
        countries, aggs, notes = whole_aggregates(region, panel)
        for n in notes:
            print(f"== {region}: {n}", flush=True)
        if not aggs:
            continue
        files = sorted({fp for u in countries for fp in u["news_dirs"]})
        anchor = _anchor(files)
        print(f"== {region}: {len(aggs)} aggregate(s) over {len(countries)} countries, "
              f"{len(files)} sources, daily tail {anchor}", flush=True)
        for u in aggs:
            t = time.time()
            diag = process_unit_v2(
                name=u["name"], level=u["level"], news_dirs=u["news_dirs"], output_dir=u["output_dir"],
                cache_dir=u["cache_dir"], cutoff_start_date=start, cutoff_end_date=end, subset_condition=subset,
                source_languages=u["source_languages"], max_parallel_sources=a.parallel_sources,
                data_root=build.DATA_ROOT, cache_root=build.CACHE_DIR, daily_tail_start=anchor,
            )
            epu = u["output_dir"] / "epu" / "epu.csv"
            if diag.get("status") != "ok" or not epu.exists() or epu.stat().st_mtime < t - 1:
                print(f"== {u['name']}: failed ({diag.get('status')}: {diag.get('error')})")
                return 1
            print(f"== {u['name']}: ok, {diag['total_articles']} articles, {time.time() - t:.0f}s -> "
                  f"{u['output_dir']}", flush=True)
    return 0


def _link(link: Path, target: Path) -> str | None:
    """Point `link` at `target`; a real file or directory there is never replaced."""
    if link.is_symlink():
        if link.resolve() == target.resolve():
            return None
        os.unlink(link)
    elif link.exists():
        return f"{link} is real, expected a link to {target}"
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(target)
    print(f"  linked {link} -> {target}", flush=True)
    return None


def step_publish(a) -> int:
    import click

    from text import publish

    if a.publish_root is None:
        print("publish needs --publish-root")
        return 1
    out = a.publish_root / a.run_id
    if out.exists():
        print(f"{out} exists: a run id publishes once")
        return 1
    trackers = [t for t in a.trackers.split(",") if t]
    for t in trackers:
        if not (a.addons_dir / TRACKERS[t]).is_dir():
            print(f"no addons for tracker {t} under {a.addons_dir}")
            return 1
    for name in PUBLISH_LINKS:
        if name.endswith(".html"):
            out.mkdir(parents=True, exist_ok=True)
        else:
            (out / name).mkdir(parents=True, exist_ok=True)
        err = _link(publish.OUTPUT_DIR / name, out / name)
        if err:
            print(err)
            return 1
    err = _link(REPO_ROOT / "src" / "text" / "plotting" / "addons", a.addons_dir)
    if err:
        print(err)
        return 1
    rc = 0
    for t in trackers:
        print(f"== tracker {t}", flush=True)
        try:
            publish.run_publish(tracker=t, skip_database_status=True)
        except click.ClickException as e:  # an addon missing for a region: the others are written
            print(f"== tracker {t}: {e.format_message()}")
            rc = 1
    htmls = sorted((out / "dashboards").glob("*/*.html"))
    for h in htmls:
        mb = h.stat().st_size / 1e6
        flag = "" if 12 <= mb <= 75 else "  OUTSIDE 12-75 MB"
        print(f"  {h.relative_to(out)}  {mb:.1f} MB{flag}")
    print(f"publish {out}: {len(htmls)} dashboards")
    if rc or not htmls:
        return 1
    _keep_newest(a.publish_root)
    return 0


def _keep_newest(root: Path) -> None:
    """Remove publish runs beyond the newest PUBLISH_KEEP (by mtime), logged in RETENTION.log."""
    if root.resolve().is_relative_to(BACKUP_MOUNT):
        print(f"{root} is on the 5TB: no retention", flush=True)
        return
    runs = sorted((p for p in root.iterdir() if p.is_dir() and (p / "dashboards").is_dir()),
                  key=lambda p: p.stat().st_mtime)
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    for old in runs[:-PUBLISH_KEEP]:
        mb = sum(f.stat().st_size for f in old.rglob("*") if f.is_file()) / 1e6
        shutil.rmtree(old)
        msg = f"{stamp} removed {old} ({mb:.0f} MB), keeping the newest {PUBLISH_KEEP}"
        print(msg, flush=True)
        with open(root / "RETENTION.log", "a") as f:
            f.write(msg + "\n")
