"""Per-source extractor for archived sklavenitis_gr captures.

sklavenitis_gr is Greece's largest supermarket chain and the single biggest
zero-yield source in the second archive pass: 58,032 captures resolved and not
one row parsed. Reading the captures explains both halves of that.

Of the 58,032, 45,485 (78.4%) are four-segment product detail pages and they
are **not recoverable at any tier**. The one sampled in full
(nikas-loukanika-mpoukies-party-230gr-244107, 2024-02-23, HTTP 200, 94,687
bytes) contains no euro sign anywhere in the payload, no JSON-LD, no microdata
``itemprop="price"`` and no price class -- this storefront renders the product
price client-side. Every generic tier had already tried and correctly found
nothing; that is not a gap to close.

The 8,547 three-segment leaf-category captures are the recoverable half, and
they carry more per capture than a product page would: each product card on a
listing page holds its own ``data-plugin-analyticsimpressions`` attribute with
a pre-parsed name and price, so one capture yields a whole shelf. A 2024-08-04
capture carried 24 priced items spanning EUR 1.07-59.00.

The trap is that the attribute's payload has two shapes, and a reader built on
the modern one alone finds prices on 2 of 15 sampled captures rather than on
most of them -- the same era mismatch that costs this project depth elsewhere,
here inside the JSON rather than in a URL:

* Newer captures (seen 2024-2025) nest a GA4 payload: ``Call`` is an object
  with ``ecommerce.items[]``, each item carrying ``item_name`` and ``price``.
* Older captures (seen 2022-2023) put a Universal Analytics payload in a
  *string*: ``Call`` is the literal JS source
  ``window.tagManagerPush({"id": ..., "name": ..., "price": 3.20, ...});``
  with ``name`` and ``price`` at the top level and no ``item_`` prefix.

Both are read. Prices are already floats in EUR on both shapes -- no
minor-unit and no regex-on-markup risk -- and no per-kg reference figure
appears in either payload, so the shelf-price-versus-unit-price trap that
frisco_pl and edeka24_de have to navigate does not arise here.

Some category captures legitimately carry no blob at all (a 2021-07-28 capture
had none, and no price markup of any kind); those yield nothing rather than
being forced.
"""
from __future__ import annotations

import json
import re
from typing import Any

from .archived import price_row as _row

_ATTR = "data-plugin-analyticsimpressions"
# The older payload is JS, not JSON: pull the single object literal out of the
# tagManagerPush call and parse that. Non-greedy up to the last brace before
# the closing paren, because the object itself contains no nested braces.
_PUSH = re.compile(r"tagManagerPush\(\s*(\{.*\})\s*\)", re.S)
_CURRENCY = "EUR"


def _items(payload: Any) -> list[dict]:
    """Every product record inside one blob, whichever shape it uses."""
    call = payload.get("Call") if isinstance(payload, dict) else None
    if isinstance(call, str):
        m = _PUSH.search(call)
        if not m:
            return []
        try:
            obj = json.loads(m.group(1))
        except ValueError:
            return []
        return [obj] if isinstance(obj, dict) else []
    if isinstance(call, dict):
        items = call.get("ecommerce", {}).get("items")
        return [i for i in items if isinstance(i, dict)] if isinstance(items, list) else []
    return []


def _name_price(item: dict) -> tuple[str | None, str | None]:
    name = item.get("item_name") or item.get("name")
    price = item.get("price")
    if price is None or not name:
        return None, None
    return str(name).strip(), str(price)


def extract(doc: Any, url: str) -> list[dict]:
    """Every priced product card on an archived sklavenitis category page.

    Returns a list because a listing capture holds a whole shelf; the caller
    passes a list straight through rather than collapsing it to the page's own
    product, which is what a detail-page extractor would want.
    """
    rows: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for el in doc.xpath("//*[@%s]" % _ATTR):
        raw = el.get(_ATTR)
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except ValueError:
            continue
        for item in _items(payload):
            name, price = _name_price(item)
            if not name or price is None:
                continue
            key = (name, price)
            if key in seen:
                continue
            seen.add(key)
            row = _row(name, price, url, _CURRENCY)
            if row:
                rows.append(row)
    return rows
