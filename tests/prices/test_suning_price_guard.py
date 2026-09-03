import json
import sys
from pathlib import Path

import pytest

_PRICES = Path(__file__).resolve().parents[2] / "src" / "prices"
if str(_PRICES) not in sys.path:
    sys.path.insert(0, str(_PRICES))

scrapy = pytest.importorskip("scrapy")
from scrapy.http import Request, TextResponse  # noqa: E402

from price_scraping.spiders.suning import SuningSpider  # noqa: E402


def _price_response(net_price):
    payload = {"data": {"price": {"saleInfo": [{"netPrice": net_price}]}}}
    body = f"pcData({json.dumps(payload)});"
    url = "https://pas.suning.com/nspcsale_0_000000000000000001_000000000000000001_0000000000_180_377_3770100_0_0_0_0_Z001___0_0___.html"
    return TextResponse(
        url=url,
        body=body.encode(),
        encoding="utf-8",
        request=Request(
            url,
            meta={
                "product_id": "1",
                "product_name": "Test",
                "category": "food",
                "url": "https://product.suning.com/0000000000/1.html",
            },
        ),
    )


def test_price_range_is_refused():
    """Suning's price microservice sometimes returns a spec-range string
    ('10.20-38.60') instead of a single netPrice; must not be emitted."""
    spider = SuningSpider()
    items = list(spider.parse_price(_price_response("10.20-38.60")))
    assert items == []


def test_numeric_price_is_emitted():
    spider = SuningSpider()
    items = list(spider.parse_price(_price_response("19.90")))
    assert len(items) == 1
    assert items[0]["price"] == "19.90"
