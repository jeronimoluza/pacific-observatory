"""Layer-1 unit-value adoption gate.

`extract.py` answers "what does this product name literally say". This module
answers the separate question "should that reading be adopted as a unit-value
denominator". Keeping the two apart is deliberate: extraction stays a pure
function of the string, and precision becomes a property of adoption, which is
where the COICOP leaf is available to inform it.

The gate exists because the pre-existing defense was a deny-list of lexical
contexts (`extract_patterns._VU_SUPPRESS_CTX_RE`, `_PHARMA_PER_UNIT_RE`, the
`_PHRASE_STRIP_PATTERNS` block). That shape cannot converge -- the pharma strip
only fires when a dosage is followed by a literal `Tablet`/`Capsule` word, so
`Avodart 0.5mg` still emits basis=mass at 5e-07 kg. The set of strings that
merely LOOK like a net quantity is unbounded; the set of categories where a
mass/volume denominator is physically meaningful is not, and is enumerated here.

Scope: layer 1 gates the MEASURED bases only (mass / volume / length). `count`
and `item` carry their own error modes and are passed through untouched with a
reason that names them as ungated, so no caller mistakes a pass for a check.
"""

from __future__ import annotations

from typing import Optional

# Bases whose denominator is a physical quantity read off the product name.
# These are the ones a category gate has an opinion about.
GATED_BASES = frozenset({"mass", "volume", "length"})

# COICOP 2018 prefixes where a net mass/volume is the sale quantity.
# Matched on segment boundaries, never as a bare string prefix.
#
# Deliberately EXCLUDED, and why:
#   02.3.0    tobacco       -- sold per stick/pack; loose tobacco is the rare case
#   04.5.1    electricity   -- billed per kWh, not mass or volume
#   04.4.1    water supply  -- utility volume, not a retail pack
#   05.6.1.9  other household non-durables -- bin bags and sacks are sized by
#             CAPACITY ("350 L, 10 bucati", "120 l 7 ks"), so the litre figure is
#             the container's volume, not the quantity sold. Measured at 2 errors
#             in 4 adjudicated rows; its sibling 05.6.1.1 does not share the flaw.
#   13.2.9    other personal effects -- nappies are sized by the WEARER's weight
#             ("13-24kg"); 71 of 462 measured rows exceed 20 kg.
ALLOWED_PREFIXES: tuple[str, ...] = (
    "01",  # Food and non-alcoholic beverages
    "02.1",  # Alcoholic beverages (spirits, wine, beer, other)
    "04.5.2",  # Gas -- bottled LPG, sold by net kg
    "04.5.3",  # Liquid fuels
    "04.5.4",  # Solid fuels (charcoal, firewood)
    "05.6.1.1",  # Cleaning products (detergent, bleach, dish liquid)
    "07.2.2",  # Fuels and lubricants for personal transport
    "13.1.2",  # Personal-care products (toothpaste, soap, deodorant, cream)
)

OK = "ok"
BASIS_NOT_GATED = "basis_not_gated"
NO_COICOP_CODE = "no_coicop_code"
LEAF_NOT_ALLOWED = "leaf_not_allowed"


def is_allowed_leaf(code: Optional[str]) -> bool:
    """True iff `code` sits under an allowed COICOP prefix.

    Segment-aware: "02.1" admits "02.1.3.0" but never "02.10" -- a bare
    `startswith` would be correct for single-digit segments today and silently
    wrong the moment a two-digit segment appears.
    """
    if not isinstance(code, str) or not code:
        return False
    return any(code == p or code.startswith(p + ".") for p in ALLOWED_PREFIXES)


def gate(coicop_code: Optional[str], pricing_basis: Optional[str]) -> tuple[bool, str]:
    """(adopt_denominator, reason) for one classified row.

    `coicop_code` is the ACCEPTED leaf, not `leaf_top1`: a row the classifier
    refused has no category evidence, so its measured denominator is not
    adoptable no matter what the regex read.
    """
    if pricing_basis not in GATED_BASES:
        return True, BASIS_NOT_GATED
    if not isinstance(coicop_code, str) or not coicop_code:
        return False, NO_COICOP_CODE
    if not is_allowed_leaf(coicop_code):
        return False, LEAF_NOT_ALLOWED
    return True, OK
