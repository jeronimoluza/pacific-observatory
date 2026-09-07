"""A measure glued to a preceding abbreviation or ellipsis dot is still a measure.

`VALUE_UNIT`'s left guard was `(?<![A-Za-z0-9.])`. The `.` half exists to stop
the match landing INSIDE a decimal -- "1.5kg" must not read as 5 kg -- but as a
blanket "no dot before" it also rejected every size written flush against an
abbreviation or an ellipsis:

    Sara Lee Family Size Pound Cake....16oz   -> item (no quantity at all)
    DOMASKO KUR.STEHNA HORNE CA.6,4KG         -> 4 kg  (decimal truncated)
    Вино J.P.Chenet Merlot кр.сух.0,75л       -> 75 lt (leading 0 eaten)

Narrowing the guard to a dot that FOLLOWS A DIGIT keeps the decimal protection
exactly as strong. The leading-dot value form (".5L") additionally grew a
`(?<![.,])` guard, without which "....16oz" reads as 0.16 oz.

Measured on a 288,147-row corpus sample: 478 rows change, 459 of them from
`item` (no quantity) to a real mass/volume and 15 from a truncated decimal to
the correct one. 308 are classified and uv_gate-adoptable; 307 of those 308 land
on a plausible retail quantity.
"""

from __future__ import annotations

import pytest

from prices.enrich.extract import extract


def _ex(name, lang="en"):
    return extract(name, None, "", lang)


@pytest.mark.parametrize(
    "name, expected_basis, expected_av",
    [
        # ellipsis-separated size (a whole retailer catalogue writes them this way)
        ("Sara Lee Family Size Pound Cake....16oz", "mass", 0.453592),
        ("Sara Lee Pound Cake....10.75oz", "mass", 10.75 * 0.0283495),
        ("Tidal Bay Organic White Wine.....750ml", "volume", 0.75),
        ("Granny Smith Apple (Large).....1lb", "mass", 0.453592),
        # abbreviation dot, with a comma decimal
        ("DOMASKO KUR.STEHNA HORNE CA.6,4KG", "mass", 6.4),
        ("Вино J.P.Chenet Merlot кр.сух.0,75л ст/б", "volume", 0.75),
        ("Turku zirnu makar.SAMMILS bez.glut.250g", "mass", 0.25),
        # comma directly after an abbreviation dot
        ("Sv.visciuko broilerio peteliai be antib.,500g", "mass", 0.5),
    ],
)
def test_measure_after_an_abbreviation_dot_is_read(name, expected_basis, expected_av):
    sf = _ex(name)
    assert sf.pricing_basis == expected_basis
    assert sf.amount_value == pytest.approx(expected_av, rel=1e-9)


@pytest.mark.parametrize(
    "name, expected_av",
    [
        # the decimal guard is the point of the `.` half and must still hold:
        # neither of these may read as 5 kg / 5 lt.
        ("Widget 1.5kg", 1.5),
        ("Cadbury Dairy Milk 1.5kg Bar", 1.5),
        ("Juice 2.5l Bottle", 2.5),
    ],
)
def test_a_decimal_is_still_never_split(name, expected_av):
    sf = _ex(name)
    assert sf.amount_value == pytest.approx(expected_av, rel=1e-9)


def test_leading_dot_decimal_still_parses_on_its_own():
    sf = _ex("Bottle .5L Water")
    assert sf.pricing_basis == "volume"
    assert sf.amount_value == pytest.approx(0.5, rel=1e-9)
