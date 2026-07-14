"""Registry that loads and composes regex patterns from the tier-a tree.

Walks the regex_patterns tree at module load, indexes every PackPattern by id,
and exposes load_for(country, lang) that returns the composed list in priority
order. Composition rules per ADR-0005 (design.md §Decisions):

- Base = shared/* + lang/<lang>/* (+ script/<script_of(lang)>/* when lang has a
  script-family module).
- Country patch at country/<slug>/patch.py applies ops in order:
  REMOVALS -> ADDITIONS -> REPLACEMENTS.
- Globally-unique pattern IDs across the whole tree; collision raises at
  module import.
- lang=None resolution: if a country is given, try _resolve_lang(country); if
  still None, fall back to shared/* + every lang/*/* + every script/*/* directory
  so misclassified rows still have a chance to match (REGEX_ITER_LEARNINGS.md §1).
"""

from __future__ import annotations

import importlib
import pkgutil
from typing import Iterable

from prices.enrich.regex_patterns.types import PackPattern

_ROOT = "prices.enrich.regex_patterns"
_BUCKETS_PKG = f"{_ROOT}.buckets"
_COUNTRY_PKG = f"{_ROOT}.country"

# lang -> script family. The script axis carries structure shared *within* a
# script (numeral systems, counter grammar); only CJK + Latin content exists
# today. Arabic/Devanagari/Thai are deferred to the regex-script-families seed —
# add an entry here (and a script/<family>/ dir) when the first such source lands.
_SCRIPT_OF: dict[str, str] = {
    "zh": "cjk",
    "ja": "cjk",
    "ko": "cjk",
    "en": "latin",
    "es": "latin",
    "pt": "latin",
    "fr": "latin",
    "vi": "latin",
    "id": "latin",
    "ms": "latin",
}


def _script_family_for(lang: str | None) -> str | None:
    """The script family (cjk | latin | None) selected for a given lang.

    Mirrors the pre-reorg _script_pkg_for resolution: _SCRIPT_OF lookup plus the
    zh-prefix fallback. Drives load_for's script-field membership predicate."""
    if not lang:
        return None
    family = _SCRIPT_OF.get(lang)
    if family is None and lang.startswith("zh"):
        family = "cjk"
    return family


def _iter_pattern_modules(package_name: str) -> Iterable[str]:
    """Yield fully-qualified module names beneath `package_name` (recursive).

    Country `patch.py` files are excluded — they carry deltas, not patterns.
    Silently yields nothing for missing packages.
    """
    try:
        pkg = importlib.import_module(package_name)
    except ModuleNotFoundError:
        return
    pkg_paths = getattr(pkg, "__path__", None)
    if not pkg_paths:
        return
    for info in pkgutil.iter_modules(pkg_paths):
        full = f"{package_name}.{info.name}"
        if info.ispkg:
            yield from _iter_pattern_modules(full)
        else:
            if full.startswith(_COUNTRY_PKG) and full.endswith(".patch"):
                continue
            yield full


def _patterns_in_module(module_name: str) -> tuple[PackPattern, ...]:
    mod = importlib.import_module(module_name)
    patterns = getattr(mod, "PATTERNS", None)
    if patterns is None:
        return ()
    return tuple(patterns)


def _scan_all_patterns() -> dict[str, tuple[PackPattern, str]]:
    """Return id -> (pattern, source_module). Raise on collision."""
    index: dict[str, tuple[PackPattern, str]] = {}
    for root in (_BUCKETS_PKG, _COUNTRY_PKG):
        for mod in _iter_pattern_modules(root):
            for pat in _patterns_in_module(mod):
                if pat.id in index:
                    _, prev_mod = index[pat.id]
                    raise RuntimeError(
                        f"Duplicate pattern id {pat.id!r}: defined in "
                        f"{prev_mod} and {mod}"
                    )
                index[pat.id] = (pat, mod)
    return index


_INDEX: dict[str, tuple[PackPattern, str]] = _scan_all_patterns()

