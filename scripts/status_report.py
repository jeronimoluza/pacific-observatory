"""Accurate status reporter for the rebuild.

Fixes two prior bugs:
- Counted child worker PIDs as separate scrapes (overcounted ~2.5x)
- Read stale tqdm progress lines from old log files (showed bogus ETAs
  for sources that finished long ago)

Usage: poetry run python3 scripts/status_report.py
"""
from __future__ import annotations

import glob
import os
import re
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
os.chdir(REPO_ROOT)


def get_running_sources() -> set[tuple[str, str]]:
    """Return {(country, source)} pairs for currently running 'po text collect'
    processes. Only counts processes that have BOTH -c (or --country) and -s
    (or --source) flags. Filters out zsh wrapper false positives where '-c'
    means 'zsh -c <script>'."""
    out = subprocess.check_output(
        "ps aux | grep 'po text collect' | grep -v grep",
        shell=True, text=True,
    )
    seen = set()
    for line in out.strip().split("\n"):
        if not line:
            continue
        # Skip zsh wrappers — they have '/bin/zsh -c' followed by a shell script
        if "/bin/zsh" in line and "shell-snapshots" in line:
            continue
        # Look for country and source flags
        c = re.search(r" (?:-c|--country) (\S+)", line)
        s = re.search(r" (?:-s|--source) (\S+)", line)
        if not s:
            continue
        country = c.group(1) if c else None
        source = s.group(1)
        # Even without -c, we accept the source — we'll resolve country from yaml
        seen.add((country, source))
    return seen


def find_country_for_source(source: str) -> str | None:
    """Given a source name with no -c flag, find which country YAML it lives in."""
    matches = glob.glob(f"src/text/configs/eca/*/*/{source}.yaml")
    if not matches:
        return None
    # path like src/text/configs/eca/<sub>/<country>/<source>.yaml
    parts = matches[0].split("/")
    return parts[-2]


def parse_recent_eta(log_path: str, max_age_minutes: int = 5) -> float | None:
    """Return ETA in hours from the last tqdm line in the log, but ONLY if the
    log was modified recently (i.e., the scrape is actively writing). Stale
    logs return None."""
    if not log_path or not os.path.exists(log_path):
        return None
    mtime = datetime.fromtimestamp(os.path.getmtime(log_path))
    if datetime.now() - mtime > timedelta(minutes=max_age_minutes):
        return None
    try:
        text = open(log_path).read()
    except OSError:
        return None
    for line in reversed(text.replace("\r", "\n").split("\n")):
        m = re.search(r"\[(.+?)<(.+?),", line)
        if m:
            eta = m.group(2)
            parts = eta.split(":")
            if len(parts) == 3:
                try:
                    return int(parts[0]) + int(parts[1]) / 60
                except ValueError:
                    return None
    return None


def find_log(country: str, source: str) -> str | None:
    """Return the most recently modified ORCHESTRATOR log (logs/rebuild/*) for
    this source — those are where tqdm progress bars are written. The
    logs/text/ files contain DEBUG-level HTTP traces with no progress info."""
    slug = source.replace("/", "_")
    candidates = glob.glob(f"logs/rebuild/*_{country}_{slug}.log")
    if not candidates:
        return None
    return max(candidates, key=lambda p: os.path.getmtime(p))


def main() -> None:
    running_pairs = get_running_sources()
    # Resolve missing country values
    resolved_running: set[tuple[str, str]] = set()
    for country, source in running_pairs:
        if country is None:
            country = find_country_for_source(source) or "unknown"
        resolved_running.add((country, source))

    running_sources_only = {s for _, s in resolved_running}

    now = datetime.now()
    cutoff_24h = now - timedelta(hours=24)

    rows = []
    for yaml_path in glob.glob("src/text/configs/eca/*/*/*.yaml"):
        name = os.path.basename(yaml_path)
        parts = yaml_path.split("/")
        subregion = parts[-3]
        country = parts[-2]
        is_disabled = name.startswith("_0_")
        source = name[:-5].replace("_0_", "") if is_disabled else name[:-5]

        csv = f"data/text/eca/{subregion}/{country}/{source}/news.csv"
        urls = f"data/text/eca/{subregion}/{country}/{source}/urls.csv"
        n = 0
        expected = 0
        mtime: datetime | None = None
        if os.path.exists(csv):
            try:
                n = len(pd.read_csv(csv, usecols=["url"], low_memory=False))
            except Exception:
                pass
            mtime = datetime.fromtimestamp(os.path.getmtime(csv))
        if os.path.exists(urls):
            try:
                expected = len(pd.read_csv(urls, usecols=["url"], low_memory=False))
            except Exception:
                pass
        if expected < n:
            expected = n

        is_running = source in running_sources_only
        eta_h = parse_recent_eta(find_log(country, source)) if is_running else None
        rows.append({
            "subregion": subregion, "country": country, "source": source,
            "rows": n, "expected": expected,
            "is_disabled": is_disabled,
            "is_running": is_running,
            "is_recent_done": bool(
                mtime and mtime > cutoff_24h
                and not is_running
                and n > 100
            ),
            "eta_h": eta_h,
        })

    df = pd.DataFrame(rows)

    hdr = (
        f'{"country":<22} {"act":>4} {"dis":>4} {"run":>4} {"24h":>4}'
        f' {"current":>11} {"expected":>11} {"cov%":>5} {"ETA":>6}'
    )
    print(hdr)
    print("-" * len(hdr))
    sub_order = [
        "eastern_europe", "south_caucasus", "central_asia",
        "western_balkans", "central_europe", "turkiye", "russian_federation",
    ]
    for sub in sub_order:
        print(f"\n--- {sub} ---")
        g = df[df["subregion"] == sub]
        for country, gc in g.groupby("country"):
            active = (~gc["is_disabled"]).sum()
            disabled = gc["is_disabled"].sum()
            rn = gc["is_running"].sum()
            d24 = gc["is_recent_done"].sum()
            cur = gc["rows"].sum()
            exp = gc["expected"].sum()
            cov = 100 * cur / exp if exp else 0
            etas = gc[gc["is_running"]]["eta_h"].dropna()
            eta_str = f"{etas.max():.0f}h" if len(etas) else "-"
            print(
                f"  {country:<20} {active:>4} {disabled:>4} {rn:>4} {d24:>4}"
                f" {cur:>11,} {exp:>11,} {cov:>5.1f}% {eta_str:>6}"
            )
    print("\n" + "=" * len(hdr))
    active = (~df["is_disabled"]).sum()
    disabled = df["is_disabled"].sum()
    rn = df["is_running"].sum()
    d24 = df["is_recent_done"].sum()
    cur = df["rows"].sum()
    exp = df["expected"].sum()
    print(
        f"  TOTAL                {active:>4} {disabled:>4} {rn:>4} {d24:>4}"
        f" {cur:>11,} {exp:>11,} {100 * cur / exp:>5.1f}%"
    )

    # Sanity numbers
    print()
    print(f"  Unique running sources (real count): {len(running_sources_only)}")
    print(f"  Sources with active progress (recent ETA): "
          f"{df[df['is_running']]['eta_h'].dropna().count()}")


if __name__ == "__main__":
    main()
