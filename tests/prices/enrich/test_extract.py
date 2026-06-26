"""Unit tests for `prices.enrich.normalize.extract` — tier (a) regex extractor.

Covers per-language pack/unit patterns, multipack, promo + bundle markers,
and edge cases (empty input, no-match, cl, length-like-mass false-positive).
"""

from __future__ import annotations

import pytest

from prices.enrich.extract import extract


def _ex(name, lang=None, country=""):
    return extract(name, None, country, lang)


# --- defaults / edge cases ---------------------------------------------------


def test_empty_input_returns_all_none():
    sf = _ex("")
    assert sf.pricing_basis is None
    assert sf.amount_value is None
    assert sf.standard_unit is None
    assert sf.count is None
    assert sf.is_multipack is None


def test_whitespace_only_returns_all_none():
    sf = _ex("   ")
    assert sf.pricing_basis is None


def test_no_unit_no_count_defaults_to_item():
    sf = _ex("Generic Brand Raincoat XL", lang="en")
    assert sf.pricing_basis == "item"
    assert sf.standard_unit == "item"
    assert sf.amount_value is None
    assert sf.count == 1
    assert sf.multiplier == 1
    assert sf.is_multipack is False


# --- mass / volume / cl ------------------------------------------------------


@pytest.mark.parametrize(
    "name, expected_av, expected_su",
    [
        ("Coca-Cola 500ml", 0.5, "lt"),
        ("Pepsi 1L", 1.0, "lt"),
        ("Milk 1.5L", 1.5, "lt"),
        ("Bottle 75cl", 0.75, "lt"),
        ("Sugar 2KG", 2.0, "kg"),
        ("Wardah Lip Balm 7G", 0.007, "kg"),
        ("Salt 250g", 0.25, "kg"),
    ],
)
def test_value_unit_extraction(name, expected_av, expected_su):
    sf = _ex(name, lang="en")
    assert sf.standard_unit == expected_su
    assert sf.amount_value == pytest.approx(expected_av, rel=1e-6)
    assert sf.pricing_basis in {"mass", "volume"}


def test_mass_marker_overrides_item_default():
    sf = _ex("Wardah Lip Balm 7G", lang="en")
    assert sf.pricing_basis == "mass"


def test_volume_marker_overrides_item_default():
    sf = _ex("Tonic 250ml", lang="en")
    assert sf.pricing_basis == "volume"


def test_cm_does_not_register_as_pack():
    """Cutlery dimensions must NOT become pricing_basis=length."""
    sf = _ex("Chef Knife 16.5cm", lang="en")
    assert sf.pricing_basis == "item"
    assert sf.amount_value is None


@pytest.mark.parametrize(
    "name, expected_av",
    [
        ("Macro Organic Soy Milk 1ltr", 1.0),
        ("SIMPLY SOYA BEAN OIL 5LT", 5.0),
        ("Crush Natural Artesian Water 1.5LTR", 1.5),
        ("Jucy Orange 2.25LTRS", 2.25),
        ("Redribbon Sce 3LTR", 3.0),
    ],
)
def test_litre_spellings_extract_as_volume(name, expected_av):
    """`ltr`/`lt`/`ltrs` are real retail litre spellings (Fiji/PNG data)."""
    sf = _ex(name, lang="en")
    assert sf.pricing_basis == "volume"
    assert sf.standard_unit == "lt"
    assert sf.amount_value == pytest.approx(expected_av, rel=1e-6)


@pytest.mark.parametrize(
    "name",
    [
        "Himalayan Pink Salt 250g",  # 'lt' inside salt; 250g must win → mass
        "Cordless Drill 5 Bolt Kit",  # 'bolt' after a number must not read as litre
        "Default Moisturiser 50ml",  # 'lt' inside default; 50ml must win → volume/ml
    ],
)
def test_litre_lookalikes_not_misread(name):
    """The litre spellings need a preceding number; word-internal 'lt' must not fire."""
    sf = _ex(name, lang="en")
    assert sf.amount_value != pytest.approx(5.0)  # no spurious "5 litre" etc.


