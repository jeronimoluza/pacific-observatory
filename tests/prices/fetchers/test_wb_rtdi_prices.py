"""The WB RTDI lookup table is hand-written, so it is pinned here.

The failure mode this guards is silent: a `coicop_code` that is not a deepest
leaf does not raise anywhere. `coicop_codes.is_narrow` simply returns False, the
row falls through to the classifier, and a curated feed quietly becomes an
uncurated one. That is the same defect as the 36 shipped configs carrying
`08.1.0` and `08.3.0`, neither of which exists in the taxonomy.
"""

import pytest

from prices.fetchers._shared.eap.wb_rtdi_prices import _ITEMS, _STUDIES


@pytest.fixture(scope="module")
def leaves():
    taxonomy = pytest.importorskip("prices.enrich.coicop_taxonomy")
    try:
        valid, _ = taxonomy.load_taxonomy_index()
    except FileNotFoundError:
        pytest.skip("coicop_categories.xlsx not available")
    return valid


@pytest.mark.parametrize("key", sorted(_ITEMS))
def test_every_curated_code_is_a_deepest_leaf(key, leaves):
    from prices.enrich import coicop_codes

    code = _ITEMS[key][0]
    parsed = coicop_codes.parse_codes(code)
    assert coicop_codes.is_narrow(parsed, leaves), (
        f"{key} -> {code} is not a deepest leaf; it would fall through to the "
        "classifier instead of short-circuiting to narrow_source"
    )


def test_every_item_belongs_to_a_declared_study():
    assert {iso for iso, _ in _ITEMS} <= set(_STUDIES)


def test_every_study_contributes_items():
    covered = {iso for iso, _ in _ITEMS}
    assert covered == set(_STUDIES), f"study with no items: {set(_STUDIES) - covered}"


def test_the_index_ticker_is_not_mapped():
    """food_price_index is an INDEX (Jan 2018 = 1), not a price level.

    It is the one ticker present in all 37 RTFP studies, so it is the easiest to
    add by accident and the most damaging: indices and levels cannot share a
    cell."""
    assert not [k for k in _ITEMS if k[1] == "food_price_index"]


def test_no_non_consumption_tickers_are_mapped():
    banned = {"exchange_rate_unofficial", "fuel_diesel", "fuel_petrol_gasoline",
              "wage_qualified_labour", "milling_cost_wheat"}
    assert not {t for _, t in _ITEMS} & banned


def test_all_codes_are_food_or_beverage():
    """The build keeps only divisions 01 and 02, so anything else is dead
    weight that would be filtered out downstream anyway."""
    bad = {k: v[0] for k, v in _ITEMS.items() if not v[0].startswith(("01.", "02."))}
    assert not bad, bad


@pytest.mark.parametrize("key", sorted(_ITEMS))
def test_units_are_the_studies_own_vocabulary(key):
    """Units are passed through raw and normalised downstream by
    `parse_declared_unit`, which folds case. "Unit" is knowingly included even
    though it does NOT resolve -- see the module docstring."""
    assert _ITEMS[key][1] in {"KG", "L", "Unit"}


def test_same_ticker_can_carry_different_leaves_across_countries():
    """The reason the table keys on (iso3, ticker) rather than ticker alone.

    If this ever collapses to one leaf per ticker, the mapping has been
    flattened and Myanmar's palm oil is being priced as Indonesian vegetable
    oil."""
    oils = {iso: code for (iso, t), (code, _, _) in _ITEMS.items() if t == "oil"}
    assert len(set(oils.values())) > 1, oils
