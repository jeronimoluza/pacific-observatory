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
_SHARED_PKG = f"{_ROOT}.shared"
_SCRIPT_PKG = f"{_ROOT}.script"
_LANG_PKG = f"{_ROOT}.lang"
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


def _script_pkg_for(lang: str | None) -> str | None:
    if not lang:
        return None
    family = _SCRIPT_OF.get(lang)
    if family is None and lang.startswith("zh"):
        family = "cjk"
    if family is None:
        return None
    return f"{_SCRIPT_PKG}.{family}"


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
    for root in (_SHARED_PKG, _SCRIPT_PKG, _LANG_PKG, _COUNTRY_PKG):
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

    base: list[PackPattern] = list(_patterns_under(_SHARED_PKG))

    if lang is None:
        base.extend(_patterns_under(_LANG_PKG))
        base.extend(_patterns_under(_SCRIPT_PKG))
    else:
        base.extend(_patterns_under(f"{_LANG_PKG}.{lang}"))
        script_pkg = _script_pkg_for(lang)
        if script_pkg is not None:
            base.extend(_patterns_under(script_pkg))

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
