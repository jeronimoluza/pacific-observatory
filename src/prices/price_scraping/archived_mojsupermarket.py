"""Per-source extractor for archived mojsupermarket_me captures.

mojsupermarket_me is a Montenegrin grocery price comparison site. It resolved
11,820 captures across 2014-2025 -- twelve distinct years -- and parsed none.
The captures are category listings carrying roughly thirty products each, so
the row count this unlocks is far larger than the capture count suggests.

Each product sits in a block whose name is the anchor text inside an ``h4`` and
whose price is a ``span.amount`` inside a ``div.price``::

    <h4><a ... data-title="Proizvod 1 od 30"> Mesni narezak Franca 150g ... </a></h4>
    <div class="rating"></div>
    <div class="price">
      <span>Cijena: </span>
      <span class="amount">1,03 &euro;</span>
      <span class="orange pull-right">150g</span>
      <!--small>0,69 ...-->

Two decoys sit inside that same ``div.price`` and both are avoided by reading
``span.amount`` specifically rather than the div's text:

* ``span.orange pull-right`` holds the pack size ("150g"). Read as a number it
  would bank 150 as a price.
* A per-unit price ("0,69") follows in an HTML **comment**. lxml exposes
  comments as nodes, and a text sweep that included them would sometimes pick
  the unit price over the shelf price -- the same per-kilo trap that frisco_pl
  and edeka24_de navigate, here hidden in a comment rather than a sibling
  class.

Figures use the decimal comma ("1,03 &euro;" is one euro three cents).
Montenegro uses the euro despite not being in the euro area, so EUR is recorded
from the markup's own symbol rather than assumed from the country.
"""
from __future__ import annotations

import re
from typing import Any

from .archived import price_row as _row

_CURRENCY = "EUR"
_NUM = re.compile(r"\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2}|\d+(?:\.\d+)?")

_AMOUNT = ('.//*[contains(concat(" ", normalize-space(@class), " "), " amount ")]')
_PRICE = ('.//*[contains(concat(" ", normalize-space(@class), " "), " price ")]')


def _num(text: str | None) -> str | None:
    if not text:
        return None
    m = _NUM.search(text.replace("\xa0", " "))
    if not m:
        return None
    raw = m.group(0)
    if "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    return raw


def extract(doc: Any, url: str) -> list[dict]:
    """Every priced product on an archived mojsupermarket listing capture."""
    rows: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for price_div in doc.xpath(
            '//*[contains(concat(" ", normalize-space(@class), " "), " price ")]'):
        amounts = price_div.xpath(_AMOUNT)
        if not amounts:
            continue
        price = _num(amounts[0].text_content())
        if not price:
            continue
        # The name is the nearest preceding h4 anchor; walking up to a shared
        # ancestor and back down keeps a product's name with its own price on a
        # listing where thirty of these repeat.
        name = None
        node = price_div
        for _ in range(4):
            node = node.getparent()
            if node is None:
                break
            found = node.xpath(".//h4//a")
            if found:
                name = " ".join((found[0].text_content() or "").split())
                break
        if not name:
            continue
        key = (name, price)
        if key in seen:
            continue
        seen.add(key)
        row = _row(name, price, url, _CURRENCY)
        if row:
            rows.append(row)
    return rows
