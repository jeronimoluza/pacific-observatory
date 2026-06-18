"""Cross-check Phase 2 — consolidation layer.

Compares the structural enricher's `pricing_basis` against the categorical
enricher's classified leaf+sub_label. `consolidate()` returns a routing bucket
so the cascade can arbitrate disagreements via `allowed_bases` instead of
relying on the conservative `pricing_basis_mismatch` refusal that Phase 1
inherited.

Buckets:
  PASS_THROUGH    : allowed_bases is permissive — no action
  CLEAN           : structural ∈ allowed — no action
  NO_STRUCTURAL   : tier-a produced no basis — no action
  SILENT_OVERRIDE : |allowed|=1 and structural disagrees — rewrite basis
  ESCALATE_MULTI  : |allowed|>1 and structural disagrees — defer to tier-c
"""

from __future__ import annotations

import threading
from typing import Iterable, Optional

import pandas as pd

from prices.enrich import config
from prices.enrich.keywords import _registry as registry
from prices.enrich.keywords.types import COICOPClass, SubLabel

_CROSS_CHECK_PARQUET = config.ENRICH_DIR / "cross_check.parquet"

_lock = threading.Lock()
_class_cache: dict[str, COICOPClass | None] = {}

# Canonical (basis → standard_unit) mapping mirroring schemas.ProductEnrichment.
# Used by the leaf-gate B-reset: when SILENT_OVERRIDE rewrites the basis, the
# old amount/unit (whatever tier-a extracted) is no longer trustworthy and
# must be reset together with the basis. count/multiplier are basis-orthogonal
# and are preserved by the caller.
_CANONICAL_UNIT_FOR_BASIS: dict[str, str] = {
    "mass": "kg",
    "volume": "lt",
    "length": "mt",
    "count": "unit",
    "item": "item",
}


def canonical_unit_for_basis(basis: str) -> str | None:
    """Return the canonical standard_unit for a basis, or None if unknown."""
    return _CANONICAL_UNIT_FOR_BASIS.get(basis)


def _class_for(code: str) -> Optional[COICOPClass]:
    if not code:
        return None
    cc = code.split(".")[0].zfill(2)
    if cc not in _class_cache:
        try:
            _class_cache[cc] = registry.load(cc)
        except Exception:
            _class_cache[cc] = None
    return _class_cache.get(cc)


def _walk_to_leaf(klass: COICOPClass, leaf_code: str):
    for grp in klass.groups:
        for sg in grp.subgroups:
            for leaf in sg.leaves:
                if leaf.code == leaf_code:
                    return grp, sg, leaf
    return None, None, None


def _union_subs(subs: tuple[SubLabel, ...]) -> Optional[frozenset[str]]:
    """Union allowed_bases across sub_labels. `_other` is excluded (it's the
    open-vocab fallback, not a constraint). A non-_other sub_label with None
    allowed_bases still flips the union to permissive."""
    bases: set[str] = set()
    saw_permissive = False
    for s in subs:
        if s.id == "_other":
            continue
        if s.allowed_bases is None:
            saw_permissive = True
        else:
            bases.update(s.allowed_bases)
    if saw_permissive or not bases:
        return None
    return frozenset(bases)


def lookup_allowed_bases(
    coicop_code: str, sub_label_id: str | None
) -> tuple[Optional[frozenset[str]], str]:
    """Return (allowed_bases, resolved_level).

    Walks from sub_label → leaf → subgroup → group → class until something
    has a non-None allowed_bases. Returns (None, "permissive") when every
    candidate is permissive — that means the row CANNOT be flagged.
    """
    if not coicop_code:
        return None, "no_code"

    klass = _class_for(coicop_code)
    if klass is None:
        return None, "unknown_class"

    leaf_code = ".".join(coicop_code.split(".")[:4])
    grp, sg, leaf = _walk_to_leaf(klass, leaf_code)
    if leaf is None:
        return None, "unknown_leaf"

    if sub_label_id:
        for sl in leaf.sub_labels:
            if sl.id == sub_label_id:
                if sl.allowed_bases is not None:
                    return sl.allowed_bases, "sub_label"
                break

    bases = _union_subs(leaf.sub_labels)
    if bases is not None:
        return bases, "leaf"

    if sg is not None:
        leaves_union: set[str] = set()
        any_perm = False
        for lf in sg.leaves:
            u = _union_subs(lf.sub_labels)
            if u is None:
                any_perm = True
            else:
                leaves_union.update(u)
        if not any_perm and leaves_union:
            return frozenset(leaves_union), "subgroup"

    return None, "permissive"


def consolidate(
    structural_basis: str | None,
    categorical_code: str,
    categorical_sub_label: str | None,
) -> tuple[str, Optional[str]]:
    """Decide consolidation action against `allowed_bases`.

    Returns (bucket, override_basis). `override_basis` is the singleton-allowed
    basis the caller should rewrite into the payload when bucket is
    SILENT_OVERRIDE; None otherwise.
    """
    allowed, _level = lookup_allowed_bases(
        categorical_code or "", categorical_sub_label
    )
    if allowed is None:
        return "PASS_THROUGH", None
    if structural_basis is None or structural_basis == "":
        return "NO_STRUCTURAL", None
    if structural_basis in allowed:
        return "CLEAN", None
    if len(allowed) == 1:
        return "SILENT_OVERRIDE", next(iter(allowed))
    return "ESCALATE_MULTI", None


def build_row(
    *,
    row_id: str,
    country: str,
    structural_basis: str | None,
    categorical_code: str,
    categorical_sub_label: str | None,
    matched_at: str,
    consolidation_bucket: str | None = None,
) -> dict:
    allowed, level = lookup_allowed_bases(categorical_code, categorical_sub_label)
    if allowed is None:
        flag_reason = ""
    elif structural_basis is None:
        flag_reason = ""
    elif structural_basis in allowed:
        flag_reason = ""
    else:
        flag_reason = "structural_not_in_allowed_bases"
    return {
        "row_id": row_id,
        "country": country,
        "structural_basis": structural_basis or "",
        "categorical_code": categorical_code or "",
        "categorical_sub_label": categorical_sub_label or "",
        "allowed_bases_at_finest": "|".join(sorted(allowed)) if allowed else "",
        "resolved_level": level,
        "flag_reason": flag_reason,
        "consolidation_bucket": consolidation_bucket or "",
        "matched_at": matched_at,
    }


def append(rows: Iterable[dict]) -> None:
    rows = list(rows)
    if not rows:
        return
    path = _CROSS_CHECK_PARQUET
    path.parent.mkdir(parents=True, exist_ok=True)
    new = pd.DataFrame(rows)
    with _lock:
        if path.exists():
            existing = pd.read_parquet(path)
            out = pd.concat([existing, new], ignore_index=True)
        else:
            out = new
        out.to_parquet(path, index=False)
