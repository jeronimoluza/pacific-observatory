"""Per-source extractors for archived classifieds pages.

These sites list one item per page at an asking price, which is a price
observation but not a retail one: the seller is usually a private individual,
the item is often second-hand, and nothing guarantees the asking price is what
was paid. Anything consuming these rows needs to know that.

Three of the ten classifieds sources in the miss corpus are read here. The
other seven were measured and refused, and the reasons are worth keeping
because each looks like a yield on any score that does not read its samples:

  hotpepper_jp  its figure is a per-person budget BAND ("予算 2001～3000円"),
                not a price, on 93% of captures.
  livingcost    every figure is a modelled cost-of-living estimate for a city
                ("Cost of Living in Blankenberge"), not an observed price.
                Banking those would feed a third party's index back into this
                corpus as though it were a measurement.
  tap_az        no `h1`, and its captures are category listings whose title is
                a breadcrumb, so there is no item name to pair a price with.
  reklama5_mk   money on 3 to 5 captures in 15, in every era sampled.
  olx_pl        price classes are per-build hashes (`css-okktvh-Text`), which
  olx_ro        is not a selector, and money reaches only 6 or 7 captures in 15
                on olx_ro.
  batdongsan_vn quotes in scaled Vietnamese units ("8.2 tỷ", "25 triệu/tháng")
                and mixes sale prices with monthly rents in the same class.

The house rule is the one the rest of this package follows: abstain rather
than guess.
"""

from __future__ import annotations

import re
from typing import Any

from .archived import normalize_price, price_row

# A figure spanning two values is a band, not a price. olx_pk carries job
# adverts alongside goods -- "Rs 12,000 - 15,000" against "Staff required as
# data entry operator" -- and a monthly salary band is neither this item's
# price nor a single number.
_RANGE = re.compile(r"\d[\d,. ]*\s*(?:-|–|—|to|do)\s*\d")

# pakwheels prints four to six other listings' asking prices in a rail on every
# capture, under the same class as its own. Matching the class alone attributes
# a different car's price to this URL.
_RAIL_CLASSES = re.compile(
    r"recent-vehicle|similar-|related|recommend", re.IGNORECASE)

_PKR = re.compile(r"(?:PKR|Rs\.?|₨)\s*([\d,]{3,})")
_SOMONI = re.compile(r"([\d   ,]{2,})\s*(?:c\.|с\.|сомони)")
_USD = re.compile(r"\$\s*([\d,]+(?:\.\d+)?)")


def _classes(el: Any) -> list[str]:
    return (el.get("class") or "").split()


def _text(el: Any) -> str:
    return " ".join((el.text_content() or "").split())


def _h1(doc: Any) -> str | None:
    el = doc.find(".//h1")
    if el is None:
        return None
    return _text(el) or None


def _in_rail(el: Any) -> bool:
    node = el
    while node is not None:
        if _RAIL_CLASSES.search(node.get("class") or ""):
            return True
        node = node.getparent()
    return False


def _first_with_class(doc: Any, name: str) -> Any:
    for el in doc.iter():
        if isinstance(el.tag, str) and name in _classes(el) and not _in_rail(el):
            return el
    return None


def extract_olx_pk(doc: Any, url: str) -> dict | None:
    """The asking price on an olx.com.pk advert.

    `div.pricelabel` occurs exactly once per capture and the `h1` names the
    item, which is as clean as this corpus gets. The range guard is what earns
    its keep: olx_pk's 2018 era carries job adverts whose `pricelabel` holds a
    monthly salary band, and they are indistinguishable from goods by markup.
    """
    el = _first_with_class(doc, "pricelabel")
    if el is None:
        return None
    body = _text(el)
    if _RANGE.search(body):
        return None
    found = _PKR.search(body)
    if not found:
        return None
    return price_row(_h1(doc), normalize_price(found.group(1), "PKR"),
                     url, "PKR")


def extract_somon_tj(doc: Any, url: str) -> dict | None:
    """The asking price on a somon.tj advert, in whichever currency it names.

    `.announcement-price` occurs once per capture and the `h1` names the item.
    The figure is often suffixed "торг" (negotiable), which is a note about the
    price rather than part of it. Somoni is written "c." -- a Latin c, not the
    Cyrillic с, on the captures inspected -- and some adverts quote dollars
    instead, so the symbol is read rather than assumed from the country.
    """
    el = _first_with_class(doc, "announcement-price")
    if el is None:
        return None
    body = _text(el)
    if _RANGE.search(body):
        return None
    found = _SOMONI.search(body)
    currency = "TJS"
    if not found:
        found = _USD.search(body)
        currency = "USD"
    if not found:
        return None
    digits = re.sub(r"[^\d.]", "", found.group(1))
    if not digits:
        return None
    return price_row(_h1(doc), normalize_price(digits, currency), url, currency)


def extract_pakwheels_pk(doc: Any, url: str) -> dict | None:
    """The asking price of the car this page is about, if the page states it.

    Only the 2018-and-later template does. On the 2017 template -- 39% of this
    source's misses -- every PKR figure in the markup belongs to the
    "recently viewed" rail, and the page's own price is not server-rendered at
    all, so those captures abstain. That is the finding rather than a gap: the
    class that scored 93% coverage there was scoring other people's cars.

    Where the page does state its price it does so twice, in a `strong` and an
    `h5`, agreeing; the first outside the rail is taken.
    """
    values = []
    for el in doc.iter():
        if not isinstance(el.tag, str) or _in_rail(el):
            continue
        body = _text(el)
        if len(body) > 24 or _RANGE.search(body):
            continue
        found = _PKR.fullmatch(body.strip())
        if found:
            values.append(found.group(1))
    if not values:
        return None
    # A single-vehicle page states its price twice, in a `strong` and an `h5`,
    # agreeing -- so one distinct value. Several distinct values outside the
    # rail means this is a search or category listing, whose `h1` is the query
    # ("Used Cars for Sale in Faisalabad") rather than any item's name; pairing
    # that heading with whichever price came first invents a product.
    if len(set(values)) > 1:
        return None
    return price_row(_h1(doc), normalize_price(values[0], "PKR"), url, "PKR")
