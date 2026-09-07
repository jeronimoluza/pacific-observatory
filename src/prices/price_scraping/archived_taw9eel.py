"""Per-source extractor for archived taw9eel_kw (taw9eel.com) captures.

taw9eel_kw is a Kuwaiti online supermarket and the largest single block of
misses in the second archive pass: 149,262 records, 24% of the whole set, on a
source that already banks 16,213 rows elsewhere. Its captures were falling
through every tier for a reason none of them reports.

The page *does* carry ``application/ld+json``, which is why it looks like the
JSON-LD tier should have read it, and why the malformed-JSON repair tier was
the first suspect. Neither applies. The block parses cleanly and is an
``@type: Organization`` -- the site's own name, url and social profiles, with
no offer and no price anywhere in it. That is a third failure mode beside the
malformed and the absent: **valid JSON-LD of the wrong type**. There is nothing
to repair and nothing to widen; the price simply is not in that block.

It is in Magento 1.x markup instead, and two decoys sit in the same class:

* The header mini-cart renders ``<span class="price">KD0.000</span>`` on every
  page including product pages. A first-match read of ``.price`` takes it, and
  a zero banked as a price is the failure that scores perfectly against any
  is-this-a-number check while being wrong on every row.
* A discounted product renders the pre-discount figure as
  ``<span class="price" id="old-price-44535">KD2.400</span>`` directly above
  the charged one. Reading it overstates the observation -- on the sampled
  capture by 14%.

Both decoys are excluded structurally rather than by ordering or by class name,
because Magento gives the charged figure an id the decoys never carry: the
``<span class="price">`` whose own id is ``product-price-<n>``. On a plain page
that is the regular price; on a discounted page it is the special price
(``id="product-price-44535"`` holds KD2.100 while ``old-price-44535`` holds
KD2.400), so one rule reads both shapes and neither decoy. Exactly one such id
appears per capture across the sample.

The name comes from ``h1``: ``og:title`` and ``<title>`` both prefix the
merchandising word "Buy" and ``<title>`` additionally appends the site name in
Arabic.

Prices are quoted ``KD2.100`` -- Kuwaiti dinar, three minor digits. The prefix
is stripped and the figure kept as written; KWD is not a zero-decimal currency
so no minor-unit rescaling applies.

The anchor is stock Magento 1.x rather than anything specific to this
storefront, so other Magento sources in the miss set are likely readable the
same way. None are claimed here -- this module is registered for the one source
whose captures were actually sampled.
"""
from __future__ import annotations

import re
from typing import Any

from .archived import price_row as _row

_CURRENCY = "KWD"
_PRICE_ID = re.compile(r"^product-price-\d+$")
_NUM = re.compile(r"[-+]?\d[\d,]*(?:\.\d+)?")


def _clean(text: str | None) -> str | None:
    """The bare figure out of a quoted price like ``KD2.100``."""
    if not text:
        return None
    m = _NUM.search(text.replace(",", ""))
    return m.group(0) if m else None


def _name(doc: Any) -> str | None:
    for el in doc.xpath("//h1"):
        txt = " ".join((el.text_content() or "").split())
        if txt:
            return txt
    return None


def extract(doc: Any, url: str) -> dict | None:
    """The charged price on an archived taw9eel product page, or nothing."""
    price = None
    for el in doc.xpath("//*[@id]"):
        if not _PRICE_ID.match(el.get("id") or ""):
            continue
        # Magento hangs that id on two different elements depending on whether
        # the item is discounted: on a plain page it is the outer
        # ``span.regular-price`` wrapping a ``span.price`` child, on a
        # discounted one it is the ``span.price`` itself. Reading the element's
        # own text_content covers both, where matching the inner span directly
        # would have banked discounted items only -- a price series biased
        # toward whatever happened to be on offer.
        price = _clean(el.text_content())
        if price:
            break
    if not price:
        return None
    return _row(_name(doc), price, url, _CURRENCY)
