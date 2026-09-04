import sys
from pathlib import Path

import pytest

_PRICES = Path(__file__).resolve().parents[2] / "src" / "prices"
if str(_PRICES) not in sys.path:
    sys.path.insert(0, str(_PRICES))

pytest.importorskip("scrapy")

from price_scraping.spiders._watsons_base import WatsonsBaseSpider  # noqa: E402


class _TestWatsonsPhSpider(WatsonsBaseSpider):
    name = "watsons_ph_guard_test"
    allowed_domains = ["watsons.com.ph"]
    currency = "PHP"
    language = "en"
    SITEMAP_INDEX = "https://www.watsons.com.ph/sitemap.xml"
    SITEMAP_FILTER = "sitemap_prd_en"
    PRICE_SYMBOL = "₱"


def _jsonld_html(price_currency: str) -> str:
    return f"""
    <html><head>
    <script type="application/ld+json">
    {{"@context":"https://schema.org","@type":"Product","name":"Sunblock 100ml",
     "sku":"BP_12345","offers":{{"@type":"Offer","price":"269","priceCurrency":"{price_currency}"}}}}
    </script>
    </head></html>
    """


def test_archived_page_currency_is_overridden_by_the_spider():
    """watsons_ph shipped 446 archived rows (2018-2020) tagged TWD because a
    stale/cross-region snapshot's JSON-LD said so, at ~2x the unit value of
    its correctly-tagged PHP rows. The site has only ever charged PHP."""
    rows = list(
        _TestWatsonsPhSpider.parse_html(
            _jsonld_html("TWD"), "https://www.watsons.com.ph/p/bp_12345"
        )
    )
    assert len(rows) == 1
    assert rows[0]["currency"] == "PHP"


def test_correct_page_currency_is_unaffected():
    rows = list(
        _TestWatsonsPhSpider.parse_html(
            _jsonld_html("PHP"), "https://www.watsons.com.ph/p/bp_12345"
        )
    )
    assert len(rows) == 1
    assert rows[0]["currency"] == "PHP"
