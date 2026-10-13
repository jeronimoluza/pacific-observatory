"""Per-source extractor for archived eternalandorra_ad (eternalandorra.pro).

The 2024-2026 captures are per-club WooCommerce multisite shops
(``/<club>/tienda/<category>/<product>/``) run through a translation plugin
that also translated the markup itself: the amount span is
``woocommerce-Preu-amount`` and the JSON-LD type is ``"Producte"``, so the
generic WooCommerce / schema.org tiers miss it, and most JSON-LD offers carry
no ``price`` at all. The product's own price sits directly under the title::

    <h1 itemprop="name" class="product_title entry-title">Pack Futbol Sala Jugador/a</h1>
    <div class="price-single">
      <div class="price"><span class="woocommerce-Preu-amount amount">115,00&nbsp;
        <span class="woocommerce-Preu-currencySymbol">&euro;</span></span></div>
    </div>

Older captures (2024-2025) print ``115,00 €``, newer ones (2026) ``6.00€``;
both are read through ``normalize_price``. EUR is recorded, never read from
the page.

Abstains on: product pages whose ``price-single`` block is empty (variable
products / club items with no price shown), blocks with a sale (``<del>`` /
``<ins>``) or more than one amount, pages whose JSON-LD offer price disagrees
with the visible price, and the "related products" grid below the product
(other products' prices).
"""
from __future__ import annotations

import json
import re
from typing import Any

import lxml.html

from ..archived import normalize_price, price_row

_CURRENCY = "EUR"
_XML_DECL = re.compile(r"^\s*<\?xml[^>]*\?>")
_AMOUNT = re.compile(r"^(\d[\d.,]*)\s*€$")


def _text(el: Any) -> str:
    return " ".join((el.text_content() or "").replace("\xa0", " ").split())


def _ld_prices(doc: Any) -> set[float]:
    out: set[float] = set()
    for s in doc.xpath('//script[@type="application/ld+json"]'):
        try:
            data = json.loads(s.text or "")
        except ValueError:
            continue
        offers = data.get("offers") if isinstance(data, dict) else None
        if isinstance(offers, dict):
            offers = [offers]
        for o in offers or []:
            if isinstance(o, dict) and o.get("price") not in (None, ""):
                try:
                    out.add(round(float(o["price"]), 2))
                except (TypeError, ValueError):
                    pass
    return out


def extract(html: str, url: str) -> list[dict]:
    """The own price on an archived eternalandorra_ad product page."""
    doc = lxml.html.fromstring(_XML_DECL.sub("", html, count=1))
    names = doc.xpath('//h1[contains(concat(" ", @class, " "), " product_title ")]')
    blocks = doc.xpath('//div[@class="price-single"]/div[@class="price"]')
    if len(names) != 1 or len(blocks) != 1:
        return []
    block = blocks[0]
    if block.xpath(".//del | .//ins"):
        return []
    amounts = block.xpath('.//span[contains(concat(" ", @class, " "), " amount ")]')
    if len(amounts) != 1:
        return []
    m = _AMOUNT.match(_text(amounts[0]))
    if not m:
        return []
    price = normalize_price(m.group(1), _CURRENCY)
    if price is None:
        return []
    ld = _ld_prices(doc)
    if ld and ld != {round(float(price), 2)}:
        return []
    row = price_row(_text(names[0]), price, url, _CURRENCY)
    return [row] if row else []
