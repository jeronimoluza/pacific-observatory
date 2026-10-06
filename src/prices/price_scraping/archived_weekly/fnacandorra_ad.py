"""Per-source extractor for archived fnacandorra_ad (fnac-andorra.com) captures.

The archived URLs are OpenCart ``/index.php?route=product/category`` and
``route=product/search`` listings, so a page carries one card per product and
no structured price. Two Journal themes cover the samples.

Journal2 (2018-2019)::

    <div class="product-thumb "> ...
      <h4 class="name"><a href="...">1% Esquizofrenia</a></h4>
      <p class="price">8,25€</p>

Journal3 (late 2019-2024)::

    <div class="product-thumb"> ...
      <div class="name"><a href="...">Adaptador Hub Hama USB-c 7 en 1</a></div>
      <div class="price"><div><span class="price-normal">91,73€</span></div></div>

Each card yields its own name and price. Abstains on a card whose price block
carries ``price-old``/``price-new`` (a special, where the struck figure sits
beside the current one -- none seen in the samples), on a price text that is not
exactly one euro amount, and on a card without a name.
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
        raw = _text(normal[0]) if len(normal) == 1 else _text(box)
        m = _AMOUNT.match(raw)
        if not m:
            continue
        row = price_row(_text(names[0]), normalize_price(m.group(1), _CURRENCY), url, _CURRENCY)
        if row:
            rows.append(row)
    return rows
