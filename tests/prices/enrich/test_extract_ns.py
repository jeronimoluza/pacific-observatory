"""Unit tests for the NS (compact count-suffix) grammar shape.

`EN_APOS_S` (`\\d+'s`) and `EN_SACHETS` (bare `\\d+s`) used to be excluded from
promoting into a co-occurring measure's count/multiplier (`_LOOSE_PROMOTE_IDS`
in extract_decide.py) — so "Mission Quinoa Wraps 8s 360g" resolved to
count=1 instead of count=8. The bare-adjacency shape (no `X`/`×` operator) is
exactly the mass/volume->count convention the promotion path exists for; the
explicit-multiplier shape ("Centrum 20'S X 2g") is a distinct earlier
candidate ("apos", rung 1) that already wins before this promotion is ever
considered, and the no-measure brand-token shape ("333'S OLIVES") never
reaches promotion because it requires a co-occurring pack_unit measure.
"""

from __future__ import annotations

import pytest

from prices.enrich.extract import extract


def _ex(name, lang="en"):
    return extract(name, None, None, lang)


@pytest.mark.parametrize(
    "name, expected_basis, expected_av, expected_count",
    [
        ("Mission Quinoa Wraps 8s 360g", "mass", 0.36, 8),
        ("RAM SAMI EGGS 30s 1.80kg", "mass", 1.8, 30),
        ("Laughing Cow Sliced Cheddar 10s 200g", "mass", 0.2, 10),
        ("Levipil 1gm Tablet 10'S", "mass", 0.001, 10),
        ("BIZBIZE Cikolax Cocoa Pistachio Sandwich 6S 180GM", "mass", 0.18, 6),
    ],
)
def test_bare_apos_s_and_sachets_promote_to_count(
    name, expected_basis, expected_av, expected_count
):
    sf = _ex(name)
    assert sf.pricing_basis == expected_basis
    assert sf.amount_value == pytest.approx(expected_av, rel=1e-6)
    assert sf.count == expected_count
    assert sf.multiplier == 1


def test_bare_sachets_volume_measure_promotes_to_multiplier():
    # basis=volume routes the promoted noun-count to multiplier, not count
    # (mass/count -> count, volume -> multiplier — same convention as the
    # explicit-operator MEAS_x_N shape).
    sf = _ex("OATSIDE Caramel Macchiato Oat Milk 6S x 240ml")
    assert sf.pricing_basis == "volume"
    assert sf.amount_value == pytest.approx(0.24, rel=1e-6)
    assert sf.count == 1
    assert sf.multiplier == 6


def test_explicit_x_multiplier_form_still_wins_as_multiplier_not_count():
    # "Centrum 20'S X 2g": the explicit X-multiplier apos candidate (rung 1)
    # must still win over the bare-adjacency promotion path (rung 3) — this
    # is the one behavior the precision guard was written to protect.
    sf = _ex("Centrum 20'S X 2g")
    assert sf.pricing_basis == "mass"
    assert sf.amount_value == pytest.approx(0.002, rel=1e-6)
    assert sf.count == 1
    assert sf.multiplier == 20


@pytest.mark.parametrize("name", ["333'S OLIVES", "24Bottles"])
def test_no_measure_bare_suffix_never_reaches_promotion(name):
    # No co-occurring measure means rung 3 (pack_unit) never fires, so the
    # loosened _LOOSE_PROMOTE_IDS cannot promote a brand/marketing suffix
    # into a fabricated mass/volume amount. (The rung-8 extra_count fallback
    # that fires here is pre-existing behavior, unchanged by this fix.)
    sf = _ex(name)
    assert sf.pricing_basis == "count"
    assert sf.amount_value is None


def test_mg_dose_measure_is_not_promoted():
    # A milligram "measure" beside a pack count ("160mg Softgel 100s") is a
    # per-unit drug dose misread as the pack's mass, not a real sale weight —
    # promoting the count would compound one wrong field into two.
    sf = _ex("GNC Herbal Plus Saw Palmetto Extract 160mg Softgel 100s")
    assert sf.count == 1
    assert sf.multiplier == 1


def test_bonus_pack_plus_suffix_is_not_promoted():
    # "18+2s" is a "buy 18 get 2 free" bonus-pack idiom — the suffixed number
    # is a promo bonus count, not the pack's piece count.
    sf = _ex("BREEZE Fresh Lavender Power Laundry Capsules 18+2s 210g")
    assert sf.count == 1
    assert sf.multiplier == 1


def test_promote_count_cap_still_rejects_implausible_counts():
    sf = _ex("Bahlsen Pick Up Minis Chocolate & Milk Crackers 200s 106g")
    assert sf.count == 1
    assert sf.multiplier == 1
