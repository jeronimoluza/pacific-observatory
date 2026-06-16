"""Registry that loads a COICOP class file, injecting sub_labels from its sidecar.

For each `keywords/coicop/c<NN>.py` there is a sibling `c<NN>_subs.py` exposing
`SUB_LABELS_BY_LEAF: dict[str, tuple[SubLabel, ...]]`. The registry walks the
class tree at load time, injects the matching sub_labels into each Leaf via
`dataclasses.replace`, and validates that every sub_label's parent leaf exists.

Validation (raised when the class file is loaded):
- Sub-label dicts must reference leaves that exist in the class.
- Leaf `excludes` references must resolve to another code in the same class.
"""

from __future__ import annotations

import dataclasses
import importlib
from typing import Mapping

from prices.enrich.keywords.types import COICOPClass, Group, Leaf, SubLabel, Subgroup

_COICOP_PKG = "prices.enrich.keywords.coicop"


def _load_sub_labels_for(class_code: str) -> Mapping[str, tuple[SubLabel, ...]]:
    mod_name = f"{_COICOP_PKG}.c{class_code}_subs"
    try:
        mod = importlib.import_module(mod_name)
    except ModuleNotFoundError:
        return {}
    return getattr(mod, "SUB_LABELS_BY_LEAF", {})


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

    Returns None if no `c{NN}.py` exists. Raises on validation errors.
    """
    mod_name = f"{_COICOP_PKG}.c{class_code}"
    try:
        mod = importlib.import_module(mod_name)
    except ModuleNotFoundError:
        return None
    klass: COICOPClass | None = getattr(mod, "CLASS", None)
    if klass is None:
        return None
    by_leaf = _load_sub_labels_for(class_code)
    _validate(klass, by_leaf)
    return _inject_sub_labels(klass, by_leaf)
