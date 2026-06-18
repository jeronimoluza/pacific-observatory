"""CPI-survey count idiom patterns (extract role).

Targets short CPI-style product descriptions whose pack count appears as a
free-text phrase rather than a structured `N Pack` / `N PCS` marker:

- `4 rolls of toilet paper` / `Toilet paper, 4 rolls`
- `Eggs, x12`
- `HYPERMART VALUE PLUS BABY COTTON BUDS POT 50 PCS`
- `Lululun Face Mask 7's` / `POKANA MASK ADULT EARLOOP 5'S`
- `2 tickets to the theater`

Compiled WITHOUT re.IGNORECASE — extract-role patterns enumerate case
variants explicitly (matches the loader convention in dict_view).
"""

from __future__ import annotations

import re

from prices.enrich.regex_patterns.types import PackPattern


def _p(id_: str, regex: str, groups: tuple[str, ...]) -> PackPattern:
    return PackPattern(
        id=id_,
        regex=re.compile(regex),
        groups=groups,
        lang="any",
        role="extract",
    )


PATTERNS: tuple[PackPattern, ...] = (
    # "4 rolls of toilet paper", "Toilet paper, 4 rolls"
    _p("en_n_rolls", r"\b(?P<count>\d+)\s+(?:Rolls?|rolls?|ROLLS?)\b", ("count",)),
    # "Eggs, x12" — comma-anchored to avoid colliding with " X4 box" multipack
    _p("en_comma_xn", r",\s*[xX]\s*(?P<count>\d+)\b", ("count",)),
    # "50 PCS", "10 Pcs.", "5 pcs" — word-boundary before digits so SKU tail
    # "SM15CT" no longer matches (multipack_pcs_en still handles canonicalization).
    _p(
        "en_n_pcs",
        r"(?<!\w)(?P<count>\d+)\s*(?:PCS|Pcs|pcs|PIECES|Pieces|pieces|PIECE|Piece|piece)\.?\b",
        ("count",),
    ),
    # "7's", "50'S", "5'S" — apostrophe-S variant of en_sachets_s.
    # ASCII ' (U+0027), curly ' (U+2019), backtick ` (U+0060).
    _p("en_apos_s", r"\b(?P<count>\d+)\s*['’`]\s*[sS]\b", ("count",)),
    # "2 tickets to the theater"
    _p(
        "en_n_tickets",
        r"\b(?P<count>\d+)\s+(?:Tickets?|tickets?|TICKETS?)\b",
        ("count",),
    ),
)
