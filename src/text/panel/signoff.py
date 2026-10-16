"""Sign-off for corpus writes: nothing lands in the canonical corpus without the user's signature.

- plan:  from finished staging runs, write <pending-root>/<plan_id>/ with, per source, the new
         news.csv/urls.csv rows (url-deduplicated across the runs and against the corpus file,
         alias losers sent to their winner folder), the corpus file each goes to with its sha256
         and row count now, and PLAN.tsv. The corpus and the staging runs are only read.
- apply: `po text panel signoff <plan_id>`: per source, refuse if a corpus file's sha256 is no
         longer the planned one, else append with text.merge.merge_source (tmp + os.replace),
         update the panel ledger, mark the panel's own staging runs merged, write APPLIED.
"""

from __future__ import annotations

import csv
import hashlib
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

PLAN = "PLAN.tsv"
RUNS = "RUNS"
APPLIED = "APPLIED"
# One line per source written, so a re-run after a refusal skips them instead of refusing them.
APPLIED_SOURCES = "APPLIED_SOURCES"
COLUMNS = ["region", "key", "file", "target", "target_sha256", "target_rows_before", "new_rows", "from"]


def sha256(path: Path) -> str:
    if not path.exists():
        return "absent"
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 22):
            h.update(chunk)
    return h.hexdigest()


def planned_runs(pending_root: Path) -> set[str]:
    """`<run>/<region>` of every plan not yet applied: step merge does not plan them twice."""
    if not pending_root.is_dir():
        return set()
    return {
        line for p in pending_root.glob(f"*/{RUNS}") if not (p.parent / APPLIED).exists()
        for line in p.read_text().split()
    }


def _new_rows(stage_csvs: list[Path], target: Path) -> tuple[pd.DataFrame, int]:
    staged = pd.concat([pd.read_csv(p, dtype=str, keep_default_na=False) for p in stage_csvs])
    staged = staged.drop_duplicates("url")
    before = 0
    if target.exists():
        urls = pd.read_csv(target, usecols=["url"], dtype=str, keep_default_na=False)["url"]
        before = len(urls)
        staged = staged[~staged["url"].isin(set(urls))]
    return staged, before


def plan(run_regions: list[Path], countries: set[str], corpus_root: Path, plan_dir: Path) -> list[dict]:
    """run_regions: <staging>/<run>/<region> dirs, oldest first. Returns the PLAN.tsv rows."""
    from text.ledger import iter_source_dirs
    from text.merge import _copy_dir_files
    from text.source_keys import aliases

    by_key: dict[tuple[str, str], list[Path]] = {}
    for rd in run_regions:
        for key, stage_dir in iter_source_dirs(rd):
            sub, country, folder = key.split("/")
            if country not in countries:
                continue
            folder = aliases().get(f"{country}/{folder}", folder)
            by_key.setdefault((rd.name, f"{sub}/{country}/{folder}"), []).append(stage_dir)
    plan_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for (region, key), stage_dirs in sorted(by_key.items()):
        out = plan_dir / region / key
        out.mkdir(parents=True, exist_ok=True)
        for name in ("news.csv", "urls.csv"):
            csvs = [d / name for d in stage_dirs if (d / name).exists()]
            if not csvs:
                continue
            target = corpus_root / region / key / name
            delta, before = _new_rows(csvs, target)
            if len(delta):
                delta.to_csv(out / name, index=False)
            rows.append({"region": region, "key": key, "file": name, "target": str(target),
                         "target_sha256": sha256(target), "target_rows_before": before,
                         "new_rows": len(delta), "from": ",".join(str(d) for d in stage_dirs)})
        failed = [d / "failed_urls_seen.csv" for d in stage_dirs if (d / "failed_urls_seen.csv").exists()]
        if failed:  # merge_source replaces it with the newest run's copy
            shutil.copy2(failed[-1], out / "failed_urls_seen.csv")
        for d in stage_dirs:
            for sub in ("failed", "metadata"):
                _copy_dir_files(d / sub, out / sub)
    with open(plan_dir / PLAN, "w", newline="") as f:
        w = csv.DictWriter(f, COLUMNS, delimiter="\t")
        w.writeheader()
        w.writerows(rows)
    (plan_dir / RUNS).write_text("".join(f"{rd.parent.name}/{rd.name}\n" for rd in run_regions))
    return rows


def summary(rows: list[dict]) -> str:
    by: dict[str, list[int]] = {}
    for r in rows:
        s = by.setdefault(r["region"], [set(), 0, 0])
        s[0].add(r["key"])
        s[1 if r["file"] == "news.csv" else 2] += int(r["new_rows"])
    return "; ".join(f"{g}: {len(k)} sources, +{n:,} news, +{u:,} urls" for g, (k, n, u) in sorted(by.items()))


def apply(plan_dir: Path, staging_root: Path) -> int:
    from text.ledger import Ledger
    from text.merge import MERGED_MARKER, merge_source

    if (plan_dir / APPLIED).exists():
        print(f"{plan_dir.name}: already applied ({(plan_dir / APPLIED).read_text().strip()})")
        return 1
    with open(plan_dir / PLAN, newline="") as f:
        rows = list(csv.DictReader(f, delimiter="\t"))
    by_source: dict[tuple[str, str], list[dict]] = {}
    for r in rows:
        by_source.setdefault((r["region"], r["key"]), []).append(r)
    log = plan_dir / APPLIED_SOURCES
    already = set(log.read_text().splitlines()) if log.exists() else set()
    refused, done = [], {}
    ledgers: dict[str, Ledger] = {}
    try:
        for (region, key), rs in sorted(by_source.items()):
            if f"{region}/{key}" in already:
                continue
            changed = [r["file"] for r in rs if sha256(Path(r["target"])) != r["target_sha256"]]
            if changed:
                refused.append(f"{region}/{key}: {', '.join(changed)} changed since the plan")
                print(f"REFUSED {region}/{key}: {', '.join(changed)} sha256 changed since the plan", flush=True)
                continue
            ledger = ledgers.setdefault(region, Ledger(region))
            target_dir = Path(rs[0]["target"]).parent
            state, a, b = merge_source(plan_dir / region / key, target_dir, ledger.get(key))
            ledger.put(key, state)
            with open(log, "a") as f:
                f.write(f"{region}/{key}\n")
            d = done.setdefault(region, [0, 0, 0])
            d[0] += 1
            d[1] += a
            d[2] += b
            if a or b:
                print(f"  {region}/{key}: +{a} news, +{b} urls", flush=True)
    finally:
        for ledger in ledgers.values():
            ledger.close()
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for g, (n, a, b) in sorted(done.items()):
        print(f"== {g}: {n} sources, +{a:,} news, +{b:,} urls", flush=True)
    if refused:
        print(f"{len(refused)} source(s) refused; plan not marked {APPLIED}")
        return 1
    # Only the panel's own staging runs are marked merged; prod's run dirs are never written.
    for line in (plan_dir / RUNS).read_text().split():
        rd = staging_root / line
        if rd.is_dir():
            (rd / MERGED_MARKER).write_text(f"{stamp} signoff {plan_dir.name}\n")
    (plan_dir / APPLIED).write_text(
        f"{stamp} " + "; ".join(f"{g}: {n} sources +{a} news +{b} urls" for g, (n, a, b) in sorted(done.items())) + "\n"
    )
    return 0
