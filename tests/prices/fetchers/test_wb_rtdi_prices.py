"""The WB RTDI lookup table is hand-curated, so it is pinned here.

The failure mode this guards is silent: a `coicop_code` that is not a deepest
leaf does not raise anywhere. `coicop_codes.is_narrow` simply returns False, the
row falls through to the classifier, and a curated feed quietly becomes an
uncurated one. That is the same defect as the 36 shipped configs carrying
`08.1.0` and `08.3.0`, neither of which exists in the taxonomy.

The second failure mode is double counting. A country that carries both `rice`
and `rice_fao` has one commodity from two sources, often on different unit bases
-- twelve such pairs price the national series per kg and the FAO twin per
100 kg. Emitting both would post every one of those observations twice, a factor
of 100 apart. `test_no_fao_twin_*` pins the precedence rule that prevents it.
"""

from pathlib import Path

import pytest
import yaml

from prices.fetchers._shared import wb_rtdi_prices as m

_ITEMS, _COUNTRIES = m._ITEMS, m._COUNTRIES

CONFIGS = sorted(
    Path(__file__)
    .resolve()
    .parents[3]
    .glob("src/prices/configs/*/*/*/wb_rtdi_prices.yaml")
)


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


@pytest.mark.parametrize("key", sorted(_ITEMS))
def test_leaf_depth_matches_its_division(key):
    """Division 01 leaves carry five dotted levels; every other division four.

    This holds for all 538 leaves in the taxonomy, so a code of the wrong depth
    is by construction not a leaf -- and would fail silently."""
    code = _ITEMS[key][0]
    want = 5 if code.startswith("01.") else 4
    assert len(code.split(".")) == want, f"{key} -> {code}"


def test_every_item_belongs_to_a_declared_country():
    assert {iso for iso, _ in _ITEMS} <= set(_COUNTRIES)


def test_every_country_contributes_items():
    covered = {iso for iso, _ in _ITEMS}
    assert covered == set(
        _COUNTRIES
    ), f"country with no items: {set(_COUNTRIES) - covered}"


def test_the_index_ticker_is_not_mapped():
    """food_price_index is an INDEX (Jan 2018 = 1), not a price level.

    It is the one ticker present in all 40 RTFP studies, so it is the easiest to
    add by accident and the most damaging: indices and levels cannot share a
    cell."""
    assert not [k for k in _ITEMS if k[1] == "food_price_index"]


def test_no_non_consumption_tickers_are_mapped():
    """Exchange rates, wages, milling costs and fuels are not consumption goods
    the food grid can hold; live animals sold by the head are not retail food."""
    bad = [
        k
        for k in _ITEMS
        if k[1].startswith(
            ("exchange_rate", "wage_", "milling_cost", "fuel_", "livestock")
        )
    ]
    assert not bad, bad


def test_no_fao_twin_where_a_national_ticker_exists():
    """The precedence rule: national wins, `_fao` fills only real gaps.

    Both series describe the same commodity in the same markets. Where a country
    carries both, keeping both would double-count -- and since the units often
    differ (KG against 100 kg), the two copies would not even agree on scale."""
    national = {(iso, t) for iso, t in _ITEMS if not t.endswith("_fao")}
    dupes = [
        (iso, t)
        for iso, t in _ITEMS
        if t.endswith("_fao") and (iso, t[: -len("_fao")]) in national
    ]
    assert not dupes, f"FAO twin kept alongside its national sibling: {dupes}"


def test_same_ticker_can_carry_different_leaves_across_countries():
    """The reason the table keys on (iso3, ticker) rather than ticker alone.

    If this ever collapses to one leaf per ticker, the mapping has been
    flattened and Myanmar's palm oil is being priced as Indonesian vegetable
    oil."""
    oils = {iso: code for (iso, t), (code, _, _) in _ITEMS.items() if t == "oil"}
    assert len(set(oils.values())) > 1, oils


def test_full_name_is_recorded_for_every_entry():
    """`full_name` is what makes a curated leaf auditable: `oil` alone cannot be
    checked, `Oil (palm)` can."""
    missing = [k for k, v in _ITEMS.items() if not v[2].strip()]
    assert not missing, missing


# --- the manifests -----------------------------------------------------------


def test_a_config_exists_for_every_country():
    keys = {yaml.safe_load(p.read_text())["source_key"] for p in CONFIGS}
    assert keys == {f"wb_rtdi_{iso}" for iso in _COUNTRIES}


@pytest.mark.parametrize("path", CONFIGS, ids=lambda p: p.parent.name)
def test_every_config_points_at_a_real_entry_point(path):
    """A `function:` that does not exist fails only at collect time, hours into
    a run, and only for that one country."""
    cfg = yaml.safe_load(path.read_text())
    assert cfg["module"] == "_shared.wb_rtdi_prices"
    assert hasattr(m, cfg["function"]), cfg["function"]
    assert cfg["function"] == f"fetch_wb_rtdi_{cfg['source_key'].split('_')[-1]}"


@pytest.mark.parametrize("path", CONFIGS, ids=lambda p: p.parent.name)
def test_every_config_is_gated_into_the_corpus(path):
    """`_classifier_csv_map` reads a fetcher's price_observations.csv only when
    coicop_classification is `classifier` AND scaffolding is `fetcher`. Miss
    either and the rows are collected but never enter the pipeline."""
    cfg = yaml.safe_load(path.read_text())
    assert cfg["scaffolding"] == "fetcher"
    assert cfg["coicop_classification"] == "classifier"
    assert "coicop_codes" not in cfg, (
        "a per-source coicop_codes would override nothing here but signals the "
        "wrong model: this feed is curated per ITEM"
    )
