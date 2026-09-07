"""Per-source extractor for archived happycenter_tr captures.

happycenter_tr is a Turkish supermarket chain and the deepest source this
project has found: 55,621 captures spanning 2013-2025, thirteen distinct years.
It resolved cleanly and parsed nothing, which is the signature that had already
meant two different things elsewhere -- a markup no tier reads, or a price that
is not in the HTML at all -- so the captures were read before anything was
written.

They are category listing pages, not product pages, and that is what makes the
source worth a module rather than a footnote: one capture carries a whole
shelf. The two product-bearing captures sampled hold 11 and 19 products each,
so the record count understates the row count by an order of magnitude, the
same way spesalia_it turned 3,068 captures into 77,496 rows in the same pass.

Each product is a ``div.urun`` ("urun" is Turkish for product) holding exactly
one ``div.price`` whose anchor carries both the figure and the product path::

    <div id="urun-3" class="urun">
      <div class="price"><a href="/Numil_125_Gr_...">5,45</a></div>
      <div class="cart"><div class="resim"><img title="Milupa Organik ..."

The count of ``div.urun`` and the count of ``div.price`` are equal on every
sampled capture (11 and 11, then 19 and 19), so there is no second figure per
product and none of the struck-through-original ambiguity that taw9eel_kw and
frisco_pl have to navigate. The word "indirim" (discount) does appear on the
page but never inside a product block.

The name is not rendered as text next to the price -- it lives in the
``title``/``alt`` of the product thumbnail, HTML-entity encoded
("Milupa Organik S&#252;tla&#231; ..."), which lxml decodes on access.

Figures use the Turkish decimal comma ("5,45" is five lira forty-five, not five
thousand four hundred and forty-five). The comma is converted rather than
stripped; stripping it would inflate every observation by a hundredfold and
would do so silently, since the result is still a valid number.

Captures that are not listings -- the store-locator pages under /kurumsal/, one
of which was sampled -- carry no ``div.urun`` at all and yield nothing.
"""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin

from .archived import price_row as _row

_CURRENCY = "TRY"
# Turkish decimal comma, optional thousands dot: 5,45 and 1.234,50 both occur.
_NUM = re.compile(r"\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2}|\d+(?:\.\d+)?")


def _price(text: str | None) -> str | None:
    if not text:
        return None
    m = _NUM.search(text.replace("\xa0", " "))
    if not m:
        return None
    raw = m.group(0)
    if "," in raw:
        raw = raw.replace(".", "").replace(",", ".")
    return raw


def _name(block: Any) -> str | None:
    for img in block.xpath(".//img[@title or @alt]"):
        txt = " ".join((img.get("title") or img.get("alt") or "").split())
        if txt:
            return txt
    return None


def extract(doc: Any, url: str) -> list[dict]:
    """Every priced product card on an archived happycenter listing capture."""
    rows: list[dict] = []
    seen: set[str] = set()
    for block in doc.xpath('//div[contains(concat(" ", normalize-space(@class), " "), " urun ")]'):
        anchor = block.xpath('.//div[contains(concat(" ", normalize-space(@class), " "), " price ")]//a')
        if not anchor:
            continue
        price = _price(anchor[0].text_content())
        name = _name(block)
        if not price or not name:
            continue
        href = anchor[0].get("href")
        row_url = urljoin(url, href) if href else url
        if row_url in seen:
            continue
        seen.add(row_url)
        row = _row(name, price, row_url, _CURRENCY)
        if row:
            rows.append(row)
    return rows
