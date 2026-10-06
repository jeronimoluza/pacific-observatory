"""Per-source extractor for archived engrup_ad (engrup.com) captures.

Since 2020 the store runs OpenCart with the Journal3 theme; the archived pages
are brand (``/huawei.html``), tag (``/tag/<word>.html``), category and catalog
listings, one card per product::

    <div class="product-thumb"> ...
      <div class="name"><a href="...">HUAWEI AX3 PRO ...</a></div> ...
      <div class="price"><div> <span class="price-normal">69,90€</span></div>
        <span class="price-tax">Antes de impuestos:66,89€</span></div>

``price-normal`` is the shelf price; ``price-tax`` is the same price before
Andorran IGI and is never read. Abstains on a card whose price block carries
``price-old``/``price-new`` (a special -- none seen in the samples), on a figure
that is not exactly one euro amount, and on cards without a name.

Also abstains on the 2013-2017 ``/b2c/index.php?page=pp_producto(s).php``
storefront: its table layout puts banner products, description text and
``<a class=precio>`` figures side by side with no element tying a name to its
price, and those pages are not handled. Robots, contact, login and information
pages carry no product cards and yield nothing.
"""
from __future__ import annotations

import re

import lxml.html

from ..archived import normalize_price, price_row

_CURRENCY = "EUR"
_AMOUNT = re.compile(r"^(\d{1,3}(?:\.\d{3})+,\d{2}|\d+,\d{2}|\d+)\s*€$")


def _cls(token: str) -> str:
    return f'contains(concat(" ", normalize-space(@class), " "), " {token} ")'


def _text(el) -> str:
    return " ".join((el.text_content() or "").split())


def extract(html: str, url: str) -> list[dict]:
    doc = lxml.html.fromstring(html)
    rows = []
    for card in doc.xpath(f"//div[{_cls('product-thumb')}]"):
        prices = card.xpath(f".//*[{_cls('price')}]")
        names = card.xpath(f".//*[{_cls('name')}]//a")
        if len(prices) != 1 or len(names) != 1:
            continue
        box = prices[0]
        if box.xpath(f".//*[{_cls('price-old')} or {_cls('price-new')}]"):
            continue
        normal = box.xpath(f".//*[{_cls('price-normal')}]")
        if len(normal) != 1:
            continue
        m = _AMOUNT.match(_text(normal[0]))
        if not m:
            continue
        row = price_row(_text(names[0]), normalize_price(m.group(1), _CURRENCY), url, _CURRENCY)
        if row:
            rows.append(row)
    return rows
