"""Import data/prices/_enrich/coicop_categories.xlsx → keywords/coicop/_class_tree.json.

Deterministic by design — re-running emits a byte-identical store so the
CI idempotency gate (§3.6) can compare before/after.

Tree mapping:
- depth-1 code (NN)         → COICOPClass
- depth-2 code (NN.N)       → Group
- depth-3 code (NN.N.N)     → Subgroup
- depth-4 code (NN.N.N.N)   → Leaf (carries includes/alsoIncludes/excludes)
- depth-5 code (NN.N.N.N.N) → folded into parent Leaf as additional anchor rows
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path
import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_XLSX = _REPO_ROOT / "data" / "prices" / "_enrich" / "coicop_categories.xlsx"
_DEFAULT_OUT = _REPO_ROOT / "src" / "prices" / "enrich" / "keywords" / "coicop"
_DEFAULT_SUBCATS = (
    _REPO_ROOT / "src" / "prices" / "enrich" / "static" / "coicop_subcategories.json"
)

_CLASS_RE = re.compile(r"^\d{2}$")
_GROUP_RE = re.compile(r"^\d{2}\.\d$")
_SUBGROUP_RE = re.compile(r"^\d{2}\.\d\.\d$")
_LEAF_RE = re.compile(r"^\d{2}\.\d\.\d\.\d$")
_ITEM_RE = re.compile(r"^\d{2}\.\d\.\d\.\d\.\d$")

_TITLE_TAG = re.compile(r"\s*\((?:ND|SD|D|S)\)\s*$")
_BULLET_SEP = re.compile(r"(?:_x000D_)?\n\s*\*\s*")
_EXCLUDE_LINE = re.compile(r"^(?P<phrase>.+?)\s*\((?P<code>\d{2}(?:\.\d+){0,3})\)\s*$")


def _norm(s: str) -> str:
    return unicodedata.normalize("NFC", s.replace("_x000D_", "").strip())


def _split_bullets(text: object) -> list[str]:
    if text is None or (isinstance(text, float) and pd.isna(text)):
        return []
    raw = str(text)
    out: set[str] = set()
    for chunk in _BULLET_SEP.split(raw):
        item = _norm(chunk).lstrip("*-• ").strip()
        if item:
            out.add(item)
    return sorted(out)


def _parse_excludes(text: object) -> list[tuple[str, str]]:
    """Return list of (code, phrase) for bullets containing a (NN.N.N.N) ref.

    Bullets without a parenthesised code are dropped — they reference COICOP
    chapters we can't link to a leaf code, so they would fail validation.
    """
    out: list[tuple[str, str]] = []
    for item in _split_bullets(text):
        m = _EXCLUDE_LINE.match(item)
        if not m:
            continue
        code = m.group("code")
        phrase = _norm(m.group("phrase"))
        out.append((code, phrase))
    out.sort()
    return out


def _parse_excludes_full(text: object) -> list[tuple[str | None, str]]:
    out: list[tuple[str | None, str]] = []
    for item in _split_bullets(text):
        m = _EXCLUDE_LINE.match(item)
        if m:
            out.append((m.group("code"), _norm(m.group("phrase"))))
        else:
            phrase = item.strip()
            if phrase:
                out.append((None, phrase))
    return out


def _classify(code: str) -> str:
    if _CLASS_RE.match(code):
        return "class"
    if _GROUP_RE.match(code):
        return "group"
    if _SUBGROUP_RE.match(code):
        return "subgroup"
    if _LEAF_RE.match(code):
        return "leaf"
    if _ITEM_RE.match(code):
        return "item"
    return "unknown"


def _ensure_class(tree: dict[str, dict], code: str) -> dict:
    return tree.setdefault(code, {"code": code, "label": "", "groups": {}})


def _ensure_group(tree: dict[str, dict], cls: str, grp: str) -> dict:
    klass = _ensure_class(tree, cls)
    return klass["groups"].setdefault(grp, {"code": grp, "label": "", "subgroups": {}})


def _ensure_subgroup(tree: dict[str, dict], cls: str, grp: str, sub: str) -> dict:
    group = _ensure_group(tree, cls, grp)
    return group["subgroups"].setdefault(sub, {"code": sub, "label": "", "leaves": {}})


def _ensure_leaf(
    tree: dict[str, dict], cls: str, grp: str, sub: str, leaf: str
) -> dict:
    subgroup = _ensure_subgroup(tree, cls, grp, sub)
    return subgroup["leaves"].setdefault(
        leaf,
        {
            "code": leaf,
            "label": "",
            "anchors": [],
            "excludes": [],
        },
    )


def build_tree(
    df: pd.DataFrame,
) -> tuple[dict[str, dict], dict[str, dict], list[dict], dict[str, list[str]]]:
    """Return (tree, leaves_by_code, exclude_rows, items_by_code). Depth-5 items
    fold into parent leaf for the typed tree AND keep their own anchor labels
    keyed by 5-digit code for depth-5 sub_label rows."""
    df = df[df["code"].notna()].copy()
    df["code"] = df["code"].astype(str)
    df = df.sort_values("code", kind="stable")

    tree: dict[str, dict] = {}
    leaves_by_code: dict[str, dict] = {}
    exclude_rows: list[dict] = []
    items_by_code: dict[str, list[str]] = {}

    for r in df.itertuples():
        code = r.code
        title = _norm(_TITLE_TAG.sub("", str(r.title)))
        kind = _classify(code)

        if kind == "class":
            _ensure_class(tree, code)["label"] = title
        elif kind == "group":
            cls = code.split(".")[0]
            _ensure_group(tree, cls, code)["label"] = title
        elif kind == "subgroup":
            parts = code.split(".")
            _ensure_subgroup(tree, parts[0], ".".join(parts[:2]), code)["label"] = title
        elif kind == "leaf":
            parts = code.split(".")
            leaf = _ensure_leaf(
                tree, parts[0], ".".join(parts[:2]), ".".join(parts[:3]), code
            )
            leaf["label"] = title
            leaf["anchors"].extend(_split_bullets(getattr(r, "includes", None)))
            leaf["anchors"].extend(_split_bullets(getattr(r, "alsoIncludes", None)))
            leaf["excludes"] = _parse_excludes(getattr(r, "excludes", None))
            for exc_code, phrase in _parse_excludes_full(getattr(r, "excludes", None)):
                exclude_rows.append(
                    {
                        "coicop_code": code,
                        "excluded_code": exc_code,
                        "phrase": phrase.lower(),
                        "lang": "en",
                    }
                )
            leaves_by_code[code] = leaf
        elif kind == "item":
            parts = code.split(".")
            parent_leaf_code = ".".join(parts[:4])
            leaf = _ensure_leaf(
                tree,
                parts[0],
                ".".join(parts[:2]),
                ".".join(parts[:3]),
                parent_leaf_code,
            )
            inc = _split_bullets(getattr(r, "includes", None))
            also = _split_bullets(getattr(r, "alsoIncludes", None))
            if title:
                leaf["anchors"].append(title)
            leaf["anchors"].extend(inc)
            leaf["anchors"].extend(also)
            leaves_by_code[parent_leaf_code] = leaf
            item_anchors = [a for a in [title, *inc, *also] if a]
            if item_anchors:
                items_by_code[code] = sorted(set(item_anchors))

    for leaf in leaves_by_code.values():
        leaf["anchors"] = sorted({a for a in leaf["anchors"] if a})

    return tree, leaves_by_code, exclude_rows, items_by_code


def _slug(s: str) -> str:
    s = unicodedata.normalize("NFC", s.lower())
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:60]


def expand_synonyms(
    synonyms: dict[str, list[dict]], leaves_by_code: dict[str, dict]
) -> list[dict]:
    """Expand JSON keys (which may end in .0 meaning "all leaves under this subgroup")
    into a flat list of {coicop_code, id, label} synonym rows.
    `id` is the verbatim JSON entry id — preserved so anchor slugs match real-cluster slugs.
    """
    out: list[dict] = []
    leaf_codes = set(leaves_by_code)
    for key, entries in sorted(synonyms.items()):
        parts = key.split(".")
        if len(parts) == 4 and parts[-1] == "0":
            sub_prefix = ".".join(parts[:3]) + "."
            target_codes = sorted(c for c in leaf_codes if c.startswith(sub_prefix))
        elif key in leaf_codes:
            target_codes = [key]
        else:
            target_codes = sorted(c for c in leaf_codes if c.startswith(key + "."))
        if not target_codes:
            continue
        for entry in entries:
            entry_id = str(entry.get("id", "")).strip()
            entry_id = re.sub(r"[\",]+label:?$", "", entry_id).strip('"')
            label = _norm(str(entry.get("label", ""))).strip()
            syns = [_norm(str(s)) for s in entry.get("synonyms", [])]
            phrases = sorted({p for p in [label, *syns] if p})
            for code in target_codes:
                for phrase in phrases:
                    out.append({"coicop_code": code, "id": entry_id, "label": phrase})
    return out


def build_sub_labels_df(
    leaves_by_code: dict[str, dict],
    synonym_rows: list[dict],
    items_by_code: dict[str, list[str]] | None = None,
) -> pd.DataFrame:
    rows: list[dict] = []
    for code, leaf in leaves_by_code.items():
        for label in leaf["anchors"]:
            rows.append(
                {
                    "coicop_code": code,
                    "id": _slug(label),
                    "label": label,
                    "lang": "en",
                    "role": "anchor",
                }
            )
    if items_by_code:
        for code, labels in items_by_code.items():
            for label in labels:
                rows.append(
                    {
                        "coicop_code": code,
                        "id": _slug(label),
                        "label": label,
                        "lang": "en",
                        "role": "anchor",
                    }
                )
    for syn in synonym_rows:
        rows.append(
            {
                "coicop_code": syn["coicop_code"],
                "id": syn["id"],
                "label": syn["label"],
                "lang": "en",
                "role": "synonym",
            }
        )
    if not rows:
        return pd.DataFrame(columns=["coicop_code", "id", "label", "lang", "role"])
    df = pd.DataFrame(rows, columns=["coicop_code", "id", "label", "lang", "role"])
    df = df[df["label"].astype(str).str.len() > 0]
    df = df.drop_duplicates(subset=["coicop_code", "id", "label", "lang", "role"])
    df = df.sort_values(
        ["coicop_code", "role", "lang", "label"], kind="stable"
    ).reset_index(drop=True)
    return df


def build_excludes_df(exclude_rows: list[dict]) -> pd.DataFrame:
    cols = ["coicop_code", "excluded_code", "phrase", "lang"]
    if not exclude_rows:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(exclude_rows, columns=cols)
    df = df[df["phrase"].astype(str).str.len() > 0]
    return (
        df.drop_duplicates(subset=cols)
        .sort_values(["coicop_code", "phrase"], kind="stable")
        .reset_index(drop=True)
    )


def _serialize_class(klass: dict) -> dict:
    """Serialize the built tree dict into the `_class_tree.json` store shape
    consumed by `keywords._registry._build_class` (content-preserving:
    leaves carry empty keywords_by_lang, excludes carry lang="en")."""
    return {
        "code": klass["code"],
        "label": klass["label"],
        "groups": [
            {
                "code": grp["code"],
                "label": grp["label"],
                "subgroups": [
                    {
                        "code": sub["code"],
                        "label": sub["label"],
                        "leaves": [
                            {
                                "code": leaf["code"],
                                "label": leaf["label"],
                                "keywords_by_lang": {},
                                "excludes": [
                                    {"code": c, "label": lbl, "lang": "en"}
                                    for c, lbl in leaf["excludes"]
                                ],
                            }
                            for leaf_code in sorted(sub["leaves"])
                            for leaf in [sub["leaves"][leaf_code]]
                        ],
                    }
                    for sub_code in sorted(grp["subgroups"])
                    for sub in [grp["subgroups"][sub_code]]
                ],
            }
            for grp_code in sorted(klass["groups"])
            for grp in [klass["groups"][grp_code]]
        ],
    }


def emit_class_tree_store(tree: dict[str, dict]) -> str:
    """Emit the full `_class_tree.json` store text (keyed by 2-digit class)."""
    store = {cls_code: _serialize_class(tree[cls_code]) for cls_code in sorted(tree)}
    return json.dumps(store, ensure_ascii=False, sort_keys=True, indent=1) + "\n"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Import COICOP xlsx → typed Python class files + sub-labels parquet"
    )
    parser.add_argument("--xlsx", type=Path, default=_DEFAULT_XLSX)
    parser.add_argument("--out-dir", type=Path, default=_DEFAULT_OUT)
    parser.add_argument("--subcats-json", type=Path, default=_DEFAULT_SUBCATS)
    parser.add_argument("--export-sub-labels-csv", type=Path, default=None)
    parser.add_argument("--import-sub-labels-csv", type=Path, default=None)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail with diff if regenerated output differs from on-disk files (CI gate)",
    )
    args = parser.parse_args(argv)

    df = pd.read_excel(args.xlsx)
    tree, leaves_by_code, exclude_rows, items_by_code = build_tree(df)

    # Deprecated: coicop_subcategories.json is now folded into _sub_labels.parquet
    # via this importer. Edit the JSON here; the parquet is the canonical store.
    synonyms: dict[str, list[dict]] = {}
    if args.subcats_json.exists():
        synonyms = json.loads(args.subcats_json.read_text())

    synonym_rows = expand_synonyms(synonyms, leaves_by_code)
    sub_df = build_sub_labels_df(leaves_by_code, synonym_rows, items_by_code)

    if args.import_sub_labels_csv is not None:
        csv_df = pd.read_csv(args.import_sub_labels_csv)
        cols = ["coicop_code", "id", "label", "lang", "role"]
        required = ["coicop_code", "label", "lang", "role"]
        missing = set(required) - set(csv_df.columns)
        if missing:
            sys.exit(f"--import-sub-labels-csv missing columns: {sorted(missing)}")
        if "id" not in csv_df.columns:
            csv_df["id"] = csv_df["label"].apply(_slug)
        sub_df = (
            csv_df[cols]
            .drop_duplicates(subset=cols)
            .sort_values(["coicop_code", "role", "lang", "label"], kind="stable")
            .reset_index(drop=True)
        )

    if args.check:
        _run_check(args.out_dir, tree, sub_df)
        return

    args.out_dir.mkdir(parents=True, exist_ok=True)
    init_path = args.out_dir / "__init__.py"
    if not init_path.exists():
        init_path.write_text(
            '"""COICOP taxonomy store — auto-generated by tools/import_coicop_xlsx.py."""\n'
        )

    # The CLASS tree is now stored as a single JSON store
    # (keywords/coicop/_class_tree.json) read by keywords._registry, replacing
    # the former per-class c{NN}.py modules.
    class_tree_path = args.out_dir / "_class_tree.json"
    class_tree_path.write_text(emit_class_tree_store(tree))

    excludes_df = build_excludes_df(exclude_rows)
    excludes_path = args.out_dir / "_excludes.parquet"
    excludes_df.to_parquet(excludes_path, index=False)

    if args.export_sub_labels_csv is not None:
        sub_df.to_csv(args.export_sub_labels_csv, index=False)

    print(
        f"Wrote class-tree store ({len(tree)} classes) and "
        f"{len(excludes_df)} exclude rows to {args.out_dir}"
    )


def _run_check(
    out_dir: Path,
    tree: dict[str, dict],
    sub_df: pd.DataFrame,
) -> None:
    import difflib

    expected = emit_class_tree_store(tree)
    target = out_dir / "_class_tree.json"
    actual = target.read_text() if target.exists() else ""
    # _sub_labels store is owned by the sub-label generator now; the importer no
    # longer participates in that diff.

    if actual != expected:
        sys.stdout.writelines(
            difflib.unified_diff(
                actual.splitlines(keepends=True),
                expected.splitlines(keepends=True),
                fromfile=str(target),
                tofile=f"{target} (regenerated)",
            )
        )
        sys.exit(1)
    print("OK: importer output matches committed files")


if __name__ == "__main__":
    main()