@pytest.mark.parametrize(
    "name, expected_av, expected_su",
    [
        ("Rx: Epokine 4,000 IU/ .3 mL Solution for Injection", 0.0003, "lt"),
        ("Filgrastim Injection .5 mL Prefilled Syringe", 0.0005, "lt"),
        (".75 L Bottle Sparkling Water", 0.75, "lt"),
    ],
)
def test_leading_dot_decimal_measure(name, expected_av, expected_su):
    """Leading-dot decimals (`.3 mL`, common in pharma dosing) extract correctly."""
    sf = _ex(name, lang="en")
    assert sf.pricing_basis == "volume"
    assert sf.standard_unit == expected_su
    assert sf.amount_value == pytest.approx(expected_av, rel=1e-6)


def test_leading_dot_needs_clean_left_boundary():
    """A dot glued to a letter/digit (`No.3 ml`) is NOT a measure."""
    sf = _ex("Catalogue Item No.3 ml description", lang="en")
    assert sf.amount_value != pytest.approx(0.0003)


# --- "Pack of N" / "Bundle of N" outer multiplier with a per-unit measure ----


@pytest.mark.parametrize(
    "name, expected_av, expected_su, expected_mult",
    [
        ("NIVEA Spray 150ml Pack Of 2", 0.15, "lt", 2),
        ("Vaseline Lotion 70Ml Bundle of 2", 0.07, "lt", 2),
        ("Vaseline Lotion Bundle of 2 70ml", 0.07, "lt", 2),
        ("Sachet 10g Pack of 3", 0.01, "kg", 3),
    ],
)
def test_pack_of_n_promotes_to_multiplier_with_measure(
    name, expected_av, expected_su, expected_mult
):
    """A per-unit measure + 'Pack/Bundle of N' → N is the outer multiplier."""
    sf = _ex(name, lang="en")
    assert sf.pricing_basis in {"mass", "volume"}
    assert sf.standard_unit == expected_su
    assert sf.amount_value == pytest.approx(expected_av, rel=1e-6)
    assert sf.multiplier == expected_mult
    assert sf.count == 1
    assert sf.is_multipack is True


def test_pack_of_glued_measure_is_not_a_count():
    """'Pack of 500g' = a single 500g pack; 500 is the mass, not a multiplier."""
    sf = _ex("Value Pack of 500g Rice", lang="en")
    assert sf.pricing_basis == "mass"
    assert sf.amount_value == pytest.approx(0.5)
    assert sf.multiplier == 1


def test_pack_of_n_without_measure_stays_count():
    """No per-unit measure: 'Pack of 12' remains a count basis (unchanged)."""
    sf = _ex("Pencils Pack of 12", lang="en")
    assert sf.pricing_basis == "count"
    assert sf.count == 12
    assert sf.multiplier == 1


# --- multipack ---------------------------------------------------------------


@pytest.mark.parametrize(
    "name, expected_basis, expected_av",
    [
        ("Thin Sausages 24 Pack 1.8kg", "mass", 1.8),
        ("Snack Multipack 6 Pack 330ml", "volume", 0.33),
        ("Kẹo đậu Phộng Hình Quạt (4 miếng) VIETTIN MART 240g", "mass", 0.24),
        ("Vitamin Tablets 30 viên 500mg", "mass", 0.0005),
    ],
)
def test_bare_count_plus_total_measure_is_not_a_multiplier(
    name, expected_basis, expected_av
):
    """A bare 'N Pack/PCS' or 'N miếng/viên' next to a single TOTAL mass/volume
    means the measure is the pack total — the count is internal, multiplier=1."""
    sf = _ex(name)
    assert sf.pricing_basis == expected_basis
    assert sf.amount_value == pytest.approx(expected_av, rel=1e-6)
    assert sf.multiplier == 1
    assert sf.count == 1


