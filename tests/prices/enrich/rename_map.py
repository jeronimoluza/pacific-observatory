"""Authoritative old-id -> SCREAMING_SNAKE rename map (Phase 01.66 / Plan 01, SC1/SC2).

This is the SINGLE source of truth for the tier-a regex_patterns id rename that
Plan 03 applies (golden regen + live-literal renames). Both the golden regen and
the in-tree literal renames import RENAME from here — the mapping is never
duplicated.

Invariants (proven by test_rename_map.py):
  * domain == every id in the registry `_INDEX` (all 47, no miss)
  * every image matches ^[A-Z0-9_]+$
  * images are globally unique (no collision)
  * len(set(values)) == len(RENAME) == len(_INDEX) == 47  (bijection)

The SCREAMING_SNAKE style is locked; spellings group ids by their shape bucket
(per_unit_marker / single_measure / multipack / count_pack / _unrouted).
"""

from __future__ import annotations

RENAME: dict[str, str] = {
    # --- per_unit_marker -----------------------------------------------------
    "en_per_kg_bare": "PER_KG",
    "en_per_kg_parens": "PER_KG_PARENS",
    "en_per_liter_bare": "PER_LITRE",
    "en_per_l_parens": "PER_LITRE_PARENS",
    # --- single_measure ------------------------------------------------------
    "value_unit_volume_mass": "VALUE_UNIT",
    "zh_volume_mass": "VALUE_UNIT_ZH",
    "cl_volume": "CENTILITRE",
    "vi_lit_volume": "LITRE_VI",
    # --- multipack -----------------------------------------------------------
    "multipack_num_x_value_unit": "NUM_X_VALUE_UNIT",
    "multipack_value_unit_x_count": "VALUE_UNIT_X_NUM",
    "multipack_pcs_en": "NUM_PCS",
    "multipack_pc_glued_en": "NUM_PC_GLUED",
    "multipack_n_x_only": "NUM_X_TRAILING",
    "multipack_vi_loc": "LOC_VI",
    "multipack_vi_count_unit": "COUNT_UNIT_VI",
    "multipack_zh_count_unit": "COUNT_UNIT_ZH",
    "multipack_ja_kana_set": "SET_JA",
    "cjk_inner_outer_star": "INNER_X_OUTER_STAR",
    "cjk_inner_outer_full": "INNER_X_OUTER",
    # --- count_pack ----------------------------------------------------------
    "cjk_mai": "CJK_MAI",
    "cjk_pair": "CJK_PAIR",
    "cjk_grain": "CJK_GRAIN",
    "cjk_strip": "CJK_STRIP",
    "cjk_sheet_tissue": "CJK_SHEET",
    "cjk_set_group": "CJK_SET",
    "cjk_numeral_set": "CJK_NUMERAL_SET",
    "cjk_ko_pcs": "CJK_KO_PCS",
    "cjk_n_x_count": "CJK_N_X_COUNT",
    "cjk_double_pack": "CJK_DOUBLE_PACK",
    "en_caps": "EN_CAPS",
    "en_tablets": "EN_TABLETS",
    "en_sachets_s": "EN_SACHETS",
    "en_sheets": "EN_SHEETS",
    "en_pack_of": "EN_PACK_OF",
    "en_n_pack": "EN_N_PACK",
    "en_n_individual_pack": "EN_N_INDIVIDUAL_PACK",
    "en_half_dozen": "EN_HALF_DOZEN",
    "en_dozen": "EN_DOZEN",
    "en_twin_pack": "EN_TWIN_PACK",
    "en_triple_pack": "EN_TRIPLE_PACK",
    "en_double_pack": "EN_DOUBLE_PACK",
    "en_count_num_noun": "EN_COUNT_NUM_NOUN",
    "en_count_noun_trail": "EN_COUNT_NOUN_TRAIL",
    "en_n_rolls": "NUM_ROLLS",
    "en_comma_xn": "EN_COMMA_XN",
    "en_n_pcs": "EN_PCS",
    "en_apos_s": "EN_APOS_S",
    "en_n_tickets": "EN_N_TICKETS",
    "vi_m_pieces": "VI_PIECES",
    "vi_to_sheets": "VI_TO_SHEETS",
    # --- _unrouted -----------------------------------------------------------
    "cjk_numeral_version": "VERSION_CJK",
}
