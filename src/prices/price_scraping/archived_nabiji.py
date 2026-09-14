"""Per-source extractor for archived orinabiji_ge (2nabiji.ge) captures.

orinabiji_ge is a Next.js storefront whose product record sits under
``props.pageProps.product`` with the price held one level away from it, in the
stock record rather than on the product itself::

    props.pageProps.product.title          = 'ცხელი შოკოლადი "მაკ შოკოლადი" 20გრ'
    props.pageProps.product.discount.price = 0.55
    props.pageProps.stock.price            = 0.6

The portable ``__NEXT_DATA__`` tier abstains because the price is not on the
node carrying the name. Both figures here are real: ``stock.price`` is the
shelf price and ``discount.price`` the promoted one. The discounted figure is
banked when it is present and non-zero, because it is what a buyer pays and it
is the same quantity schema.org ``offers.price`` carries on every other source
in this corpus -- mixing shelf prices here with charged prices elsewhere would
put a step into cross-source comparisons that no downstream stage can see.

A ``discount`` node with a zero or missing price is a product with no promotion
running, not a free one, so it falls through to the shelf price.

Georgia prices in lari.
"""

from __future__ import annotations

import json
from typing import Any

from archived import price_row

_CURRENCY = "GEL"


def _next_data(doc: Any) -> dict | None:
    for el in doc.iter("script"):
        if el.get("id") != "__NEXT_DATA__":
            continue
        try:
            return json.loads(el.text_content() or "")
        except (ValueError, TypeError):
            return None
    return None


def _price(node: Any) -> float | None:
    if isinstance(node, dict):
        value = node.get("price")
        if isinstance(value, (int, float)) and value > 0:
            return float(value)
    return None


def extract(doc: Any, url: str) -> dict | None:
    """The charged price on an archived 2nabiji product page, or nothing."""
    data = _next_data(doc)
    if not isinstance(data, dict):
        return None
    page = (data.get("props") or {}).get("pageProps")
    if not isinstance(page, dict):
        return None
    product = page.get("product")
    if not isinstance(product, dict):
        return None
    name = product.get("title")
    if not isinstance(name, str) or not name.strip():
        return None
    price = _price(product.get("discount")) or _price(page.get("stock")) or _price(product)
    if price is None:
        return None
    return price_row(name.strip(), ("%.4f" % price).rstrip("0").rstrip("."),
                     url, _CURRENCY)