# Global base-composition order. The buckets reorg scrambles the on-disk scan
# order, so the pre-reorg directory-walk order (shared/* -> lang/<lang>/* ->
# script/<family>/*, each alpha-by-module then declaration) can no longer be
# derived from the tree. It is pinned here as the single ordering fact for
# load_for: every load_for(country, lang) result is this sequence filtered by the
# field-membership predicate, preserving order. Guarded byte-for-byte by
# tests/prices/enrich/test_composition_diff.py (LOAD_FOR_BASELINE through RENAME).
_BASE_ORDER: tuple[str, ...] = (
    # shared/* (script=None, lang="any")
    "NUM_ROLLS",
    "EN_COMMA_XN",
    "EN_PCS",
    "EN_APOS_S",
    "EN_N_TICKETS",
    "CENTILITRE",
    "LITRE_VI",
    "NUM_X_VALUE_UNIT",
    "VALUE_UNIT_X_NUM",
    "NUM_X_TRAILING",
    "VALUE_UNIT",
    "VI_TO_SHEETS",
    # lang/<lang>/* (script=None): en, ja, vi, zh
    "NUM_PCS",
    "NUM_PC_GLUED",
    "PER_KG_PARENS",
    "PER_KG",
    "PER_LITRE_PARENS",
    "PER_LITRE",
    "SET_JA",
    "VI_PIECES",
    "LOC_VI",
    "COUNT_UNIT_VI",
    "COUNT_UNIT_ZH",
    "VALUE_UNIT_ZH",
    # script/<family>/*: cjk, latin
    "CJK_MAI",
    "CJK_PAIR",
    "CJK_GRAIN",
    "CJK_STRIP",
    "CJK_SHEET",
    "CJK_SET",
    "VERSION_CJK",
    "CJK_NUMERAL_SET",
    "CJK_KO_PCS",
    "CJK_N_X_COUNT",
    "CJK_DOUBLE_PACK",
    "INNER_X_OUTER_STAR",
    "INNER_X_OUTER",
    "EN_CAPS",
    "EN_TABLETS",
    "EN_SACHETS",
    "EN_SHEETS",
    "EN_PACK_OF",
    "EN_N_PACK",
    "EN_N_INDIVIDUAL_PACK",
    "EN_TWIN_PACK",
    "EN_TRIPLE_PACK",
    "EN_DOUBLE_PACK",
)

_ORDERED_PATTERNS: tuple[PackPattern, ...] = tuple(
    _INDEX[pid][0] for pid in _BASE_ORDER
)


def _in_membership(pat: PackPattern, lang: str | None) -> bool:
    """Reproduce the pre-reorg directory membership via the lang/script fields.

    - lang=None: broad fallback = every pattern (was shared/* + every lang/*/* +
      every script/*/*).
    - lang given: shared/* (script=None, lang="any") + lang/<lang>/* (script=None,
      lang==lang) + script/<family>/* (script==script_of(lang)).
    """
    if lang is None:
        return True
    if pat.script is not None:
        return pat.script == _script_family_for(lang)
    return pat.lang == "any" or pat.lang == lang


def _compose_base(lang: str | None) -> list[PackPattern]:
    return [p for p in _ORDERED_PATTERNS if _in_membership(p, lang)]


def _resolve_lang_for_country(country: str) -> str | None:
    from prices.enrich.langs import resolve_lang

    return resolve_lang(country)


def _load_country_patch(
    country: str,
) -> tuple[tuple[str, ...], tuple[PackPattern, ...], tuple[PackPattern, ...]]:
    mod_name = f"{_COUNTRY_PKG}.{country}.patch"
    try:
        mod = importlib.import_module(mod_name)
    except ModuleNotFoundError:
        return (), (), ()
    removals = tuple(getattr(mod, "REMOVALS", ()))
    additions = tuple(getattr(mod, "ADDITIONS", ()))
    replacements = tuple(getattr(mod, "REPLACEMENTS", ()))
    return removals, additions, replacements


def load_for(
    country: str | None,
    lang: str | None,
    role: str | None = None,
) -> tuple[PackPattern, ...]:
    """Compose tier-a regex patterns for (country, lang), optionally filtered by role.

    Resolution rules (design.md §Decisions; REGEX_ITER_LEARNINGS.md §1):

    - lang given: shared/* + lang/<lang>/* (+ script/<script_of(lang)>/* when the
      lang maps to a script family).
    - lang=None and country given: try _resolve_lang(country); if it returns
      a code, behave as above. If still None, fall back to shared/* + every
      lang/*/* + every script/*/* directory so misclassified rows still match.
    - lang=None and country=None: same broad fallback.

    Country patch (when country given): REMOVALS -> ADDITIONS -> REPLACEMENTS.
    A REPLACEMENT whose id is not in the base list is appended (treated as an
    addition); the registry does not raise on this — it's interpreted as
    "ensure this exact pattern is present".

    role: when set to "canonicalization" or "extract", filters the composed
    list to patterns whose `role` field matches. None returns all patterns.
    """
    if lang is None and country:
        resolved = _resolve_lang_for_country(country)
        if resolved is not None:
            lang = resolved

    base: list[PackPattern] = _compose_base(lang)

    if not country:
        return _filter_role(base, role)

    removals, additions, replacements = _load_country_patch(country)
    if not (removals or additions or replacements):
        return _filter_role(base, role)

    removed = set(removals)
    out: list[PackPattern] = [p for p in base if p.id not in removed]
    out.extend(additions)

    if replacements:
        repl_by_id = {p.id: p for p in replacements}
        existing_ids = {p.id for p in out}
        out = [repl_by_id.get(p.id, p) for p in out]
        for p in replacements:
            if p.id not in existing_ids:
                out.append(p)

    return _filter_role(out, role)


def _filter_role(
    patterns: list[PackPattern], role: str | None
) -> tuple[PackPattern, ...]:
    if role is None:
        return tuple(patterns)
    return tuple(p for p in patterns if p.role == role)
