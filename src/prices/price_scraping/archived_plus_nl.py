"""Per-source extractor for archived plus_nl (plus.nl) captures.

plus_nl resolved 274,760 captures and parsed none of them: the storefront
carries no JSON-LD, no microdata and no product OpenGraph tag in any era this
corpus holds. What it does carry, on the product detail page only, is a single
Google Tag Manager product block whose attributes name the item and its price
outright::

    <div data-id="561873" data-name="&Samhoud Tomeato burger"
         data-price="2.69" data-brand="&Samhoud"
         data-category="Vlees, kip, vis, vega/Vega, vleesvervangers"
         data-list-name="Product Detail Page">

``data-price`` appears **exactly once** per capture across every sampled page
-- the block is emitted for the page's own product and for nothing else, so
there is no carousel of substitutes to disambiguate against and no per-kilo
reference figure under the same attribute. That uniqueness is the safety
property this extractor leans on, so more than one occurrence abstains rather
than picking the first: a listing page that ever emitted one block per tile
would otherwise bank an arbitrary tile's price against the page's URL.

The attribute is present in the 2017, 2018, 2019 and 2022 captures and absent
from 2023 onward, when the site moved to a client-rendered shell. Captures from
2020 and 2021 are 752-830 byte interstitials carrying no product content at
all. Nothing here needs the capture date: a page without the attribute simply
abstains, so the era split costs no configuration.

The Netherlands has used the euro throughout the period this corpus covers, and
the attribute is a bare decimal with no symbol, so EUR is recorded directly.
"""

from __future__ import annotations

from typing import Any

from archived import normalize_price, price_row

_CURRENCY = "EUR"


def extract(doc: Any, url: str) -> dict | None:
    """The price this page's own GTM product block carries, or nothing."""
    blocks = [el for el in doc.iter() if el.get("data-price")]
    if len(blocks) != 1:
        return None
    el = blocks[0]
    name = (el.get("data-name") or "").strip()
    if not name:
        return None
    return price_row(name, normalize_price(el.get("data-price"), _CURRENCY),
                     url, _CURRENCY)
