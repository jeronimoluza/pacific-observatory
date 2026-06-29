"""Permanent branch-equivalence regression net for the enumerate-then-decide refactor.

Each row's expected 9-field ``StructuralFields`` tuple was captured ONCE from the
frozen pre-refactor oracle (``extract_legacy.extract``) during Phase 1.5 Wave 3 and
baked here as parametrize literals. The test asserts the NEW
``prices.enrich.extract.extract`` reproduces those values field-for-field. It does
NOT import ``extract_legacy`` at runtime, so it survives that throwaway's deletion.

The rows exercise every precedence rung and suppression path: apos outer-multiplier,
pharma per-unit, mass/volume pack units, CJK outer multipliers, appliance-capacity
suppression and the consumable negative-guard rescue, marketing-limit / purchase-limit
clauses, total-breakdown and servings vetoes, Pack-of-N promotion, count-only markers,
multipacks, bundle markers, promo markers, range lower-bound collapse, spelled-out
litre, and the plain-item fallback.
"""

from __future__ import annotations

import pytest

from prices.enrich.extract import extract

_FIELDS = (
    "pricing_basis",
    "amount_value",
    "standard_unit",
    "count",
    "multiplier",
    "is_promotion",
    "is_bundle",
    "is_multipack",
    "promo_reason",
)

