"""CJK count markers (extract role) — translated verbatim from regex_units.yaml::extra_count_markers.

Part 1 of the CJK count markers. `cjk_ko_pcs` / `cjk_n_x_count` / `cjk_double_pack`
live in count_markers_b.py because, in the consumed extra_count order, the
script-agnostic `vi_to_sheets` marker (shared/vi_extras.py) sorts between this run
and that one. The file split is the order source-of-truth — there is no separate
ID-order tuple anymore (Phase 0.5 / Plan 04).
"""

from __future__ import annotations

import re

from prices.enrich.regex_patterns.types import PackPattern


def _p(
    id_: str,
    regex: str,
    groups: tuple[str, ...],
    fixed_count: int | None = None,
    kind: str = "extra_count",
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
        kind=kind,
    )


PATTERNS: tuple[PackPattern, ...] = (
    _p("cjk_mai", r"(?P<count>\d+)\s*枚", ("count",)),
    _p("cjk_pair", r"(?P<count>\d+)\s*雙", ("count",)),
    _p("cjk_grain", r"(?P<count>\d+)\s*顆", ("count",)),
    _p("cjk_strip", r"(?P<count>\d+)\s*條(?:入)?", ("count",)),
    _p("cjk_sheet_tissue", r"(?P<count>\d+)\s*抽", ("count",)),
    _p(
        "cjk_set_group",
        r"(?P<count>\d+)\s*(?:本|入|片|盒|個|包|束|件|杯|袋|張|支|冊|箱)(?:組|套(?:書|裝)?|入り?)?",
        ("count",),
    ),
    # kind="unrouted": cjk_numeral_version (二版/二種/二樣/二品) dropped 2026-06-16
    # — these are almost always style/edition descriptors, not pack counts (e.g.
    # 經典二版 = "classic 2nd edition" on a book title). Surfaced as gold=item /
    # pred=count failures during the tier-a precision lift. Declared but not fed to
    # any consumed bucket (was: deliberately omitted from _EXTRA_COUNT_ORDER).
    _p(
        "cjk_numeral_version",
        r"(?P<count_cjk>[一二三四五六七八九十]+)(?:版|種(?:口味)?|樣|樣式|品)",
        ("count_cjk",),
        kind="unrouted",
    ),
    _p(
        "cjk_numeral_set",
        r"(?P<count_cjk>[一二三四五六七八九十]+)(?:本|入|片|盒|個|包|束|件|杯|袋|張|支|冊|箱)(?:組|套)?",
        ("count_cjk",),
    ),
)
