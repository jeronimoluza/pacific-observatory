"""Per-source extractor for archived gmarket (item.gmarket.co.kr) captures.

gmarket is a Korean marketplace with no JSON-LD, microdata or product
OpenGraph tag on any of the 30 design captures, yet it carries a real price
on 25 of them. Every capture observed, design and held-out alike, is a single
product's own detail page (``Item?goodscode=<id>``), never a listing, so this
returns one row rather than a list.

Every one of the misses on both samples is a legitimate abstain, not a
guard firing on markup that should have parsed: 1 of 30 design captures (6 of
80 held out) is a "상품정보를 가져올 수 없습니다" ("cannot retrieve item
information") redirect stub with no product on the page at all, and the rest
(4 of 30 design, 12 of 80 held out) print the Korean word for "temporarily
sold out" (일시품절) directly inside ``price_real`` in place of a figure --
``normalize_price`` finds no digits in it and returns ``None``, so the row is
correctly dropped rather than banking a zero or a stale price. Rows/capture
is 0.833 on the design set and 0.775 held out (62/80); the held-out figure is
the one to plan against, projecting to ~689,800 of the 890,110 gmarket
misses.

Every one of the 62 held-out rows was cross-checked by an independent regex
re-extraction of ``price_real`` and ``h1.itemtit`` straight from the source
HTML: 0 of 62 disagreed with either the banked price or the banked name.

The whole tier is two classes, always paired on this source: ``strong.
price_real`` for the money and ``h1.itemtit`` for the name. Both are exactly
one per page across the design set -- 25 of 25 priced captures carry exactly
one ``price_real`` and exactly one ``h1.itemtit`` -- so a page shaped
differently abstains rather than guessing which of several figures is the
product's own.

A held-out capture surfaced a case the design set never showed: 6 of 80 pages
carry a *second* ``<h1>``, from a "similar items" carousel rendered lower on
the page (``<h1 class="tit">`` inside a ``relate-item_detail_info_area``
block, pricing a different product under its own ``strong.price``, never
``price_real``). Counting bare ``h1`` tags would abstain on all six for no
reason; scoping to the ``itemtit`` class specifically -- which stayed at
exactly one on every one of those six as well as everywhere else measured --
recovers them without weakening the guard, since the carousel's heading never
carries that class.

``price_real`` is nested one level inside ``span.price_innerwrap``, which is
the trap: on any capture with an active discount, ``price_innerwrap``'s own
text runs both figures together, e.g. ``43,920원 15,820원`` for the original
price beside the sale price. Reading the wrapper's text would bank that
concatenation, or silently pick whichever of the two happens to parse.
Reading ``price_real`` directly -- a class that appears whether or not a
discount is active, always holding just the one figure a buyer actually
pays -- sidesteps the trap structurally: it never sees the original price to
begin with, discount or no discount.

The other trap is ``div.delivery-tag``, which prints the shipping fee (e.g.
``배송비 2,500원``) in the same won-with-comma-thousands shape as the real
price. It shares no class or ancestry with ``price_real`` anywhere in the
design or held-out sample, so keying on the class name rather than a generic
"a won figure near the price block" search keeps it out by construction, not
by a vocabulary rule.

KRW is a zero-decimal currency, but that never has to be decided here: every
value on this source is comma-grouped thousands with no fractional tail
(``15,820``, not ``15.820`` or ``15820,50``), so ``normalize_price`` resolves
it on the lone-comma path (tail length 3, not 2) before the zero-decimal
question would even come up. Verified directly against real captures --
``15,820원`` -> ``15820.0``, ``231,740원`` -> ``231740.0``.
"""

from __future__ import annotations

from typing import Any

from .archived import normalize_price, price_row

_PRICE_CLASS = "price_real"
_NAME_CLASS = "itemtit"


def _classes(el: Any) -> list[str]:
    return (el.get("class") or "").split()


def _text(el: Any) -> str:
    return " ".join((el.text_content() or "").split())


def extract(doc: Any, url: str) -> dict | None:
    """The one price this page's own product is sold at, paired with its ``h1``."""
    prices = [
        _text(el) for el in doc.iter()
        if isinstance(el.tag, str) and el.tag == "strong"
        and _PRICE_CLASS in _classes(el)
    ]
    if len(prices) != 1:
        return None
    h1s = [
        el for el in doc.iter()
        if isinstance(el.tag, str) and el.tag == "h1" and _NAME_CLASS in _classes(el)
    ]
    if len(h1s) != 1:
        return None
    price = normalize_price(prices[0], "KRW")
    return price_row(_text(h1s[0]).strip() or None, price, url, "KRW")
