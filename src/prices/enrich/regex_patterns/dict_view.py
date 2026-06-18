"""Adapters that present the typed tree as the dict shape extract.py and
normalize.py historically built from YAML.

After §6 swap, extract.py and normalize.py import these instead of running
the YAML loader. Keeping a fixed list-order (rather than walking `_INDEX`
in dict-insertion order) preserves byte-identity with the YAML-driven path.
"""

from __future__ import annotations

import re
from typing import Any

from prices.enrich.regex_patterns._registry import _INDEX
from prices.enrich.regex_patterns.flag_markers import BUNDLE_MARKERS, PROMO_MARKERS
from prices.enrich.regex_patterns.unit_tables import UNIT_MAP, UNIT_NORM

# Source-order of patterns inside the original YAMLs. Locked here so the
# emitted lists stay deterministic and don't drift with import-graph changes.
_CANON_ORDER: tuple[str, ...] = (
    "multipack_num_x_value_unit",
    "multipack_value_unit_x_count",
    "multipack_pcs_en",
    "multipack_n_x_only",
    "multipack_vi_loc",
    "multipack_vi_count_unit",
    "multipack_zh_count_unit",
    "multipack_ja_kana_set",
    "value_unit_volume_mass",
    "zh_volume_mass",
)

_EXTRA_UNIT_ORDER: tuple[str, ...] = ("cl_volume", "vi_lit_volume")

_EXTRA_COUNT_ORDER: tuple[str, ...] = (
    "cjk_mai",
    "cjk_pair",
    "cjk_grain",
    "cjk_strip",
    "cjk_sheet_tissue",
    "cjk_set_group",
    # cjk_numeral_version (二版/二種/二樣/二品) dropped 2026-06-16: these are
    # almost always style/edition descriptors, not pack counts (e.g. 經典二版
    # = "classic 2nd edition" on a book title). Surfaced as gold=item / pred=
    # count failures during the tier-a precision lift.
    "cjk_numeral_set",
    "vi_to_sheets",
    "cjk_ko_pcs",
    "cjk_n_x_count",
    "cjk_double_pack",
    "en_caps",
    "en_tablets",
    "en_sachets_s",
    "en_sheets",
    "en_pack_of",
    "en_n_pack",
    "en_n_individual_pack",
    "en_twin_pack",
    "en_triple_pack",
    "en_double_pack",
    "vi_m_pieces",
    # CPI-survey idioms (added 2026-06-16) — short product names where the
    # pack count is a free-text phrase rather than a structured marker.
    "en_n_rolls",
    "en_comma_xn",
    "en_n_pcs",
    "en_apos_s",
    "en_n_tickets",
)

_MULTI_PACK_ORDER: tuple[str, ...] = (
    "cjk_inner_outer_star",
    "cjk_inner_outer_full",
)

_PRICING_BASIS_MARKER_ORDER: tuple[str, ...] = (
    "en_per_kg_parens",
    "en_per_kg_bare",
    "en_per_l_parens",
    "en_per_liter_bare",
)


def _marker_block(table: dict[str, tuple[str, ...]]) -> list[dict[str, Any]]:
    return [
        {
            "lang": lang,
            "patterns": [re.compile(p, flags=re.IGNORECASE) for p in pats],
        }
        for lang, pats in table.items()
    ]


def pack_patterns_for_normalize() -> list[dict[str, Any]]:
    """Shape that normalize.py's old `_load_pack_patterns` produced.

    Each entry has `id`, `lang`, `regex` (pre-compiled), `groups` (dict).
    The `groups` dict is keyed by named group, value is the field name —
    which equals the group name in every YAML record, so we mirror that.
    """
    out: list[dict[str, Any]] = []
    for pid in _CANON_ORDER:
        pat, _ = _INDEX[pid]
        out.append(
            {
                "id": pat.id,
                "lang": pat.lang,
                "regex": pat.regex,
                "groups": {g: g for g in pat.groups},
            }
        )
    return out


def unit_norm() -> dict[str, str]:
    return dict(UNIT_NORM)


def regex_units_for_extract() -> (
    tuple[
        dict[str, dict[str, Any]],
        list[dict[str, Any]],
        list[dict[str, Any]],
        list[dict[str, Any]],
        list[dict[str, Any]],
        list[dict[str, Any]],
        list[dict[str, Any]],
    ]
):
    """Shape that extract.py's old `_load_regex_units` returned, now a 7-tuple.

    Order: unit_map, extra_units, extra_count, multi_pack, promo, bundle,
           pricing_basis_markers.
    """
    unit_map = {
        k: {"basis": v.basis, "su": v.su, "mul": float(v.mul)}
        for k, v in UNIT_MAP.items()
    }

    extra_units: list[dict[str, Any]] = []
    for pid in _EXTRA_UNIT_ORDER:
        pat, _ = _INDEX[pid]
        ue = pat.unit_emit
        assert ue is not None, f"{pid} missing unit_emit"
        extra_units.append(
            {
                "id": pat.id,
                "lang": pat.lang,
                "regex": pat.regex,
                "basis": ue.basis,
                "su": ue.su,
                "mul": float(ue.mul),
            }
        )

    extra_count: list[dict[str, Any]] = []
    for pid in _EXTRA_COUNT_ORDER:
        pat, _ = _INDEX[pid]
        extra_count.append(
            {
                "id": pat.id,
                "lang": pat.lang,
                "regex": pat.regex,
                "fixed_count": pat.fixed_count,
            }
        )

    multi_pack: list[dict[str, Any]] = []
    for pid in _MULTI_PACK_ORDER:
        pat, _ = _INDEX[pid]
        multi_pack.append(
            {
                "id": pat.id,
                "lang": pat.lang,
                "regex": pat.regex,
            }
        )

    pricing_basis_markers: list[dict[str, Any]] = []
    for pid in _PRICING_BASIS_MARKER_ORDER:
        pat, _ = _INDEX[pid]
        assert pat.pricing_basis_emit is not None, f"{pid} missing pricing_basis_emit"
        pricing_basis_markers.append(
            {
                "id": pat.id,
                "lang": pat.lang,
                "regex": pat.regex,
                "pricing_basis_emit": pat.pricing_basis_emit,
            }
        )

    return (
        unit_map,
        extra_units,
        extra_count,
        multi_pack,
        _marker_block(dict(PROMO_MARKERS)),
        _marker_block(dict(BUNDLE_MARKERS)),
        pricing_basis_markers,
    )
