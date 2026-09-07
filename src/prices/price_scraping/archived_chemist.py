"""Per-source extractor for chemist_warehouse archived pages.

chemist_warehouse.com.au tags its product detail page with the old
``data-vocabulary.org/Offer`` microdata scheme instead of schema.org, so the
JSON-LD/microdata tiers in ``archived.py`` never see it and every capture
banks as a miss. The page still carries the price in a single, consistently
named class -- but a 2019 sale-era template nests three dollar figures inside
it, and reading the whole class as one blob of text silently corrupts the
price on every capture from that era.
"""

from __future__ import annotations

import re
from typing import Any

from .archived import normalize_price, price_row

_CURRENCY = "AUD"
_DOLLAR = re.compile(r"\$[\d,]+(?:\.\d+)?")


def _classes(el: Any) -> list[str]:
    return (el.get("class") or "").split()


def _text(el: Any) -> str:
    return " ".join((el.text_content() or "").split())


def extract(doc: Any, url: str) -> dict | None:
    """The price a buyer is charged today, never the RRP, the SAVE amount, or a struck original.

    Measured over 30 design captures plus 80 held out, the page prints three
    dollar figures in three distinct classes: ``div.Price`` is what the shop
    actually charges (verified against every observed pair, e.g. "Seven
    Wonders Coconut Oil Conditioner 250ml" -> $14.49), ``div.retailPrice`` is
    the manufacturer's list price rendered as "Don't Pay RRP: $15.95", and
    ``div.Savings`` is the discount amount rendered as "SAVE $1.46". All three
    appear together on every capture that prices anything, so reading
    anything but the exact ``Price`` class token would silently bank the
    wrong number on nearly every row -- ``retailPrice`` and ``Savings`` each
    contain the substring "price" but are distinct class tokens, never
    confused with ``Price`` by exact-token matching.

    A 2019 sale-era template complicates ``div.Price`` itself: 32 of 68
    held-out captures with a price nest a hidden "BLACK FRIDAY"/"FRENZY SALE"
    banner repeating the sale price, a struck-through original price (an
    ``on-sale-before`` figure this tier must never bank), and a third copy of
    the sale price, all inside the one ``Price`` div with no whitespace
    between some of them -- reading the div's full text concatenates two or
    three figures into one nonsense number (observed: "$4.99$4.99$4.99"
    parsed as 499949994999.0). A ``product__price``-classed element is always
    present exactly once among these and always holds the sale price, on
    whichever of the three copies happens to carry the class in a given
    capture (measured: it moves between the banner span and the bottom node
    across captures, but the value under it never does) -- so that element,
    read on its own rather than the whole div, is what this reads first. Pages
    with no sale running carry none of that nesting, just one bare figure
    directly in ``div.Price`` with no ``product__price`` node at all, and
    that single figure is read as a fallback -- but only when it is the one
    distinct figure present in the div, so a future template variant that
    packs several disagreeing figures with no ``product__price`` marker
    abstains instead of guessing which one is real.

    The other 6 of 30 design captures carry none of the three classes at
    all -- the only dollar figures on those pages are the empty shopping-cart
    total (``$0.00``) and the "FREE SHIPPING OVER $50" banner, neither of
    which is a product price, and the page has no ``Price`` div to read, so
    this abstains rather than reach for either one. The shared ``price_row``
    helper's non-zero guard also protects against a stray zero-valued
    ``Price`` div, though none was observed in the design sample.

    The name is the ``itemprop="name"`` node, present and clean on every
    capture that also carries a price.
    """
    price_div = None
    for el in doc.iter("div"):
        if "Price" in _classes(el):
            price_div = el
            break
    if price_div is None:
        return None

    sale_node = None
    for el in price_div.iter():
        if el is not price_div and "product__price" in _classes(el):
            sale_node = el
            break

    if sale_node is not None:
        figures = _DOLLAR.findall(_text(sale_node))
        raw = figures[0] if figures else None
    else:
        figures = set(_DOLLAR.findall(_text(price_div)))
        raw = figures.pop() if len(figures) == 1 else None
    if raw is None:
        return None
    price = normalize_price(raw, _CURRENCY)
    if price is None:
        return None

    name = None
    for el in doc.iter():
        if isinstance(el.tag, str) and el.get("itemprop") == "name":
            name = _text(el)
            break

    return price_row((name or "").strip() or None, price, url, _CURRENCY)
