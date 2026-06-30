"""Parked / unrouted bucket — declared patterns deliberately fed to no consumed bucket.

VERSION_CJK (was cjk_numeral_version) is a live registry pattern (so it is part of
the rename surface and the load_for membership) but kind="unrouted" keeps it out of
every consumed composition bucket — 二版/二種/二樣/二品 are almost always
style/edition descriptors, not pack counts (e.g. 經典二版 = "classic 2nd edition"
on a book title). Dropped from extra_count 2026-06-16. Moved VERBATIM from
script/cjk/count_markers.py; script="cjk" (was under script/cjk/).
"""

from __future__ import annotations

import re

from prices.enrich.regex_patterns.types import PackPattern

PATTERNS: tuple[PackPattern, ...] = (
    PackPattern(
        id="VERSION_CJK",
        regex=re.compile(
            r"(?P<count_cjk>[一二三四五六七八九十]+)(?:版|種(?:口味)?|樣|樣式|品)",
        ),
        groups=("count_cjk",),
        lang="any",
        role="extract",
        kind="unrouted",
        bucket="_unrouted",
        script="cjk",
    ),
)
