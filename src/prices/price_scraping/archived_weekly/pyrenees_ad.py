"""Per-source extractor for archived pyrenees_ad (pyrenees.ad/alimentacio) captures.

The grocery store runs OpenCart with the Journal3 theme in every archived crawl
(2021-2025). Product pages already parse through JSON-LD; the misses are the
category listings (``/<cat>/<sub>/``, ``.../page-N/``, in Catalan and under the
``/fr/``, ``/es/`` and ``/en/`` prefixes), twenty cards per page::

    <div class="main-products product-grid"> ...
      <div class="product-thumb"> ...
        <div class="name"><a ...>AGRADO DEO DONA FRESH FANTASY 150ML</a></div>
        <div class="description">1 l / 8,60 €</div>
        <div class="price"><div><span class="price-normal">1,29€</span></div>
          <span class="price-tax">Sense IVA:1,29€</span></div>

Only cards inside the ``main-products`` grid are read: product pages and
articles carry related-product carousels with the same card markup, and those
are not the page's own listing. ``price-normal`` is the shelf price;
``price-tax`` (before IGI) and the per-kilo/litre ``description`` are never
read. The figure is ``1,29€`` on Catalan and Spanish pages and ``1.29€`` on
French and English ones (and some Catalan ones from 2024 on); both are read.
Abstains on a card whose price block carries ``price-old``/``price-new`` (a
special -- none seen in the samples), on a figure that is not exactly one euro
amount, and on cards without a name. Out-of-stock items show ``0,00€``,
which ``price_row`` rejects. Legal, shipping, cookie and article pages carry
no grid and yield nothing.
"""
from __future__ import annotations

import re

import lxml.html

from ..archived import normalize_price, price_row

_CURRENCY = "EUR"
_AMOUNT = re.compile(
    r"^(\d{1,3}(?:\.\d{3})+,\d{2}|\d{1,3}(?:,\d{3})+\.\d{2}|\d+[.,]\d{2}|\d+)\s*€$"
)


def _cls(token: str) -> str:
    return f'contains(concat(" ", normalize-space(@class), " "), " {token} ")'


def _text(el) -> str:
    return " ".join((el.text_content() or "").split())


def extract(html: str, url: str) -> list[dict]:
    doc = lxml.html.fromstring(html)
    rows = []
    for card in doc.xpath(f"//div[{_cls('main-products')}]//div[{_cls('product-thumb')}]"):
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
