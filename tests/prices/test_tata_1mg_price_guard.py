import json
import sys
from pathlib import Path

import pytest

_PRICES = Path(__file__).resolve().parents[2] / "src" / "prices"
if str(_PRICES) not in sys.path:
    sys.path.insert(0, str(_PRICES))

scrapy = pytest.importorskip("scrapy")
from scrapy.http import HtmlResponse, Request  # noqa: E402

from price_scraping.spiders.tata_1mg import Tata1mgSpider  # noqa: E402


def _response(offer_price):
    data = {
        "@type": "Product",
        "name": "Test Product",
        "sku": "12345",
        "offers": {"price": offer_price, "priceCurrency": "INR"},
    }
    body = (
        "<html><head>"
        f'<script type="application/ld+json">{json.dumps(data)}</script>'
        "</head><body></body></html>"
    )
    url = "https://www.1mg.com/otc/test-product-otc12345"
    return HtmlResponse(
        url=url, body=body.encode(), encoding="utf-8", request=Request(url)
    )


def test_non_numeric_price_is_refused():
    """1mg's JSON-LD sometimes carries disclaimer text ('Inclusive of all
    taxes') in offers.price instead of a number; that must not be emitted."""
    spider = Tata1mgSpider()
    items = list(spider.parse_product(_response("Inclusive of all taxes")))
    assert items == []


def test_numeric_price_is_emitted():
    spider = Tata1mgSpider()
    items = list(spider.parse_product(_response(129.5)))
    assert len(items) == 1
    assert items[0]["price"] == 129.5
