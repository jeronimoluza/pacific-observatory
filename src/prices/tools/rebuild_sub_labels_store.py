"""Deterministic rebuild of `_sub_labels_store.json` + division-01 class-tree leaves.

Assembles the locked 538-leaf short-item-only sub-label store (D1 purge prose,
D2 538-leaf digit invariant, D3 in-leaf grounding, D4 English-only) from the
COICOP xlsx via `harvest_leaf_items` (Plan 01), and reconciles `_class_tree.json`
so division-01 leaves move from 4-digit to 5-digit (OQ1) — keeping
`registry.load('01')` valid against the new food leaf keys.

The script reads the xlsx (read-only) and the existing class tree, then writes
`_sub_labels_store.json` and `_class_tree.json`. Running it twice is idempotent
(stable id/label ordering: sub_labels sorted by id, leaf keys sorted, division
keys sorted; classes 02..15 left byte-unchanged).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

from prices.enrich import config
from prices.tools.harvest_coicop_short_items import harvest_leaf_items

_COICOP_DIR = Path(__file__).resolve().parent.parent / "enrich" / "keywords" / "coicop"
_SUB_LABELS_PATH = _COICOP_DIR / "_sub_labels_store.json"
_CLASS_TREE_PATH = _COICOP_DIR / "_class_tree.json"
_SHEET = "COICOP_2018"

_PAREN_RE = re.compile(r"\([^)]*\)")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def _load_xlsx() -> pd.DataFrame:
    df = pd.read_excel(config.COICOP_XLSX, sheet_name=_SHEET)
    df = df[df["code"].notna()].copy()
    df["code"] = df["code"].astype(str)
    return df


def _derive_leaves(codes: set[str]) -> list[str]:
    """Deepest-available xlsx leaves — mirrors taxonomy_index.load_taxonomy_index."""
    return [
        c
        for c in codes
        if not any(other != c and other.startswith(c + ".") for other in codes)
    ]


def _slugify(item: str) -> str:
    """Slug id: lowercase, strip parenthetical content, non-alnum -> single hyphen.

    Mirrors the existing store convention (e.g. `Maize (corn)` -> `maize-corn`).
    """
    s = _PAREN_RE.sub(" ", item).lower()
    s = _NON_ALNUM_RE.sub("-", s).strip("-")
    return s


def _keywords_for(item: str) -> list[str]:
    """English-only keyword list `[item, item.lower()]`, deduped, order-preserving."""
    out: list[str] = []
    for kw in (item, item.lower()):
        if kw and kw not in out:
            out.append(kw)
    return out


def _build_sub_records(items: list[str], numeric_id: str | None) -> list[dict]:
    """SubLabel dicts for one leaf, deduped by slug id, sorted by id."""
    by_id: dict[str, dict] = {}
    for item in items:
        slug = _slugify(item)
        if not slug or slug in by_id:
            continue
        by_id[slug] = {
            "allowed_bases": None,
            "id": slug,
            "keywords_by_lang": {"en": _keywords_for(item)},
            "label": item,
            "numeric_id": numeric_id,
            "role": "anchor",
        }
    return [by_id[k] for k in sorted(by_id)]


def build_store(harvest: dict[str, list[str]], leaves: list[str]) -> dict:
    """Assemble the 538-leaf store keyed by division -> leaf_code -> [SubLabel...]."""
    store: dict[str, dict[str, list[dict]]] = {}
    for leaf in leaves:
        division = leaf.split(".")[0]
        is_food = division == "01"
        numeric_id = leaf if is_food else None
        records = _build_sub_records(harvest.get(leaf, []), numeric_id)
        store.setdefault(division, {})[leaf] = records
    # Stable ordering: division keys, then leaf keys within each division.
    return {
        div: {leaf: store[div][leaf] for leaf in sorted(store[div])}
        for div in sorted(store)
    }


def reconcile_class_tree(tree: dict, df: pd.DataFrame) -> dict:
    """Replace division-01 4-digit leaves with their xlsx 5-digit children.

    Group/subgroup nesting is preserved: each 5-digit leaf maps to the subgroup
    whose code equals its first 3 dotted parts. Classes 02..15 are untouched.
    """
    titles = dict(zip(df["code"], df["title"]))
    codes = set(df["code"])
    food5 = sorted(c for c in codes if c.startswith("01") and c.count(".") == 4)
    by_subgroup: dict[str, list[str]] = {}
    for code in food5:
        subgroup = ".".join(code.split(".")[:3])
        by_subgroup.setdefault(subgroup, []).append(code)

    klass = tree["01"]
    for grp in klass["groups"]:
        for sg in grp["subgroups"]:
            children = sorted(by_subgroup.get(sg["code"], []))
            new_leaves = []
            for code in children:
                title = str(titles[code])
                new_leaves.append(
                    {
                        "code": code,
                        "excludes": [],
                        "keywords_by_lang": {"en": _keywords_for(title)},
                        "label": title,
                    }
                )
            sg["leaves"] = new_leaves
    return tree


def _write_json(path: Path, data: dict) -> None:
    text = json.dumps(data, indent=1, ensure_ascii=False) + "\n"
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text)
    tmp.replace(path)


def main() -> None:
    df = _load_xlsx()
    codes = set(df["code"])
    leaves = _derive_leaves(codes)

    food5 = [c for c in leaves if c.startswith("01") and c.count(".") == 4]
    nf4 = [c for c in leaves if not c.startswith("01") and c.count(".") == 3]
    food4 = [c for c in leaves if c.startswith("01") and c.count(".") == 3]
    assert len(leaves) == 538, f"expected 538 leaves, got {len(leaves)}"
    assert len(food5) == 269, f"expected 269 food-5-digit, got {len(food5)}"
    assert len(nf4) == 269, f"expected 269 non-food-4-digit, got {len(nf4)}"
    assert not food4, f"food 4-digit leaves must be gone, got {food4}"

    harvest = harvest_leaf_items(set(leaves))
    store = build_store(harvest, leaves)

    tree = json.loads(_CLASS_TREE_PATH.read_text())
    tree = reconcile_class_tree(tree, df)

    _write_json(_SUB_LABELS_PATH, store)
    _write_json(_CLASS_TREE_PATH, tree)

    total = sum(len(store[d]) for d in store)
    print(f"wrote {total} leaf keys to {_SUB_LABELS_PATH.name}")
    print(f"reconciled division-01 leaves in {_CLASS_TREE_PATH.name}")


if __name__ == "__main__":
    main()
