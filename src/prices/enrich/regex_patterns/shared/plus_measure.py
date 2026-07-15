"""Additive dual-measure -> summed single measure (a+b same-unit idiom).

"400g+100g" states the product ships as two components in the same net-weight
unit ("Keventer Pork Sausages 400g+100g", "Raisins 190g + 50g"); the real sale
quantity is the SUM of the two, not either half. Collapse
`<a><unit> + <b><unit>` (same literal unit spelling) to `<a+b><unit>` before
any pattern runs, mirroring `range_lower.collapse_numeric_ranges`.
"""

from __future__ import annotations

import re

_PLUS_SAME_UNIT_RE = re.compile(
    r"(?<![A-Za-z0-9.])(\d+(?:[.,]\d+)?)\s*"
    r"(ml|mL|ML|l|L|kg|KG|g|G|mg|MG|gm|GM|gr|GR|oz|OZ|lb|LB)\s*\+\s*"
    r"(\d+(?:[.,]\d+)?)\s*\2\b"
)


def _sub(m: re.Match) -> str:
    try:
        a = float(m.group(1).replace(",", "."))
        b = float(m.group(3).replace(",", "."))
    except ValueError:
        return m.group(0)
    return f"{a + b:g}{m.group(2)}"


def collapse_additive_measure(name: str) -> str:
    """Rewrite `<a><unit> + <b><unit>` -> `<a+b><unit>` (spec: additive -> sum)."""
    return _PLUS_SAME_UNIT_RE.sub(_sub, name)
