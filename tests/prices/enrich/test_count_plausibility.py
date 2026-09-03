"""An implausible count fabricates a per-piece price; it must fall back to item."""

import pytest

from prices.enrich.extract import extract


def _basis(name: str, lang: str = "en") -> tuple[str, int]:
    r = extract(name, None, None, lang)
    return r.pricing_basis, r.count


@pytest.mark.unit
@pytest.mark.parametrize(
    "name,lang",
    [
        # SKU trailing a pack noun -- was count=806939, uv $0.000006
        ("AVOCADO Ripe Duo Pack 806939", "en"),
        # EAN barcode -- was count=8000570552505
        ("Вино ігристе Martini Prosecco біле 0.75 л 11% (8000570552505M)", "uk"),
        # gram weight read through the noun-trailing pattern
        ("BOLCI ASSORTED CHOCOLATE PRALINES TIN BOX 250", "en"),
    ],
)
def test_implausible_count_falls_back_to_item(name, lang):
    basis, count = _basis(name, lang)
    assert basis == "item"
    assert count == 1


@pytest.mark.unit
@pytest.mark.parametrize(
    "name,expected",
    [
        ("Hass Avocados 5 Pack", 5),
        ("Pack of 6 Eggs", 6),
        # large but real, and written number-first
        ("Sweetener Sticks 300 Pack", 300),
        ("FIVE ROSES CEYLON BLEND TAGLESS TEABAGS 200'S BOX", 200),
        # two-digit noun-trailing stays a count
        ("Yogurt Box 12", 12),
    ],
)
def test_real_counts_still_parse(name, expected):
    basis, count = _basis(name)
    assert basis == "count"
    assert count == expected
