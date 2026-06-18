"""Adapters that present the typed tree as the dict shape extract.py and
normalize.py historically built from YAML.

After §6 swap, extract.py and normalize.py import these instead of running
the YAML loader. The composed bucket lists are derived from a single source of
truth — there is no longer a hand-maintained ID-order tuple per bucket.

Source of truth for ordering & routing (Phase 0.5 / Plan 04, SC7):

  * Routing — each PackPattern carries an explicit ``kind`` field
    (canon | extra_unit | extra_count | multi_pack | pricing_basis_marker |
    unrouted). The bucket a pattern feeds is on the record, not in a tuple.
  * Ordering — ``MODULE_ORDER`` lists the pattern modules in cross-file
    precedence order (the only non-derivable fact; it is NOT alphabetical —
    cpi_count_markers sorts last). Each consumed bucket is composed by walking
    MODULE_ORDER, preserving each module's in-PATTERNS declaration order, and
    filtering by ``kind``.

Adding a pattern is now a one-file edit (drop it in the right module with the
right kind). MODULE_ORDER changes only when a whole new module is added (rare,
visible). The byte-identity snapshot + no-silent-drop tests in
tests/prices/enrich/test_regex_patterns_layout.py guard against drift.
"""

from __future__ import annotations

import re
from typing import Any

from prices.enrich.regex_patterns._registry import _INDEX
from prices.enrich.regex_patterns.flag_markers import BUNDLE_MARKERS, PROMO_MARKERS
from prices.enrich.regex_patterns.unit_tables import UNIT_MAP, UNIT_NORM

# Cross-file precedence of the pattern modules. The ONLY hand-maintained order
# fact left — within each module, in-PATTERNS declaration order is authoritative.
# Modules are listed by their import path under regex_patterns/. Changing this
# list reorders the composed buckets, so it is guarded by the snapshot test.
MODULE_ORDER: tuple[str, ...] = (
    "shared.multipack",
    "lang.en.multipack",
    "shared.multipack_trailing",
    "lang.vi.multipack",
    "lang.zh.multipack",
    "lang.ja.multipack",
    "shared.value_unit",
    "lang.zh.volume_mass",
    "shared.extra_units",
    "script.cjk.count_markers",
    "shared.vi_extras",
    "script.cjk.count_markers_b",
    "script.latin.count_markers",
    "lang.vi.count_markers",
    "shared.cpi_count_markers",
    "script.cjk.multi_pack",
    "lang.en.per_unit_markers",
)

_ROOT = "prices.enrich.regex_patterns"


def _ids_for_kind(kind: str) -> tuple[str, ...]:
    """Compose a bucket: walk MODULE_ORDER, preserve in-module declaration order,
    keep only patterns whose ``kind`` matches. The _INDEX records each pattern's
    source module, so we group by module and emit in MODULE_ORDER sequence."""
    by_module: dict[str, list[str]] = {}
    for pid, (pat, mod) in _INDEX.items():
        if pat.kind != kind:
            continue
        short = mod[len(_ROOT) + 1 :] if mod.startswith(_ROOT + ".") else mod
        by_module.setdefault(short, []).append(pid)

    # Within a module, preserve PATTERNS declaration order. _INDEX is built by
    # iterating each module's PATTERNS tuple in order, and dict preserves
    # insertion order, so the per-module lists above are already in declaration
    # order.
    out: list[str] = []
    for module in MODULE_ORDER:
        out.extend(by_module.get(module, []))
    return tuple(out)


def _marker_block(table: dict[str, tuple[str, ...]]) -> list[dict[str, Any]]:
    return [
        {
            "lang": lang,
            "patterns": [re.compile(p, flags=re.IGNORECASE) for p in pats],
        }
        for lang, pats in table.items()
    ]


def pack_patterns_for_normalize() -> list[dict[str, Any]]:
    """Shape that normalize.py's old `_load_pack_patterns` produced.

    Each entry has `id`, `lang`, `regex` (pre-compiled), `groups` (dict).
    The `groups` dict is keyed by named group, value is the field name —
    which equals the group name in every YAML record, so we mirror that.
    """
    out: list[dict[str, Any]] = []
    for pid in _ids_for_kind("canon"):
        pat, _ = _INDEX[pid]
        out.append(
            {
                "id": pat.id,
                "lang": pat.lang,
                "regex": pat.regex,
                "groups": {g: g for g in pat.groups},
            }
        )
    return out


def unit_norm() -> dict[str, str]:
    return dict(UNIT_NORM)


def regex_units_for_extract() -> (
    tuple[
        dict[str, dict[str, Any]],
        list[dict[str, Any]],
        list[dict[str, Any]],
        list[dict[str, Any]],
        list[dict[str, Any]],
        list[dict[str, Any]],
        list[dict[str, Any]],
    ]
):
    """Shape that extract.py's old `_load_regex_units` returned, now a 7-tuple.

    Order: unit_map, extra_units, extra_count, multi_pack, promo, bundle,
           pricing_basis_markers.
    """
    unit_map = {
        k: {"basis": v.basis, "su": v.su, "mul": float(v.mul)}
        for k, v in UNIT_MAP.items()
    }

    extra_units: list[dict[str, Any]] = []
    for pid in _ids_for_kind("extra_unit"):
        pat, _ = _INDEX[pid]
        ue = pat.unit_emit
        assert ue is not None, f"{pid} missing unit_emit"
        extra_units.append(
            {
                "id": pat.id,
                "lang": pat.lang,
                "regex": pat.regex,
                "basis": ue.basis,
                "su": ue.su,
                "mul": float(ue.mul),
            }
        )

    extra_count: list[dict[str, Any]] = []
    for pid in _ids_for_kind("extra_count"):
        pat, _ = _INDEX[pid]
        extra_count.append(
            {
                "id": pat.id,
                "lang": pat.lang,
                "regex": pat.regex,
                "fixed_count": pat.fixed_count,
            }
        )

    multi_pack: list[dict[str, Any]] = []
    for pid in _ids_for_kind("multi_pack"):
        pat, _ = _INDEX[pid]
        multi_pack.append(
            {
                "id": pat.id,
                "lang": pat.lang,
                "regex": pat.regex,
            }
        )

    pricing_basis_markers: list[dict[str, Any]] = []
    for pid in _ids_for_kind("pricing_basis_marker"):
        pat, _ = _INDEX[pid]
        assert pat.pricing_basis_emit is not None, f"{pid} missing pricing_basis_emit"
        pricing_basis_markers.append(
            {
                "id": pat.id,
                "lang": pat.lang,
                "regex": pat.regex,
                "pricing_basis_emit": pat.pricing_basis_emit,
            }
        )

    return (
        unit_map,
        extra_units,
        extra_count,
        multi_pack,
        _marker_block(dict(PROMO_MARKERS)),
        _marker_block(dict(BUNDLE_MARKERS)),
        pricing_basis_markers,
    )
