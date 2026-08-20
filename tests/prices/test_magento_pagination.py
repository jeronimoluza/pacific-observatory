import sys
from pathlib import Path

import pytest

_PRICES = Path(__file__).resolve().parents[2] / "src" / "prices"
if str(_PRICES) not in sys.path:
    sys.path.insert(0, str(_PRICES))

scrapy = pytest.importorskip("scrapy")
from scrapy.http import HtmlResponse, Request  # noqa: E402

from price_scraping.spiders._magento_base import MagentoSSRBaseSpider  # noqa: E402


def _listing_html(slugs):
    blocks = []
    for s in slugs:
        blocks.append(
            f'<a class="product-item-link" href="https://x.test/{s}.html"> {s} </a>'
            f'<span data-price-amount="9.99"></span>'
        )
    return "<html><body>" + "".join(blocks) + "</body></html>"


class _Spider(MagentoSSRBaseSpider):
    name = "t_magento"
    allowed_domains = ["x.test"]
    currency = "JMD"
    language = "en"
    START_URLS = ["https://x.test/cat.html"]
    MAX_PAGES = 50


def _response(spider, url, slugs, page, base, seen=None):
    meta = {"page": page, "base": base}
    if seen is not None:
        meta["seen"] = seen
    return HtmlResponse(
        url=url,
        body=_listing_html(slugs).encode(),
        encoding="utf-8",
        request=Request(url, meta=meta),
    )


def _split(out):
    items = [o for o in out if isinstance(o, dict)]
    reqs = [o for o in out if isinstance(o, Request)]
    return items, reqs


def test_stops_paginating_when_page_repeats_previous_products():
    """A storefront that re-serves the same page forever must not loop to MAX_PAGES."""
    spider = _Spider()
    base = "https://x.test/cat.html"
    slugs = ["alpha", "beta", "gamma"]

    out = list(
        _split(list(spider.parse_listing(_response(spider, base, slugs, 1, base))))[
            0:2
        ][1]
    )
    assert out, "page 1 with products should request page 2"
    nxt = out[0]

    # page 2 serves the identical products -> pagination must stop here
    r2 = _response(
        spider, nxt.url, slugs, nxt.meta["page"], base, seen=nxt.meta.get("seen")
    )
    items2, reqs2 = _split(list(spider.parse_listing(r2)))

    assert reqs2 == [], "repeated page must end pagination, not queue page 3"
    assert items2 == [], "repeated products must not be re-emitted"


def test_keeps_paginating_while_products_are_new():
    spider = _Spider()
    base = "https://x.test/cat.html"

    items1, reqs1 = _split(
        list(spider.parse_listing(_response(spider, base, ["a", "b"], 1, base)))
    )
    assert len(items1) == 2
    assert len(reqs1) == 1

    nxt = reqs1[0]
    r2 = _response(
        spider, nxt.url, ["c", "d"], nxt.meta["page"], base, seen=nxt.meta.get("seen")
    )
    items2, reqs2 = _split(list(spider.parse_listing(r2)))
    assert [i["product_id"] for i in items2] == ["c.html", "d.html"]
    assert len(reqs2) == 1, "fresh products should keep pagination going"


def test_partial_overlap_still_advances_and_dedups():
    spider = _Spider()
    base = "https://x.test/cat.html"
    _, reqs1 = _split(
        list(spider.parse_listing(_response(spider, base, ["a", "b"], 1, base)))
    )
    nxt = reqs1[0]
    r2 = _response(
        spider, nxt.url, ["b", "c"], nxt.meta["page"], base, seen=nxt.meta.get("seen")
    )
    items2, reqs2 = _split(list(spider.parse_listing(r2)))
    assert [i["product_id"] for i in items2] == [
        "c.html"
    ], "only the unseen product is emitted"
    assert len(reqs2) == 1


def test_empty_page_stops():
    spider = _Spider()
    base = "https://x.test/cat.html"
    _, reqs = _split(list(spider.parse_listing(_response(spider, base, [], 1, base))))
    assert reqs == []


def test_separate_categories_do_not_starve_each_other():
    """Cross-category overlap must not stop a fresh branch on its first page."""
    spider = _Spider()
    a, b = "https://x.test/a.html", "https://x.test/b.html"
    _, reqs_a = _split(
        list(spider.parse_listing(_response(spider, a, ["p", "q"], 1, a)))
    )
    assert len(reqs_a) == 1
    # category b's page 1 holds the very same products; it must still paginate
    items_b, reqs_b = _split(
        list(spider.parse_listing(_response(spider, b, ["p", "q"], 1, b)))
    )
    assert len(items_b) == 2, "a second category must still emit its products"
    assert (
        len(reqs_b) == 1
    ), "a second category must not be cut off by another's history"
