#!/usr/bin/env python3
"""Merge corpus-discovered policy measures into a region's tracker workbook.

The discovery pipeline leaves its output in ``discovered_<region>.json`` sidecars
that only the dashboard builder reads, so the workbooks a human opens still show
the curated rows alone. This folds the sidecar rows into the ``Policies`` sheet
so the workbook is the full historic record, backing up the original first.

Discovered rows are appended, never merged over existing ones, and are marked in
a ``Provenance`` column so curated and corpus rows stay distinguishable.

The sidecar ``Label`` ("active", "announced") is a lifecycle state, while the
workbook ``Label`` is a controlled response-type vocabulary ("Secure supply",
"Support to households"). They are different axes, so the sidecar value goes to
a new ``Status`` column and ``Label`` is left blank rather than filled with an
out-of-vocabulary value that would silently corrupt the column.

Usage:
    python scripts/policy_merge_workbook.py --region sar --tracker fuel
    python scripts/policy_merge_workbook.py --all
"""

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

CANON = Path("data/text/policy_tracker")
SIDECAR = Path("data/text/policy_tracker_extended")

# Columns carried over from the sidecar that the workbook does not already have.
EXTRA_COLS = [
    "Provenance",
    "Status",
    "Date Basis",
    "Date Confidence",
    "Articles",
    "Onset Year",
]


def paths_for(region: str, tracker: str) -> tuple[Path, Path]:
    """Workbook and sidecar for one region/tracker pair."""
    sub = "" if tracker == "fuel" else "food_security"
    return CANON / sub / f"{region}.xlsx", SIDECAR / sub / f"discovered_{region}.json"


def build_rows(discovered: list[dict], existing: pd.DataFrame) -> pd.DataFrame:
    """Map sidecar records onto the workbook's column set.

    ``#`` is a per-country counter in the workbook -- sparse and restarting at 1
    for each country -- so new rows continue from each country's own maximum
    rather than from the sheet length.
    """
    next_num = existing.groupby("Country")["#"].max().to_dict()
    out = []
    for rec in discovered:
        # provenance "both" means the discovery matched a measure the workbook
        # already carries -- it enriches that row with corpus evidence rather
        # than describing a new measure, so appending it would duplicate an
        # existing curated entry under a different wording.
        if rec.get("provenance") == "both":
            continue
        country = rec.get("Country")
        n = int(next_num.get(country, 0) or 0) + 1
        next_num[country] = n
        out.append(
            {
                "Country": country,
                "#": n,
                "Policy": rec.get("Policy"),
                "Policy Description": rec.get("Policy Description"),
                "Label": None,
                "Active or Proposed Date": rec.get("Active or Proposed Date"),
                "Source": rec.get("Source"),
                "Evaluation": None,
                "Reason": None,
                "Source URL": None,
                "Category": rec.get("category"),
                "Subcategory": rec.get("subcategory"),
                "ID_v6": rec.get("ID_v6"),
                "Provenance": rec.get("provenance") or "corpus",
                "Status": rec.get("Label"),
                "Date Basis": rec.get("date_basis"),
                "Date Confidence": rec.get("date_confidence"),
                "Articles": rec.get("n_articles"),
                "Onset Year": rec.get("onset_year"),
            }
        )
    return pd.DataFrame(out)


def merge(region: str, tracker: str, stamp: str) -> str:
    wb_path, sc_path = paths_for(region, tracker)
    if not wb_path.exists():
        return f"{tracker:5s} {region:7s} SKIP - no workbook"
    if not sc_path.exists():
        return f"{tracker:5s} {region:7s} SKIP - no sidecar"

    discovered = json.loads(sc_path.read_text())
    xl = pd.ExcelFile(wb_path)
    sheets = {name: xl.parse(name) for name in xl.sheet_names}
    policies = sheets["Policies"]

    if "Provenance" in policies.columns and (policies["Provenance"] == "corpus").any():
        n = int((policies["Provenance"] == "corpus").sum())
        return f"{tracker:5s} {region:7s} SKIP - already merged ({n} corpus rows)"

    before = len(policies)
    policies = policies.copy()
    policies["Provenance"] = "workbook"
    for col in EXTRA_COLS:
        if col not in policies.columns:
            policies[col] = None

    new_rows = build_rows(discovered, policies)
    merged = pd.concat([policies, new_rows], ignore_index=True)
    merged = merged[list(policies.columns)]

    backup = wb_path.with_suffix(f".pre-discovery-{stamp}.bak.xlsx")
    shutil.copy2(wb_path, backup)

    with pd.ExcelWriter(wb_path, engine="openpyxl") as xw:
        merged.to_excel(xw, sheet_name="Policies", index=False)
        for name, df in sheets.items():
            if name != "Policies":
                df.to_excel(xw, sheet_name=name, index=False)

    return (
        f"{tracker:5s} {region:7s} {before:4d} + {len(new_rows):4d} = {len(merged):4d} rows"
        f"   backup: {backup.name}"
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--region")
    ap.add_argument("--tracker", choices=["fuel", "food"])
    ap.add_argument("--all", action="store_true", help="every region with a sidecar")
    args = ap.parse_args()

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    if args.all:
        jobs = []
        for tracker, sub in (("fuel", ""), ("food", "food_security")):
            for sc in sorted((SIDECAR / sub).glob("discovered_*.json")):
                jobs.append((sc.stem.replace("discovered_", ""), tracker))
    else:
        if not args.region or not args.tracker:
            ap.error("--region and --tracker required unless --all")
        jobs = [(args.region, args.tracker)]

    for region, tracker in jobs:
        print(merge(region, tracker, stamp))


if __name__ == "__main__":
    main()
