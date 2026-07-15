"""Unit tests for the NS (compact count-suffix) grammar shape.

`EN_APOS_S` (`\\d+'s`) and `EN_SACHETS` (bare `\\d+s`) are eligible to promote
into a co-occurring measure's count/multiplier (`_LOOSE_PROMOTE_IDS` in
extract_decide.py is empty). The bare-adjacency shape (no `X`/`×` operator —
that form is a distinct earlier candidate, "apos", handled by rung 1) IS the
mass/volume->count convention this promotion exists for
("Mission Quinoa Wraps 8s 360g" -> count=8); the no-measure brand-token shape
("333'S OLIVES") never reaches promotion because it requires a co-occurring
pack_unit measure.

A 182-row corpus holdout
(`data/prices/_enrich/validation_runs/structural_gold_agreed_20260715.parquet`,
bucket startswith "NS") found that unit=mg was wrongly blocking promotion
(100/100 mg holdout rows want the trailing count captured — see
`test_mg_dose_count_suffix_is_promoted`) and that a bare count-suffix
PRECEDING an implausibly large measure ("100s and 1000s ... 85g") is a
size-descriptor, not a pack quantity — but a general count-before-measure
suppression directly conflicts with the canonical NS gold slice the
scoreboard gate is built from (e.g. "Laughing Cow Sliced Cheddar Cheese 10s
200g", gold count=10, is the same shape as "Mini Babybel Tasty Cheddar
Cheese 5s 100g" from the corpus holdout, which wants count=1 — no textual
signal separates them). `_COUNT_BEFORE_MEASURE_CAP=30` in extract_decide.py
is a narrow, gate-safe compromise: it only rejects a count-before-measure
bare suffix ABOVE the highest such value in the canonical gold slice.
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


def test_mg_dose_count_suffix_is_promoted():
    """Defect #1 fix: a milligram measure beside a trailing piece count
    ("160mg Softgel 100s") IS the per-piece drug DOSE plus the genuine pack
    quantity — the corpus holdout shows 100/100 mg rows want the count
    captured (0 counterexamples), so unit=mg is no longer specially blocked."""
    sf = _ex("GNC Herbal Plus Saw Palmetto Extract 160mg Softgel 100s")
    assert sf.pricing_basis == "mass"
    assert sf.count == 100
    assert sf.multiplier == 1


@pytest.mark.parametrize(
    "name, expected_av",
    [
        ("Waitrose 100s and 1000s Multi Colorured Sugar Decoretion 85g.", 0.085),
        ("Biodance Collagen Gel Toner Pads 60s 140g", 0.14),
        ("Nagar Pyan Finest Myanmar Tea 50's 100g", 0.1),
    ],
)
def test_count_before_measure_above_gold_max_stays_unpromoted(name, expected_av):
    """Defect #2 partial fix: a bare count-suffix PRECEDING the measure, above
    30 (the highest such value in the canonical NS gold slice), is an
    implausible per-piece pack size (e.g. "100s and 1000s" decorative sugar
    sprinkles) — real over-fire examples from the 20260715 corpus holdout."""
    sf = _ex(name)
    assert sf.pricing_basis == "mass"
    assert sf.amount_value == pytest.approx(expected_av, rel=1e-6)
    assert sf.count == 1
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
