"""The currency a Common Crawl row is stamped with when the manifest is silent.

Regression: `waltermart` (a Philippine supermarket whose spider hardcodes
`currency = "PHP"`) shipped 23,741 archived rows tagged USD, because its
manifest declares no `currency:` and the archived Freshop pages' own
`priceCurrency` said USD. `concatenate.py`'s modal back-fill only fills blank
cells, so a populated-but-wrong currency survived into the build and was
divided by an FX rate of 1.0.
"""

from __future__ import annotations

import pytest

from prices.cc_config import declared_currency_for

pytestmark = pytest.mark.unit


def test_waltermart_resolves_to_php():
    assert declared_currency_for("waltermart") == "PHP"


def test_manifest_currency_wins_over_the_spider_attribute(monkeypatch):
    monkeypatch.setattr(
        "prices.cc_config.all_cc_configs",
        lambda: {"waltermart": {"prefix": "x/", "path_re": "", "currency": "sgd"}},
    )
    declared_currency_for.cache_clear()
    try:
        assert declared_currency_for("waltermart") == "SGD"
    finally:
        declared_currency_for.cache_clear()


def test_no_fallback_for_a_spider_with_a_parse_html_hook():
    """A `parse_html` hook is the source's own per-row currency logic.

    Aggregator/platform spiders emit rows in several currencies from one
    archived page, so a class-level `currency` must not be stamped over them.
    """
    assert declared_currency_for("livingcost") == ""


def test_unknown_spider_is_empty():
    assert declared_currency_for("no_such_spider_anywhere") == ""