# (id, name, lang, country, expected 9-field StructuralFields tuple)
# Expected tuples captured verbatim from extract_legacy.extract (the frozen
# pre-refactor byte-copy) — see _FIELDS for the field order.
ROWS = [
    (
        "apos",
        "Centrum 20'S X 2g",
        "en",
        "",
        ("mass", 0.002, "kg", 1, 20, False, False, True, None),
    ),
    (
        "pharma",
        "Paracetamol 100mg (per Tablet)",
        "en",
        "",
        ("count", None, "unit", 1, 1, False, False, False, None),
    ),
    (
        "pack_unit_volume_ml",
        "Coca-Cola 500ml",
        "en",
        "",
        ("volume", 0.5, "lt", 1, 1, False, False, False, None),
    ),
    (
        "pack_unit_mass_kg",
        "Sugar 2KG",
        "en",
        "",
        ("mass", 2.0, "kg", 1, 1, False, False, False, None),
    ),
    (
        "pack_unit_volume_l",
        "Pepsi 1L",
        "en",
        "",
        ("volume", 1.0, "lt", 1, 1, False, False, False, None),
    ),
    (
        "pack_unit_small_mass",
        "Wardah Lip Balm 7G",
        "en",
        "",
        ("mass", 0.007, "kg", 1, 1, False, False, False, None),
    ),
    (
        "cjk_outer_mult_vol",
        "三ツ矢サイダー 500ml×24本",
        "ja",
        "",
        ("volume", 0.5, "lt", 1, 24, False, False, True, None),
    ),
    (
        "cjk_outer_mult_mass",
        "せんべい 120g×28袋",
        "ja",
        "",
        ("mass", 0.12, "kg", 1, 28, False, False, True, None),
    ),
    (
        "appliance_suppress_cooker",
        "Classic 2 Rice Cooker 3L",
        "en",
        "",
        ("item", None, "item", 1, 1, False, False, False, None),
    ),
    (
        "appliance_suppress_airfryer",
        "EY905 - Dual Easy Fry & Grill Air fryer 8.3L",
        "en",
        "",
        ("item", None, "item", 1, 1, False, False, False, None),
    ),
    (
        "neg_guard_consumable",
        "Rice Cooker Descaler Cleaner 500ml",
        "en",
        "",
        ("volume", 0.5, "lt", 1, 1, False, False, False, None),
    ),
    (
        "total_breakdown",
        "コシヒカリ 白米 10kg（5kg×2袋）令和7年産",
        "ja",
        "",
        ("mass", 10.0, "kg", 1, 1, False, False, False, None),
    ),
    (
        "servings",
        "即席スープ [50杯分] 200g×1袋 お徳用",
        "ja",
        "",
        ("mass", 0.2, "kg", 1, 1, True, False, False, None),
    ),
    (
        "limit_clause",
        "緑茶 500ml お一人様5本限り",
        "ja",
        "",
        ("volume", 0.5, "lt", 1, 1, False, False, False, None),
    ),
    (
        "marketing_limit_rescan",
        "ウェットティッシュ 953枚突破 4枚セット",
        "ja",
        "",
        ("item", None, "item", 1, 1, False, False, False, None),
    ),
    (
        "pack_of_n_measure",
        "NIVEA Spray 150ml Pack Of 2",
        "en",
        "",
        ("volume", 0.15, "lt", 1, 2, False, False, True, None),
    ),
    (
        "pack_of_n_no_measure",
        "Pencils Pack of 12",
        "en",
        "",
        ("count", None, "unit", 12, 1, False, False, True, None),
    ),
    (
        "pack_of_glued_measure",
        "Value Pack of 500g Rice",
        "en",
        "",
        ("mass", 0.5, "kg", 1, 1, False, False, False, None),
    ),
    (
        "count_only_pcs",
        "Pencils 12 PCS",
        "en",
        "",
        ("count", None, "unit", 12, 1, False, False, True, None),
    ),
    (
        "count_only_glued",
        "Cotton Buds 50pcs",
        "en",
        "",
        ("count", None, "unit", 50, 1, False, False, True, None),
    ),
    (
        "multipack_mass",
        "Plain Crackers 4x20g",
        "en",
        "",
        ("mass", 0.02, "kg", 1, 4, False, False, True, None),
    ),
    (
        "multipack_volume",
        "Ganzberg Beer 24x330ml",
        "en",
        "",
        ("volume", 0.33, "lt", 1, 24, False, False, True, None),
    ),
    (
        "plain_item",
        "Generic Brand Raincoat XL",
        "en",
        "",
        ("item", None, "item", 1, 1, False, False, False, None),
    ),
    (
        "bare_count_total_measure",
        "Thin Sausages 24 Pack 1.8kg",
        "en",
        "",
        ("mass", 1.8, "kg", 1, 1, False, False, False, None),
    ),
    (
        "vietnamese_counter_mass",
        "Vitamin Tablets 30 viên 500mg",
        None,
        "",
        ("mass", 0.0005, "kg", 1, 1, False, False, False, None),
    ),
    (
        "vietnamese_count",
        "Khẩu trang y tế Hộp 50 Miếng",
        None,
        "",
        ("count", None, "unit", 50, 1, False, False, True, None),
    ),
    (
        "bundle_gift_set",
        "Lavender Gift Set",
        "en",
        "",
        ("item", None, "item", 1, 1, False, True, False, None),
    ),
    (
        "bundle_ja_gift",
        "ギフトセット 化粧水",
        "ja",
        "",
        ("item", None, "item", 1, 1, False, True, False, None),
    ),
    (
        "bundle_zh_box",
        "月餅 禮盒",
        "zh",
        "",
        ("item", None, "item", 1, 1, False, True, False, None),
    ),
    (
        "promo_mass",
        "Detergent 500g 50% off",
        None,
        "",
        ("mass", 0.5, "kg", 1, 1, True, False, False, None),
    ),
    (
        "range_lower_bound",
        'Pechay Baguio "Wombok" (600-700g)',
        "en",
        "",
        ("mass", 0.6, "kg", 1, 1, False, False, False, None),
    ),
    (
        "spelled_litre",
        "DIAMOND MILK UHT LOW FAT 1 LITER",
        "en",
        "",
        ("volume", 1.0, "lt", 1, 1, False, False, False, None),
    ),
    (
        "cm_not_pack",
        "Chef Knife 16.5cm",
        "en",
        "",
        ("item", None, "item", 1, 1, False, False, False, None),
    ),
    ("empty", "", "en", "", (None, None, None, None, None, None, None, None, None)),
]


@pytest.mark.unit
@pytest.mark.parametrize(
    "name, lang, country, expected",
    [(name, lang, country, expected) for _id, name, lang, country, expected in ROWS],
    ids=[r[0] for r in ROWS],
)
def test_extract_matches_frozen_oracle(name, lang, country, expected):
    sf = extract(name, None, country, lang)
    got = tuple(getattr(sf, f) for f in _FIELDS)
    for field, want, have in zip(_FIELDS, expected, got):
        if field == "amount_value" and want is not None:
            assert have == pytest.approx(
                want, rel=1e-9
            ), f"{field}: {have!r} != {want!r}"
        else:
            assert have == want, f"{field}: {have!r} != {want!r}"
