"""Per-source extractor for archived bvihsa_vg (bvihsa.vg) captures.

The BVI Health Services Authority site was swept without a product filter, so
almost every capture is a news, clinic or staff page with no price (the dollar
figures in news posts are donations and grants -- never read). From 2025 the
site carries a WooCommerce pharmacy on a "hospa" theme; its listing pages
(``/product-tag/...``, ``/product-category/...``) show each product as a loop
card and again as a quick-view modal::

    <li class="product type-product ..."><div class="shop-item"> ...
      <div class="shop-content">
        <h3><a href=".../product/levonorgestrel-1-5mg-1-tablet/">Levonorgestrel 1.5MG 1 Tablet</a></h3>
        <div class="price"><span class="price"><span class="woocommerce-Price-amount amount">
          <bdi><span class="woocommerce-Price-currencySymbol">&#36;</span>4.20</bdi></span></span></div>

    <div class="modal productsQuickView fade" id="productsQuickView17361"> ...
      <div class="content"><h3>Terbinafine Cream 30g</h3>
        <span class="price"><span class="woocommerce-Price-amount amount">...6.00...</span></span>

Both blocks are read and deduplicated on (name, price). Eras: 2025-2026
pharmacy pages only. Abstains on any price block holding a ``<del>`` (sale /
was price) or more than one amount (variable-product ranges), and on every
page without these blocks (all pre-2025 captures).
"""
from __future__ import annotations

import lxml.html

from ..archived import normalize_price, price_row

_CURRENCY = "USD"
_CARD = (
    '//li[contains(concat(" ", normalize-space(@class), " "), " product ")]'
    '//div[contains(concat(" ", normalize-space(@class), " "), " shop-content ")]'
    ' | //div[contains(concat(" ", normalize-space(@class), " "), " productsQuickView ")]'
    '//div[contains(concat(" ", normalize-space(@class), " "), " content ")]'
)
_PRICE = './/span[contains(concat(" ", normalize-space(@class), " "), " price ")][1]'
_AMOUNT = './/span[contains(concat(" ", normalize-space(@class), " "), " woocommerce-Price-amount ")]'


def _text(el) -> str:
    return " ".join((el.text_content() or "").split())


def extract(html: str, url: str) -> list[dict]:
    """Pharmacy product prices on an archived bvihsa_vg listing page, or nothing."""
    doc = lxml.html.fromstring(html)
    rows, seen = [], set()
    for card in doc.xpath(_CARD):
        names = card.xpath("./h3")
        prices = card.xpath(_PRICE)
        if len(names) != 1 or not prices:
            continue
        block = prices[0]
        amounts = block.xpath(_AMOUNT)
        if block.xpath(".//del") or len(amounts) != 1:
            continue
        name = _text(names[0])
        price = normalize_price(_text(amounts[0]), _CURRENCY)
        key = (name, price)
        if key in seen:
            continue
        seen.add(key)
        row = price_row(name, price, url, _CURRENCY)
        if row:
            rows.append(row)
    return rows
