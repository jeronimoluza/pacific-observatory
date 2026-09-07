"""Per-source extractors for edeka24_de and elvi_lv archived pages.

Both are single-product detail pages -- verified against every miss the design
cache holds -- where a shared price-shaped class is reused elsewhere on the
same page for unrelated recommendation or related-product tiles. Each
extractor scopes to the container that is structurally tied to the page's own
product before reading a price out of it, so a class name alone is never
trusted to mean "this page's price".
"""

from __future__ import annotations

from typing import Any

from .archived import normalize_price, price_row

_EDEKA24_WIDGET_ID = "jq_widgetContainer_articleDetailsPrice"


def _classes(el: Any) -> list[str]:
    return (el.get("class") or "").split()


def _text(el: Any) -> str:
    return " ".join((el.text_content() or "").split())


def extract_edeka24(doc: Any, url: str) -> dict | None:
    """The price this page's own product is sold at, read from its own widget.

    A capture routinely repeats ``price``/``price-note`` several times over --
    one design page carried eight pairs -- because a "customers also bought"
    rail below the fold prices several other items with the exact same
    classes. Scoping to ``#jq_widgetContainer_articleDetailsPrice``, the one
    container tied to the page's own article, is what keeps those out; the
    rail's tiles sit outside it in every capture checked. The one design
    capture missing this widget entirely is a responsible-drinking
    interstitial with no product on it, and is correctly read as nothing.

    ``price-note`` looks like a price and sits right next to the real one, but
    every value it held across the design sample carried a unit suffix
    (``/1 ltr``, ``/kg``, ``/100 g`` ...) -- it is the Grundpreis, the
    per-kilogram-or-litre reference price German retailers are legally
    required to print, not what the shop charges for the item as packaged.
    Banking it would silently divide every edeka24_de price by the pack size.
    The actual charged figure is the sibling ``div.price``, which carries a
    ``priceReduced`` modifier when a markdown is active; a struck original
    price lives in a separate ``p.oldPrice``, never inside ``div.price``, so
    it is never read even when present alongside a promo.

    The widget carries no product name of its own -- its only link is a
    "wishlist" control, not the item -- so the name always comes from
    ``h1``, which was present and clean on all thirty design captures across
    both the older ``EDEKA24 | X | kaufen``-titled era and the newer bare-title
    one.
    """
    widget = None
    for el in doc.iter():
        if isinstance(el.tag, str) and el.get("id") == _EDEKA24_WIDGET_ID:
            widget = el
            break
    if widget is None:
        return None
    price = None
    for el in widget.iter():
        if isinstance(el.tag, str) and el.tag == "div" and "price" in _classes(el):
            price = normalize_price(_text(el), "EUR")
            break
    h1 = doc.find(".//h1")
    name = _text(h1) if h1 is not None else ""
    return price_row(name.strip() or None, price, url, "EUR")


def extract_elvi(doc: Any, url: str) -> dict | None:
    """The price of this page's own product, only while a promotion is live.

    elvi.lv is a weekly promotions flyer, not a checkout store: a product's
    page prints a price only during the ``Akcijas periods`` (promotion period)
    it is on offer for. 25 of the 30 design captures show nothing but "the
    promotion has ended" in the product's own price slot, and that is read as
    no observation rather than guessed at -- there is no everyday price on the
    page to fall back to.

    The page's own slot is ``div.product-wrapper.single``. A "related
    products" rail immediately below reuses the identical ``price``/
    ``discount`` classes to price several unrelated items -- one design
    capture carried five such pairs, of which only the first belonged to the
    page's own product -- and those tiles are ``product-wrapper`` without the
    ``single`` token, so they are excluded by construction rather than by
    guessing which one is real.

    Inside that slot the price div carries a variant modifier. ``default`` is
    a plain single item: its ``col.discount`` holds a ``span`` (the
    pre-markdown list price, sometimes a size range) beside a ``p`` (what a
    buyer pays now). A second variant seen only on other items in this sample,
    ``two-plus``, prices a quantity-gated multi-buy deal under a *second*,
    separate ``col`` labelled "buying more!", set against a plain ``col.old``
    holding the regular one-unit price -- confirming ``discount`` consistently
    names the figure after a price cut, never before one, and this tier does
    not read a ``two-plus`` figure since it is conditional on quantity, not
    what one unit costs. ``percent`` prices a multi-size item with only a
    percentage-off badge and no absolute figure, because the cut is not the
    same across its sizes; that carries nothing this tier can bank either.

    The product name comes from ``h1``, present and clean on every one of the
    thirty design captures.
    """
    wrapper = None
    for el in doc.iter():
        if not isinstance(el.tag, str):
            continue
        cl = _classes(el)
        if "product-wrapper" in cl and "single" in cl:
            wrapper = el
            break
    if wrapper is None:
        return None
    price = None
    for el in wrapper.iter():
        if not isinstance(el.tag, str) or el.tag != "div":
            continue
        cl = _classes(el)
        if "price" in cl and "default" in cl:
            for col in el.iter("div"):
                if "discount" in _classes(col):
                    p_tag = col.find("p")
                    if p_tag is not None and _text(p_tag):
                        price = normalize_price(_text(p_tag), "EUR")
                    break
            break
    h1 = doc.find(".//h1")
    name = _text(h1) if h1 is not None else ""
    return price_row(name.strip() or None, price, url, "EUR")
