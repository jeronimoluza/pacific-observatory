"""A residual leaf is marked and withheld from the cross-country comparison."""

from __future__ import annotations

import pandas as pd

from prices import publish

TITLES = {
    "01.1.1.3.9": "Other bakery products",
    "01.1.9.9.0": "Other food products n.e.c.",
    "01.1.5.1.9": "Other edible vegetable oils n.e.c.",
    # The reason the rule anchors "other" to the START of the title. Each of
    # these is a named leaf that merely mentions the word, and a substring test
    # would suppress all of them.
    "01.1.2.2.6": "Meat of horses and other equines, fresh, chilled or frozen",
    "01.1.6.5.3": "Cantaloupes and other melons, fresh",
    "01.1.4.8.1": "Eggs of hen and other birds, in shell, fresh",
    "02.1.2.2": "Wine from other sources",
    "01.1.6.1.2": "Bananas, fresh",
}


def test_catch_all_titles_are_residual():
    r = publish._residual_leaves(TITLES)
    assert r == {"01.1.1.3.9", "01.1.9.9.0", "01.1.5.1.9"}


def test_a_named_leaf_that_merely_says_other_is_not_residual():
    r = publish._residual_leaves(TITLES)
    for code in ("01.1.2.2.6", "01.1.6.5.3", "01.1.4.8.1", "02.1.2.2", "01.1.6.1.2"):
        assert code not in r, TITLES[code]


def test_nec_is_matched_wherever_it_sits_in_the_title():
    assert publish._residual_leaves(
        {"x": "Other sugar confectionery and desserts n.e.c. (not containing cocoa)"}
    ) == {"x"}


def _current(codes):
    return pd.DataFrame(
        {
            "coicop_code": codes,
            "country": ["fiji", "tonga"] * (len(codes) // 2),
            "standard_unit": ["kg"] * len(codes),
            "median_usd": [2.0, 3.0] * (len(codes) // 2),
            "n_obs": [10] * len(codes),
            "last_seen": pd.to_datetime(["2026-09-01"] * len(codes)),
        }
    )


def test_a_residual_leaf_gets_no_region_median(monkeypatch):
    """Its per-country cells survive; only the cross-country figure is withheld."""
    monkeypatch.setattr(publish, "_load_coicop_titles", lambda: TITLES)
    monkeypatch.setattr(publish, "_load_country_names", lambda: {})
    monkeypatch.setattr(publish, "_load_regions", lambda: ({}, []))

    current = _current(["01.1.1.3.9", "01.1.1.3.9", "01.1.6.1.2", "01.1.6.1.2"])
    payload = publish._payload(current, current.assign(month=current["last_seen"]))

    assert payload["residual_leaves"] == ["01.1.1.3.9"]
    assert publish._cell_key("01.1.1.3.9", "kg") not in payload["region_medians"]
    assert publish._cell_key("01.1.6.1.2", "kg") in payload["region_medians"]
    # The rows themselves are still shipped, so coverage stays visible.
    assert sum(r["coicop_code"] == "01.1.1.3.9" for r in payload["current"]) == 2


def test_the_leaf_count_kpi_excludes_residual_leaves(monkeypatch):
    monkeypatch.setattr(publish, "_load_coicop_titles", lambda: TITLES)
    monkeypatch.setattr(publish, "_load_country_names", lambda: {})
    monkeypatch.setattr(publish, "_load_regions", lambda: ({}, []))

    current = _current(["01.1.1.3.9", "01.1.9.9.0", "01.1.6.1.2", "01.1.6.1.2"])
    payload = publish._payload(current, current.assign(month=current["last_seen"]))

    assert payload["kpi"]["coicop_leaves"] == 1
