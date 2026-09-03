"""count_pack bucket — CJK count markers, part 1 (extract role).

Records moved VERBATIM from script/cjk/count_markers.py (minus the parked
VERSION_CJK, now in buckets/_unrouted.py), ids renamed to SCREAMING_SNAKE. Split
from cjk_b.py because in GOLDEN_EXTRA_COUNT the script-agnostic VI_TO_SHEETS sorts
between this run and that one — the file boundary is the ordering lever.
script="cjk" (was under script/cjk/). bucket="count_pack" (the monitoring axis).
"""

from __future__ import annotations

import re

from prices.enrich.regex_patterns.types import PackPattern


def _p(
    id_: str,
    regex: str,
    groups: tuple[str, ...],
    fixed_count: int | None = None,
) -> PackPattern:
    # NOTE: extract-role patterns compile WITHOUT re.IGNORECASE to mirror the
    # YAML loader at extract.py::_load_regex_units (which only flag-applies
    # IGNORECASE on promo/bundle markers).
    return PackPattern(
        id=id_,
        regex=re.compile(regex),
        groups=groups,
        lang="any",
        role="extract",
        fixed_count=fixed_count,
        kind="extra_count",
        bucket="count_pack",
        script="cjk",
    )


PATTERNS: tuple[PackPattern, ...] = (
    _p("CJK_MAI", r"(?P<count>\d+)\s*枚", ("count",)),
    _p("CJK_PAIR", r"(?P<count>\d+)\s*雙", ("count",)),
    # 玉 is the Japanese counter for the same round-object class as 顆; without
    # it a mass-less "みかん 10玉" falls to `item` and prices a whole box as one
    # fruit. The optional leading group absorbs a RANGE ("36-40玉", "2玉～3玉"),
    # which extract() resolves to the interval midpoint -- left to the plain
    # branch, the two range spellings matched opposite ends of the interval.
    _p(
        "CJK_GRAIN",
        r"(?:(?P<count_lo>\d+)\s*[顆玉]?\s*[-–~〜～]\s*)?(?P<count>\d+)\s*[顆玉]",
        ("count_lo", "count"),
    ),
    _p("CJK_STRIP", r"(?P<count>\d+)\s*條(?:入)?", ("count",)),
    _p("CJK_SHEET", r"(?P<count>\d+)\s*抽", ("count",)),
    _p(
        "CJK_SET",
        r"(?P<count>\d+)\s*(?:本|入|片|丸|盒|個|包|束|件|杯|袋|張|支|冊|箱|缶|瓶|錠)(?:組|套(?:書|裝)?|入り?)?",
        ("count",),
    ),
    _p(
        "CJK_NUMERAL_SET",
        r"(?P<count_cjk>[一二三四五六七八九十]+)(?:本|入|片|丸|盒|個|包|束|件|杯|袋|張|支|冊|箱|缶|瓶|錠)(?:組|套)?",
        ("count_cjk",),
    ),
)
