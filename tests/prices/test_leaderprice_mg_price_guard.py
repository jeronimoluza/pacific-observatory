import sys
from pathlib import Path

import pytest

_PRICES = Path(__file__).resolve().parents[2] / "src" / "prices"
if str(_PRICES) not in sys.path:
    sys.path.insert(0, str(_PRICES))

scrapy = pytest.importorskip("scrapy")
from scrapy.http import HtmlResponse, Request  # noqa: E402

from price_scraping.spiders.leaderprice_mg import (  # noqa: E402
    LeaderpriceMgSpider,
    _parse_price,
)


def _card_html(product_id, title, price_text):
    return (
        f"<img src='x.jpg' title=\"{title}\"><div class='desc'>"
        f"<p class='text2'>trunc</p>"
        f"<p class='text2'><span>{price_text}</span></p></div>"
    ).replace("<img", f"<div id='bordu_{product_id}' class='bordu product'><img", 1)


def _response(cards):
    body = "<html><body>" + "".join(cards) + "</body></html>"
    url = "https://www.leaderprice.mg/Promo"
    return HtmlResponse(
        url=url,
        body=body.encode(),
        encoding="utf-8",
        request=Request(url, meta={"path": "/Promo"}),
    )


def test_masked_price_is_refused():
    """The site occasionally masks the displayed price ('*****'); that text
    must not be forwarded as a price."""
    assert _parse_price("*****") is None
    spider = LeaderpriceMgSpider()
    items = list(spider.parse_page(_response([_card_html(1, "Item", "*****")])))
    assert items == []


def test_normal_price_is_parsed():
    assert _parse_price("39 900,00 Ar") == "39900.00"
    spider = LeaderpriceMgSpider()
    items = list(spider.parse_page(_response([_card_html(1, "Item", "39 900,00 Ar")])))
    assert len(items) == 1
    assert items[0]["price"] == "39900.00"
