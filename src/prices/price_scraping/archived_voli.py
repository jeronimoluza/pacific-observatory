"""Per-source extractor for archived voli_me (voli.me) captures.

Voli is a Montenegrin supermarket chain: 11,333 miss records over 2021-2025,
product detail pages under ``/proizvod/<id>``.

The page's own price is ``span.new-price`` and appears exactly once. Below it a
related-products carousel repeats ``div.product-price`` ten times with entirely
different figures -- on the sampled capture the page's product costs 1.85 EUR
while the carousel shows 1.59, 1.10 and others. This is the same shape as the
frisco_pl carousel: the decoy is not a variant of the price, it is a different
product's price, so reading it produces a plausible number attached to the
wrong item and no check on the value alone would catch it.

Both classes carry a ``sub.product-quantity-unit`` giving the basis ("/kom"
per piece, "/kg" per kilo). It is left in the markup and excluded from the
figure rather than being used to reject rows: on weighed goods the per-kilo
figure IS the shelf price, so discarding "/kg" rows would drop produce
entirely.

Montenegro uses the euro despite being outside the euro area; EUR is taken
from the markup's own symbol.

The name comes from ``og:title``, which suffixes " - Voli eCommerce"; there is
no ``h1`` on these captures.
"""
from __future__ import annotations

import re
from typing import Any

from .archived import price_row as _row

_CURRENCY = "EUR"
_NUM = re.compile(r"\d+(?:[.,]\d+)?")
_SUFFIX = " - Voli eCommerce"
_CLS = 'contains(concat(" ", normalize-space(@class), " "), " %s ")'


def _name(doc: Any) -> str | None:
    for el in doc.xpath('//meta[@property="og:title"]/@content'):
        txt = " ".join(str(el).split())
        if txt.endswith(_SUFFIX):
            txt = txt[: -len(_SUFFIX)]
        if txt:
            return txt.strip()
    return None


def extract(doc: Any, url: str) -> dict | None:
    """The page's own price, never the related-products carousel."""
    for el in doc.xpath("//*[%s]" % (_CLS % "new-price")):
        # The unit sub-element is a sibling inside the same node; take only the
        # element's direct text so "/kom" cannot be glued onto the figure.
        raw = (el.text or "").strip() or el.text_content()
        m = _NUM.search(raw.replace("\xa0", " "))
        if not m:
            continue
        price = m.group(0).replace(",", ".")
        return _row(_name(doc), price, url, _CURRENCY)
    return None
