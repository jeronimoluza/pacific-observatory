"""Latin-script count-marker patterns (extract role) — translated from regex_units.yaml::extra_count_markers."""

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
    )


PATTERNS: tuple[PackPattern, ...] = (
    _p(
        "en_caps",
        r"\b(?P<count>\d+)\s*(?:Caps?|Capsules?|caps?|capsules?|CAPS?|CAPSULES?)\b",
        ("count",),
    ),
    _p(
        "en_tablets",
        r"\b(?P<count>\d+)\s*(?:Tabs?|Tablets?|tabs?|tablets?|TABS?|TABLETS?)\b",
        ("count",),
    ),
    _p("en_sachets_s", r"\b(?P<count>\d+)[sS]\b(?:\s|$)", ("count",)),
    _p(
        "en_sheets",
        r"\b(?P<count>\d+)\s*(?:Sheets?|sheets?|SHEETS?)\b",
        ("count",),
    ),
    _p("en_pack_of", r"\bPack\s*of\s*(?P<count>\d+)\b", ("count",)),
    _p(
        "en_n_pack",
        r"\b(?P<count>\d+)\s*[-]?\s*(?:Pack|PACK|pack)\b",
        ("count",),
    ),
    _p(
        "en_n_individual_pack",
        r"\b(?P<count>\d+)\s*(?:INDIVIDUAL|Individual|individual)\s*(?:PACK|Pack|pack)\b",
        ("count",),
    ),
    _p("en_twin_pack", r"\bTwin\s*Pack\b", (), fixed_count=2),
    _p(
        "en_triple_pack",
        r"\b(?:Triple\s*Pack|Tri\s*Pack)\b",
        (),
        fixed_count=3,
    ),
    _p("en_double_pack", r"\bDouble\s*Pack\b", (), fixed_count=2),
)
