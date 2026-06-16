"""COICOP scope-set construction for tier-c LLM calls.

A "scope set" is a `frozenset[str]` of COICOP leaf codes that bounds the
taxonomy block injected into a tier-c prompt. Two construction rules:

  * Constrained: tier-b locked the coicop_code; the LLM only picks
    `sub_label_id`. Scope is the locked code alone.

  * Residual: tier-b couldn't accept; the LLM picks both `coicop_code`
    and `sub_label_id`. Scope is KNN neighbor codes padded with sibling
    leaves at the COICOP-3 (4-digit) prefix to absorb "right family,
    wrong leaf" KNN misses.

`None` scope means full taxonomy (see `taxonomy_index.load_coicop_context`).
Pure functions; no I/O at module import.
"""

from __future__ import annotations

from typing import Iterable, Optional


def _coicop_3_prefix(code: str) -> str:
    """Return the 4-character COICOP-3 prefix ("13.1", "06.1"). Codes shorter
    than 4 chars are returned as-is."""
    return code[:4] if len(code) >= 4 else code


def build_scope_constrained(locked_code: str) -> frozenset[str]:
    """Constrained-call scope: just the locked leaf."""
    return frozenset({locked_code})


def build_scope_residual(
    neighbor_codes: Iterable[Optional[str]],
    leaves: Iterable[str],
) -> frozenset[str]:
    """Residual-call scope: neighbors plus their COICOP-3 siblings.

    The cushion guards against KNN landing in the right family but missing
    the correct leaf. `leaves` is the full deepest-available leaf set used
    to expand each neighbor's 4-digit prefix.

    Empty input → empty set; caller's responsibility to translate that into
    a `scope=None` (full-taxonomy) fallback.
    """
    nbrs = {c for c in neighbor_codes if c}
    if not nbrs:
        return frozenset()
    prefixes = {_coicop_3_prefix(c) + "." for c in nbrs}
    leaves_set = set(leaves)
    expanded = {
        leaf for leaf in leaves_set if any(leaf.startswith(p) for p in prefixes)
    }
    return frozenset(nbrs | expanded)
