"""Merge corpus-discovered policy measures into a region's tracker workbook.

The discovery pipeline leaves its output in ``discovered_<region>.json`` sidecars
that only the dashboard builder reads, so the workbooks a human opens still show
the curated rows alone. This folds the sidecar rows into the ``Policies`` sheet
so the workbook is the full historic record. The merged workbook is written to
today's edition (``outputs/text/policy_tracker/<tracker>/YYYY-MM-DD/``) and the
pre-merge copy to that tracker's ``backups/``.

Discovered rows are appended, never merged over existing ones, and are marked in
a ``Provenance`` column so curated and corpus rows stay distinguishable.

The sidecar ``Label`` ("active", "announced") is a lifecycle state, while the
workbook ``Label`` is a controlled response-type vocabulary ("Secure supply",
"Support to households"). They are different axes, so the sidecar value goes to
a new ``Status`` column and ``Label`` is left blank rather than filled with an
out-of-vocabulary value that would silently corrupt the column.

Usage:
    po text policy-merge-workbook --region sar --tracker fuel
    po text policy-merge-workbook --all
"""

import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from text.plotting.trackers import (
    WORKBOOK_ROOT,
    latest_workbook,
    start_edition,
    workbook_dir,
)

from text.policy import DEFAULT_OUT_DIR

# Columns carried over from the sidecar that the workbook does not already have.
EXTRA_COLS = [
    "Provenance",
    "Status",
    "Date Basis",
    "Date Confidence",
    "Articles",
    "Onset Year",
]


def paths_for(region: str, tracker: str, sidecar: Path) -> tuple[Path | None, Path]:
    """Current workbook (newest edition) and sidecar for one region/tracker pair."""
    sub = "" if tracker == "fuel" else "food_security"
    root = workbook_dir(WORKBOOK_ROOT, tracker)
    return latest_workbook(root, region), sidecar / sub / f"discovered_{region}.json"


def build_rows(discovered: list[dict], existing: pd.DataFrame) -> pd.DataFrame:
    """Map sidecar records onto the workbook's column set.

    ``#`` is a per-country counter in the workbook -- sparse and restarting at 1
    for each country -- so new rows continue from each country's own maximum
    rather than from the sheet length.

    Not every workbook keeps that promise: eca/fuel mixes plain integers with
    two global string ID schemes ("P002", "R010") in the same column, which
    makes the column object dtype and ``max()`` raise. Those spellings carry no
    per-country ordinal, so they are ignored for the counter and new rows fall
    back to integers, which cannot collide with them.
    """
    numeric = pd.to_numeric(existing["#"], errors="coerce")
    next_num = numeric.groupby(existing["Country"]).max().to_dict()
    out = []
    for rec in discovered:
        # provenance "both" means the discovery matched a measure the workbook
        # already carries -- it enriches that row with corpus evidence rather
        # than describing a new measure, so appending it would duplicate an
        # existing curated entry under a different wording.
        if rec.get("provenance") == "both":
            continue
        country = rec.get("Country")
        # NaN when the country's every existing row uses a string ID scheme, so
        # it has no integer to continue from and starts at 1.
        prev = next_num.get(country)
        prev = 0 if prev is None or pd.isna(prev) else int(prev)
        n = prev + 1
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


def merge(region: str, tracker: str, stamp: str, sidecar: Path) -> str:
    wb_path, sc_path = paths_for(region, tracker, sidecar)
    if wb_path is None:
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

    root = workbook_dir(WORKBOOK_ROOT, tracker)
    backup = root / "backups" / f"{region}.pre-discovery-{stamp}.bak.xlsx"
    backup.parent.mkdir(exist_ok=True)
    shutil.copy2(wb_path, backup)
    out_path = start_edition(root) / f"{region}.xlsx"

    with pd.ExcelWriter(out_path, engine="openpyxl") as xw:
        merged.to_excel(xw, sheet_name="Policies", index=False)
        for name, df in sheets.items():
            if name != "Policies":
                df.to_excel(xw, sheet_name=name, index=False)

    return (
        f"{tracker:5s} {region:7s} {before:4d} + {len(new_rows):4d} = {len(merged):4d} rows"
        f"   -> {out_path.parent.name}/{out_path.name}   backup: {backup.name}"
    )


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="po text policy-merge-workbook")
    ap.add_argument("--region")
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    ap.add_argument("--tracker", choices=["fuel", "food"])
    ap.add_argument("--all", action="store_true", help="every region with a sidecar")
    args = ap.parse_args(argv)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    if args.all:
        jobs = []
        for tracker, sub in (("fuel", ""), ("food", "food_security")):
            for sc in sorted((args.out_dir / sub).glob("discovered_*.json")):
                jobs.append((sc.stem.replace("discovered_", ""), tracker))
    else:
        if not args.region or not args.tracker:
            ap.error("--region and --tracker required unless --all")
        jobs = [(args.region, args.tracker)]

    for region, tracker in jobs:
        print(merge(region, tracker, stamp, args.out_dir))


if __name__ == "__main__":
    main()
