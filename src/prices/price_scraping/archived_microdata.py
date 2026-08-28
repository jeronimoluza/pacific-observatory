"""Price rows from inline schema.org microdata.

The shipped generic tiers read JSON-LD and ``<meta>`` tags. Neither sees
microdata written onto ordinary elements -- ``<span itemprop="price">`` inside
an ``itemscope`` -- which is how storefronts marked up products before JSON-LD
became the norm. A miss autopsy over 12,603 unreadable archived pages found
1,884 (15.0%) recoverable and **96.7% of those recover through microdata**,
lifting the volume-weighted readable rate from 55.7% to 63.4%.

It is the era-appropriate tier in the literal sense: its uplift is **1.71x on
pre-2020 captures against 1.04x on 2023+**, exactly inverse to JSON-LD's
availability curve. Common Crawl's dense-revisit years are 2016-2018, so this
is the tier that reads the years worth fetching.

Two decisions worth keeping:

**Ownership is resolved by the microdata spec, not by proximity.** An
``itemprop`` belongs to its nearest ancestor ``itemscope``. Taking the first
``itemprop="name"`` found anywhere under the Product element instead -- what a
naive reading does -- names 86% of otto_de's rows ``variationId`` (the *name*
of a nested ``PropertyValue``) and gives ebay_uk a breadcrumb category 59% of
the time. Scoping the name strictly to the Product removes both entirely.

**lxml, not BeautifulSoup.** Measured on the miss corpus, tree construction is
0.8 ms/page against 7.7 ms, and the substring gate skips the 64% of pages
carrying no ``itemprop`` at all. Across a full-archive sweep that difference is
days of CPU.
"""

from __future__ import annotations

import html as _html
from typing import Any
from urllib.parse import urljoin

import lxml.etree
import lxml.html

from .archived import _dedupe_product_rows, _valid_currency, normalize_price

_PRICE_PROPS = frozenset({"price", "lowprice", "highprice"})
# schema.org puts the price on an Offer nested inside the Product, so a price
# owned by a nested *offer* scope still belongs to this product. Any other
# nested scope (Brand, Review, BreadcrumbList, PropertyValue) does not.
_OFFER_TYPES = frozenset({"offer", "aggregateoffer"})


def _attr(el: Any, name: str) -> str:
    v = el.get(name)
    return (v or "").strip().lower()


def _type_of(el: Any) -> str:
    """Bare schema.org type token, e.g. ``product`` for ``.../Product``."""
    return _attr(el, "itemtype").rsplit("/", 1)[-1]


def _is_scope(el: Any) -> bool:
    return "itemscope" in el.attrib or "itemtype" in el.attrib


def _owner(el: Any, root: Any) -> Any:
    """The item this property belongs to: nearest ancestor with an itemscope."""
    cur = el.getparent()
    while cur is not None:
        if _is_scope(cur):
            return cur
        if cur is root:
            return root
        cur = cur.getparent()
    return None


def _value(el: Any) -> str | None:
    """``content`` wins, then ``href`` on a link, then the element's text."""
    v = el.get("content")
    if v and v.strip():
        return v.strip()
    if el.tag == "link":
        href = el.get("href")
        return href.strip() if href else None
    text = el.text_content()
    return " ".join(text.split()) or None


def _positive(price: str | None) -> bool:
    if not price:
        return False
    try:
        return float(price) > 0
    except (TypeError, ValueError):
        return False


def _row_for_scope(scope: Any, url: str) -> dict | None:
    price_raw = currency = name = sku = category = availability = None
    own_url = None

    for el in scope.iter():
        if el is scope or "itemprop" not in el.attrib:
            continue
        owner = _owner(el, scope)
        if owner is None:
            continue
        direct = owner is scope
        # A price may sit on the Product or on an Offer nested inside it.
        priced_scope = direct or _type_of(owner) in _OFFER_TYPES
        for prop in _attr(el, "itemprop").split():
            if prop in _PRICE_PROPS and price_raw is None and priced_scope:
                price_raw = _value(el)
            elif prop == "pricecurrency" and currency is None and priced_scope:
                currency = _value(el)
            elif prop == "availability" and availability is None and priced_scope:
                availability = _value(el)
            elif prop == "name" and name is None and direct:
                name = _value(el)
            elif prop == "sku" and sku is None and direct:
                sku = _value(el)
            elif prop == "category" and category is None and direct:
                category = _value(el)
            elif prop == "url" and own_url is None and direct:
                own_url = _value(el)

    currency = _valid_currency(currency)
    price = normalize_price(price_raw, currency)
    if not _positive(price) or not name:
        return None

    row: dict[str, Any] = {
        "product_name": _html.unescape(str(name)).strip()[:500],
        "price": price,
        "url": urljoin(url, own_url or url),
    }
    if sku:
        row["product_id"] = str(sku)
    if currency:
        row["currency"] = currency
    if category:
        row["category"] = str(category)
    if availability:
        low = str(availability).lower()
        if "outofstock" in low or "soldout" in low or "discontinued" in low:
            row["available"] = False
        elif "instock" in low or "limitedavailability" in low:
            row["available"] = True
    return row


def rows_from_microdata(html_text: str, url: str) -> list[dict]:
    """Price rows from every schema.org Product itemscope in the page."""
    if not html_text or "itemprop" not in html_text:
        return []
    try:
        tree = lxml.html.fromstring(html_text)
    except (ValueError, SyntaxError, lxml.etree.ParserError):
        return []

    rows: list[dict] = []
    for scope in tree.iter():
        if "itemtype" not in scope.attrib:
            continue
        if _type_of(scope) != "product":
            continue
        row = _row_for_scope(scope, url)
        if row:
            rows.append(row)
    return _dedupe_product_rows(rows, url)
