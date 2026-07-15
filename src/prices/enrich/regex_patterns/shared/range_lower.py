"""Single-unit mass/volume range -> lower bound (spec rule).

A range where only the UPPER bound carries the unit ("600-700g", "1.5-2kg")
would let value_unit_volume_mass match the upper. The spec mandates the LOWER
bound (`(600-700g)` -> 0.6 kg), so collapse `<low>-<high><unit>` to `<low><unit>`
before any pattern runs. The both-sided form ("800g-1Kg") is untouched (the `g`
after the low number breaks this regex) and already yields the lower bound via
leftmost matching. A hyphenated SKU with no trailing mass/volume unit
("Nj-009-127/128") never matches.

RATIO GATE (`high/low < _MAX_RANGE_RATIO`): a genuine product-weight range is
tight — across the live cache every real range sits at ratio <= 2.0 (the widest
is "1-2kg" saba). Wider "ranges" are NOT product mass: SKU-then-weight idioms
("LINGUINE N. 182 - 500G" -> 6.4x, where 182 is an item number and 500g the real
mass), selectable-capacity options ("300-750ml" -> 2.5x), and body-weight/spec
ratings. Collapsing those would corrupt a correct upper-bound match, so we only
collapse when the two bounds are close (equal bounds, e.g. a degenerate
"1.0 - 1kg", are the tightest possible case and also collapse).

The separator also accepts the word "to" (any spacing, e.g. "900 to 1000g" or
the glued "400to500g" idiom), and unit spelling is matched case-insensitively
("3-5Kg") — the emitted unit is lower-cased so downstream extract_pack always
recognizes it.
"""

from __future__ import annotations

import re

_MAX_RANGE_RATIO = 2.5

_NUM_RANGE_LOWER_RE = re.compile(
    r"(?<![A-Za-z0-9.])(\d+(?:[.,]\d+)?)\s*(?:[-–—~〜]|to)\s*(\d+(?:[.,]\d+)?)(\s*)"
    r"(ml|ltrs|ltr|lt|l|kg|g|mg|gm|gr|oz|lb)\b",
    re.IGNORECASE,
)


def _sub(m: re.Match) -> str:
    try:
        lo = float(m.group(1).replace(",", "."))
        hi = float(m.group(2).replace(",", "."))
    except ValueError:
        return m.group(0)
    if lo <= 0 or hi < lo or hi / lo >= _MAX_RANGE_RATIO:
        return m.group(0)
    return f"{m.group(1)}{m.group(3)}{m.group(4).lower()}"


def collapse_numeric_ranges(name: str) -> str:
    """Rewrite a tight `<low>-<high><unit>` -> `<low><unit>` (spec: range -> lower)."""
    return _NUM_RANGE_LOWER_RE.sub(_sub, name)
