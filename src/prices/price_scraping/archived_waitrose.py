"""Per-source extractor for archived waitrose (waitrose.com) captures.

Two eras carry a price no generic tier reads:

- 2013-2017 ``/shop/ProductView-...`` pages and ``DisplayProductFlyout``
  flyouts: ``p.price > strong`` beside the ``h1`` (name plus pack size). The
  figure is written three ways -- ``£1.32``, ``79p`` for anything under a
  pound (``80pper kg`` on loose veg), and ``£4.65 each (est.)`` for
  typical-weight items. The ``(19.8p per 100g)`` span is a unit price and is
  not read; "£ FREE" hire items carry no figure.
- 2018-2022 React product pages: the hidden ``itemprop=price`` Offer inside
  ``section.productPricing`` beside ``h1#productName``.

2017 SPA shells and the 2023+ pages render no price.
"""

from __future__ import annotations

import re
from typing import Any

from .archived import normalize_price, price_row as _row

# The figure is matched rather than the whole label handed to normalize_price:
# "79p" read as 79 pounds and "£4.65 each (est.)" kept the "(est.)" period and
# collapsed to 465 -- both a clean 100x on 2014-17 history.
_POUNDS = re.compile(r"£\s*(\d[\d,]*(?:\.\d+)?)")
_PENCE = re.compile(r"(?<![\d.,£])(\d+(?:\.\d+)?)\s*p(?:\b|(?=per\b))")


def _text(el: Any) -> str:
    return " ".join((el.text_content() or "").split())


def _label_price(raw: str) -> str | None:
    m = _POUNDS.search(raw)
    if m:
        return normalize_price(m.group(1), "GBP")
    m = _PENCE.search(raw)
    if m:
        return str(round(float(m.group(1)) / 100, 4))
    return None


def extract(doc: Any, url: str) -> dict | None:
    """The price on an archived waitrose product page or flyout, or nothing."""
    sec = doc.xpath('//section[contains(@class,"productPricing")]')
    h1 = doc.xpath('//h1[@id="productName"]')
    if sec and h1:
        p = sec[0].xpath('.//*[@itemprop="price"]')
        raw = (p[0].get("content") or _text(p[0])) if p else ""
        if re.search("\\d", raw):
            name = " ".join(_text(s) for s in h1[0].xpath("./span")) or _text(h1[0])
            return _row(name.strip(), normalize_price(raw, "GBP"), url, "GBP")
        return None
    strong = doc.xpath('//p[@class="price"]/strong')
    h1 = doc.xpath("//h1")
    if not strong or not h1:
        return None
    return _row(_text(h1[0]), _label_price(_text(strong[0])), url, "GBP")
