#!/usr/bin/env python3
"""One-shot layout consolidation to match the repointed config paths.

Three moves, all renames within the same filesystem (instant, no copy):

  1. data/prices/_enrich/  -> data/prices/enrich/   (working artifacts fold in
     alongside the curated gold/; confirmed-dead items are left behind)
  2. data/prices/_build/   -> data/prices/build/     (live eap_fnb_* outputs;
     the producer-less eap_pharma_* orphans are left behind)
  3. gold: archive the orphan gold_labels.parquet, rebuild it as the consolidated
     union of the gold_v5_* sources, and rename the holdout to held_out_gold.parquet

DATA SAFETY: this MOVES files under data/ and NEVER deletes. Per CLAUDE.md, Claude
does NOT run it — the USER runs it from the repo root:

    PYTHONPATH=src python scripts/migrate_layout_consolidation.py

Idempotent: re-running skips items already moved. Confirmed-dead leftovers are
printed as an rm-list for you to remove by hand once you've verified the move.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

DATA = REPO_ROOT / "data" / "prices"
OLD_ENRICH = DATA / "_enrich"
NEW_ENRICH = DATA / "enrich"
OLD_BUILD = DATA / "_build"
NEW_BUILD = DATA / "build"
GOLD = NEW_ENRICH / "gold"

# Confirmed-dead items in _enrich — left behind (never moved) for manual removal.
DEAD_ENRICH = {
    "products.parquet",  # producer-less orphan (0% input_hash overlap)
    "_deprecated",  # retired cascade cache (enrichments.parquet et al.)
    "_tier_b_index",  # retired KNN/HNSW index
    "_tier_b_index_ft_v2",  # retired KNN/HNSW index
    "_tier_b_misses.parquet",  # retired cascade artifact
    "validation_runs",  # retired base_items classify skill output
    "gold_labels.parquet",  # legacy tainted (canonical now lives in enrich/gold/)
    "gold_labels_v4.parquet",  # legacy
}
DEAD_BUILD_GLOB = "eap_pharma_personal_care_*"  # no producer in current build code
# Retired base_items package outputs sitting at the data/prices root.
DEAD_ROOT = (
    "base_items.parquet",
    "gazetteer.parquet",
    "derived_form_lexicon.parquet",
    "derived_neg_lexicon.parquet",
    "source_boilerplate.parquet",
)


def _move_into(src_dir: Path, dst_dir: Path, skip: set[str]) -> tuple[list, list]:
    moved: list[str] = []
    left: list[str] = []
    if not src_dir.exists():
        return moved, left
    dst_dir.mkdir(parents=True, exist_ok=True)
    for item in sorted(src_dir.iterdir()):
        if item.name in skip:
            left.append(item.name)
            continue
        target = dst_dir / item.name
        if target.exists():
            left.append(f"{item.name} (target exists — skipped)")
            continue
        shutil.move(str(item), str(target))
        moved.append(item.name)
    return moved, left


def _consolidate_and_rename_gold() -> None:
    from prices.enrich.classifier import dataset

    labels = GOLD / "gold_labels.parquet"
    archive = GOLD / "gold_labels.pre_consolidation.parquet"
    if labels.exists() and not archive.exists():
        shutil.move(str(labels), str(archive))
        print(f"  archived orphan gold_labels.parquet -> {archive.name}")

    summary = dataset.consolidate_gold(GOLD)
    print(
        f"  built gold_labels.parquet: {summary['n_rows']} rows "
        f"from {len(summary['sources'])} sources"
    )

    old_holdout = GOLD / "holdout_cert_raw.parquet"
    new_holdout = GOLD / "held_out_gold.parquet"
    if old_holdout.exists() and not new_holdout.exists():
        shutil.move(str(old_holdout), str(new_holdout))
        print(f"  renamed holdout -> {new_holdout.name}")


def main() -> None:
    print("== _enrich -> enrich ==")
    moved, _ = _move_into(OLD_ENRICH, NEW_ENRICH, DEAD_ENRICH)
    print(f"  moved {len(moved)} item(s){': ' + ', '.join(moved) if moved else ''}")

    print("== _build -> build ==")
    dead_build = (
        {p.name for p in OLD_BUILD.glob(DEAD_BUILD_GLOB)}
        if OLD_BUILD.exists()
        else set()
    )
    bmoved, _ = _move_into(OLD_BUILD, NEW_BUILD, dead_build)
    print(f"  moved {len(bmoved)} item(s){': ' + ', '.join(bmoved) if bmoved else ''}")

    print("== gold consolidation ==")
    if GOLD.exists():
        _consolidate_and_rename_gold()
    else:
        print("  (no enrich/gold — skipped)")

    print("\n== MANUAL CLEANUP — run these yourself (the safety hook blocks Claude) ==")
    if OLD_ENRICH.exists():
        print(
            f"  rm -rf {OLD_ENRICH}   # dead leftovers only, after verifying the move"
        )
    for p in DATA.glob("_build/" + DEAD_BUILD_GLOB):
        print(f"  rm {p}")
    if OLD_BUILD.exists():
        print(f"  rmdir {OLD_BUILD}   # once empty")
    for name in DEAD_ROOT:
        p = DATA / name
        if p.exists():
            print(f"  rm {p}   # retired base_items output")


if __name__ == "__main__":
    main()
