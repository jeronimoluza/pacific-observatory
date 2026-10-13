"""Per-source extractor for archived colebourn_im (colebourn.com).

The 2018-2019 captures (CC-MAIN-2018-51, CC-MAIN-2019-04) are product pages
(``/product/<slug>/``) from a custom WordPress theme with no structured price
markup. The product summary carries one title and one price; a sale price
nests the struck "Was" figure inside the same span::

    <div class="summary">
      <h2 class="product_title underline">PANASONIC DMPUB700</h2>
      <span class='price'>£294.95<span class='sale'>Was <b>£329.99</b></span></span>
    ...
    <div class='points'><span class='finance finance-12'>
      <h3>Available on finance</h3><i>12</i> monthly payments of <b>£15.33</b></span>

Only the price span's own leading text is read (the current price); the
nested "Was" span and the finance/monthly block are never touched. Prices are
in pounds sterling; GBP is recorded, never read from the page.

Abstains on: pages without exactly one summary title and one summary price
span, a price text holding anything but a single £ figure, and any page
that is not a product page (listings, info pages).
"""
from __future__ import annotations

import re
from typing import Any

import lxml.html

from ..archived import normalize_price, price_row

_CURRENCY = "GBP"
_GBP = re.compile(r"^£\s*(\d[\d,]*(?:\.\d+)?)$")
_XML_DECL = re.compile(r"^\s*<\?xml[^>]*\?>")


def _price(el: Any) -> str | None:
    # el.text is the text before the first child, i.e. before the nested "Was" span.
    m = _GBP.match(" ".join((el.text or "").split()))
    return normalize_price(m.group(1), _CURRENCY) if m else None


def extract(html: str, url: str) -> list[dict]:
    """Own price on an archived colebourn_im product page."""
    doc = lxml.html.fromstring(_XML_DECL.sub("", html, count=1))
    summaries = doc.xpath('//div[@class="summary"]')
    if len(summaries) != 1:
        return []
    names = summaries[0].xpath('./h2[contains(concat(" ", @class, " "), " product_title ")]')
    prices = summaries[0].xpath('./span[@class="price"]')
    if len(names) != 1 or len(prices) != 1:
        return []
    name = " ".join(names[0].text_content().split())
    row = price_row(name, _price(prices[0]), url, _CURRENCY)
    return [row] if row else []
