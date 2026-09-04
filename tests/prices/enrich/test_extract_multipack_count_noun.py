"""Multipack shape `<N count-noun> x <measure>` ("25 sachets x 20g").

The measure-first spelling ("20g x 25") and the bare operator spelling
("25 x 20g") both routed N into `multiplier`. The count-noun spelling did not:
the promoted count landed in the UV-inert `count` on mass basis, so a 25-sachet
box priced as one 20g sachet and the unit value came out 25x too high.
"""

from __future__ import annotations

import pytest

from prices.enrich.extract import extract

pytestmark = pytest.mark.unit


def _ex(name, lang="en"):
    return extract(name, None, "", lang)


@pytest.mark.parametrize(
    "name, expected_av, expected_mult",
    [
        ("Coffee Mix 25 sachets x 20g", 0.02, 25),
        ("Lipton Yellow Label Tea 100 bags x 2g", 0.002, 100),
        ("Nescafe 3in1 20 sticks x 2g", 0.002, 20),
        ("Milo Cereal Bars 6 pcs x 25g", 0.025, 6),
        ("Kirkland Cheese 10 slices * 200g", 0.2, 10),
    ],
)
def test_count_noun_before_operator_multiplies_the_measure(
    name, expected_av, expected_mult
):
    sf = _ex(name)
    assert sf.pricing_basis == "mass"
    assert sf.amount_value == pytest.approx(expected_av, rel=1e-6)
    assert sf.count == 1
    assert sf.multiplier == expected_mult
    assert sf.is_multipack is True


def test_the_measure_first_spelling_is_unchanged():
    """The mirror shape already worked; the new trailing-operator test must not
    disturb it."""
    sf = _ex("Twisties Snacks 250g x 5pcs")
    assert sf.amount_value == pytest.approx(0.25)
    assert sf.count == 1
    assert sf.multiplier == 5


def test_a_count_noun_with_no_operator_stays_inert():
    """Convention A: without an explicit multiply operator the piece count is
    captured but never scales a stated pack total ("10s 200g" is 200g total)."""
    sf = _ex("Laughing Cow Sliced Cheddar Cheese 10s 200g")
    assert sf.amount_value == pytest.approx(0.2)
    assert sf.count == 10
    assert sf.multiplier == 1


def test_a_trailing_x_that_is_not_a_multiplication_is_rejected():
    """The operator only counts when a number follows it — a size letter or a
    stray token after the count noun must not fabricate a multiplier."""
    sf = _ex("Cotton Gloves 4 pcs XL Grey 250g")
    assert sf.multiplier == 1
