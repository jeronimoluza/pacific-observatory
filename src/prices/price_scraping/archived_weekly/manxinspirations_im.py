"""Per-source extractor for archived manxinspirations_im (manxinspirations.com).

The 2013-2019 captures are an OpenCart 1.5 storefront that prints prices as
plain text with no structured markup, so no generic tier reaches them. Two
layouts carry the store's own prices.

Product pages (``/<Category>/<Product>``, ``?product_id=N``)::

    <div id="content"> ... <h1>5 x 3 flag</h1>
      <div class="product-info"> ... <div class="right"> ...
        <div class="price">Price:   £6.99   <br /></div>

Category listings (``/<Category>``, ``?page=N``)::

    <div class="product-list"><div>
      <div class="name"><a href="...">2014 A4 Wall Calendar</a></div>
      <div class="price">  £4.99  </div> ...

Prices are in pounds sterling; GBP is recorded, never read from the page.

Abstains on: the "Related Products" tab and side-column boxes (other products'
prices on a product page), any price block carrying a special/old price,
tax line or more than one figure (none seen in the samples, so they are
refused rather than guessed), and information/contact pages.
"""
from __future__ import annotations

import re
from typing import Any

import lxml.html

from ..archived import normalize_price, price_row

_CURRENCY = "GBP"
_GBP = re.compile(r"£\s*(\d[\d,]*(?:\.\d+)?)")
_REFUSE = re.compile(r"price-old|price-new|price-tax|Ex Tax", re.I)
_XML_DECL = re.compile(r"^\s*<\?xml[^>]*\?>")


def _text(el: Any) -> str:
    return " ".join((el.text_content() or "").split())


def _price(el: Any) -> str | None:
    if _REFUSE.search(lxml.html.tostring(el, encoding="unicode")):
        return None
    hits = _GBP.findall(_text(el))
    if len(hits) != 1:
        return None
    return normalize_price(hits[0], _CURRENCY)


def _product(doc: Any, url: str) -> list[dict]:
    prices = doc.xpath('//div[@class="product-info"]/div[@class="right"]/div[@class="price"]')
    names = doc.xpath('//div[@id="content"]/h1')
    if len(prices) != 1 or len(names) != 1:
        return []
    row = price_row(_text(names[0]), _price(prices[0]), url, _CURRENCY)
    return [row] if row else []


def _listing(doc: Any, url: str) -> list[dict]:
    rows = []
    items = doc.xpath('//div[@id="content"]//div[@class="product-list" or @class="product-grid"]/div')
    for item in items:
        names = item.xpath('./div[@class="name"]/a')
        prices = item.xpath('./div[@class="price"]')
        if len(names) != 1 or len(prices) != 1:
            continue
        row = price_row(_text(names[0]), _price(prices[0]), url, _CURRENCY)
        if row:
            rows.append(row)
    return rows


def extract(html: str, url: str) -> list[dict]:
    """Own prices on an archived manxinspirations_im product or listing page."""
    # Most captures open with an XML declaration, which lxml refuses on str input.
    doc = lxml.html.fromstring(_XML_DECL.sub("", html, count=1))
    if doc.xpath('//div[@class="product-info"]'):
        return _product(doc, url)
    return _listing(doc, url)