def test_multipack_value_unit():
    sf = _ex("Plain Crackers 4x20g", lang="en")
    assert sf.pricing_basis == "mass"
    assert sf.amount_value == pytest.approx(0.02)
    assert sf.standard_unit == "kg"
    assert sf.multiplier == 4
    assert sf.count == 1
    assert sf.is_multipack is True


def test_multipack_24_x_330ml():
    sf = _ex("Ganzberg Beer 24x330ml", lang="en")
    assert sf.pricing_basis == "volume"
    assert sf.amount_value == pytest.approx(0.33)
    assert sf.multiplier == 24
    assert sf.count == 1
    assert sf.is_multipack is True


def test_cjk_outer_multiplier_at_declared_lang():
    # `×24本` is a script-specific outer-pack multiplier that needs lang=None
    # patterns; a successful per-unit `500ml` match in declared lang used to
    # suppress the retry, dropping the multiplier (left it at 1).
    sf = _ex("三ツ矢サイダー 500ml×24本", lang="ja")
    assert sf.pricing_basis == "volume"
    assert sf.amount_value == pytest.approx(0.5)
    assert sf.standard_unit == "lt"
    assert sf.count == 1
    assert sf.multiplier == 24
    assert sf.is_multipack is True


def test_cjk_outer_multiplier_mass_at_declared_lang():
    sf = _ex("せんべい 120g×28袋", lang="ja")
    assert sf.pricing_basis == "mass"
    assert sf.amount_value == pytest.approx(0.12)
    assert sf.standard_unit == "kg"
    assert sf.count == 1
    assert sf.multiplier == 28


def test_cjk_total_breakdown_not_double_counted():
    # `10kg（5kg×2袋）` states a TOTAL (10kg) then its breakdown; the ×2 is the
    # breakdown, not an extra multiplier, so multiplier must stay 1 (total 10kg),
    # not become 2 (which would imply 20kg).
    sf = _ex("コシヒカリ 白米 10kg（5kg×2袋）令和7年産", lang="ja")
    assert sf.pricing_basis == "mass"
    assert sf.amount_value == pytest.approx(10.0)
    assert sf.multiplier == 1


def test_cjk_servings_count_not_treated_as_multiplier():
    # `50杯分` (50 servings) is a portions count, not a pack multiplier; the real
    # pack is `×1袋`, so multiplier must stay 1.
    sf = _ex("即席スープ [50杯分] 200g×1袋 お徳用", lang="ja")
    assert sf.pricing_basis == "mass"
    assert sf.amount_value == pytest.approx(0.2)
    assert sf.multiplier == 1


def test_cjk_outer_multiplier_suppressed_in_limit_clause():
    # A CJK count inside a purchase-limit clause (お一人様…限り) must NOT be
    # mistaken for an outer-pack multiplier.
    sf = _ex("緑茶 500ml お一人様5本限り", lang="ja")
    assert sf.pricing_basis == "volume"
    assert sf.amount_value == pytest.approx(0.5)
    assert sf.multiplier == 1


@pytest.mark.parametrize(
    "name, expected_count",
    [
        ("Miếng dán mụn giúp giảm mụn sưng viêm Acnes Clear Patch (24 Miếng)", 24),
        ("Thuốc bổ Vitamin C (60 viên)", 60),
        ("Khẩu trang y tế Hộp 50 Miếng", 50),
    ],
)
def test_vietnamese_counter_vocab_yields_count(name, expected_count):
    """Vietnamese `viên`/`miếng` counters → count basis (lang=None retry path)."""
    sf = _ex(name)
    assert sf.pricing_basis == "count"
    assert sf.standard_unit == "unit"
    assert sf.count == expected_count
    assert sf.multiplier == 1


