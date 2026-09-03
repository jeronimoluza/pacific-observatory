"""玉 counts round fruit the way 顆 does; without it a box prices as one fruit."""

import pytest

from prices.enrich.extract import extract


def _x(name: str):
    r = extract(name, None, None, "ja")
    return r.pricing_basis, r.count, r.standard_unit


@pytest.mark.unit
def test_plain_tama_count_parses():
    assert _x("みかん 10玉") == ("count", 10, "unit")


@pytest.mark.unit
def test_single_tama_stays_item():
    # count == 1 is not a pack; the count rungs require > 1
    basis, count, _ = _x("キャベツ 1玉")
    assert basis == "item"
    assert count == 1


@pytest.mark.unit
def test_mass_still_outranks_the_counter():
    # a name carrying both a 玉 count and a mass resolves on mass, as before
    basis, _, unit = _x("ゼスプリ サンゴールドキウイ 20玉 約2kg")
    assert (basis, unit) == ("mass", "kg")


@pytest.mark.unit
def test_onion_is_not_a_count():
    # 玉ねぎ is an onion, not "N 玉" -- it takes no digit immediately before 玉
    basis, _, unit = _x("新玉ねぎ 5kg")
    assert (basis, unit) == ("mass", "kg")


@pytest.mark.unit
def test_ke_counter_unaffected():
    assert _x("パイナップル 約8-12顆") == ("count", 12, "unit")


@pytest.mark.unit
@pytest.mark.parametrize(
    "name,expected",
    [
        # hyphen range, counter only on the high side -> midpoint of 36..40
        ("グレープフルーツお徳用36-40玉フル箱", 38),
        # wave dash
        ("ゼスプリ サンゴールドキウイ 22〜27玉", 24),
        ("ドラゴンフルーツ 4〜8玉", 6),
        # counter repeated on both sides, full-width tilde; 2..3 floors to 2
        ("みやざき 完熟マンゴー 2玉 ～ 3玉", 2),
    ],
)
def test_range_resolves_to_interval_midpoint(name, expected):
    basis, count, unit = _x(name)
    assert (basis, unit) == ("count", "unit")
    assert count == expected


@pytest.mark.unit
def test_non_ascending_pair_is_not_a_range():
    # "5-3玉" is not an interval; fall back to the plain reading rather than
    # invent a midpoint from a reversed pair
    assert _x("みかん 5-3玉")[1] == 3
