"""Per-source extractor for archived farmaciapiolets_ad (farmaciapiolets.com).

An Andorran pharmacy on OpenCart 2 themes that print prices as bare text with
no JSON-LD, microdata or product OpenGraph tag, so no generic tier reaches
them. Three layouts carry the store's own prices.

Product pages, 2022-2026 (``/marcas-<brand>/productos-<slug>``)::

    <div class="col-sm-6 col-lg-6 product-info-details"><div class="inner">
      <h1><strong>Apivita Lady gel intimo protector sequedad</strong></h1> ...
      <p class="price"> <strong>12.50€</strong> </p>

Product pages, 2019 (``/<slug>``)::

    <div id="content"> <div class="product-view"> ...
      <div class="product-name"><h1>Natrol Advanced Sleep Melatonin 10 mg</h1></div>
      <div class="price"> 15,00€ <span class="price-tax"></span> </div>

Category listings, 2016-2018 (``/<brand>``)::

    <div id="content"> ... <div class="item-inner"> <div class="box-item">...</div>
      <div class="right-block"><div class="caption">
      <div class="name"><a href="...">Inca Rose Stick Labial Black Diamond</a></div>
      ... <p class="price"> 18,95€ </p>

Both ``12.50`` and ``15,00`` decimal styles occur; EUR is recorded, never read
from the page.

Abstains on: the left/right-column "Ofertas" boxes (other products, with
"A partir de" teasers and struck ``price-old`` figures), any price block
carrying ``price-old``/``price-new`` or a non-empty ``price-tax`` line or more
than one figure, the 2022+ category listings (no prices in the HTML), the
2013 static brochure site and empty category shells.
"""
from __future__ import annotations

import re
from typing import Any

import lxml.html

from ..archived import normalize_price, price_row

_CURRENCY = "EUR"
_EUR = re.compile(r"(\d[\d.,]*)\s*€")
_REFUSE = re.compile(r"price-old|price-new|a partir", re.I)
_XML_DECL = re.compile(r"^\s*<\?xml[^>]*\?>")


def _text(el: Any) -> str:
    return " ".join((el.text_content() or "").split())


def _price(el: Any) -> str | None:
    if _REFUSE.search(lxml.html.tostring(el, encoding="unicode")):
        return None
    for tax in el.xpath('.//*[contains(@class, "price-tax")]'):
        if _text(tax):
            return None
    hits = _EUR.findall(_text(el))
    if len(hits) != 1:
        return None
    return normalize_price(hits[0], _CURRENCY)


def _one(doc: Any, name_xp: str, price_xp: str, url: str) -> list[dict]:
    names = doc.xpath(name_xp)
    prices = doc.xpath(price_xp)
    if len(names) != 1 or len(prices) != 1:
        return []
    row = price_row(_text(names[0]), _price(prices[0]), url, _CURRENCY)
    return [row] if row else []


def _listing(doc: Any, url: str) -> list[dict]:
    rows = []
    for cap in doc.xpath('//div[@id="content"]//div[@class="item-inner"]'
                         '/div[@class="right-block"]/div[@class="caption"]'):
        names = cap.xpath('./div[@class="name"]/a')
        prices = cap.xpath('./p[@class="price"]')
        if len(names) != 1 or len(prices) != 1:
            continue
        row = price_row(_text(names[0]), _price(prices[0]), url, _CURRENCY)
        if row:
            rows.append(row)
    return rows


def extract(html: str, url: str) -> list[dict]:
    """Own prices on an archived farmaciapiolets_ad product or listing page."""
    doc = lxml.html.fromstring(_XML_DECL.sub("", html, count=1))
    if doc.xpath('//div[contains(@class, "product-info-details")]//h1'):
        base = '//div[contains(concat(" ", @class, " "), " product-info-details ")]'
        return _one(doc, base + "//h1", base + '//p[@class="price"]', url)
    if doc.xpath('//div[@id="content"]//div[@class="product-view"]'):
        base = '//div[@id="content"]//div[@class="product-view"]'
        return _one(doc, base + '//div[@class="product-name"]/h1',
                    base + '//div[@class="price"]', url)
    return _listing(doc, url)
