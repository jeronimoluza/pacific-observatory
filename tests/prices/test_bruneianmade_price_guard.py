import sys
from pathlib import Path

import pytest

_PRICES = Path(__file__).resolve().parents[2] / "src" / "prices"
if str(_PRICES) not in sys.path:
    sys.path.insert(0, str(_PRICES))

scrapy = pytest.importorskip("scrapy")
from scrapy.http import HtmlResponse, Request  # noqa: E402

from price_scraping.spiders.bruneianmade import BruneianmadeSpider  # noqa: E402


def _listing(price_html):
    body = f"""
    <html><body>
      <li class="product type-product">
        <h2 class="woocommerce-loop-product__title">Test Product</h2>
        <a class="woocommerce-LoopProduct-link" href="https://bruneianmade.com/product/test/"></a>
        <span class="price">{price_html}</span>
      </li>
    </body></html>
    """
    url = "https://bruneianmade.com/shop/"
    return HtmlResponse(
        url=url, body=body.encode(), encoding="utf-8", request=Request(url)
    )


def test_variable_price_range_is_refused():
    """A WooCommerce variable product renders two bdi price nodes
    ('$25.00' .. '$60.00'); joining their text concatenates into an
    unparseable blob ('25.0060.00') and must not be emitted."""
    price_html = (
        '<span class="woocommerce-Price-amount amount">'
        '<bdi>25.00<span class="woocommerce-Price-currencySymbol">BND</span></bdi></span>'
        " &ndash; "
        '<span class="woocommerce-Price-amount amount">'
        '<bdi>60.00<span class="woocommerce-Price-currencySymbol">BND</span></bdi></span>'
    )
    spider = BruneianmadeSpider()
    items = list(spider.parse_listing(_listing(price_html)))
    assert items == []


def test_single_price_is_parsed():
    price_html = (
        '<span class="woocommerce-Price-amount amount">'
        '<bdi>3.70<span class="woocommerce-Price-currencySymbol">BND</span></bdi></span>'
    )
    spider = BruneianmadeSpider()
    items = list(spider.parse_listing(_listing(price_html)))
    assert len(items) == 1
    assert items[0]["price"] == "3.70"
