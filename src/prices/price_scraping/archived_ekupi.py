"""Per-source extractor for ekupi_hr archived pages.

ekupi.hr never carries any of the three portable surfaces on its product
pages in the era this corpus spans, so every capture banks as a miss. The
markup does carry a single, unmoving price class across a decade of
captures -- but Croatia switched its currency from the kuna to the euro on
2023-01-01, and this corpus straddles that changeover (measured: 36,724 of
110,854 misses, 33%, predate it). Reading the currency from the page's own
text rather than assuming one avoids understating every pre-2023 price by
roughly 7.5x.
"""

from __future__ import annotations

from typing import Any

from .archived import normalize_price, price_row


def _classes(el: Any) -> list[str]:
    return (el.get("class") or "").split()


def _text(el: Any) -> str:
    return " ".join((el.text_content() or "").split())


def extract(doc: Any, url: str) -> dict | None:
    """The price this page's own product carries, in whichever currency it is printed in.

    ``dd.final-price`` holds the charged figure on every one of 50 design
    captures spanning 2020 through 2025, one page each. Its *own* text (not
    the full subtree) is read deliberately: from September 2022, Croatia's
    mandated dual-pricing rollout added a sibling ``p.altPrice`` inside the
    same ``dd`` carrying the other currency's converted preview figure (e.g.
    "125,00 kn" beside a converted "16,59 &euro;") -- reading the whole
    subtree's text would concatenate both figures, or silently prefer
    whichever currency's regex matched first. ``el.text`` stops at that
    child and returns only the figure this page is actually priced in.

    That text also names the currency: a kuna-era capture prints "219,90 kn"
    with no euro sign anywhere in the price cell, a euro-era one prints
    "3,09 &euro;", and the dual-pricing window still leads with the kuna
    figure -- confirming the kuna price, not the preview conversion, is what a
    buyer paid until the changeover. Reading the page's own text this way
    means the capture timestamp is never needed to pick a currency; a capture
    whose price cell holds neither symbol abstains rather than guess.

    The product name comes from ``<title>``, always "<name> | <breadcrumb...>
    | eKupi.hr - ...": confirmed identical (once HTML-unescaped) to
    ``h1.name``'s own text on every capture that carries an ``h1`` at all, and
    a third of the design sample's older captures carry no ``h1`` whatsoever,
    making the title the only name source that works across every era. ``h1``
    also nests the item's SKU code directly against the name with no
    separating whitespace (``...2-11-718<span class="sku">ID EK000548872``),
    which the title never repeats, so preferring the title sidesteps that
    concatenation rather than having to strip it.
    """
    dd = None
    for el in doc.iter():
        if isinstance(el.tag, str) and el.tag == "dd" and "final-price" in _classes(el):
            dd = el
            break
    if dd is None:
        return None

    text = " ".join((dd.text or "").split())
    if "\u20ac" in text:
        currency = "EUR"
    elif "kn" in text.lower():
        currency = "HRK"
    else:
        return None
    price = normalize_price(text, currency)

    title_el = doc.find(".//title")
    title = _text(title_el) if title_el is not None else ""
    name = title.split("|", 1)[0].strip()
    return price_row(name or None, price, url, currency)
