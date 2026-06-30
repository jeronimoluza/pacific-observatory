"""count_pack bucket — CPI-survey count idiom patterns (extract role).

Records moved VERBATIM from shared/cpi_count_markers.py (lang="any"), ids renamed
to SCREAMING_SNAKE. Targets short CPI-style descriptions whose pack count appears
as free text rather than a structured marker. Sorts LAST in GOLDEN_EXTRA_COUNT.
script=None (was under shared/). Compiled WITHOUT re.IGNORECASE — extract-role
patterns enumerate case variants explicitly.
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
        kind="extra_count",
        bucket="count_pack",
    )


PATTERNS: tuple[PackPattern, ...] = (
    # "4 rolls of toilet paper", "Toilet paper, 4 rolls"
    _p("NUM_ROLLS", r"\b(?P<count>\d+)\s+(?:Rolls?|rolls?|ROLLS?)\b", ("count",)),
    # "Eggs, x12" — comma-anchored to avoid colliding with " X4 box" multipack
    _p("EN_COMMA_XN", r",\s*[xX]\s*(?P<count>\d+)\b", ("count",)),
    # "50 PCS", "10 Pcs.", "5 pcs" — word-boundary before digits so SKU tail
    # "SM15CT" no longer matches (NUM_PCS still handles canonicalization).
    _p(
        "EN_PCS",
        r"(?<!\w)(?P<count>\d+)\s*(?:PCS|Pcs|pcs|PIECES|Pieces|pieces|PIECE|Piece|piece)\.?\b",
        ("count",),
    ),
    # "7's", "50'S", "5'S" — apostrophe-S variant of EN_SACHETS.
    # ASCII ' (U+0027), curly ' (U+2019), backtick ` (U+0060).
    _p("EN_APOS_S", r"\b(?P<count>\d+)\s*['’`]\s*[sS]\b", ("count",)),
    # "2 tickets to the theater"
    _p(
        "EN_N_TICKETS",
        r"\b(?P<count>\d+)\s+(?:Tickets?|tickets?|TICKETS?)\b",
        ("count",),
    ),
)
