"""COICOP taxonomy predicates shared by every renderer.

Only one lives here so far, and it is the one two dashboards must agree on: a
residual leaf is the taxonomy's own catch-all -- "... n.e.c." or a title that
OPENS with "Other". The opening anchor is what makes the rule safe: "Meat of
horses and other equines" and "Cantaloupes and other melons" are named leaves
that merely mention the word, and a substring test would swallow them.

These leaves hold whatever was placed confidently at the subclass level but
never resolved to a named sibling, so their members share no common good. A
LEVEL for such a group is not a quantity -- a dollars-per-kilo of "other
bakery products" compares one country's croissants with another's flatbread --
and neither is a cross-country median of one. A CHANGE is a different matter:
month over month the same catch-all in the same country is a defensible basket
of its own, so nothing here is applied to the chained index.

Lifted out of `prices.publish`, which has withheld the cross-country figure on
these leaves since it was written while the explorer showed it. Two renderers
with the same taxonomy and different answers is the failure this prevents.
"""

from __future__ import annotations

import re

__all__ = ["RESIDUAL_TITLE_RE", "residual_leaves"]

RESIDUAL_TITLE_RE = re.compile(r"n\.e\.c\.|^other\b", re.IGNORECASE)


def residual_leaves(titles: dict[str, str]) -> frozenset[str]:
    """Codes whose title marks them as the taxonomy's catch-all."""
    return frozenset(
        code for code, title in titles.items() if RESIDUAL_TITLE_RE.search(title)
    )
