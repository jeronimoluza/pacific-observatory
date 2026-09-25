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

import functools
import importlib
import re
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from prices.enrich.regex_patterns._registry import _INDEX
from prices.enrich.regex_patterns.flag_markers import BUNDLE_MARKERS, PROMO_MARKERS
from prices.enrich.regex_patterns.types import PackPattern, SourcePatch
from prices.enrich.regex_patterns.unit_tables import UNIT_MAP, UNIT_NORM

# Cross-file precedence of the pattern modules. The ONLY hand-maintained order
# fact left — within each module, in-PATTERNS declaration order is authoritative.
# Modules are listed by their import path under regex_patterns/. Changing this
# list reorders the composed buckets, so it is guarded by the snapshot test.
MODULE_ORDER: tuple[str, ...] = (
    "buckets.multipack",
    "buckets.single_measure",
    "buckets.count_pack.cjk",
    "buckets.count_pack.vi_sheets",
    "buckets.count_pack.cjk_b",
    "buckets.count_pack.latin",
    "buckets.count_pack.vi",
    "buckets.count_pack.latin_cpi",
    "buckets.per_unit_marker",
    "buckets._unrouted",
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


def _canon_entry(pat: PackPattern) -> dict[str, Any]:
    return {
        "id": pat.id,
        "lang": pat.lang,
        "regex": pat.regex,
        "groups": {g: g for g in pat.groups},
    }


def _extra_unit_entry(pat: PackPattern) -> dict[str, Any]:
    ue = pat.unit_emit
    assert ue is not None, f"{pat.id} missing unit_emit"
    return {
        "id": pat.id,
        "lang": pat.lang,
        "regex": pat.regex,
        "basis": ue.basis,
        "su": ue.su,
        "mul": float(ue.mul),
    }


def _extra_count_entry(pat: PackPattern) -> dict[str, Any]:
    return {
        "id": pat.id,
        "lang": pat.lang,
        "regex": pat.regex,
        "fixed_count": pat.fixed_count,
    }


def _multi_pack_entry(pat: PackPattern) -> dict[str, Any]:
    return {"id": pat.id, "lang": pat.lang, "regex": pat.regex}


def _basis_marker_entry(pat: PackPattern) -> dict[str, Any]:
    assert pat.pricing_basis_emit is not None, f"{pat.id} missing pricing_basis_emit"
    return {
        "id": pat.id,
        "lang": pat.lang,
        "regex": pat.regex,
        "pricing_basis_emit": pat.pricing_basis_emit,
    }


# The consumed buckets, in the order extract.py's 7-tuple lists them. Each kind
# maps to the dict shape its matcher reads.
_ENTRY_FOR_KIND = {
    "canon": _canon_entry,
    "extra_unit": _extra_unit_entry,
    "extra_count": _extra_count_entry,
    "multi_pack": _multi_pack_entry,
    "pricing_basis_marker": _basis_marker_entry,
}


def _bucket(kind: str, patterns: list[PackPattern]) -> list[dict[str, Any]]:
    return [_ENTRY_FOR_KIND[kind](p) for p in patterns]


def _shared_patterns(kind: str) -> list[PackPattern]:
    return [_INDEX[pid][0] for pid in _ids_for_kind(kind)]


def pack_patterns_for_normalize() -> list[dict[str, Any]]:
    """Shape that normalize.py's old `_load_pack_patterns` produced.

    Each entry has `id`, `lang`, `regex` (pre-compiled), `groups` (dict).
    The `groups` dict is keyed by named group, value is the field name —
    which equals the group name in every YAML record, so we mirror that.
    """
    return _bucket("canon", _shared_patterns("canon"))


def unit_norm() -> dict[str, str]:
    return dict(UNIT_NORM)


def value_unit_pattern() -> tuple[re.Pattern[str], int | None]:
    """Compiled regex + ``suppress_window`` for the canon mass/volume pattern,
    surfaced so extract.py can apply local-window context suppression of
    appliance-capacity / apparel-fabric-weight false positives (BUG 3 / BUG 4)."""
    pat, _ = _INDEX["VALUE_UNIT"]
    return pat.regex, pat.suppress_window


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
    return (
        unit_map,
        _bucket("extra_unit", _shared_patterns("extra_unit")),
        _bucket("extra_count", _shared_patterns("extra_count")),
        _bucket("multi_pack", _shared_patterns("multi_pack")),
        _marker_block(dict(PROMO_MARKERS)),
        _marker_block(dict(BUNDLE_MARKERS)),
        _bucket("pricing_basis_marker", _shared_patterns("pricing_basis_marker")),
    )


# ---------------------------------------------------------------------------
# Source layer: regex_patterns/source/<slug>/patch.py
#
# A source patch edits the shared buckets for ONE source, so an agent fixing
# its source cannot move rows anywhere else. Ops per bucket: REMOVALS ->
# REPLACEMENTS (in place, keeping precedence) -> ADDITIONS, which go FIRST in
# their bucket: the buckets are first-match-wins, and a source rule is the most
# specific evidence there is. Lang filtering still happens at match time.
# ---------------------------------------------------------------------------

_SOURCE_PKG = f"{_ROOT}.source"

# Post-match transforms a source may switch on. Add a flag only when a real
# source needs one.
KNOWN_FLAGS = frozenset({"piece_is_case"})

# Read directly by extract.py / extract_decide.py outside the buckets, so a
# source patch that removed or replaced it would only half-apply.
_UNPATCHABLE = frozenset({"VALUE_UNIT"})


@dataclass(frozen=True)
class PatternSet:
    """The composed buckets one source's rows are matched against."""

    pack: list[dict[str, Any]]
    extra_units: list[dict[str, Any]]
    extra_count: list[dict[str, Any]]
    multi_pack: list[dict[str, Any]]
    pricing_basis_markers: list[dict[str, Any]]
    flags: frozenset[str] = frozenset()


def load_source_patch(source: str | None) -> SourcePatch | None:
    """The source's patch, validated, or None when it has none."""
    if not isinstance(source, str) or not source.isidentifier():
        return None
    mod_name = f"{_SOURCE_PKG}.{source}.patch"
    try:
        mod = importlib.import_module(mod_name)
    except ModuleNotFoundError as e:
        # Only a missing patch means "no patch"; a patch that imports something
        # missing is a broken patch.
        if e.name is not None and mod_name.startswith(e.name):
            return None
        raise
    patch = getattr(mod, "PATCH", None)
    if not isinstance(patch, SourcePatch):
        raise RuntimeError(f"{mod_name} must define PATCH = SourcePatch(...)")
    _validate(source, patch)
    return patch


def _validate(source: str, patch: SourcePatch) -> None:
    where = f"source patch {source!r}"
    for p in patch.additions:
        if p.id in _INDEX:
            raise RuntimeError(f"{where}: addition {p.id!r} reuses a shared id; use a replacement")
        if p.kind not in _ENTRY_FOR_KIND:
            raise RuntimeError(f"{where}: addition {p.id!r} has unconsumed kind {p.kind!r}")
    for pid in (*patch.removals, *(p.id for p in patch.replacements)):
        if pid not in _INDEX:
            raise RuntimeError(f"{where}: {pid!r} is not a shared pattern id")
        if pid in _UNPATCHABLE:
            raise RuntimeError(f"{where}: {pid!r} cannot be removed or replaced per source")
    for p in patch.replacements:
        if p.kind != _INDEX[p.id][0].kind:
            raise RuntimeError(f"{where}: replacement {p.id!r} changes kind")
    unknown = patch.flags - KNOWN_FLAGS
    if unknown:
        raise RuntimeError(f"{where}: unknown flags {sorted(unknown)}")
    keys = {
        *(p.id for p in patch.additions),
        *patch.removals,
        *(p.id for p in patch.replacements),
        *patch.flags,
    }
    missing, stray = keys - patch.intent.keys(), patch.intent.keys() - keys
    if missing or stray:
        raise RuntimeError(
            f"{where}: intent missing for {sorted(missing)}, intent for unknown {sorted(stray)}"
        )


def _apply(kind: str, patch: SourcePatch) -> list[PackPattern]:
    removed = set(patch.removals)
    repl = {p.id: p for p in patch.replacements}
    out = [repl.get(p.id, p) for p in _shared_patterns(kind) if p.id not in removed]
    return [p for p in patch.additions if p.kind == kind] + out


_, _eu, _ec, _mp, _, _, _pbm = regex_units_for_extract()
_DEFAULT = PatternSet(
    pack=pack_patterns_for_normalize(),
    extra_units=_eu,
    extra_count=_ec,
    multi_pack=_mp,
    pricing_basis_markers=_pbm,
)


def compose(patch: SourcePatch | None) -> PatternSet:
    """The buckets `patch` produces over the shared ones (None: the shared ones)."""
    if patch is None:
        return _DEFAULT
    return PatternSet(
        pack=_bucket("canon", _apply("canon", patch)),
        extra_units=_bucket("extra_unit", _apply("extra_unit", patch)),
        extra_count=_bucket("extra_count", _apply("extra_count", patch)),
        multi_pack=_bucket("multi_pack", _apply("multi_pack", patch)),
        pricing_basis_markers=_bucket(
            "pricing_basis_marker", _apply("pricing_basis_marker", patch)
        ),
        flags=patch.flags,
    )


# Set only by the rule-check harness, to extract a source as if its patch (or
# one entry of it) were absent. Empty in every pipeline run.
_OVERRIDES: dict[str, PatternSet] = {}


@contextmanager
def override(source: str, ps: PatternSet):
    _OVERRIDES[source] = ps
    try:
        yield
    finally:
        _OVERRIDES.pop(source, None)


@functools.lru_cache(maxsize=None)
def _composed(source: str | None) -> PatternSet:
    return compose(load_source_patch(source))


def pattern_set(source: str | None) -> PatternSet:
    """Composed buckets for `source`: the shared ones unless it has a patch.

    Cached per source (~2,300 distinct), never composed per row.
    """
    if _OVERRIDES and source in _OVERRIDES:
        return _OVERRIDES[source]
    return _composed(source)
