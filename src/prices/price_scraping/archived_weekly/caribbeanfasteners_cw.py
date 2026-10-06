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
      <td><p>Oil for Piston Compressors 0.6L</p></td>
      <td class="sylius-product-variant-price"><p>ANG 24.13</p></td><td>1</td>

ANG (Netherlands Antillean guilder) is recorded, never read from the page; a
figure is kept only when it is written with the literal ``ANG`` prefix, so a
capture priced in anything else (USD, the 2025 Caribbean guilder) is skipped.

Abstains on: products sold by the box (box quantity other than 1), where the
storefront's "Price/1" figure may be per piece rather than per item sold;
pages with no box quantity at all; listing, brand and review pages, whose
product cards carry no box quantity and include "From ANG x" minimum-variant
prices; the related-product cards under a product page; shipping figures.
"""
from __future__ import annotations

import re
from typing import Any

import lxml.html

from ..archived import normalize_price, price_row

_CURRENCY = "ANG"
_ANG = re.compile(r"^ANG\s*(\d[\d,]*(?:\.\d+)?)$")


def _text(el: Any) -> str:
    return " ".join((el.text_content() or "").split())


def _ang(el: Any) -> str | None:
    m = _ANG.match(_text(el))
    return normalize_price(m.group(1), _CURRENCY) if m else None


def _variants(table: Any, url: str) -> list[dict]:
    heads = [_text(th) for th in table.xpath("./thead/tr/th")]
    if heads[:3] != ["Variant", "Price/1", "Box"]:
        return []
    rows = []
    for tr in table.xpath("./tbody/tr"):
        tds = tr.xpath("./td")
        if len(tds) < 3 or _text(tds[2]) != "1":
            continue
        row = price_row(_text(tds[0]), _ang(tds[1]), url, _CURRENCY)
        if row:
            rows.append(row)
    return rows


def extract(html: str, url: str) -> list[dict]:
    """The product's own price(s) on an archived caribbeanfasteners_cw product page."""
    doc = lxml.html.fromstring(html)
    names = doc.xpath('//h1[@id="sylius-product-name"]')
    if len(names) != 1:
        return []
    tables = doc.xpath('//table[@id="sylius-product-variants"]')
    if tables:
        return _variants(tables[0], url) if len(tables) == 1 else []
    boxes = doc.xpath('//td[@id="attribute-unit_size"]')
    prices = doc.xpath('//span[@id="product-price"]')
    if len(boxes) != 1 or _text(boxes[0]) != "1" or len(prices) != 1:
        return []
    row = price_row(_text(names[0]), _ang(prices[0]), url, _CURRENCY)
    return [row] if row else []
