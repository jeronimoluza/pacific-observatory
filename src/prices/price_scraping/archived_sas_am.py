r"""Per-source extractor for archived sas_am (sas.am) captures.

SAS is an Armenian supermarket chain: 36,578 miss records over 2021-2024, all
of them product detail pages under ``/catalog/<category>/<id>/``, none parsed.

The charged price is the ``span.price__text`` inside ``div.price__new``, with
the currency in a nested ``span.price__currency`` reading "դր." (dram)::

    <div class="price"><div class="price__new ">
      <span class="price__text">16&#160;800<span class="price__currency">դր.</span></span>

Two details make a naive read wrong:

* The thousands separator is a non-breaking space, so "16 800" is sixteen
  thousand eight hundred dram. Splitting on whitespace or matching ``\d+``
  without normalising first takes the 16 and banks a price a thousandfold low.
* A ``card__prise-converter-popup`` sits directly after the price block and
  restates the same amount in other currencies. Reading it would bank a dram
  figure under a foreign currency, or a foreign figure as dram; anchoring on
  ``price__new`` excludes it structurally.

The currency element is stripped from the text before the number is taken --
"դր." contains no digits, but the nesting means a naive ``text_content()`` on
the parent concatenates the two, and future markup may not be so forgiving.

Amounts are whole dram. AMD has minor units on paper and none in practice on
this storefront, and no capture in the sample carried a decimal.
"""
from __future__ import annotations

import re
from typing import Any

from .archived import price_row as _row

_CURRENCY = "AMD"
_NUM = re.compile(r"\d[\d.]*")
_CLS = 'contains(concat(" ", normalize-space(@class), " "), " %s ")'


def _name(doc: Any) -> str | None:
    for el in doc.xpath("//h1"):
        txt = " ".join((el.text_content() or "").split())
        if txt:
            return txt
    return None


def extract(doc: Any, url: str) -> dict | None:
    """The charged price on an archived sas.am product page, or nothing."""
    for block in doc.xpath("//*[%s]" % (_CLS % "price__new")):
        for el in block.xpath(".//*[%s]" % (_CLS % "price__text")):
            # Drop the nested currency span so only the figure remains.
            parts = [el.text or ""]
            for child in el:
                if "price__currency" not in (child.get("class") or ""):
                    parts.append(child.text_content() or "")
                parts.append(child.tail or "")
            raw = "".join(parts).replace("\xa0", "").replace(" ", "")
            m = _NUM.search(raw)
            if m:
                return _row(_name(doc), m.group(0), url, _CURRENCY)
    return None
