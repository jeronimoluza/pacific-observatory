"""Phase 0.9 — atomize the COICOP sub-label store (STAGE + MERGE).

Two deterministic passes bracket a Claude Sonnet agent fan-out (driven by the
executing Claude Code session, NOT this script — there is no LLM client here,
no pydantic_ai, no rate_limit, no API key):

  1. `python scripts/prices_phase09_atomize_sub_labels.py stage`
     Reads the current sub-label store (via keywords._registry) + the COICOP
     xlsx, writes one grounded input bundle per leaf to
     data/prices/enrich/_audit/atomize_inputs/{leaf}.json. No LLM calls.

  2. (fan-out) The executing session dispatches Sonnet subagents over the 538
     bundles; each leaf gets one AtomizedLeaf proposal JSON written to
     data/prices/enrich/_audit/atomize_proposals/{leaf}.json.

  3. `python scripts/prices_phase09_atomize_sub_labels.py merge`
     Validates every proposal against the AtomizedLeaf pydantic schema (the
     trust boundary: untrusted LLM output crosses into the frozen vocabulary
     here), assembles the new store with exactly ONE canonical lowercase
     keyword per id, enforces the per-leaf cross-product cap (logged, never
     silently truncated), and atomically writes it. The store is left
     WRITTEN-BUT-UNACCEPTED (A4): Plan 03's human spot-review accepts/freezes it.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import pandas as pd
from pydantic import BaseModel, Field, field_validator

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from prices.enrich import config  # noqa: E402
from prices.enrich.keywords import _registry  # noqa: E402

INPUTS_DIR = config.ENRICH_DIR / "_audit" / "atomize_inputs"
PROPOSALS_DIR = config.ENRICH_DIR / "_audit" / "atomize_proposals"
STORE_PATH = (
    REPO_ROOT
    / "src"
    / "prices"
    / "enrich"
    / "keywords"
    / "coicop"
    / "_sub_labels_store.json"
)

# Per-leaf cross-product cap (Pitfall 3 / Open Q1). Bounds single-leaf class-6/7
# balloon; the aggregate bound is Plan 01's test_parquet_row_ceiling=4260.
PER_LEAF_CAP = 40

# Cleanliness contract — mirrors test_labels_atomic_clean (SC-3). Kept as
# constants, not prose, so a negative grep elsewhere cannot self-trip.
_DURABILITY_RE = re.compile(r"\((?:nd|sd|s|d)\)", re.IGNORECASE)
_SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def _label_violations(label: str) -> list[str]:
    """Return the list of atomic/clean violations for a label (empty == clean)."""
    out: list[str] = []
    low = label.lower()
    if "n.e.c" in low:
        out.append("nec")
    if low.startswith("other "):
        out.append("leading-other")
    if ":" in label:
        out.append("colon")
    if ";" in label:
        out.append("semicolon")
    if "," in label:
        out.append("comma")
    if " and " in f" {low} ":
        out.append("and-run")
    if " or " in f" {low} ":
        out.append("or-run")
    if _DURABILITY_RE.search(label):
        out.append("durability")
    return out


class AtomizedItem(BaseModel):
    """One atomic sub-label: a slug id + its single canonical lowercase keyword."""

    id: str
    label: str

    @field_validator("id")
    @classmethod
    def _slug_ok(cls, v: str) -> str:
        v = v.strip().lower()
        if not _SLUG_RE.match(v):
            raise ValueError(f"id {v!r} is not a lowercase hyphen/alnum slug (SC-4b)")
        return v

    @field_validator("label")
    @classmethod
    def _clean_ok(cls, v: str) -> str:
        v = v.strip().lower()
        if not v:
            raise ValueError("empty label")
        bad = _label_violations(v)
        if bad:
            raise ValueError(f"label {v!r} not atomic/clean (SC-3): {bad}")
        return v


class AtomizedLeaf(BaseModel):
    coicop_code: str
    items: list[AtomizedItem] = Field(min_length=1)


def _leaf_title(df: pd.DataFrame, code: str) -> str:
    row = df[df["code"] == code]
    if row.empty:
        return ""
    return str(row.iloc[0]["title"]).replace("_x000D_", "").strip()


def _leaf_text(df: pd.DataFrame, code: str, col: str) -> str:
    row = df[df["code"] == code]
    if row.empty:
        return ""
    val = row.iloc[0][col]
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    return str(val).replace("_x000D_", "").strip()


def _iter_leaves():
    """Yield (class_code, leaf_code, current_labels) over the CURRENT store."""
    store = _registry._sub_labels_store()
    for cc, by_leaf in store.items():
        for leaf_code, records in by_leaf.items():
            yield cc, leaf_code, [r["label"] for r in records]


def cmd_stage() -> None:
    INPUTS_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.read_excel(config.COICOP_XLSX)
    df = df[df["code"].notna()].copy()
    df["code"] = df["code"].astype(str)
    staged = 0
    thin = 0
    for cc, leaf_code, current_items in _iter_leaves():
        is_food = leaf_code.startswith("01")
        is_thin = len(current_items) == 0
        bundle = {
            "leaf_code": leaf_code,
            "class_code": cc,
            "title": _leaf_title(df, leaf_code),
            "intro": _leaf_text(df, leaf_code, "intro"),
            "includes": _leaf_text(df, leaf_code, "includes"),
            "alsoIncludes": _leaf_text(df, leaf_code, "alsoIncludes"),
            "excludes": _leaf_text(df, leaf_code, "excludes"),
            "current_items": current_items,
            "sibling_rows": current_items,
            "is_food": is_food,
            "numeric_id": leaf_code if is_food else None,
            "thin": is_thin,
        }
        (INPUTS_DIR / f"{leaf_code}.json").write_text(
            json.dumps(bundle, indent=2, ensure_ascii=False)
        )
        staged += 1
        thin += int(is_thin)
    print(f"Staged {staged} leaf bundles to {INPUTS_DIR}")
    print(f"  thin (empty current_items, enrichment targets): {thin}")


def _write_json(path: Path, data: dict) -> None:
    text = json.dumps(data, indent=1, ensure_ascii=False) + "\n"
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text)
    tmp.replace(path)


def cmd_merge() -> None:
    store = _registry._sub_labels_store()
    expected = [(cc, lc) for cc, by in store.items() for lc in by]

    proposals: dict[str, AtomizedLeaf] = {}
    missing: list[str] = []
    malformed: list[tuple[str, str]] = []
    for _cc, leaf_code in expected:
        pth = PROPOSALS_DIR / f"{leaf_code}.json"
        if not pth.exists():
            missing.append(leaf_code)
            continue
        try:
            proposals[leaf_code] = AtomizedLeaf.model_validate_json(pth.read_text())
        except Exception as e:  # pydantic ValidationError or bad JSON
            malformed.append((leaf_code, str(e).splitlines()[0]))

    if missing or malformed:
        print("MERGE ABORTED — store NOT written (trust-boundary gate).")
        if missing:
            head = ", ".join(missing[:20])
            print(
                f"  missing {len(missing)} proposals: {head}{' ...' if len(missing) > 20 else ''}"
            )
        for lc, err in malformed[:20]:
            print(f"  malformed {lc}: {err}")
        if len(malformed) > 20:
            print(f"  ... and {len(malformed) - 20} more malformed")
        raise SystemExit(1)

    new_store: dict[str, dict[str, list[dict]]] = {}
    capped: list[tuple[str, int]] = []
    for cc, by in store.items():
        new_store[cc] = {}
        for leaf_code in by:
            al = proposals[leaf_code]
            is_food = leaf_code.startswith("01")
            seen_ids: set[str] = set()
            items: list[AtomizedItem] = []
            for it in al.items:
                if it.id in seen_ids:
                    continue  # one canonical keyword per id (kills case-variant dups at source)
                seen_ids.add(it.id)
                items.append(it)
            if len(items) > PER_LEAF_CAP:
                capped.append((leaf_code, len(items) - PER_LEAF_CAP))
                items = items[:PER_LEAF_CAP]
            if not items:
                raise SystemExit(
                    f"leaf {leaf_code} has 0 items after dedup — fail loud (SC-2)"
                )
            new_store[cc][leaf_code] = [
                {
                    "allowed_bases": None,
                    "id": it.id,
                    "keywords_by_lang": {"en": [it.label]},
                    "label": it.label,
                    "numeric_id": leaf_code if is_food else None,
                    "role": "anchor",
                }
                for it in items
            ]

    _write_json(STORE_PATH, new_store)
    total_items = sum(len(recs) for by in new_store.values() for recs in by.values())
    print(
        f"Wrote atomized store: {len(expected)} leaves, {total_items} items -> {STORE_PATH}"
    )
    if capped:
        print(f"  per-leaf cap ({PER_LEAF_CAP}) applied to {len(capped)} leaves:")
        for lc, dropped in capped:
            print(f"    {lc}: dropped {dropped}")
    else:
        print(f"  per-leaf cap ({PER_LEAF_CAP}): no leaf exceeded it")
    print(
        "Store is WRITTEN-BUT-UNACCEPTED (A4): not committed/frozen until Plan 03 sign-off."
    )


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Phase 0.9 sub-label atomization STAGE/MERGE"
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser(
        "stage", help="Write per-leaf grounded input bundles (no LLM, no key)"
    )
    sub.add_parser(
        "merge", help="Validate proposals + atomically write the atomized store"
    )
    args = ap.parse_args()
    if args.cmd == "stage":
        cmd_stage()
    elif args.cmd == "merge":
        cmd_merge()


if __name__ == "__main__":
    main()
