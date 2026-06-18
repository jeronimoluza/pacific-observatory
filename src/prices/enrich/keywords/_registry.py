"""Registry that loads a COICOP class tree, injecting sub_labels from the store.

The COICOP taxonomy data lives in two JSON stores under `keywords/coicop/`:
- `_class_tree.json`        — the hierarchical COICOPClass/Group/Subgroup/Leaf/
                              ExcludeRef tree, keyed by 2-digit class code.
- `_sub_labels_store.json`  — the flat SubLabel records (id, label,
                              keywords_by_lang, allowed_bases, role, numeric_id),
                              keyed by class code → leaf code.

Both stores are the single source of truth (content byte-preserved from the
former c{NN}.py / c{NN}_subs.py modules). The registry reconstructs the typed
dataclasses from the stores at load time, injects the matching sub_labels into
each Leaf via `dataclasses.replace`, and validates the result.

Validation (raised when a class is loaded):
- Sub-label dicts must reference leaves that exist in the class.
- Leaf `excludes` references must resolve to another code in the same class.
"""

from __future__ import annotations

import dataclasses
import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

from prices.enrich.keywords.types import (
    COICOPClass,
    ExcludeRef,
    Group,
    Leaf,
    SubLabel,
    Subgroup,
)

_COICOP_DIR = Path(__file__).resolve().parent / "coicop"
_CLASS_TREE_PATH = _COICOP_DIR / "_class_tree.json"
_SUB_LABELS_PATH = _COICOP_DIR / "_sub_labels_store.json"


@lru_cache(maxsize=1)
def _class_store() -> Mapping[str, Any]:
    if not _CLASS_TREE_PATH.exists():
        return {}
    return json.loads(_CLASS_TREE_PATH.read_text())


@lru_cache(maxsize=1)
def _sub_labels_store() -> Mapping[str, Any]:
    if not _SUB_LABELS_PATH.exists():
        return {}
    return json.loads(_SUB_LABELS_PATH.read_text())


def _build_sublabel(d: Mapping[str, Any]) -> SubLabel:
    bases = d.get("allowed_bases")
    return SubLabel(
        id=d["id"],
        label=d["label"],
        keywords_by_lang={k: tuple(v) for k, v in d["keywords_by_lang"].items()},
        allowed_bases=frozenset(bases) if bases is not None else None,
        role=d["role"],
        numeric_id=d.get("numeric_id"),
    )


def _load_sub_labels_for(class_code: str) -> Mapping[str, tuple[SubLabel, ...]]:
    by_leaf = _sub_labels_store().get(class_code, {})
    return {
        leaf_code: tuple(_build_sublabel(d) for d in records)
        for leaf_code, records in by_leaf.items()
    }


def _build_leaf(d: Mapping[str, Any]) -> Leaf:
    return Leaf(
        code=d["code"],
        label=d["label"],
        keywords_by_lang={k: tuple(v) for k, v in d["keywords_by_lang"].items()},
        excludes=tuple(
            ExcludeRef(code=e["code"], label=e["label"], lang=e["lang"])
            for e in d["excludes"]
        ),
    )


def _build_class(d: Mapping[str, Any]) -> COICOPClass:
    return COICOPClass(
        code=d["code"],
        label=d["label"],
        groups=tuple(
            Group(
                code=g["code"],
                label=g["label"],
                subgroups=tuple(
                    Subgroup(
                        code=sg["code"],
                        label=sg["label"],
                        leaves=tuple(_build_leaf(x) for x in sg["leaves"]),
                    )
                    for sg in g["subgroups"]
                ),
            )
            for g in d["groups"]
        ),
    )


def _collect_leaf_codes(klass: COICOPClass) -> set[str]:
    out: set[str] = set()
    for grp in klass.groups:
        for sub in grp.subgroups:
            for leaf in sub.leaves:
                out.add(leaf.code)
    return out


def _collect_all_codes(klass: COICOPClass) -> set[str]:
    out: set[str] = {klass.code}
    for grp in klass.groups:
        out.add(grp.code)
        for sub in grp.subgroups:
            out.add(sub.code)
            for leaf in sub.leaves:
                out.add(leaf.code)
    return out


def _validate(klass: COICOPClass, by_leaf: Mapping[str, tuple[SubLabel, ...]]) -> None:
    leaf_codes = _collect_leaf_codes(klass)
    for leaf_code in by_leaf:
        if leaf_code not in leaf_codes:
            raise RuntimeError(
                f"Orphan sub_labels: leaf {leaf_code!r} has no matching leaf in "
                f"class {klass.code}"
            )

    all_codes = _collect_all_codes(klass)
    class_prefix = klass.code + "."
    for grp in klass.groups:
        for sub in grp.subgroups:
            for leaf in sub.leaves:
                for ref in leaf.excludes:
                    if not ref.code.startswith(class_prefix):
                        continue
                    if ref.code not in all_codes:
                        raise RuntimeError(
                            f"Dangling exclude in leaf {leaf.code!r}: "
                            f"references unknown code {ref.code!r} "
                            f"within class {klass.code}"
                        )


_OTHER_FALLBACK = SubLabel(
    id="_other",
    label="Other",
    keywords_by_lang={},
    allowed_bases=None,
    role="synonym",
    numeric_id=None,
)


def _ensure_other(subs: tuple[SubLabel, ...]) -> tuple[SubLabel, ...]:
    if any(s.id == "_other" for s in subs):
        return subs
    return subs + (_OTHER_FALLBACK,)


def _inject_sub_labels(
    klass: COICOPClass, by_leaf: Mapping[str, tuple[SubLabel, ...]]
) -> COICOPClass:
    new_groups: list[Group] = []
    for grp in klass.groups:
        new_subs: list[Subgroup] = []
        for sub in grp.subgroups:
            new_leaves: list[Leaf] = []
            for leaf in sub.leaves:
                subs_for_leaf = _ensure_other(by_leaf.get(leaf.code, ()))
                new_leaves.append(dataclasses.replace(leaf, sub_labels=subs_for_leaf))
            new_subs.append(dataclasses.replace(sub, leaves=tuple(new_leaves)))
        new_groups.append(dataclasses.replace(grp, subgroups=tuple(new_subs)))
    return dataclasses.replace(klass, groups=tuple(new_groups))


def load(class_code: str) -> COICOPClass | None:
    """Load one COICOP class by 2-digit code, with sub_labels injected.

    Returns None if the class is absent from the store. Raises on validation
    errors.
    """
    record = _class_store().get(class_code)
    if record is None:
        return None
    klass = _build_class(record)
    by_leaf = _load_sub_labels_for(class_code)
    _validate(klass, by_leaf)
    return _inject_sub_labels(klass, by_leaf)