def test_pcs_only_marker_yields_count_basis():
    sf = _ex("Pencils 12 PCS", lang="en")
    assert sf.pricing_basis == "count"
    assert sf.standard_unit == "unit"
    assert sf.count == 12
    assert sf.is_multipack is True


@pytest.mark.parametrize(
    "name, expected_count",
    [
        ("Pork Sausage with Cheese (5pc)", 5),
        ("All-Natural Donuts Plain (3pc)", 3),
        ("LS HOOK OVAL VERT 3PC M HK-1", 3),
        ("Combi Nipple Round Hole Size S 2pc", 2),
    ],
)
def test_glued_singular_pc_yields_count(name, expected_count):
    """Glued singular `Npc` (no trailing s) → count basis, like `Npcs`."""
    sf = _ex(name, lang="en")
    assert sf.pricing_basis == "count"
    assert sf.standard_unit == "unit"
    assert sf.count == expected_count
    assert sf.multiplier == 1


def test_glued_singular_pc_single_unit_is_item():
    """`1pc` is a single unit → item by the v0.2 single-unit rule, not count/1."""
    sf = _ex("Cezanne Shading Stick 02 1pc", lang="en")
    assert sf.pricing_basis == "item"
    assert sf.standard_unit == "item"


def test_spaced_pc_is_not_a_piece_count():
    """`N PC` spaced (personal computer) must NOT be read as a pieces count."""
    sf = _ex("Gaming Desktop Windows 11 PC", lang="en")
    assert sf.pricing_basis == "item"


def test_glued_pcs_still_count_not_singular_pc():
    """`Npcs` keeps its full count (the `(?!s)` guard doesn't truncate to Npc)."""
    sf = _ex("Cotton Buds 50pcs", lang="en")
    assert sf.pricing_basis == "count"
    assert sf.count == 50


# --- promo markers -----------------------------------------------------------


@pytest.mark.parametrize(
    "name, lang",
    [
        ("Shampoo 300ml SALE", "en"),
        ("Champu 300ml en OFERTA", "es"),
        ("洗髪剤 300ml 特売", "ja"),
        ("샴푸 300ml 할인", "ko"),
        ("Dầu gội 300ml giảm giá", "vi"),
        ("Champu PROMOÇÃO", "pt"),
    ],
)
def test_promo_markers_fire(name, lang):
    sf = _ex(name, lang=lang)
    assert sf.is_promotion is True


def test_promo_no_marker_returns_false():
    sf = _ex("Shampoo 300ml", lang="en")
    assert sf.is_promotion is False


# --- bundle markers ----------------------------------------------------------


def test_bundle_gift_set_marker():
    sf = _ex("Lavender Gift Set", lang="en")
    assert sf.is_bundle is True


def test_japanese_set_alone_is_NOT_bundle():
    """multipack 'セット' is count, not bundle. Only ギフトセット triggers bundle."""
    sf = _ex("おやつ 10セット", lang="ja")
    assert sf.is_bundle is False
    assert sf.is_multipack is True  # pack_patterns extracts セット as count


def test_japanese_gift_set_is_bundle():
    sf = _ex("ギフトセット 化粧水", lang="ja")
    assert sf.is_bundle is True


def test_chinese_gift_box_is_bundle():
    sf = _ex("月餅 禮盒", lang="zh")
    assert sf.is_bundle is True


# --- bool flag consistency ---------------------------------------------------


def test_default_flags_are_false_not_none_when_text_present():
    sf = _ex("Plain Shampoo", lang="en")
    assert sf.is_promotion is False
    assert sf.is_bundle is False
    assert sf.is_multipack is False


def test_unknown_language_still_extracts_mass_and_promo_via_any_bucket():
    """When lang is None, language-tagged promo markers are skipped, but the
    pack regex (lang=any) still fires for value+unit, and 'any' promo bucket
    catches '50% off'."""
    sf = _ex("Detergent 500g 50% off", lang=None)
    assert sf.pricing_basis == "mass"
    assert sf.amount_value == pytest.approx(0.5)
    assert sf.is_promotion is True


