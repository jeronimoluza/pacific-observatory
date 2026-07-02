"""Behavior-freeze guards for the tier-a regex_patterns tree (Phase 0.5 / Plan 04, SC7).

Plan 04 single-sources the tier-a routing/order knot: it adds a `kind` field to
PackPattern, collapses the five hand-maintained ID-order tuples in dict_view.py to
one MODULE_ORDER, renames any/ -> shared/, and generalizes _cjk_shared -> script/cjk
plus script/latin. The regex PATTERNS themselves do not change — only their file
layout and the routing/order source-of-truth.

These two tests are the integrity proofs that make deleting the tuples safe:

  1. Byte-identity snapshot — the composed bucket lists (in their exact current,
     ID-by-ID order) are frozen here as a golden constant captured from the
     PRE-reorg tree. The live composition must reproduce it bit-for-bit. This is the
     SC7 byte-identity guard.

  2. No-silent-drop — every PackPattern in the regex_patterns tree lands in exactly
     one of the five PackPattern-routed buckets (canon / extra_unit / extra_count /
     multi_pack / pricing_basis_marker). No pattern routes to zero or two buckets.

The snapshot deliberately captures EXACTLY what composes today, including the known
`cjk_numeral_version` drift: that pattern is a live PATTERN in the tree but is
deliberately omitted from the extra_count composition (dict_view dropped it
2026-06-16). The reorg must reproduce that omission bit-for-bit — it must NOT
"correct" it.
"""

from __future__ import annotations

import pytest

