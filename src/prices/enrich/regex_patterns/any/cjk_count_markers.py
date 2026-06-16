"""CJK count markers (extract role) — translated verbatim from regex_units.yaml::extra_count_markers."""

from __future__ import annotations

import re

from prices.enrich.regex_patterns.types import PackPattern


def _p(
    id_: str, regex: str, groups: tuple[str, ...], fixed_count: int | None = None
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
    _p(
        "cjk_numeral_version",
        r"(?P<count_cjk>[一二三四五六七八九十]+)(?:版|種(?:口味)?|樣|樣式|品)",
        ("count_cjk",),
    ),
    _p(
        "cjk_numeral_set",
        r"(?P<count_cjk>[一二三四五六七八九十]+)(?:本|入|片|盒|個|包|束|件|杯|袋|張|支|冊|箱)(?:組|套)?",
        ("count_cjk",),
    ),
    _p("cjk_ko_pcs", r"(?P<count>\d+)\s*(?:개|매|병|봉|장|회)", ("count",)),
    _p(
        "cjk_n_x_count",
        r"\bM?[xX×]\s*(?P<count>\d+)\s*(?:組|セット|本|入|片|盒|個|包|束|件|杯|袋|張)\b",
        ("count",),
    ),
    _p(
        "cjk_double_pack",
        r"\b(?:ダブルパック|ツインパック|デュアルパック)\b",
        (),
        fixed_count=2,
    ),
)
