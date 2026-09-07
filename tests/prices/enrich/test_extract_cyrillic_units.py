"""Unit tests for the Cyrillic mass/volume measure surfaces (M/P-class vocab).

`units.yaml` carried only latin (and a hand-written zh) unit spelling, so every
ru/uk/bg/kk/ky/tk/mk/be/mn product name stated its pack size in a script the
`VALUE_UNIT` alternation could not read. Those rows fell all the way through to
`pricing_basis="item"` and were priced per PIECE rather than per kg / per litre
-- measured at 19-59% of the rows in those countries on a 288k-row corpus
sample (5,088 rows / 1.77% of the sample flipped once the surfaces were added,
and not one non-Cyrillic row changed).

The additions are `гр`/`г` -> g, `кг` -> kg, `мг` -> mg, `мл` -> ml, `л` -> l,
plus the Cyrillic multiply operator `х`/`Х` in the P-class separator class.
"""

from __future__ import annotations

import pytest

from prices.enrich.extract import extract


def _ex(name, lang=None, country=""):
    return extract(name, None, country, lang)


@pytest.mark.parametrize(
    "name, expected_basis, expected_av, expected_su",
    [
        # bare `г` / `гр` (gram) -- Bulgarian, Mongolian, Macedonian
        ("Моцарела ARLA слайс 150г", "mass", 0.15, "kg"),
        ("Зөгийн бал 250гр - Mild pure bee honey", "mass", 0.25, "kg"),
        ("Wellness кекс со суво грозје 210 г", "mass", 0.21, "kg"),
        # `кг`, with a comma decimal
        ("Макароны Цесна Перья 1,6кг Меш", "mass", 1.6, "kg"),
        # `мл` and bare `л`
        ("Millenia байгалийн эрдэст ус, 500мл", "volume", 0.5, "lt"),
        ("Сок Gracio зеленое яблоко 100% без сахара 1 л", "volume", 1.0, "lt"),
        # `мг` -- a milligram is still a mass reading (the uv_gate, not the
        # regex, is what keeps a pharma dose out of the unit-value denominator).
        ("Парацетамол 500мг №10 шахмал", "mass", 0.0005, "kg"),
        # upper-case surfaces fold through `raw.lower()` in the UNIT_NORM lookup
        ("АКТИВИА БИО ЙОГУРТ 110Г", "mass", 0.11, "kg"),
    ],
)
def test_cyrillic_measure_is_read(name, expected_basis, expected_av, expected_su):
    sf = _ex(name)
    assert sf.pricing_basis == expected_basis
    assert sf.amount_value == pytest.approx(expected_av, rel=1e-9)
    assert sf.standard_unit == expected_su


@pytest.mark.parametrize(
    "name, expected_av, expected_mult",
    [
        # latin `x`/`*` operator with a Cyrillic unit
        ("Пауч за котки LOVETT заешко, агнешко, пуешко  4x100 гр.", 0.100, 4),
        ("Каша Моя овсянушка овсян ассорти 5*40г", 0.040, 5),
        # Cyrillic `х` (U+0445) as the multiply operator
        ("Супа за котки FELIX пиле 6х48 г", 0.048, 6),
        ("Сметана за кафе - Meggle - 10х7,5гр.", 0.0075, 10),
    ],
)
def test_cyrillic_multipack_operator(name, expected_av, expected_mult):
    sf = _ex(name)
    assert sf.pricing_basis == "mass"
    assert sf.amount_value == pytest.approx(expected_av, rel=1e-9)
    assert sf.count == 1
    assert sf.multiplier == expected_mult
    assert sf.is_multipack is True


def test_cyrillic_surfaces_do_not_leak_into_latin_names():
    """The Cyrillic codepoints are disjoint from the latin ones, so a latin
    name must parse exactly as it did before the surfaces were added."""
    sf = _ex("Coca Cola 330ml 24 Pack", lang="en")
    assert (sf.pricing_basis, sf.amount_value, sf.multiplier) == ("volume", 0.33, 24)
    sf = _ex("Cadbury Dairy Milk 200g", lang="en")
    assert (sf.pricing_basis, sf.amount_value, sf.multiplier) == ("mass", 0.2, 1)


def test_cyrillic_unit_letter_needs_a_word_boundary():
    """`г`/`л` are single letters: they must not fire inside a longer Cyrillic
    word, otherwise every `10 голов` / `35 листов` becomes a quantity."""
    sf = _ex("Конструктор 68 голов")
    assert sf.pricing_basis == "item"
    assert sf.amount_value is None
