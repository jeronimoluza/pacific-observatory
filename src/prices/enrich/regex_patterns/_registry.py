"""Registry that loads and composes regex patterns from the tier-a tree.

Walks the regex_patterns tree at module load, indexes every PackPattern by id,
and exposes load_for(country, lang) that returns the composed list in priority
order. Composition rules per ADR-0005 (design.md §Decisions):

- Base = any/* + lang/<lang>/* (+ lang/_cjk_shared/* when lang is CJK).
- Country patch at country/<slug>/patch.py applies ops in order:
  REMOVALS -> ADDITIONS -> REPLACEMENTS.
- Globally-unique pattern IDs across the whole tree; collision raises at
  module import.
- lang=None resolution: if a country is given, try _resolve_lang(country); if
  still None, fall back to any/* + every lang/*/* directory so misclassified
  CJK rows still have a chance to match (REGEX_ITER_LEARNINGS.md §1).
"""

from __future__ import annotations

import importlib
import pkgutil
from typing import Iterable

from prices.enrich.regex_patterns.types import PackPattern

_ROOT = "prices.enrich.regex_patterns"
_ANY_PKG = f"{_ROOT}.any"
_LANG_PKG = f"{_ROOT}.lang"
_COUNTRY_PKG = f"{_ROOT}.country"
_CJK_SHARED_PKG = f"{_LANG_PKG}._cjk_shared"

_CJK_LANGS = frozenset({"zh", "ja", "ko"})


def _is_cjk(lang: str | None) -> bool:
    if not lang:
        return False
    return lang in _CJK_LANGS or lang.startswith("zh")


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


def _patterns_under(package_name: str) -> tuple[PackPattern, ...]:
    out: list[PackPattern] = []
    for mod in _iter_pattern_modules(package_name):
        out.extend(_patterns_in_module(mod))
    return tuple(out)


def _scan_all_patterns() -> dict[str, tuple[PackPattern, str]]:
    """Return id -> (pattern, source_module). Raise on collision."""
    index: dict[str, tuple[PackPattern, str]] = {}
    for root in (_ANY_PKG, _LANG_PKG, _COUNTRY_PKG):
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


def _resolve_lang_for_country(country: str) -> str | None:
    try:
        from prices.enrich.stages.enrich import _resolve_lang
    except Exception:
        return None
    return _resolve_lang(country)


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

    - lang given: any/* + lang/<lang>/* (+ lang/_cjk_shared/* when CJK).
    - lang=None and country given: try _resolve_lang(country); if it returns
      a code, behave as above. If still None, fall back to any/* + every
      lang/*/* directory so misclassified Asian countries still match CJK
      patterns.
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

    base: list[PackPattern] = list(_patterns_under(_ANY_PKG))

    if lang is None:
        base.extend(_patterns_under(_LANG_PKG))
    else:
        base.extend(_patterns_under(f"{_LANG_PKG}.{lang}"))
        if _is_cjk(lang):
            base.extend(_patterns_under(_CJK_SHARED_PKG))

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