from rename_map import RENAME

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Golden snapshot — frozen from the PRE-reorg tree at commit 48b1a750 (the
# PARITY-ANCHOR.md before-point). Captured via:
#
#   from prices.enrich.regex_patterns.dict_view import (
#       regex_units_for_extract, pack_patterns_for_normalize)
#   _, eu, ec, mp, promo, bundle, pbm = regex_units_for_extract()
#   [p["id"] for p in pack_patterns_for_normalize()]   # CANON
#   [e["id"] for e in eu], [e["id"] for e in ec], ...  # the rest
#   [b["lang"] for b in promo], [b["lang"] for b in bundle]
#
# `cjk_numeral_version` is intentionally absent from GOLDEN_EXTRA_COUNT.
# ---------------------------------------------------------------------------

_PRE_RENAME_CANON: tuple[str, ...] = (
    "multipack_num_x_value_unit",
    "multipack_value_unit_x_count",
    "multipack_pcs_en",
    "multipack_pc_glued_en",
    "multipack_n_x_only",
    "multipack_vi_loc",
    "multipack_vi_count_unit",
    "multipack_zh_count_unit",
    "multipack_ja_kana_set",
    "value_unit_volume_mass",
    "zh_volume_mass",
)

_PRE_RENAME_EXTRA_UNITS: tuple[str, ...] = ("cl_volume", "vi_lit_volume")

_PRE_RENAME_EXTRA_COUNT: tuple[str, ...] = (
    "cjk_mai",
    "cjk_pair",
    "cjk_grain",
    "cjk_strip",
    "cjk_sheet_tissue",
    "cjk_set_group",
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
    "en_half_dozen",
    "en_dozen",
    "en_twin_pack",
    "en_triple_pack",
    "en_double_pack",
    "vi_m_pieces",
    "en_n_rolls",
    "en_comma_xn",
    "en_n_pcs",
    "en_apos_s",
    "en_n_tickets",
)

_PRE_RENAME_MULTI_PACK: tuple[str, ...] = (
    "cjk_inner_outer_star",
    "cjk_inner_outer_full",
)

_PRE_RENAME_PRICING_BASIS_MARKERS: tuple[str, ...] = (
    "en_per_kg_parens",
    "en_per_kg_bare",
    "en_per_l_parens",
    "en_per_liter_bare",
)

# --------------------------------------------------------------------------- #
# Plan 03 reorg: the live composer now emits SCREAMING_SNAKE ids. Each golden is
# regenerated POSITIONALLY by mapping the frozen pre-reorg sequence through the
# authoritative RENAME map — `tuple(RENAME[x] for x in OLD)`. This deliberately
# does NOT re-run the live composer (that would silently absorb a reorder and
# defeat the byte-identity net). Promo/bundle langs are not ids, so they are
# unchanged.
# --------------------------------------------------------------------------- #
GOLDEN_CANON: tuple[str, ...] = tuple(RENAME[x] for x in _PRE_RENAME_CANON)
GOLDEN_EXTRA_UNITS: tuple[str, ...] = tuple(RENAME[x] for x in _PRE_RENAME_EXTRA_UNITS)
GOLDEN_EXTRA_COUNT: tuple[str, ...] = tuple(RENAME[x] for x in _PRE_RENAME_EXTRA_COUNT)
GOLDEN_MULTI_PACK: tuple[str, ...] = tuple(RENAME[x] for x in _PRE_RENAME_MULTI_PACK)
GOLDEN_PRICING_BASIS_MARKERS: tuple[str, ...] = tuple(
    RENAME[x] for x in _PRE_RENAME_PRICING_BASIS_MARKERS
)

GOLDEN_PROMO_LANGS: tuple[str, ...] = (
    "any",
    "en",
    "es",
    "pt",
    "fr",
    "zh",
    "ja",
    "ko",
    "vi",
    "th",
    "id",
    "ms",
)

GOLDEN_BUNDLE_LANGS: tuple[str, ...] = (
    "any",
    "en",
    "zh",
    "ja",
    "ko",
    "es",
    "pt",
)

# `cjk_numeral_version` is a live PATTERN in the tree but is deliberately NOT
# routed into the consumed extra_count bucket. The no-silent-drop test treats it
# as a sanctioned exception so the byte-identity snapshot stays honest.
SANCTIONED_UNROUTED: frozenset[str] = frozenset({"VERSION_CJK"})


def _live_composed() -> dict[str, tuple[str, ...]]:
    from prices.enrich.regex_patterns.dict_view import (
        pack_patterns_for_normalize,
        regex_units_for_extract,
    )

    (
        _unit_map,
        extra_units,
        extra_count,
        multi_pack,
        promo,
        bundle,
        pricing_basis_markers,
    ) = regex_units_for_extract()
    return {
        "canon": tuple(p["id"] for p in pack_patterns_for_normalize()),
        "extra_units": tuple(e["id"] for e in extra_units),
        "extra_count": tuple(e["id"] for e in extra_count),
        "multi_pack": tuple(e["id"] for e in multi_pack),
        "pricing_basis_markers": tuple(e["id"] for e in pricing_basis_markers),
        "promo_langs": tuple(b["lang"] for b in promo),
        "bundle_langs": tuple(b["lang"] for b in bundle),
    }


def test_byte_identity_snapshot() -> None:
    """The live-composed bucket lists byte-match the frozen golden snapshot.

    This is the SC7 byte-identity guard: it must hold before AND after the
    routing/order reorg, proving no pattern was dropped, added, or reordered.
    """
    live = _live_composed()
    assert live["canon"] == GOLDEN_CANON
    assert live["extra_units"] == GOLDEN_EXTRA_UNITS
    assert live["extra_count"] == GOLDEN_EXTRA_COUNT
    assert live["multi_pack"] == GOLDEN_MULTI_PACK
    assert live["pricing_basis_markers"] == GOLDEN_PRICING_BASIS_MARKERS
    assert live["promo_langs"] == GOLDEN_PROMO_LANGS
    assert live["bundle_langs"] == GOLDEN_BUNDLE_LANGS


def test_no_silent_drop() -> None:
    """Every PackPattern in the tree lands in exactly one consumed bucket.

    Walks the entire regex_patterns tree via the registry index, then checks each
    pattern id against the five PackPattern-routed composed buckets. A pattern that
    appears in zero buckets (other than the sanctioned drift) or in two buckets is a
    routing bug.
    """
    from prices.enrich.regex_patterns._registry import _INDEX

    live = _live_composed()
    routed_buckets = (
        live["canon"],
        live["extra_units"],
        live["extra_count"],
        live["multi_pack"],
        live["pricing_basis_markers"],
    )

    all_ids = set(_INDEX.keys())

    membership: dict[str, int] = {pid: 0 for pid in all_ids}
    for bucket in routed_buckets:
        for pid in bucket:
            assert pid in membership, f"composed id {pid!r} not in tree index"
            membership[pid] += 1

    zero_bucket = {
        pid
        for pid, n in membership.items()
        if n == 0 and pid not in SANCTIONED_UNROUTED
    }
    multi_bucket = {pid for pid, n in membership.items() if n > 1}

    assert (
        not zero_bucket
    ), f"patterns routed to NO bucket (silent drop): {sorted(zero_bucket)}"
    assert (
        not multi_bucket
    ), f"patterns routed to MULTIPLE buckets: {sorted(multi_bucket)}"
