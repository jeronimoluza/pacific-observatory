"""count_pack bucket — Latin-script count markers (extract role).

Records moved VERBATIM from script/latin/count_markers.py, ids renamed to
SCREAMING_SNAKE. script="latin" (was under script/latin/). bucket="count_pack".
"""

from __future__ import annotations

import re

from prices.enrich.regex_patterns.types import PackPattern


def _p(
    id_: str, regex: str, groups: tuple[str, ...], fixed_count: int | None = None
) -> PackPattern:
    # extract-role patterns compile WITHOUT re.IGNORECASE — see
    # extract.py::_load_regex_units (only promo/bundle markers get IGNORECASE).
    # The author of these patterns deliberately enumerated case variants
    # (Caps?|Capsules?|caps?|CAPS?) rather than relying on the flag.
    return PackPattern(
        id=id_,
        regex=re.compile(regex),
        groups=groups,
        lang="any",
        role="extract",
        fixed_count=fixed_count,
        kind="extra_count",
        bucket="count_pack",
        script="latin",
    )


PATTERNS: tuple[PackPattern, ...] = (
    _p(
        "EN_CAPS",
        r"\b(?P<count>\d+)\s*(?:Caps?|Capsules?|caps?|capsules?|CAPS?|CAPSULES?)\b",
        ("count",),
    ),
    _p(
        "EN_TABLETS",
        r"\b(?P<count>\d+)\s*(?:Tabs?|Tablets?|tabs?|tablets?|TABS?|TABLETS?)\b",
        ("count",),
    ),
    _p("EN_SACHETS", r"\b(?P<count>\d+)[sS]\b(?:\s|$)", ("count",)),
    _p(
        "EN_SHEETS",
        r"\b(?P<count>\d+)\s*(?:Sheets?|sheets?|SHEETS?)\b",
        ("count",),
    ),
    _p("EN_PACK_OF", r"\bPack\s*of\s*(?P<count>\d+)\b", ("count",)),
    _p(
        "EN_N_PACK",
        r"\b(?P<count>\d+)\s*[-]?\s*(?:Pack|PACK|pack)\b",
        ("count",),
    ),
    _p(
        "EN_N_INDIVIDUAL_PACK",
        r"\b(?P<count>\d+)\s*(?:INDIVIDUAL|Individual|individual)\s*(?:PACK|Pack|pack)\b",
        ("count",),
    ),
    _p("EN_TWIN_PACK", r"\bTwin\s*Pack\b", (), fixed_count=2),
    _p(
        "EN_TRIPLE_PACK",
        r"\b(?:Triple\s*Pack|Tri\s*Pack)\b",
        (),
        fixed_count=3,
    ),
    _p("EN_DOUBLE_PACK", r"\bDouble\s*Pack\b", (), fixed_count=2),
)
