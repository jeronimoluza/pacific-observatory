"""Non-food piece grammar: patterns for goods sold by the piece.

Leaves whose allowed bases are only `item`/`count` (garments, furniture,
electronics, kitchenware ...) are read with this grammar instead of the food
one, because their measures are attributes, not quantities: "500 ml" on a
thermos is its capacity, "L" on a shirt is its size, "43S803W" is a model code.
Only an explicit pack ("pack of 3", "6 pares", "3 шт") changes the divisor.

Layers, as in the food library: shared -> country -> source. A country or
source patch lives at `country/<slug>.py` or `source/<source>.py` and exposes
`PATCH = NFPatch(...)`; its additions go first and its removals drop shared
ids. Pattern ids are unique across the tree.

Roles:
- `blank`  : erase the span before anything else reads the name ("2 in 1",
             multi-buy promos, "for 12 pairs", "+ 2 years warranty").
- `bundle` : different products sold under one price -> excluded.
- `strong` : a homogeneous pack; its N is the divisor.
- `weak`   : a piece count ("9 pcs") that is a divisor only when the name
             does not describe a set.
- `set`    : the N counts a set's components ("7 Piece Dining Set"); the set
             is one item.
- `setnoun`: words that make a name a set, which silences `weak` counts.
"""

from __future__ import annotations

import importlib
import re
from dataclasses import dataclass, field

ROLES = ("blank", "bundle", "strong", "weak", "set", "setnoun")


@dataclass(frozen=True)
class NFPattern:
    id: str
    role: str
    regex: re.Pattern
    # COICOP prefixes the pattern applies to; None = every piece leaf.
    leaves: tuple[str, ...] | None = None

    def applies(self, code: str | None) -> bool:
        if self.leaves is None:
            return True
        return bool(code) and any(code == p or code.startswith(p + ".") for p in self.leaves)


@dataclass(frozen=True)
class Intent:
    why: str
    expect: str
    rows: int
    examples: tuple[str, ...]


@dataclass(frozen=True)
class NFPatch:
    additions: tuple[NFPattern, ...] = ()
    removals: tuple[str, ...] = ()
    intent: dict[str, Intent] = field(default_factory=dict)


def _patch(kind: str, key: str | None) -> NFPatch | None:
    if not key:
        return None
    try:
        mod = importlib.import_module(f"{__name__}.{kind}.{key}")
    except ModuleNotFoundError as e:
        if e.name == f"{__name__}.{kind}.{key}":
            return None
        raise
    return mod.PATCH


_CACHE: dict[tuple[str | None, str | None], tuple[NFPattern, ...]] = {}


def load(country: str | None, source: str | None) -> tuple[NFPattern, ...]:
    """Composed patterns for one (country, source): source additions, country
    additions, then shared, minus every removal."""
    key = (country, source)
    if key not in _CACHE:
        from prices.enrich.regex_patterns_nonfood.shared import SHARED

        patches = [p for p in (_patch("source", source), _patch("country", country)) if p]
        drop = {i for p in patches for i in p.removals}
        pats = [x for p in patches for x in p.additions] + list(SHARED)
        pats = [p for p in pats if p.id not in drop]
        ids = [p.id for p in pats]
        if len(ids) != len(set(ids)):
            raise RuntimeError(f"duplicate non-food pattern id for {key}: {ids}")
        _CACHE[key] = tuple(pats)
    return _CACHE[key]