# --- appliance/drinkware capacity-spec suppression (BUG3/BUG4 cue extension) --


@pytest.mark.parametrize(
    "name",
    [
        "EY905 - Dual Easy Fry & Grill Air fryer 8.3L",
        "Classic 2 Rice Cooker 3L",
        "名入れ 部活 スポーツ タンブラー 真空 350ml 全5色",
        "炊飯器 5.5合 3L",
        "サーモス 水筒 真空断熱 ステンレス ボトル 350ml 500ml",
    ],
)
def test_appliance_capacity_litres_not_sellable_volume(name):
    sf = _ex(name, lang="en")
    assert sf.pricing_basis == "item"
    assert sf.standard_unit == "item"
    assert sf.amount_value is None


def test_real_volume_without_appliance_cue_still_extracts():
    sf = _ex("Cooking Oil 3L", lang="en")
    assert sf.pricing_basis == "volume"
    assert sf.amount_value == pytest.approx(3.0)


def test_rice_cooker_descaler_consumable_keeps_volume():
    # Appliance noun present, but the consumable-form neg guard (cleaner/descal)
    # must keep the real by-volume sale quantity.
    sf = _ex("Rice Cooker Descaler Cleaner 500ml", lang="en")
    assert sf.pricing_basis == "volume"
    assert sf.amount_value == pytest.approx(0.5)


# --- single-unit mass/volume range -> lower bound (spec rule) ----------------


@pytest.mark.parametrize(
    "name,lower",
    [
        ('Pechay Baguio "Wombok" (600-700g)', 0.6),
        ("Green Ice Lettuce (350-400g) by Mayani", 0.35),
        ('Singkamas "Turnips" (300-400g)', 0.3),
        ("Frozen Chicken Thigh with Bone (550-650g)", 0.55),
        ("Frozen [Choice] Ribeye Tomahawk End Cut (1.1-1.2kg)", 1.1),
        ("Beef 1.5-2kg", 1.5),
    ],
)
def test_single_unit_mass_range_uses_lower_bound(name, lower):
    # Range where only the upper bound carries the unit ("600-700g"): the spec
    # mandates the LOWER bound. The both-sided form ("800g-1Kg") already works
    # because value_unit matches the leftmost (lower) token.
    sf = _ex(name, lang="en")
    assert sf.pricing_basis == "mass"
    assert sf.amount_value == pytest.approx(lower)


def test_both_sided_mass_range_still_lower_bound():
    sf = _ex("Rice 800g-1Kg", lang="en")
    assert sf.pricing_basis == "mass"
    assert sf.amount_value == pytest.approx(0.8)


def test_sku_dash_not_treated_as_range():
    # A hyphenated SKU with no trailing mass/volume unit must stay item.
    sf = _ex("Nj-009-127/128", lang="en")
    assert sf.pricing_basis == "item"
    assert sf.amount_value is None


@pytest.mark.parametrize(
    "name,unchanged",
    [
        # 182 = item no., 500g is the real mass; must NOT collapse to 0.182.
        ("GRANORO DEDICATO LINGUINE N. 182 -  500G", 0.5),
        ("CAMPAGNA LINGUINE #6 -  500G", 0.5),
        # selectable capacity (ratio 2.5): upper-bound match survives unchanged.
        ("HARIO Filter Bottle 3color 300-750ml", 0.75),
    ],
)
def test_wide_ratio_sku_or_capacity_not_collapsed_to_lower(name, unchanged):
    # The range collapse only fires for tight (high/low < 2.5) product-weight
    # ranges; a wide "range" is an SKU-then-weight or selectable-capacity idiom
    # whose pre-existing match must survive unchanged (no collapse to lower).
    sf = _ex(name, lang="en")
    assert sf.amount_value == pytest.approx(unchanged)
