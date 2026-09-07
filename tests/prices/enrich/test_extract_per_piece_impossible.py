"""A pack total that implies an impossible per-piece mass is a per-UNIT measure.

Convention A keeps `count` UV-inert on a measured basis, because the stated
mass is normally the pack TOTAL ("Anchor Tasty Slice Cheese 12s 250g" is 250 g
of cheese, not 12 x 250 g). That is the right default and it stays. But the same
word shape also carries the opposite meaning -- "Lipton Yellow Label Tea Bags 2g
100 Bags" is 100 bags of 2 g -- and reading THAT as a total priced a 200 g box
as a single 2 g tea bag, i.e. 100x too expensive per kg.

Nothing in the text separates the two readings; only the magnitude does, and
only at the extreme. The rule added here fires solely where the total reading is
physically impossible: `amount_value / count` below 0.5 g, mass basis, unit not
`mg`, and the measure written BEFORE the count. Measured on a 288,147-row corpus
sample it moves 17 rows, 9 of them classified and uv_gate-adoptable, and every
one was hand-checked as an improvement.
"""

from __future__ import annotations

import pytest

from prices.enrich.extract import extract


def _ex(name, lang="en"):
    return extract(name, None, "", lang)


@pytest.mark.parametrize(
    "name, expected_av, expected_mult",
    [
        # 100 bags x 2 g -- was count=100, multiplier=1, uv = price / 0.002
        ("Lipton Yellow Label Tea Bags 2g 100 Bags", 0.002, 100),
        ("Nescafe coffee sticks 2g 10pcs (557531)", 0.002, 10),
        ("Mentos Toffee Mint 2.7G 19Pcs Handy Pack (KD)", 0.0027, 19),
        ("Isigny Unsalted Butter, 10 g - 60 Pieces", 0.010, 60),
        ("Hang Viet Nam Brand Longevity Tea Size 1.5g box of 20sachet", 0.0015, 20),
        ("Galaxy Fruit & Nut 36gm,Carton of 144pcs", 0.036, 144),
    ],
)
def test_impossible_total_promotes_the_count(name, expected_av, expected_mult):
    sf = _ex(name)
    assert sf.pricing_basis == "mass"
    assert sf.amount_value == pytest.approx(expected_av, rel=1e-9)
    assert sf.count == 1
    assert sf.multiplier == expected_mult
    assert sf.is_multipack is True


@pytest.mark.parametrize(
    "name, expected_av, expected_count",
    [
        # A plausible per-piece mass keeps the default TOTAL reading, whichever
        # order the two figures are written in.
        ("Lipton Yellow Label Tea Bags 20s 40g", 0.04, 20),  # 2.0 g / bag
        ("Anchor Tasty Slice Cheese 12s 250g", 0.25, 12),  # 20.8 g / slice
        ("LEMNOS CHEESE SLICES 250G 12S", 0.25, 12),  # measure first, still a total
        ("Infusion camomille 25 sachets 22,5g", 0.0225, 25),  # 0.9 g / bag
        ("Wrigley's Extra Peppermint Sugar Free Chewing Gum 46 Pieces 64 g", 0.064, 46),
    ],
)
def test_plausible_total_is_left_alone(name, expected_av, expected_count):
    sf = _ex(name)
    assert sf.pricing_basis == "mass"
    assert sf.amount_value == pytest.approx(expected_av, rel=1e-9)
    assert sf.count == expected_count
    assert sf.multiplier == 1


def test_mg_dose_beside_a_pack_count_is_not_promoted():
    """`mg` is excluded: there the figure is a per-piece drug DOSE sitting
    beside the genuine pack quantity, and the NS corpus holdout wants the count
    (100/100 rows, 0 counterexamples). Promoting it would fabricate a
    100 x 160 mg "pack mass" out of a strength label."""
    sf = _ex("Softgel 160mg 100s")
    assert sf.count == 100
    assert sf.multiplier == 1


def test_count_before_measure_is_not_promoted():
    """The mirror word order states a total, so the rule must not fire on it --
    "30 Tablets 8.5g" is the one ambiguous shape in the corpus sample."""
    sf = _ex("Canderel Sweetener 30 Tablets 8.5g")
    assert sf.count == 30
    assert sf.multiplier == 1


def test_loose_bare_suffix_matchers_are_excluded():
    """`\\d+s` / `\\d+'s` are the ids the NS corpus holdout is built on, and it
    settled the opposite convention for this exact shape -- a per-piece drug
    dose written in grams beside a trailing piece count keeps its `count`."""
    sf = _ex("Levipil 1gm Tablet 10'S")
    assert sf.pricing_basis == "mass"
    assert sf.amount_value == pytest.approx(0.001, rel=1e-9)
    assert sf.count == 10
    assert sf.multiplier == 1
