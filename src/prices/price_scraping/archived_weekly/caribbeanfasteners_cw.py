"""Per-source extractor for archived caribbeanfasteners_cw (caribbean-fasteners.com).

The 2023-2026 captures are a Sylius storefront that prints prices as text with
no structured markup. Product pages (``/en/products/<slug>``) carry the
product's own price next to its name, and a "Box quantity" attribute::

    <h1 id="sylius-product-name" ...>K 2 Compact Dirt Nozzle 220-240V/1/50/60Hz</h1>
    <span class="ui huge header" id="product-price">  ANG 343.87  </span>
    ...
    <td class="sylius-product-attribute-name">Box quantity</td>
    <td class="sylius-product-attribute-value" id="attribute-unit_size"> 1 </td>

Multi-variant products replace that with a table, one row per variant::

    <table id="sylius-product-variants"><th>Variant</th><th>Price/1</th><th>Box</th>...
      <td><p>M 2 - 0.4</p></td>
      <td class="sylius-product-variant-price"><p>ANG 0.23</p></td><td>1000</td>

Every price is per piece, whatever the box quantity: the variant column is
headed "Price/1", and on a variant page ``#product-price`` repeats the first
variant's Price/1 (hex nut M 2: ANG 0.23, box 1000). So the box quantity is the
carton size, not what the price buys, and is never written into the name (a
"box of N" in the name would be read downstream as a pack count and divide the
piece price again). Variant labels are often only a size ("M 2 - 0.4"), so the
product name is prefixed unless the label already starts with it.

Listing, brand and home pages show product cards::

    <div class="ui fluid card"> ...
      <a href="/en/products/..." class="header sylius-product-name">Oil for Pneumatic Machines oil 0.6L</a>
      <div class="sylius-product-price"> ANG 17.05 </div>

A card priced "From ANG x" is a multi-variant product's minimum and is skipped;
a plain "ANG x" card is a single-variant product's own price. Cards are read
only on pages that are not product pages (there they are related products).

ANG (Netherlands Antillean guilder) is recorded, never read from the page; a
figure is kept only when it is written with the literal ``ANG`` prefix, so a
capture priced in anything else (USD, the 2025 Caribbean guilder) is skipped.
"""
from __future__ import annotations

import re
from typing import Any

import lxml.html

from ..archived import normalize_price, price_row

_CURRENCY = "ANG"
_ANG = re.compile(r"^ANG\s*(\d[\d,]*(?:\.\d+)?)$")
_CARD = '//div[contains(concat(" ", normalize-space(@class), " "), " card ")]'


def _text(el: Any) -> str:
    return " ".join((el.text_content() or "").split())


def _ang(el: Any) -> str | None:
    m = _ANG.match(_text(el))
    return normalize_price(m.group(1), _CURRENCY) if m else None


def _variant_name(product: str, label: str) -> str:
    if label.lower().startswith(product.split()[0].lower()):
        return label
    return f"{product} {label}"


def _variants(table: Any, product: str, url: str) -> list[dict]:
    heads = [_text(th) for th in table.xpath("./thead/tr/th")]
    if heads[:3] != ["Variant", "Price/1", "Box"]:
        return []
    rows = []
    for tr in table.xpath("./tbody/tr"):
        tds = tr.xpath("./td")
        if len(tds) < 3 or not _text(tds[0]):
            continue
        row = price_row(_variant_name(product, _text(tds[0])), _ang(tds[1]), url, _CURRENCY)
        if row:
            rows.append(row)
    return rows


def _cards(doc: Any, url: str) -> list[dict]:
    rows, seen = [], set()
    for card in doc.xpath(_CARD):
        names = card.xpath('.//a[contains(@class, "sylius-product-name")]')
        prices = card.xpath('.//*[contains(@class, "sylius-product-price")]')
        if len(names) != 1 or len(prices) != 1:
            continue
        key = (_text(names[0]), _ang(prices[0]))
        if key in seen:
            continue
        seen.add(key)
        row = price_row(key[0], key[1], url, _CURRENCY)
        if row:
            rows.append(row)
    return rows


def extract(html: str, url: str) -> list[dict]:
    """Per-piece prices on an archived caribbeanfasteners_cw product or listing page."""
    doc = lxml.html.fromstring(html)
    names = doc.xpath('//h1[@id="sylius-product-name"]')
    if not names:
        return _cards(doc, url)
    product = _text(names[0]) if len(names) == 1 else ""
    if not product:
        return []
    tables = doc.xpath('//table[@id="sylius-product-variants"]')
    if tables:
        return _variants(tables[0], product, url) if len(tables) == 1 else []
    boxes = doc.xpath('//td[@id="attribute-unit_size"]')
    prices = doc.xpath('//span[@id="product-price"]')
    if len(boxes) != 1 or len(prices) != 1:
        return []
    row = price_row(product, _ang(prices[0]), url, _CURRENCY)
    return [row] if row else []
