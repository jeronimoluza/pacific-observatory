"""Per-source extractor for archived hausples_pg (hausples.com.pg) captures.

hausples_pg is Papua New Guinea's property portal and the only PNG price source
in this corpus with a usable history. It is a Next.js listing site whose
rendered price lives in the page cache rather than on a product node, which is
why the portable ``__NEXT_DATA__`` tier abstains::

    props.pageProps.cacheData.listing.data.header.rentPrice   = 'K1,500'
    props.pageProps.cacheData.listing.data.header.rentPeriod  = 'per week'
    props.pageProps.cacheData.listing.data.header.salePrice   = ''
    props.pageProps.cacheData.listing.data.header.rentPriceSqm = 'POA'

This is a rental listing, so the figure is a **flow, not a level**: it is a
price per week, per fortnight or per month depending on the listing, and the
period is carried in its own field. The period is appended to the name rather
than dropped, so a downstream stage comparing two listings can see that they
are not the same quantity. Banking "1500" with no period against a series that
also holds monthly rents would silently mix a weekly and a monthly figure.

Only one of ``rentPrice`` and ``salePrice`` is populated on a given listing;
whichever is present is read, with rent preferred when a listing somehow
carries both, because the rent figure is the one the page's own header
renders. ``rentPriceSqm``/``salePriceSqm`` are per-square-metre reference
figures and are never read, and the literal ``POA`` ("price on application")
that fills them on most listings is not a number and abstains on its own.

The kina prints as a ``K`` prefix with thousands commas. PNG prices in PGK.
"""

from __future__ import annotations

import json
import re
from typing import Any

from archived import normalize_price, price_row

_CURRENCY = "PGK"
_NUM = re.compile(r"\d[\d,. ]*")


def _next_data(doc: Any) -> dict | None:
    for el in doc.iter("script"):
        if el.get("id") != "__NEXT_DATA__":
            continue
        try:
            return json.loads(el.text_content() or "")
        except (ValueError, TypeError):
            return None
    return None


def _dig(node: Any, *path: str) -> Any:
    for key in path:
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    return node


def extract(doc: Any, url: str) -> dict | None:
    """The advertised rent or sale price on an archived hausples listing."""
    data = _next_data(doc)
    if not isinstance(data, dict):
        return None
    header = _dig(data, "props", "pageProps", "cacheData", "listing", "data", "header")
    if not isinstance(header, dict):
        return None
    aside = _dig(data, "props", "pageProps", "cacheData", "listing", "data", "aside", "listing")
    for field, period_field in (("rentPrice", "rentPeriod"), ("salePrice", None)):
        raw = header.get(field)
        if not isinstance(raw, str) or not raw.strip():
            continue
        m = _NUM.search(raw)
        if not m:
            continue
        price = normalize_price(m.group(0).strip(), _CURRENCY)
        name = ""
        if isinstance(aside, dict):
            for key in ("title", "name", "heading"):
                value = aside.get(key)
                if isinstance(value, str) and value.strip():
                    name = value.strip()
                    break
        if not name:
            for h1 in doc.iter("h1"):
                name = " ".join((h1.text_content() or "").split())
                if name:
                    break
        if not name:
            continue
        period = header.get(period_field) if period_field else "sale"
        if isinstance(period, str) and period.strip():
            name = "%s (%s)" % (name, period.strip())
        row = price_row(name, price, url, _CURRENCY)
        if row:
            return row
    return None
